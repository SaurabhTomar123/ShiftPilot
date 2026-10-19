"""B1.2 part 2: schedule reads. Validation and metrics come from the independent validator (B2.1),
evaluated against current live facts, so an absence confirmed after publication shows up."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.errors import ApiError, not_found
from api.v2.service import _outlet, week_bounds
from core.auth import Caller, Role, assert_outlet
from db.models import Employee as EmployeeRow
from db.models import Outlet as OutletRow
from db.models_v2 import Absence, EmployeeSkill, Schedule, ScheduleVersion, Skill, VersionShift
from db.session import tenant_session
from scheduling import metrics, snapshot_db, validator
from scheduling.model import Shift


def _shift_view(row: VersionShift, tz: ZoneInfo) -> s.Shift:
    return s.Shift(
        id=row.id,
        logical_shift_id=row.logical_shift_id,
        outlet_id=row.outlet_id,
        employee_id=row.employee_id,
        skill_id=row.skill_id,
        start_at=row.start_at.astimezone(tz),
        end_at=row.end_at.astimezone(tz),
        break_start_at=row.break_start_at.astimezone(tz) if row.break_start_at else None,
        break_minutes=row.break_minutes,
        locked=row.locked,
        lock_reason=row.lock_reason,
    )


def _summary(v: ScheduleVersion, tz: ZoneInfo) -> dict[str, object]:
    return dict(
        id=v.id,
        schedule_id=v.schedule_id,
        version_number=v.version_number,
        status=v.status,
        source=v.source,
        reason=v.reason,
        base_version_id=v.base_version_id,
        optimization_run_id=v.optimization_run_id,
        created_by_user_id=v.created_by_user_id,
        approved_by_user_id=v.approved_by_user_id,
        created_at=v.created_at.astimezone(tz),
        published_at=v.published_at.astimezone(tz) if v.published_at else None,
        revision=v.revision,
    )


def version_view(session: Session, version: ScheduleVersion) -> s.ScheduleVersion:
    schedule = session.get(Schedule, version.schedule_id)
    assert schedule is not None
    outlet = session.get(OutletRow, schedule.outlet_id)
    assert outlet is not None
    tz = ZoneInfo(outlet.timezone)
    rows = list(
        session.scalars(
            select(VersionShift)
            .where(VersionShift.version_id == version.id)
            .order_by(VersionShift.start_at, VersionShift.logical_shift_id)
        )
    )
    roster: list[Shift] = [snapshot_db.to_shift(r) for r in rows]
    snap = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, roster, schedule.id)
    result = validator.validate(snap, roster)
    m = metrics.compute(snap, roster)
    return s.ScheduleVersion(
        **_summary(version, tz),  # type: ignore[arg-type]
        input_hash=version.input_hash,
        shifts=[_shift_view(r, tz) for r in rows],
        metrics=s.Metrics(
            coverage_ratio=m.coverage_ratio,
            minimum_deficit_minutes=m.minimum_deficit_minutes,
            preferred_deficit_minutes=m.preferred_deficit_minutes,
            labour_cost=s.Money(amount_paise=m.labour_cost_paise),
            overtime_cost=s.Money(amount_paise=m.overtime_cost_paise),
            overtime_minutes=m.overtime_minutes,
            preference_match_ratio=m.preference_match_ratio,
            open_shifts=m.open_shifts,
            assigned_minutes=m.assigned_minutes,
        ),
        coverage=[
            s.CoverageCell(
                skill_id=c.skill_id,
                interval_start=c.interval_start.astimezone(tz),
                minimum_required=c.minimum_required,
                preferred_required=c.preferred_required,
                scheduled=c.scheduled,
            )
            for c in m.cells
        ],
        validation=s.ValidationResult(
            hard_violations=result.hard,
            soft_violations=result.soft,
            violations=[
                s.Violation.model_validate(
                    {
                        "code": v.code,
                        "severity": v.severity,
                        "message": v.message,
                        "employee_id": v.employee_id,
                        "logical_shift_ids": list(v.logical_shift_ids),
                        "facts": v.facts,
                    }
                )
                for v in result.violations
            ],
        ),
    )


def week_etag(current_version_id: uuid.UUID | None, drafts: list[ScheduleVersion]) -> str:
    base = f"week-{current_version_id or 'none'}"
    if drafts:
        digest = hashlib.sha256("|".join(f"{d.id}:{d.status}" for d in drafts).encode()).hexdigest()[:12]
        base += f"-{digest}"
    return f'"{base}"'


def schedule_week(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, if_none_match: str | None = None
) -> tuple[str, s.ScheduleWeek | None]:
    """(etag, body). Authorization runs first; the body is None when if_none_match is current."""
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "Staff see their own week under /v2/me/shifts.")
    with tenant_session(caller) as session:
        outlet = _outlet(session, caller, outlet_id)
        start, end = week_bounds(outlet, week_start)
        tz = ZoneInfo(outlet.timezone)
        schedule = session.scalars(
            select(Schedule).where(Schedule.outlet_id == outlet_id, Schedule.week_start == week_start)
        ).first()
        drafts = (
            []
            if schedule is None
            else list(
                session.scalars(
                    select(ScheduleVersion)
                    .where(ScheduleVersion.schedule_id == schedule.id, ScheduleVersion.status == "draft")
                    .order_by(ScheduleVersion.version_number)
                )
            )
        )
        current = (
            session.get(ScheduleVersion, schedule.current_version_id)
            if schedule and schedule.current_version_id
            else None
        )
        etag = week_etag(current.id if current else None, drafts)
        if if_none_match == etag:
            return etag, None
        current_view = version_view(session, current) if current else None
        rostered = {sh.employee_id for sh in (current_view.shifts if current_view else []) if sh.employee_id}
        rows = list(
            session.scalars(
                select(EmployeeRow)
                .where(
                    ((EmployeeRow.outlet_id == outlet_id) & (EmployeeRow.status == "active"))
                    | EmployeeRow.id.in_(rostered)
                )
                .order_by(EmployeeRow.name)
            )
        )
        ids = [r.id for r in rows]
        skills: dict[uuid.UUID, list[uuid.UUID]] = {i: [] for i in ids}
        for es in session.scalars(
            select(EmployeeSkill)
            .where(EmployeeSkill.employee_id.in_(ids))
            .order_by(EmployeeSkill.level.desc(), EmployeeSkill.skill_id)
        ):
            skills[es.employee_id].append(es.skill_id)
        minutes: dict[uuid.UUID, int] = dict.fromkeys(ids, 0)
        for r in snapshot_db.live_shifts(session, start, end, employee_ids=ids):
            if r.employee_id is not None and start <= r.start_at < end:
                minutes[r.employee_id] += snapshot_db.to_shift(r).paid_minutes
        absences = list(
            session.scalars(
                select(Absence)
                .where(
                    Absence.employee_id.in_(ids),
                    Absence.start_at < end,
                    Absence.end_at > start,
                    Absence.status.in_(("requested", "confirmed")),
                )
                .order_by(Absence.start_at)
            )
        )
        body = s.ScheduleWeek(
            outlet_id=outlet.id,
            week_start=week_start,
            timezone=outlet.timezone,
            schedule_id=schedule.id if schedule else None,
            current_version=current_view,
            drafts=[s.ScheduleVersionSummary.model_validate(_summary(d, tz)) for d in drafts],
            employees=[
                s.RosterEmployee(
                    id=r.id,
                    name=r.name,
                    home_outlet_id=r.outlet_id,
                    skill_ids=skills[r.id],
                    status="active" if r.status == "active" else "inactive",
                    scheduled_minutes=minutes[r.id],
                    regular_weekly_minutes=r.regular_weekly_minutes,
                    max_weekly_minutes=r.max_weekly_minutes,
                )
                for r in rows
            ],
            absences=[
                s.AbsenceMark.model_validate(
                    {
                        "id": a.id,
                        "employee_id": a.employee_id,
                        "start_at": a.start_at.astimezone(tz),
                        "end_at": a.end_at.astimezone(tz),
                        "kind": a.kind,
                        "status": a.status,
                    }
                )
                for a in absences
            ],
        )
        return etag, body


def version_etag(version_id: uuid.UUID, status: str, revision: int) -> str:
    """Changes when the status (published -> superseded) or a draft's revision changes."""
    return f'"{version_id}:{status}:{revision}"'


