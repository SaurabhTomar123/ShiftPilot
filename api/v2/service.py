"""B1.2 data services. Every function runs inside tenant_session (RLS on app.org_id) and checks
outlet scope explicitly: RLS isolates organizations, not outlets."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import and_, delete, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from core.auth import Caller, Role, assert_outlet
from db.models import AuditLog, Employee, Outlet
from db.models_v2 import (
    DemandWeek,
    EmployeeAvailability,
    EmployeeSkill,
    IdempotencyKey,
    Skill,
    StaffingRequirement,
)
from db.session import tenant_session

INTERVAL_MINUTES = 30


# ---------------------------------------------------------------- helpers


def _uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _scope(caller: Caller, outlet_id: uuid.UUID) -> None:
    assert_outlet(caller, str(outlet_id))


# Audit event names (architecture v3 section 26). v3 names IMPORT_COMMITTED, RULE_CREATED, SHIFT_EDITED,
# OPTIMIZATION_REQUESTED, ABSENCE_REPORTED, PROPOSAL_APPROVED, SCHEDULE_PUBLISHED and SCHEDULE_RESTORED;
# the first two arrive with CSV import (B5.4) and rules (B5.2). Rows are never renamed: before contract 3.7
# a draft edit was recorded as SHIFTS_EDITED.
AUDIT_ACTIONS = frozenset(
    {
        "ABSENCE_REPORTED",
        "ABSENCE_CONFIRMED",  # absence decisions: ABSENCE_{status} in absences.update
        "ABSENCE_REJECTED",
        "ABSENCE_CANCELLED",
        "AVAILABILITY_REPLACED",
        "CANDIDATE_SELECTED",
        "DRAFT_CREATED",
        "DRAFT_DISCARDED",
        "EMPLOYEE_CREATED",
        "EMPLOYEE_UPDATED",
        "IMPORT_STAGED",
        "IMPORT_COMMITTED",
        "RULE_CREATED",
        "RULE_ARCHIVED",
        "OPTIMIZATION_REQUESTED",
        "PROPOSAL_APPROVED",
        "PROPOSAL_CREATED",
        "PROPOSAL_REJECTED",
        "SCENARIO_CREATED",
        "SCENARIO_EVENT_ADDED",
        "SCENARIO_CONVERTED",
        "SCENARIO_DISCARDED",
        "SCHEDULE_PUBLISHED",
        "SCHEDULE_RESTORED",
        "SHIFT_EDITED",
        "STAFFING_EXPANDED",
        "STAFFING_REPLACED",
        "STAFFING_TEMPLATE_REPLACED",
    }
)


def _audit(
    session: Session,
    caller: Caller,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    before: BaseModel | None,
    after: BaseModel | None,
) -> None:
    if action not in AUDIT_ACTIONS:
        raise ValueError(f"unregistered audit action {action}")  # a typo would silently fork the log
    session.add(
        AuditLog(
            id=uuid.uuid7(),
            org_id=uuid.UUID(caller.org_id),
            actor_user_id=uuid.UUID(caller.user_id),
            channel="web",
            tool=action.lower(),
            args_redacted={},
            outcome="ok",
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before.model_dump(mode="json") if before else None,
            after=after.model_dump(mode="json") if after else None,
        )
    )


def idempotent(
    session: Session,
    caller: Caller,
    key: str,
    operation: str,
    request: BaseModel,
    produce: Callable[[], BaseModel],
) -> dict[str, Any]:
    """Replay the stored result for a repeated key; reject the same key with a different request."""
    org = uuid.UUID(caller.org_id)
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"{org}:{key}"})
    digest = hashlib.sha256(
        json.dumps({"op": operation, "body": request.model_dump(mode="json")}, sort_keys=True).encode()
    ).hexdigest()
    stored = session.get(IdempotencyKey, (org, key))
    if stored is not None:
        if stored.operation != operation or stored.request_hash != digest:
            raise ApiError("idempotency_conflict", "This request key was already used with different input.")
        return stored.response
    result = produce().model_dump(mode="json")
    session.add(
        IdempotencyKey(
            org_id=org, key=key, operation=operation, request_hash=digest, status_code=201, response=result
        )
    )
    return result


def _paise(rate: Decimal) -> int:
    return int((rate * 100).to_integral_value())


def _employee_view(session: Session, e: Employee) -> s.Employee:
    skills = session.scalars(select(EmployeeSkill).where(EmployeeSkill.employee_id == e.id)).all()
    return s.Employee(
        id=e.id,
        name=e.name,
        home_outlet_id=e.outlet_id,
        status=e.status,  # type: ignore[arg-type]
        hourly_rate=s.Money(amount_paise=_paise(e.hourly_rate)),
        skills=sorted(
            (s.EmployeeSkill(skill_id=k.skill_id, level=k.level) for k in skills),
            key=lambda k: (-k.level, str(k.skill_id)),
        ),
        tags=list(e.tags),
        regular_weekly_minutes=e.regular_weekly_minutes,
        max_weekly_minutes=e.max_weekly_minutes,
        preferred_weekly_minutes=e.preferred_weekly_minutes,
        overtime_allowed=e.overtime_allowed,
        cross_outlet_eligible=e.cross_outlet_eligible,
        revision=e.revision,
    )


def _check_skills(session: Session, skills: list[s.EmployeeSkill]) -> None:
    ids = [k.skill_id for k in skills]
    if len(set(ids)) != len(ids):
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            fields=[{"path": ["skills"], "message": "Each skill may appear only once."}],
        )
    known = set(session.scalars(select(Skill.id).where(Skill.id.in_(ids))).all()) if ids else set()
    unknown = [str(i) for i in ids if i not in known]
    if unknown:
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            fields=[{"path": ["skills"], "message": f"Unknown skill: {', '.join(unknown)}"}],
        )


def _check_caps(regular: int, maximum: int) -> None:
    if maximum < regular:
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            fields=[{"path": ["max_weekly_minutes"], "message": "Must be at least regular_weekly_minutes."}],
        )


def _outlet(session: Session, caller: Caller, outlet_id: uuid.UUID) -> Outlet:
    outlet = session.get(Outlet, outlet_id)
    if outlet is None:
        raise not_found("Outlet")
    _scope(caller, outlet_id)
    return outlet


def week_bounds(outlet: Outlet, week_start: date) -> tuple[datetime, datetime]:
    if week_start.isoweekday() != 1:
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            fields=[{"path": ["week_start"], "message": "week_start must be a Monday."}],
        )
    start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=ZoneInfo(outlet.timezone))
    return start, start + timedelta(days=7)


# ---------------------------------------------------------------- outlets and skills


def _outlet_view(o: Outlet) -> s.Outlet:
    hours = o.operating_hours or {}
    windows = [
        s.OperatingWindow(weekday=int(d), open_minute=a, close_minute=b)
        for d, spans in sorted(hours.items(), key=lambda kv: int(kv[0]))
        for a, b in spans
    ]
    return s.Outlet(id=o.id, name=o.name, slug=o.slug, timezone=o.timezone, operating_hours=windows)


def list_outlets(caller: Caller) -> s.OutletList:
    with tenant_session(caller) as session:
        query = select(Outlet).order_by(Outlet.name)
        if caller.role is not Role.OWNER:
            query = query.where(Outlet.id == _uuid(caller.outlet_id))
        return s.OutletList(items=[_outlet_view(o) for o in session.scalars(query)])


def list_skills(caller: Caller) -> s.SkillList:
    with tenant_session(caller) as session:
        return s.SkillList(
            items=[s.Skill(id=k.id, name=k.name) for k in session.scalars(select(Skill).order_by(Skill.name))]
        )


# ---------------------------------------------------------------- employees


def _cursor(name: str, ident: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([name, str(ident)]).encode()).decode()


def list_employees(
    caller: Caller, outlet_id: uuid.UUID | None, status: str | None, cursor: str | None, limit: int
) -> s.EmployeeList:
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "Staff can only see their own schedule.")
    if caller.role is Role.MANAGER:
        outlet_id = outlet_id or _uuid(caller.outlet_id)
    if outlet_id is not None:
        _scope(caller, outlet_id)
    with tenant_session(caller) as session:
        query = select(Employee).order_by(Employee.name, Employee.id).limit(limit + 1)
        if outlet_id is not None:
            query = query.where(Employee.outlet_id == outlet_id)
        if status:
            query = query.where(Employee.status == status)
        if cursor:
            try:
                name, ident = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                after = (str(name), uuid.UUID(ident))
            except Exception as exc:
                raise ApiError(
                    "validation_failed",
                    "Some fields need attention.",
                    fields=[{"path": ["cursor"], "message": "Invalid cursor."}],
                ) from exc
            query = query.where(
                or_(Employee.name > after[0], and_(Employee.name == after[0], Employee.id > after[1]))
            )
        rows = list(session.scalars(query))
        page, more = rows[:limit], len(rows) > limit
        return s.EmployeeList(
            items=[_employee_view(session, e) for e in page],
            next_cursor=_cursor(page[-1].name, page[-1].id) if more else None,
        )


def _load_employee(
    session: Session, caller: Caller, employee_id: uuid.UUID, *, for_update: bool = False
) -> Employee:
    query = select(Employee).where(Employee.id == employee_id)
    employee = session.scalars(query.with_for_update() if for_update else query).first()
    if employee is None:
        raise not_found("Employee")
    if caller.role is Role.STAFF:
        if caller.employee_id != str(employee_id):
            raise ApiError("permission_denied", "Staff can only see their own records.")
    else:
        _scope(caller, employee.outlet_id)
    return employee


def get_employee(caller: Caller, employee_id: uuid.UUID) -> s.Employee:
    with tenant_session(caller) as session:
        return _employee_view(session, _load_employee(session, caller, employee_id))


def create_employee(caller: Caller, key: str, body: s.EmployeeCreate) -> s.Employee:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:

        def produce() -> s.Employee:
            _outlet(session, caller, body.home_outlet_id)
            _check_skills(session, body.skills)
            _check_caps(body.regular_weekly_minutes, body.max_weekly_minutes)
            employee = Employee(
                id=uuid.uuid7(),
                org_id=uuid.UUID(caller.org_id),
                outlet_id=body.home_outlet_id,
                name=body.name,
                aliases=[],
                job_role="staff",
                pay_type="hourly",
                hourly_rate=Decimal(body.hourly_rate.amount_paise) / 100,
                monthly_base=None,
                phone="",
                joined_on=datetime.now(UTC).date(),
                status=body.status,
                regular_weekly_minutes=body.regular_weekly_minutes,
                max_weekly_minutes=body.max_weekly_minutes,
                preferred_weekly_minutes=body.preferred_weekly_minutes,
                tags=list(body.tags),
                overtime_allowed=body.overtime_allowed,
                cross_outlet_eligible=body.cross_outlet_eligible,
                revision=1,
            )
            session.add(employee)
            session.flush()
            session.add_all(
                [
                    EmployeeSkill(
                        org_id=employee.org_id, employee_id=employee.id, skill_id=k.skill_id, level=k.level
                    )
                    for k in body.skills
                ]
            )
            session.flush()
            view = _employee_view(session, employee)
            _audit(session, caller, "EMPLOYEE_CREATED", "employee", employee.id, None, view)
            return view

        return s.Employee.model_validate(idempotent(session, caller, key, "createEmployee", body, produce))


def update_employee(caller: Caller, employee_id: uuid.UUID, body: s.EmployeeUpdate) -> s.Employee:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:
        employee = _load_employee(session, caller, employee_id, for_update=True)
        if body.base_revision != employee.revision:
            raise ApiError(
                "stale_version",
                "This employee was changed by someone else. Reload and try again.",
                current_revision=employee.revision,
            )
        before = _employee_view(session, employee)
        changes = body.model_dump(exclude_unset=True, exclude={"base_revision"})
        if "home_outlet_id" in changes:
            _outlet(session, caller, body.home_outlet_id)  # type: ignore[arg-type]
            employee.outlet_id = changes.pop("home_outlet_id")
        if "skills" in changes:
            skills = body.skills or []
            _check_skills(session, skills)
            changes.pop("skills")
            session.execute(delete(EmployeeSkill).where(EmployeeSkill.employee_id == employee.id))
            session.add_all(
                [
                    EmployeeSkill(
                        org_id=employee.org_id, employee_id=employee.id, skill_id=k.skill_id, level=k.level
                    )
                    for k in skills
                ]
            )
        if "hourly_rate" in changes:
            employee.hourly_rate = Decimal(body.hourly_rate.amount_paise) / 100  # type: ignore[union-attr]
            changes.pop("hourly_rate")
        for field, value in changes.items():
            setattr(employee, field, value)
        _check_caps(employee.regular_weekly_minutes, employee.max_weekly_minutes)
        employee.revision += 1
        session.flush()
        after = _employee_view(session, employee)
        _audit(session, caller, "EMPLOYEE_UPDATED", "employee", employee.id, before, after)
        return after


# ---------------------------------------------------------------- availability


def _availability_view(session: Session, employee: Employee) -> s.Availability:
    rows = session.scalars(
        select(EmployeeAvailability)
        .where(EmployeeAvailability.employee_id == employee.id, EmployeeAvailability.valid_to.is_(None))
        .order_by(EmployeeAvailability.weekday, EmployeeAvailability.start_minute, EmployeeAvailability.kind)
    )
    windows = [
        s.AvailabilityWindow(
            weekday=w.weekday,
            start_minute=w.start_minute,
            end_minute=w.end_minute,
            kind=w.kind,  # type: ignore[arg-type]  # DB check constraint guarantees the Literal
        )
        for w in rows
    ]
    return s.Availability(employee_id=employee.id, windows=windows, revision=employee.availability_revision)


def get_availability(caller: Caller, employee_id: uuid.UUID) -> s.Availability:
    with tenant_session(caller) as session:
        return _availability_view(session, _load_employee(session, caller, employee_id))


def put_availability(caller: Caller, employee_id: uuid.UUID, body: s.AvailabilityUpdate) -> s.Availability:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:
        employee = _load_employee(session, caller, employee_id, for_update=True)
        if body.base_revision != employee.availability_revision:
            raise ApiError(
                "stale_version",
                "Availability was changed by someone else. Reload and try again.",
                current_revision=employee.availability_revision,
            )
        before = _availability_view(session, employee)
        session.execute(delete(EmployeeAvailability).where(EmployeeAvailability.employee_id == employee.id))
        today = datetime.now(UTC).date()
        session.add_all(
            [
                EmployeeAvailability(
                    id=uuid.uuid7(),
                    org_id=employee.org_id,
                    employee_id=employee.id,
                    weekday=w.weekday,
                    start_minute=w.start_minute,
                    end_minute=w.end_minute,
                    kind=w.kind,
                    valid_from=today,
                    valid_to=None,
                )
                for w in body.windows
            ]
        )
        employee.availability_revision += 1
        session.flush()
        after = _availability_view(session, employee)
        _audit(session, caller, "AVAILABILITY_REPLACED", "employee", employee.id, before, after)
        return after


# ---------------------------------------------------------------- staffing requirements


def demand_revision(
    session: Session, outlet: Outlet, week_start: date, rows: list[StaffingRequirement] | None = None
) -> int:
    """The outlet-week demand_revision (v3 section 18); weeks never written fall back to their rows."""
    week = session.get(DemandWeek, (outlet.id, week_start))
    if week is not None:
        return week.demand_revision
    return max((r.demand_revision for r in rows or []), default=1)


def bump_demand(session: Session, outlet: Outlet, week_start: date, current: int) -> int:
    revision = current + 1
    session.execute(
        pg_insert(DemandWeek)
        .values(org_id=outlet.org_id, outlet_id=outlet.id, week_start=week_start, demand_revision=revision)
        .on_conflict_do_update(index_elements=["outlet_id", "week_start"], set_={"demand_revision": revision})
    )
    return revision


def _staffing_view(session: Session, outlet: Outlet, week_start: date) -> s.StaffingRequirements:
    start, end = week_bounds(outlet, week_start)
    rows = list(
        session.scalars(
            select(StaffingRequirement)
            .where(
                StaffingRequirement.outlet_id == outlet.id,
                StaffingRequirement.interval_start >= start,
                StaffingRequirement.interval_start < end,
            )
            .order_by(StaffingRequirement.interval_start, StaffingRequirement.skill_id)
        )
    )
    revision = demand_revision(session, outlet, week_start, rows)
    local = ZoneInfo(outlet.timezone)  # instants are returned in the outlet's own offset
    return s.StaffingRequirements(
        outlet_id=outlet.id,
        week_start=week_start,
        interval_minutes=INTERVAL_MINUTES,
        demand_revision=revision,
        intervals=[
            s.StaffingInterval(
                skill_id=r.skill_id,
                interval_start=r.interval_start.astimezone(local),
                interval_end=r.interval_end.astimezone(local),
                minimum_required=r.minimum_required,
                preferred_required=r.preferred_required,
                source=r.source,  # type: ignore[arg-type]  # DB check constraint guarantees the Literal
            )
            for r in rows
        ],
    )


def get_staffing(caller: Caller, outlet_id: uuid.UUID, week_start: date) -> s.StaffingRequirements:
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "Staff cannot view staffing requirements.")
    with tenant_session(caller) as session:
        return _staffing_view(session, _outlet(session, caller, outlet_id), week_start)


def put_staffing(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, body: s.StaffingRequirementsUpdate
) -> s.StaffingRequirements:
    require(caller, "edit_demand")
    with tenant_session(caller) as session:
        outlet = _outlet(session, caller, outlet_id)
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"staffing:{outlet.id}:{week_start}"},
        )
        current = _staffing_view(session, outlet, week_start)
        if body.base_demand_revision != current.demand_revision:
            raise ApiError(
                "stale_version",
                "Staffing needs were changed by someone else. Reload and try again.",
                current_demand_revision=current.demand_revision,
            )
        start, end = week_bounds(outlet, week_start)
        _check_skills(
            session, [s.EmployeeSkill(skill_id=k, level=1) for k in {i.skill_id for i in body.intervals}]
        )
        if not body.intervals:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[{"path": ["intervals"], "message": "Send at least one interval for the week."}],
            )
        problems, seen = [], set()
        for n, interval in enumerate(body.intervals):
            local = interval.interval_start.astimezone(ZoneInfo(outlet.timezone))
            if not (start <= interval.interval_start < end):
                problems.append({"path": ["intervals", n, "interval_start"], "message": "Outside this week."})
            elif (
                (local.minute % INTERVAL_MINUTES)
                or local.second
                or interval.interval_end - interval.interval_start != timedelta(minutes=INTERVAL_MINUTES)
            ):
                problems.append(
                    {"path": ["intervals", n], "message": "Intervals must be 30-minute grid slots."}
                )
            elif (interval.skill_id, interval.interval_start) in seen:
                problems.append({"path": ["intervals", n], "message": "Duplicate skill and interval."})
            seen.add((interval.skill_id, interval.interval_start))
        if problems:
            raise ApiError("validation_failed", "Some fields need attention.", fields=problems)
        session.execute(
            delete(StaffingRequirement).where(
                StaffingRequirement.outlet_id == outlet.id,
                StaffingRequirement.interval_start >= start,
                StaffingRequirement.interval_start < end,
            )
        )
        revision = bump_demand(session, outlet, week_start, current.demand_revision)
        session.add_all(
            [
                StaffingRequirement(
                    id=uuid.uuid7(),
                    org_id=outlet.org_id,
                    outlet_id=outlet.id,
                    skill_id=i.skill_id,
                    interval_start=i.interval_start,
                    interval_end=i.interval_end,
                    minimum_required=i.minimum_required,
                    preferred_required=i.preferred_required,
                    source=i.source,
                    demand_revision=revision,
                )
                for i in body.intervals
            ]
        )
        session.flush()
        after = _staffing_view(session, outlet, week_start)
        _audit(session, caller, "STAFFING_REPLACED", "outlet", outlet.id, None, None)
        return after
