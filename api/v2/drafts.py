"""P3 backend (B3.1-B3.3): drafts, edits, publication, history, compare and restore.

Publication (v2-schema-plan section 3.4) runs in one transaction: lock the schedule row, take advisory
locks on every rostered employee in stable order (so concurrent publications elsewhere cannot create
cross-outlet conflicts), check the base version and draft revision, re-run the independent validator
against the live organization-wide roster, then supersede, publish and move the pointer, writing audit
and outbox rows in the same transaction.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from api.v2.rosters import _summary, version_view
from api.v2.service import _audit, _outlet, idempotent, week_bounds
from core.auth import Caller, Role, assert_outlet
from db.models import Outlet
from db.models_v2 import LogicalShift, OutboxEvent, Schedule, ScheduleVersion, SchedulingPolicy, VersionShift
from db.models_v2 import ShiftTemplate as ShiftTemplateRow
from db.session import tenant_session
from scheduling import diff as sched_diff
from scheduling import edits as sched_edits
from scheduling import metrics, snapshot_db, validator
from scheduling.model import Policy, Shift, Template

DEFAULT_LOCK_REASON = "Locked by manager"


# ---------------------------------------------------------------- helpers


def _version(
    session: Session, caller: Caller, version_id: uuid.UUID, *, for_update: bool = False
) -> tuple[ScheduleVersion, Schedule]:
    query = select(ScheduleVersion).where(ScheduleVersion.id == version_id)
    version = session.scalars(query.with_for_update() if for_update else query).first()
    if version is None:
        raise not_found("Schedule version")
    schedule = session.get(Schedule, version.schedule_id)
    assert schedule is not None
    assert_outlet(caller, str(schedule.outlet_id))
    return version, schedule


def _rows(session: Session, version_id: uuid.UUID) -> list[VersionShift]:
    return list(
        session.scalars(
            select(VersionShift)
            .where(VersionShift.version_id == version_id)
            .order_by(VersionShift.start_at, VersionShift.logical_shift_id)
        )
    )


def _require_draft(version: ScheduleVersion) -> None:
    if version.status != "draft":
        raise ApiError(
            "conflict",
            "Published versions cannot be edited. Create a draft first."
            if version.status in ("published", "superseded")
            else "This draft was discarded.",
        )


def _check_base(schedule: Schedule, expected: uuid.UUID | None) -> None:
    if expected != schedule.current_version_id:
        raise ApiError(
            "stale_version",
            "Someone published a newer version. Review the changes and try again.",
            current_version_id=str(schedule.current_version_id) if schedule.current_version_id else None,
        )


def _get_or_create_schedule(
    session: Session, caller: Caller, outlet_id: uuid.UUID, week_start: date
) -> Schedule:
    session.execute(
        pg_insert(Schedule)
        .values(id=uuid.uuid7(), org_id=uuid.UUID(caller.org_id), outlet_id=outlet_id, week_start=week_start)
        .on_conflict_do_nothing(index_elements=["org_id", "outlet_id", "week_start"])
    )
    schedule = session.scalars(
        select(Schedule)
        .where(Schedule.outlet_id == outlet_id, Schedule.week_start == week_start)
        .with_for_update()
    ).first()
    assert schedule is not None
    return schedule


def _new_draft(
    session: Session,
    caller: Caller,
    schedule: Schedule,
    rows: list[VersionShift],
    *,
    source: str,
    reason: str,
) -> ScheduleVersion:
    """Insert a draft (next version number) whose shifts copy `rows`, keeping their logical identity."""
    number = (
        session.scalar(
            select(func.coalesce(func.max(ScheduleVersion.version_number), 0)).where(
                ScheduleVersion.schedule_id == schedule.id
            )
        )
        or 0
    )
    draft = ScheduleVersion(
        id=uuid.uuid7(),
        org_id=schedule.org_id,
        schedule_id=schedule.id,
        version_number=number + 1,
        status="draft",
        base_version_id=schedule.current_version_id,
        source=source,
        reason=reason,
        created_by_user_id=uuid.UUID(caller.user_id),
        input_hash="draft",
        revision=1,
    )
    session.add(draft)
    session.flush()
    session.add_all(
        [
            VersionShift(
                id=uuid.uuid7(),
                org_id=r.org_id,
                schedule_id=schedule.id,
                version_id=draft.id,
                logical_shift_id=r.logical_shift_id,
                outlet_id=r.outlet_id,
                employee_id=r.employee_id,
                skill_id=r.skill_id,
                start_at=r.start_at,
                end_at=r.end_at,
                break_start_at=r.break_start_at,
                break_minutes=r.break_minutes,
                locked=r.locked,
                lock_reason=r.lock_reason,
                template_id=r.template_id,
            )
            for r in rows
        ]
    )
    session.flush()
    return draft


def _grid(session: Session) -> int:
    row = session.scalars(
        select(SchedulingPolicy)
        .where(SchedulingPolicy.outlet_id.is_(None))
        .order_by(SchedulingPolicy.revision.desc())
    ).first()
    return row.grid_minutes if row else Policy().grid_minutes


def _resolve_templates(session: Session, schedule: Schedule, body: s.EditRequest) -> s.EditRequest:
    """Turn add_from_template edits into plain adds, placing the break exactly as the solver does."""
    if not any(isinstance(e, s.AddFromTemplate) for e in body.edits):
        return body
    tz = _tz(session, schedule)
    out: list[Any] = []
    for i, e in enumerate(body.edits):
        if not isinstance(e, s.AddFromTemplate):
            out.append(e)
            continue

        def bad(field: str, message: str, index: int = i) -> ApiError:
            return ApiError(
                "validation_failed",
                "Some edits could not be applied.",
                fields=[{"path": ["edits", index, field], "message": message}],
            )

        row = session.get(ShiftTemplateRow, e.template_id)
        if row is None or row.outlet_id != schedule.outlet_id or not row.active:
            raise bad("template_id", "Not an active shift template of this outlet.")
        if not 0 <= (e.day - schedule.week_start).days < 7:
            raise bad("day", "The date must be in this draft's week.")
        skill = e.skill_id or row.skill_id
        if skill is None:
            raise bad("skill_id", "This template allows any role; choose one.")
        if row.skill_id is not None and skill != row.skill_id:
            raise bad("skill_id", "This template is for another role.")
        shape = Template(
            row.id,
            row.start_minute,
            row.duration_minutes,
            row.break_minutes,
            row.break_offset_minutes,
            row.skill_id,
        )
        start = datetime(e.day.year, e.day.month, e.day.day, tzinfo=tz) + timedelta(minutes=row.start_minute)
        offset = shape.break_offset(_grid(session))
        out.append(
            s.AddShift(
                op="add",
                employee_id=e.employee_id,
                skill_id=skill,
                start_at=start,
                end_at=start + timedelta(minutes=row.duration_minutes),
                break_start_at=start + timedelta(minutes=offset) if offset is not None else None,
                break_minutes=row.break_minutes,
                locked=e.locked,
            )
        )
    return s.EditRequest(expected_revision=body.expected_revision, edits=out)


def template_view(row: ShiftTemplateRow, grid: int) -> s.ShiftTemplate:
    shape = Template(
        row.id,
        row.start_minute,
        row.duration_minutes,
        row.break_minutes,
        row.break_offset_minutes,
        row.skill_id,
    )
    return s.ShiftTemplate(
        id=row.id,
        name=row.name,
        skill_id=row.skill_id,
        start_minute=row.start_minute,
        duration_minutes=row.duration_minutes,
        break_minutes=row.break_minutes,
        break_start_minute=shape.break_offset(grid),
    )


def list_shift_templates(caller: Caller, outlet_id: uuid.UUID) -> s.ShiftTemplateList:
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "You do not have permission to do this.")
    with tenant_session(caller) as session:
        _outlet(session, caller, outlet_id)
        grid = _grid(session)
        rows = session.scalars(
            select(ShiftTemplateRow)
            .where(ShiftTemplateRow.outlet_id == outlet_id, ShiftTemplateRow.active)
            .order_by(ShiftTemplateRow.start_minute, ShiftTemplateRow.duration_minutes, ShiftTemplateRow.name)
        )
        return s.ShiftTemplateList(outlet_id=outlet_id, items=[template_view(r, grid) for r in rows])


class _Keyed(BaseModel):
    """What an Idempotency-Key is bound to for applyEdits/discardDraft: the version and the body."""

    version_id: uuid.UUID
    body: dict[str, Any] | None = None


def _to_edits(body: s.EditRequest) -> list[sched_edits.Edit]:
    out = []
    for e in body.edits:
        if isinstance(e, s.AddShift):
            out.append(sched_edits.Edit("add", None, e.model_dump(exclude={"op"})))
        elif isinstance(e, s.UpdateShift):
            # null keeps a value, except employee_id where it unassigns: an edit echoed back with every
            # field present (e.g. a recommendation's) must not erase times. Remove a break with
            # break_minutes 0.
            fields = {
                k: getattr(e, k)
                for k in e.model_fields_set - {"op", "logical_shift_id"}
                if getattr(e, k) is not None or k == "employee_id"
            }
            out.append(sched_edits.Edit("update", e.logical_shift_id, fields))
        elif isinstance(e, s.RemoveShift):
            out.append(sched_edits.Edit("remove", e.logical_shift_id))
        elif isinstance(e, s.SetLock):
            out.append(sched_edits.Edit(e.op, e.logical_shift_id))
        else:  # add_from_template is resolved to a plain add first (_resolve_templates)
            raise AssertionError(f"unresolved edit {e.op}")
    return out


def _edited(roster: list[Shift], body: s.EditRequest, outlet_id: uuid.UUID) -> list[Shift]:
    try:
        return sched_edits.apply(roster, _to_edits(body), outlet_id)
    except sched_edits.EditError as exc:
        raise ApiError(
            "validation_failed",
            "Some edits could not be applied.",
            fields=[{"path": ["edits", exc.index], "message": exc.message}],
        ) from exc


def _changes(
    before: list[Shift], after: list[Shift], tz: ZoneInfo, ids: dict[uuid.UUID, uuid.UUID] | None = None
) -> list[s.ShiftChange]:
    def view(sh: Shift | None) -> s.Shift | None:
        return None if sh is None else _contract_shift(sh, tz, (ids or {}).get(sh.logical_id))

    return [
        s.ShiftChange.model_validate(
            {
                "logical_shift_id": c.logical_id,
                "kinds": list(c.kinds),
                "before": view(c.before),
                "after": view(c.after),
            }
        )
        for c in sched_diff.diff(before, after)
    ]


def _contract_shift(
    sh: Shift, tz: ZoneInfo, row_id: uuid.UUID | None = None, reason: str | None = None
) -> s.Shift:
    return s.Shift(
        id=row_id or uuid.uuid5(sh.logical_id, "preview"),
        logical_shift_id=sh.logical_id,
        outlet_id=sh.outlet_id,
        employee_id=sh.employee_id,
        skill_id=sh.skill_id,
        start_at=sh.start_at.astimezone(tz),
        end_at=sh.end_at.astimezone(tz),
        break_start_at=sh.break_start_at.astimezone(tz) if sh.break_start_at else None,
        break_minutes=sh.break_minutes,
        locked=sh.locked,
        lock_reason=(reason or DEFAULT_LOCK_REASON) if sh.locked else None,
    )


def _tz(session: Session, schedule: Schedule) -> ZoneInfo:
    outlet = session.get(Outlet, schedule.outlet_id)
    return ZoneInfo(outlet.timezone if outlet else "UTC")


def _outbox(
    session: Session,
    org_id: uuid.UUID,
    topic: str,
    aggregate: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    session.add(
        OutboxEvent(
            id=uuid.uuid7(),
            org_id=org_id,
            topic=topic,
            aggregate_type=aggregate,
            aggregate_id=aggregate_id,
            payload=json.loads(json.dumps(payload, default=str)),
        )
    )


# ---------------------------------------------------------------- B3.1 drafts and edits


def create_draft(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, key: str, body: s.CreateDraftRequest
) -> s.ScheduleVersion:
    require(caller, "publish")
    with tenant_session(caller) as session:

        def produce() -> s.ScheduleVersion:
            outlet = _outlet(session, caller, outlet_id)
            week_bounds(outlet, week_start)
            schedule = _get_or_create_schedule(session, caller, outlet_id, week_start)
            _check_base(schedule, body.base_version_id)
            source_id = body.copy_from_version_id or body.base_version_id
            rows: list[VersionShift] = []
            if source_id is not None:
                source = session.get(ScheduleVersion, source_id)
                if source is None or source.schedule_id != schedule.id:
                    raise ApiError(
                        "validation_failed",
                        "Some fields need attention.",
                        fields=[
                            {"path": ["copy_from_version_id"], "message": "Must be a version of this week."}
                        ],
                    )
                rows = _rows(session, source_id)
            draft = _new_draft(session, caller, schedule, rows, source="manual", reason="Manager edit")
            _audit(session, caller, "DRAFT_CREATED", "schedule_version", draft.id, None, None)
            return version_view(session, draft, record=True)

        return s.ScheduleVersion.model_validate(
            idempotent(session, caller, key, "createDraft", body, produce)
        )


def preview_edits(caller: Caller, version_id: uuid.UUID, body: s.EditRequest) -> s.EditPreview:
    require(caller, "publish")
    with tenant_session(caller) as session:
        version, schedule = _version(session, caller, version_id)
        _require_draft(version)
        if body.expected_revision != version.revision:
            raise ApiError(
                "stale_version",
                "This draft was changed by someone else. Reload and try again.",
                current_revision=version.revision,
            )
        body = _resolve_templates(session, schedule, body)
        rows = _rows(session, version.id)
        before = [snapshot_db.to_shift(r) for r in rows]
        after = _edited(before, body, schedule.outlet_id)
        tz = _tz(session, schedule)
        ids = {r.logical_shift_id: r.id for r in rows}
        reasons = {r.logical_shift_id: r.lock_reason for r in rows}
        snap = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, after, schedule.id)
        m = metrics.compute(snap, after)
        return s.EditPreview(
            version_id=version.id,
            expected_revision=version.revision,
            shifts=[
                _contract_shift(sh, tz, ids.get(sh.logical_id), reasons.get(sh.logical_id)) for sh in after
            ],
            changes=_changes(before, after, tz, ids),
            metrics=s.Metrics.model_validate(metrics.as_contract(m)),
            validation=s.ValidationResult.model_validate(
                validator.as_contract(validator.validate(snap, after))
            ),
        )


def apply_edits(
    caller: Caller, version_id: uuid.UUID, body: s.EditRequest, key: str | None = None
) -> s.ScheduleVersion:
    """With an Idempotency-Key, a repeat returns the stored result (after authorization, before the
    revision check), so a save whose response was lost can be retried safely."""
    require(caller, "publish")
    with tenant_session(caller) as session:
        if key is None:
            return _apply_edits(session, caller, version_id, body)
        keyed = _Keyed(version_id=version_id, body=body.model_dump(mode="json"))
        return s.ScheduleVersion.model_validate(
            idempotent(
                session,
                caller,
                key,
                "applyEdits",
                keyed,
                lambda: _apply_edits(session, caller, version_id, body),
            )
        )


def _apply_edits(
    session: Session, caller: Caller, version_id: uuid.UUID, body: s.EditRequest
) -> s.ScheduleVersion:
    version, schedule = _version(session, caller, version_id, for_update=True)
    _require_draft(version)
    if body.expected_revision != version.revision:
        raise ApiError(
            "stale_version",
            "This draft was changed by someone else. Reload and try again.",
            current_revision=version.revision,
        )
    body = _resolve_templates(session, schedule, body)
    rows = _rows(session, version.id)
    before = [snapshot_db.to_shift(r) for r in rows]
    after = _edited(before, body, schedule.outlet_id)
    reasons = {r.logical_shift_id: r.lock_reason for r in rows}
    templates = {r.logical_shift_id: r.template_id for r in rows}
    for e in body.edits:
        if isinstance(e, s.SetLock):
            reasons[e.logical_shift_id] = e.reason if e.op == "lock" else None
    existing = set(session.scalars(select(LogicalShift.id).where(LogicalShift.schedule_id == schedule.id)))
    session.execute(delete(VersionShift).where(VersionShift.version_id == version.id))
    session.add_all(
        [
            LogicalShift(
                id=sh.logical_id,
                org_id=schedule.org_id,
                schedule_id=schedule.id,
                created_in_version_id=version.id,
            )
            for sh in after
            if sh.logical_id not in existing
        ]
    )
    session.flush()
    session.add_all(
        [
            VersionShift(
                id=uuid.uuid7(),
                org_id=schedule.org_id,
                schedule_id=schedule.id,
                version_id=version.id,
                logical_shift_id=sh.logical_id,
                outlet_id=sh.outlet_id,
                employee_id=sh.employee_id,
                skill_id=sh.skill_id,
                start_at=sh.start_at,
                end_at=sh.end_at,
                break_start_at=sh.break_start_at,
                break_minutes=sh.break_minutes,
                locked=sh.locked,
                lock_reason=(reasons.get(sh.logical_id) or DEFAULT_LOCK_REASON) if sh.locked else None,
                template_id=templates.get(sh.logical_id),
            )
            for sh in after
        ]
    )
    version.revision += 1
    try:
        session.flush()
    except IntegrityError as exc:  # e.g. an employee or skill from another organization
        raise ApiError("validation_failed", "Some edits refer to unknown employees or roles.") from exc
    _audit(session, caller, "SHIFT_EDITED", "schedule_version", version.id, None, None)
    return version_view(session, version, record=True)


def discard_draft(caller: Caller, version_id: uuid.UUID, key: str | None = None) -> s.ScheduleVersionSummary:
    require(caller, "publish")
    with tenant_session(caller) as session:

        def produce() -> s.ScheduleVersionSummary:
            version, schedule = _version(session, caller, version_id, for_update=True)
            _require_draft(version)
            version.status = "discarded"
            version.discarded_at = datetime.now(UTC)  # starts the 7-day retention clock (v3 section 25)
            session.flush()
            _audit(session, caller, "DRAFT_DISCARDED", "schedule_version", version.id, None, None)
            view = version_view(session, version)
            return s.ScheduleVersionSummary.model_validate(
                view.model_dump(include=set(s.ScheduleVersionSummary.model_fields))
            )

        if key is None:
            return produce()
        keyed = _Keyed(version_id=version_id)
        return s.ScheduleVersionSummary.model_validate(
            idempotent(session, caller, key, "discardDraft", keyed, produce)
        )


# ---------------------------------------------------------------- B3.2 publication


def _live_check(
    session: Session, schedule: Schedule, version: ScheduleVersion
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(hard violations, metrics) of a draft against CURRENT facts: availability, absences, rules, skills
    and the organization-wide live roster. Takes advisory locks on every rostered employee in stable
    order first, so concurrent publications elsewhere cannot create cross-outlet conflicts."""
    roster = [snapshot_db.to_shift(r) for r in _rows(session, version.id)]
    for emp in sorted({str(sh.employee_id) for sh in roster if sh.employee_id}):
        session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"emp:{emp}"})
    snap = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, roster, schedule.id)
    result = validator.validate(snap, roster)
    hard = [v for v in validator.as_contract(result)["violations"] if v["severity"] == "hard"]
    return hard, metrics.as_contract(metrics.compute(snap, roster))


