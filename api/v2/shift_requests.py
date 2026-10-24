"""Employee shift requests: open-shift claims, giveaways and swaps (architecture v4 section 28).

    claim     employee sees only eligible open shifts -> claim -> validator -> pending_manager
    giveaway  employee offers an assigned shift -> a qualified colleague accepts -> validator -> pending
    swap      two assignments -> the other holder consents -> full check of both -> pending_manager

A manager's approval is the only way a request changes a schedule: the change is applied to a new draft
copied from the CURRENT published version, re-validated against current facts with employee locks, and
published through the same gate as any other version. Outcomes are reported, not raised: approved
(published), stale (the published week moved under these shifts) or invalid (current facts break it).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.drafts import _contract_shift, _live_check, _new_draft, _publish_locked, _rows, _tz
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, _outlet, week_bounds
from core.auth import Caller, Role, assert_outlet
from db.models import Employee, Outlet
from db.models_v2 import LogicalShift, Schedule, ScheduleVersion, ShiftRequest, VersionShift
from db.session import tenant_session
from scheduling import repair, snapshot_db, validator
from scheduling.model import Shift

ACTIVE = ("open", "pending_manager")


def _employee(caller: Caller) -> uuid.UUID:
    if caller.role is not Role.STAFF or not caller.employee_id:
        raise ApiError("permission_denied", "Shift requests are made by employees.")
    return uuid.UUID(caller.employee_id)


def _published(session: Session, schedule: Schedule) -> list[VersionShift]:
    version = (
        session.get(ScheduleVersion, schedule.current_version_id) if schedule.current_version_id else None
    )
    if version is None or version.status != "published":
        raise ApiError("conflict", "Only shifts in a published schedule can be requested.")
    return _rows(session, version.id)


def _assigned(rows: list[VersionShift], changes: dict[uuid.UUID, uuid.UUID | None]) -> list[Shift]:
    out = []
    for r in rows:
        sh = snapshot_db.to_shift(r)
        if r.logical_shift_id in changes:
            sh = Shift(
                sh.logical_id,
                sh.outlet_id,
                changes[r.logical_shift_id],
                sh.skill_id,
                sh.start_at,
                sh.end_at,
                sh.break_minutes,
                sh.break_start_at,
                sh.locked,
            )
        out.append(sh)
    return out


def _breaks(
    session: Session, schedule: Schedule, rows: list[VersionShift], changes: dict[uuid.UUID, uuid.UUID | None]
) -> list[dict[str, Any]]:
    """Hard violations the change would introduce for the people and shifts it touches, against
    current facts (availability, absences, rules, rest, hours, the organization-wide roster)."""
    after = _assigned(rows, changes)
    snap = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, after, schedule.id)
    people = {e for e in changes.values() if e is not None}
    hard = []
    for v in validator.as_contract(validator.validate(snap, after))["violations"]:
        touched = set(map(str, changes)) & {str(i) for i in v["logical_shift_ids"]}
        if v["severity"] == "hard" and (
            touched or (v["employee_id"] and uuid.UUID(str(v["employee_id"])) in people)
        ):
            hard.append(v)
    return hard


def _refuse(hard: list[dict[str, Any]], who: str) -> ApiError:
    return ApiError(
        "validation_failed",
        f"{who} cannot take this shift: {hard[0]['message']}",
        violations=hard,
    )


def _view(session: Session, r: ShiftRequest) -> s.ShiftRequestView:
    schedule = session.get(Schedule, r.schedule_id)
    assert schedule is not None
    tz = _tz(session, schedule)
    rows = {x.logical_shift_id: x for x in _rows(session, r.base_version_id)}

    def shift(lid: uuid.UUID | None) -> s.Shift | None:
        row = rows.get(lid) if lid else None
        return _contract_shift(snapshot_db.to_shift(row), tz, row.id, row.lock_reason) if row else None

    main = shift(r.logical_shift_id)
    assert main is not None
    return s.ShiftRequestView(
        id=r.id,
        type=r.type,  # type: ignore[arg-type]
        status=r.status,  # type: ignore[arg-type]
        schedule_id=schedule.id,
        outlet_id=schedule.outlet_id,
        week_start=schedule.week_start,
        base_version_id=r.base_version_id,
        shift=main,
        target_shift=shift(r.target_logical_shift_id),
        requester_employee_id=r.requester_employee_id,
        target_employee_id=r.target_employee_id,
        note=r.note,
        created_at=r.created_at,
        expires_at=r.expires_at,
        decided_by_user_id=r.decided_by_user_id,
        decided_at=r.decided_at,
        published_version_id=r.published_version_id,
        violations=[s.Violation.model_validate(v) for v in (r.outcome or {}).get("violations", [])],
    )


def _changes(r: ShiftRequest) -> dict[uuid.UUID, uuid.UUID | None]:
    if r.type == "open_shift_claim":
        return {r.logical_shift_id: r.requester_employee_id}
    if r.type == "giveaway":
        return {r.logical_shift_id: r.target_employee_id}
    assert r.target_logical_shift_id is not None
    return {r.logical_shift_id: r.target_employee_id, r.target_logical_shift_id: r.requester_employee_id}


def create(caller: Caller, body: s.CreateShiftRequest) -> s.ShiftRequestView:
    me = _employee(caller)
    with tenant_session(caller) as session:
        logical = session.get(LogicalShift, body.logical_shift_id)
        if logical is None:
            raise not_found("Shift")
        schedule = session.get(Schedule, logical.schedule_id)
        assert schedule is not None
        employee = session.get(Employee, me)
        if employee is None or employee.outlet_id != schedule.outlet_id:
            raise ApiError("permission_denied", "You can request shifts at your own outlet only.")
        rows = _published(session, schedule)
        by_id = {x.logical_shift_id: x for x in rows}
        row = by_id.get(body.logical_shift_id)
        if row is None:
            raise not_found("Shift")
        if body.type == "open_shift_claim" and row.employee_id is not None:
            raise ApiError("conflict", "This shift is not open.")
        if body.type in ("giveaway", "swap") and row.employee_id != me:
            raise ApiError("permission_denied", "You can only offer or swap your own shifts.")
        target_row = by_id.get(body.target_logical_shift_id) if body.target_logical_shift_id else None
        target = body.target_employee_id
        if body.type == "swap":
            if target_row is None or target_row.employee_id in (None, me):
                raise ApiError(
                    "validation_failed",
                    "Some fields need attention.",
                    fields=[
                        {
                            "path": ["target_logical_shift_id"],
                            "message": "Pick a colleague's shift this week.",
                        }
                    ],
                )
            if target is not None and target != target_row.employee_id:
                raise ApiError(
                    "validation_failed",
                    "Some fields need attention.",
                    fields=[
                        {"path": ["target_employee_id"], "message": "That shift belongs to someone else."}
                    ],
                )
            target = target_row.employee_id
        elif body.target_logical_shift_id is not None:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {"path": ["target_logical_shift_id"], "message": "Only a swap names a second shift."}
                ],
            )
        if body.type == "open_shift_claim" and target is not None:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[{"path": ["target_employee_id"], "message": "A claim is for yourself."}],
            )
        if target is not None and target == me:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[{"path": ["target_employee_id"], "message": "Choose a colleague."}],
            )
        starts = [row.start_at, *([target_row.start_at] if target_row else [])]
        if min(starts) <= datetime.now(UTC):
            raise ApiError("conflict", "This shift has already started.")
        if body.type == "open_shift_claim":
            hard = _breaks(session, schedule, rows, {row.logical_shift_id: me})
            if hard:
                raise _refuse(hard, "You")
        elif body.type == "swap" and target_row is not None:
            hard = _breaks(
                session, schedule, rows, {row.logical_shift_id: target, target_row.logical_shift_id: me}
            )
            if hard:
                raise ApiError(
                    "validation_failed", f"This swap breaks a rule: {hard[0]['message']}", violations=hard
                )
        request = ShiftRequest(
            id=uuid.uuid7(),
            org_id=schedule.org_id,
            schedule_id=schedule.id,
            type=body.type,
            logical_shift_id=row.logical_shift_id,
            base_version_id=schedule.current_version_id,
            requester_employee_id=me,
            target_employee_id=target,
            target_logical_shift_id=target_row.logical_shift_id if target_row else None,
            status="pending_manager" if body.type == "open_shift_claim" else "open",
            note=body.note,
            expires_at=min(starts),
        )
        session.add(request)
        try:
            session.flush()
        except IntegrityError as exc:
            raise ApiError("conflict", "This shift already has an open request.") from exc
        _audit(session, caller, "SHIFT_REQUEST_CREATED", "shift_request", request.id, None, None)
        return _view(session, request)


def _load(session: Session, request_id: uuid.UUID, *, for_update: bool = False) -> ShiftRequest:
    query = select(ShiftRequest).where(ShiftRequest.id == request_id)
    r = session.scalars(query.with_for_update() if for_update else query).first()
    if r is None:
        raise not_found("Shift request")
    return r


def _expire_if_due(session: Session, r: ShiftRequest) -> bool:
    if r.status in ACTIVE and r.expires_at <= datetime.now(UTC):
        r.status = "expired"
        session.flush()
        return True
    return False


def _moved(session: Session, schedule: Schedule, r: ShiftRequest) -> bool:
    """True when the published week changed any shift this request touches since it was made."""
    if schedule.current_version_id == r.base_version_id:
        return False
    assert schedule.current_version_id is not None
    keys = [r.logical_shift_id, *([r.target_logical_shift_id] if r.target_logical_shift_id else [])]

    def state(version_id: uuid.UUID) -> dict[uuid.UUID, tuple[Any, ...]]:
        return {
            x.logical_shift_id: (x.employee_id, x.skill_id, x.start_at, x.end_at)
            for x in _rows(session, version_id)
            if x.logical_shift_id in keys
        }

    return state(r.base_version_id) != state(schedule.current_version_id)


def accept(caller: Caller, request_id: uuid.UUID) -> s.ShiftRequestView:
    """A colleague takes a giveaway, or the other holder consents to a swap."""
    me = _employee(caller)
    with tenant_session(caller) as session:
        r = _load(session, request_id, for_update=True)
        schedule = session.get(Schedule, r.schedule_id)
        assert schedule is not None
        if r.requester_employee_id == me:
            raise ApiError("conflict", "You made this request.")
        if r.type == "open_shift_claim" or (r.target_employee_id is not None and r.target_employee_id != me):
            raise not_found("Shift request")
        employee = session.get(Employee, me)
        if employee is None or employee.outlet_id != schedule.outlet_id:
            raise not_found("Shift request")
        if _expire_if_due(session, r):
            return _view(session, r)
        if r.status != "open":
            raise ApiError("conflict", f"This request is {r.status}.", status=r.status)
        if _moved(session, schedule, r):
            r.status = "stale"
            session.flush()
            return _view(session, r)
        r.target_employee_id = me
        rows = _published(session, schedule)
        hard = _breaks(session, schedule, rows, _changes(r))
        if hard:
            raise _refuse(hard, "You")
        r.status = "pending_manager"
        session.flush()
        _audit(session, caller, "SHIFT_REQUEST_ACCEPTED", "shift_request", r.id, None, None)
        return _view(session, r)


def cancel(caller: Caller, request_id: uuid.UUID) -> s.ShiftRequestView:
    me = _employee(caller)
    with tenant_session(caller) as session:
        r = _load(session, request_id, for_update=True)
        if r.requester_employee_id != me:
            raise not_found("Shift request")
        if r.status not in ACTIVE:
            raise ApiError("conflict", f"This request is {r.status}.", status=r.status)
        r.status = "cancelled"
        session.flush()
        _audit(session, caller, "SHIFT_REQUEST_CANCELLED", "shift_request", r.id, None, None)
        return _view(session, r)


def mine(caller: Caller) -> s.ShiftRequestList:
    """Requests I made or that name me, and open giveaways at my outlet that anyone may take."""
    me = _employee(caller)
    with tenant_session(caller) as session:
        employee = session.get(Employee, me)
        assert employee is not None
        rows = session.scalars(
            select(ShiftRequest)
            .join(Schedule, Schedule.id == ShiftRequest.schedule_id)
            .where(
                (ShiftRequest.requester_employee_id == me)
                | (ShiftRequest.target_employee_id == me)
                | (
                    (ShiftRequest.type == "giveaway")
                    & (ShiftRequest.status == "open")
                    & ShiftRequest.target_employee_id.is_(None)
                    & (Schedule.outlet_id == employee.outlet_id)
                )
            )
            .order_by(ShiftRequest.created_at.desc())
            .limit(100)
        )
        return s.ShiftRequestList(items=[_view(session, r) for r in rows])


def open_shifts(caller: Caller, week_start: date) -> s.OpenShiftList:
    me = _employee(caller)
    with tenant_session(caller) as session:
        employee = session.get(Employee, me)
        assert employee is not None
        outlet = session.get(Outlet, employee.outlet_id)
        assert outlet is not None
        week_bounds(outlet, week_start)
        schedule = session.scalars(
            select(Schedule).where(
                Schedule.outlet_id == employee.outlet_id, Schedule.week_start == week_start
            )
        ).first()
        if schedule is None or schedule.current_version_id is None:
            return s.OpenShiftList(week_start=week_start, items=[])
        rows = _published(session, schedule)
        now = datetime.now(UTC)
        taken = set(
            session.scalars(
                select(ShiftRequest.logical_shift_id).where(
                    ShiftRequest.schedule_id == schedule.id, ShiftRequest.status.in_(ACTIVE)
                )
            )
        )
        roster = [snapshot_db.to_shift(x) for x in rows]
        snap = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, roster, schedule.id)
        week_start_at, week_end_at = snap.week_bounds()
        tz = _tz(session, schedule)
        items = []
        for row in rows:
            if row.employee_id is not None or row.start_at <= now or row.logical_shift_id in taken:
                continue
            sh = snapshot_db.to_shift(row)
            others = [o for o in roster if o.logical_id != sh.logical_id]
            facts = repair._facts(snap, sh, me, others, week_start_at, week_end_at)
            if all(f.ok for f in facts):
                items.append(
                    s.OpenShift(
                        version_id=schedule.current_version_id,
                        shift=_contract_shift(sh, tz, row.id, row.lock_reason),
                        reasons=[
                            s.ExplanationFact(code=f.code, ok=f.ok, message=f.message, facts=f.facts)  # type: ignore[arg-type]
                            for f in facts
                        ],
                    )
                )
        return s.OpenShiftList(week_start=week_start, items=items)


def for_outlet(caller: Caller, outlet_id: uuid.UUID, status: str | None) -> s.ShiftRequestList:
    require(caller, "publish")
    with tenant_session(caller) as session:
        _outlet(session, caller, outlet_id)
        query = (
            select(ShiftRequest)
            .join(Schedule, Schedule.id == ShiftRequest.schedule_id)
            .where(Schedule.outlet_id == outlet_id)
            .order_by(ShiftRequest.created_at.desc())
            .limit(100)
        )
        if status is not None:
            query = query.where(ShiftRequest.status == status)
        return s.ShiftRequestList(items=[_view(session, r) for r in session.scalars(query)])


def _decidable(session: Session, caller: Caller, request_id: uuid.UUID) -> tuple[ShiftRequest, Schedule]:
    require(caller, "publish")
    r = _load(session, request_id, for_update=True)
    schedule = session.scalars(select(Schedule).where(Schedule.id == r.schedule_id).with_for_update()).first()
    assert schedule is not None
    assert_outlet(caller, str(schedule.outlet_id))
    return r, schedule


def reject(caller: Caller, request_id: uuid.UUID) -> s.ShiftRequestView:
    with tenant_session(caller) as session:
        r, _ = _decidable(session, caller, request_id)
        if r.status not in ACTIVE:
            raise ApiError("conflict", f"This request is {r.status}.", status=r.status)
        r.status, r.decided_by_user_id, r.decided_at = (
            "rejected",
            uuid.UUID(caller.user_id),
            datetime.now(UTC),
        )
        session.flush()
        _audit(session, caller, "SHIFT_REQUEST_REJECTED", "shift_request", r.id, None, None)
        return _view(session, r)


def approve(caller: Caller, request_id: uuid.UUID) -> s.ShiftRequestView:
    """Publish the change through the normal gate, or report why not (stale, invalid, expired)."""
    with tenant_session(caller) as session:
        r, schedule = _decidable(session, caller, request_id)
        if _expire_if_due(session, r):
            return _view(session, r)
        if r.status != "pending_manager":
            raise ApiError("conflict", f"This request is {r.status}.", status=r.status)
        r.decided_by_user_id, r.decided_at = uuid.UUID(caller.user_id), datetime.now(UTC)
        if _moved(session, schedule, r):
            r.status = "stale"
            session.flush()
            return _view(session, r)
        rows = _published(session, schedule)
        names = {
            e.id: e.name
            for e in session.scalars(
                select(Employee).where(Employee.id.in_([r.requester_employee_id, r.target_employee_id]))
            )
        }
        mine_ = names.get(r.requester_employee_id)
        theirs = names.get(r.target_employee_id) if r.target_employee_id else None
        reason = {
            "open_shift_claim": f"Open shift claimed by {mine_}",
            "giveaway": f"Shift given by {mine_} to {theirs}",
            "swap": f"Shift swap: {mine_} and {theirs}",
        }[r.type]
        draft = _new_draft(session, caller, schedule, rows, source="request", reason=reason[:200])
        for lid, emp in _changes(r).items():
            row = session.scalars(
                select(VersionShift).where(
                    VersionShift.version_id == draft.id, VersionShift.logical_shift_id == lid
                )
            ).one()
            row.employee_id = emp
        session.flush()
        hard, measured = _live_check(session, schedule, draft)
        if hard:
            draft.status, draft.discarded_at = "discarded", datetime.now(UTC)
            r.status, r.outcome = "invalid", {"violations": hard}
            session.flush()
            return _view(session, r)
        _publish_locked(session, caller, schedule, draft, measured)
        r.status, r.published_version_id = "approved", draft.id
        session.flush()
        _audit(session, caller, "SHIFT_REQUEST_APPROVED", "shift_request", r.id, None, None)
        return _view(session, r)