def schedule_version(
    caller: Caller, version_id: uuid.UUID, if_none_match: str | None = None
) -> tuple[str, str, s.ScheduleVersion | None]:
    """(etag, cache-control, body). Authorization runs first; body is None when if_none_match is current."""
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "Staff see their own week under /v2/me/shifts.")
    with tenant_session(caller) as session:
        version = session.get(ScheduleVersion, version_id)
        if version is None:
            raise not_found("Schedule version")
        schedule = session.get(Schedule, version.schedule_id)
        assert schedule is not None
        assert_outlet(caller, str(schedule.outlet_id))
        cache = "private, no-cache"  # status is mutable (published -> superseded); v3 section 35
        etag = version_etag(version.id, version.status, version.revision)
        if if_none_match == etag:
            return etag, cache, None
        return etag, cache, version_view(session, version)


def my_week(caller: Caller, week_start: date) -> s.MyWeek:
    if caller.role is not Role.STAFF or not caller.employee_id:
        raise ApiError("permission_denied", "This view is for employees.")
    employee_id = uuid.UUID(caller.employee_id)
    with tenant_session(caller) as session:
        employee = session.get(EmployeeRow, employee_id)
        if employee is None:
            raise not_found("Employee")
        home = session.get(OutletRow, employee.outlet_id)
        assert home is not None
        start, end = week_bounds(home, week_start)
        rows = [
            r
            for r in snapshot_db.live_shifts(session, start, end, employee_ids=[employee_id])
            if start <= r.start_at < end
        ]
        rows.sort(key=lambda r: r.start_at)
        outlets = {
            o.id: o
            for o in session.scalars(select(OutletRow).where(OutletRow.id.in_({r.outlet_id for r in rows})))
        }
        skills = {
            k.id: k for k in session.scalars(select(Skill).where(Skill.id.in_({r.skill_id for r in rows})))
        }
        return s.MyWeek(
            employee_id=employee_id,
            week_start=week_start,
            shifts=[_shift_view(r, ZoneInfo(outlets[r.outlet_id].timezone)) for r in rows],
            outlets=[
                s.OutletRef(id=o.id, name=o.name, timezone=o.timezone)
                for o in sorted(outlets.values(), key=lambda o: o.name)
            ],
            skills=[s.Skill(id=k.id, name=k.name) for k in sorted(skills.values(), key=lambda k: k.name)],
        )