def _publish_locked(
    session: Session, caller: Caller, schedule: Schedule, version: ScheduleVersion, measured: dict[str, Any]
) -> tuple[s.ScheduleVersionSummary, uuid.UUID | None]:
    """Supersede, publish and move the pointer, with audit and outbox rows (schedule row locked).
    `measured` (from _live_check, against current facts) is stored and frozen with the version."""
    previous = schedule.current_version_id
    if previous is not None:
        session.execute(
            text("UPDATE schedule_versions SET status = 'superseded' WHERE id = :v"), {"v": previous}
        )
    version.metrics = measured
    version.status = "published"
    version.published_at = datetime.now(UTC)
    version.approved_by_user_id = uuid.UUID(caller.user_id)
    session.flush()
    schedule.current_version_id = version.id
    session.flush()
    _audit(session, caller, "SCHEDULE_PUBLISHED", "schedule_version", version.id, None, None)
    _outbox(
        session,
        schedule.org_id,
        "schedule.published",
        "schedule_version",
        version.id,
        {"schedule_id": schedule.id, "version_id": version.id, "superseded_version_id": previous},
    )
    session.refresh(version)
    view = version_view(session, version)
    summary = s.ScheduleVersionSummary.model_validate(
        view.model_dump(include=set(s.ScheduleVersionSummary.model_fields))
    )
    return summary, previous


def publish(caller: Caller, version_id: uuid.UUID, key: str, body: s.PublishRequest) -> s.PublishResult:
    require(caller, "publish")
    with tenant_session(caller) as session:

        def produce() -> s.PublishResult:
            version, schedule = _version(session, caller, version_id)
            session.execute(select(Schedule).where(Schedule.id == schedule.id).with_for_update())
            session.refresh(schedule)
            version = session.scalars(
                select(ScheduleVersion).where(ScheduleVersion.id == version_id).with_for_update()
            ).one()
            _check_base(schedule, body.expected_base_version_id)
            _require_draft(version)
            if body.expected_revision != version.revision:
                raise ApiError(
                    "stale_version",
                    "This draft was changed after you reviewed it. Review it again.",
                    current_revision=version.revision,
                )
            hard, measured = _live_check(session, schedule, version)
            if hard:
                raise ApiError(
                    "validation_failed",
                    "This draft breaks scheduling rules. Fix them before publishing.",
                    violations=hard,
                )
            summary, previous = _publish_locked(session, caller, schedule, version, measured)
            return s.PublishResult(schedule_id=schedule.id, published=summary, superseded_version_id=previous)

        return s.PublishResult.model_validate(
            idempotent(session, caller, key, "publishVersion", body, produce)
        )


# ---------------------------------------------------------------- B3.3 history, compare, restore


def list_versions(caller: Caller, schedule_id: uuid.UUID) -> s.VersionHistory:
    with tenant_session(caller) as session:
        schedule = session.get(Schedule, schedule_id)
        if schedule is None:
            raise not_found("Schedule")
        assert_outlet(caller, str(schedule.outlet_id))
        tz = _tz(session, schedule)
        versions = session.scalars(
            select(ScheduleVersion)
            .where(ScheduleVersion.schedule_id == schedule_id)
            .order_by(ScheduleVersion.version_number.desc())
        )
        return s.VersionHistory(
            schedule_id=schedule.id,
            current_version_id=schedule.current_version_id,
            items=[s.ScheduleVersionSummary.model_validate(_summary(v, tz)) for v in versions],
        )


def compare(caller: Caller, version_id: uuid.UUID, other_id: uuid.UUID) -> s.VersionDiff:
    with tenant_session(caller) as session:
        to_version, schedule = _version(session, caller, version_id)
        from_version, _ = _version(session, caller, other_id)
        tz = _tz(session, schedule)
        before_rows, after_rows = _rows(session, from_version.id), _rows(session, to_version.id)
        before = [snapshot_db.to_shift(r) for r in before_rows]
        after = [snapshot_db.to_shift(r) for r in after_rows]
        ids = {r.logical_shift_id: r.id for r in after_rows} | {
            r.logical_shift_id: r.id
            for r in before_rows
            if r.logical_shift_id not in {a.logical_id for a in after}
        }
        return s.VersionDiff(
            from_version_id=from_version.id,
            to_version_id=to_version.id,
            changes=_changes(before, after, tz, ids),
            metrics_from=version_view(session, from_version).metrics,
            metrics_to=version_view(session, to_version).metrics,
        )


def restore(caller: Caller, version_id: uuid.UUID, key: str, body: s.RestoreRequest) -> s.ScheduleVersion:
    require(caller, "publish")
    with tenant_session(caller) as session:

        def produce() -> s.ScheduleVersion:
            source, schedule = _version(session, caller, version_id)
            session.execute(select(Schedule).where(Schedule.id == schedule.id).with_for_update())
            session.refresh(schedule)
            _check_base(schedule, body.expected_base_version_id)
            if source.status == "discarded":
                raise ApiError("conflict", "Discarded drafts cannot be restored.")
            draft = _new_draft(
                session,
                caller,
                schedule,
                _rows(session, source.id),
                source="restore",
                reason=f"Restored from version {source.version_number}",
            )
            _audit(session, caller, "SCHEDULE_RESTORED", "schedule_version", draft.id, None, None)
            return version_view(session, draft, record=True)

        return s.ScheduleVersion.model_validate(
            idempotent(session, caller, key, "restoreVersion", body, produce)
        )
