"""Load a validation/optimization Snapshot for one outlet-week from the database.

Runs inside the caller's tenant session (RLS applies). Used by the schedule reads now and by the
generation enqueue (B2.3), which must read it in one REPEATABLE READ transaction.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Employee as EmployeeRow
from db.models import Outlet as OutletRow
from db.models_v2 import (
    Absence as AbsenceRow,
)
from db.models_v2 import (
    EmployeeAvailability,
    EmployeeSkill,
    Schedule,
    SchedulingPolicy,
    SchedulingRule,
    ShiftTemplate,
    Skill,
    StaffingRequirement,
    TravelTime,
    VersionShift,
)
from scheduling import rules
from scheduling.model import Absence, Employee, Outlet, Policy, Requirement, Shift, Snapshot, Template, Window

MARGIN = timedelta(days=1)  # adjacent-week commitments that can affect rest and overlap


def to_shift(row: VersionShift) -> Shift:
    return Shift(
        logical_id=row.logical_shift_id,
        outlet_id=row.outlet_id,
        employee_id=row.employee_id,
        skill_id=row.skill_id,
        start_at=row.start_at,
        end_at=row.end_at,
        break_minutes=row.break_minutes,
        break_start_at=row.break_start_at,
        locked=row.locked,
    )


def outlet_model(row: OutletRow) -> Outlet:
    hours = {
        int(d): tuple((int(a), int(b)) for a, b in spans) for d, spans in (row.operating_hours or {}).items()
    }
    return Outlet(row.id, row.name, row.timezone, hours)


def live_shifts(
    session: Session,
    start: datetime,
    end: datetime,
    exclude_schedule: uuid.UUID | None = None,
    employee_ids: Iterable[uuid.UUID] | None = None,
) -> list[VersionShift]:
    """Shifts of every schedule's current published version overlapping [start, end)."""
    query = (
        select(VersionShift)
        .join(Schedule, Schedule.current_version_id == VersionShift.version_id)
        .where(VersionShift.start_at < end, VersionShift.end_at > start)
    )
    if exclude_schedule is not None:
        query = query.where(Schedule.id != exclude_schedule)
    if employee_ids is not None:
        query = query.where(VersionShift.employee_id.in_(list(employee_ids)))
    return list(session.scalars(query))


def load(
    session: Session,
    outlet_id: uuid.UUID,
    week_start: date,
    roster: list[Shift],
    schedule_id: uuid.UUID | None,
    pool_outlet_ids: Iterable[uuid.UUID] = (),
) -> Snapshot:
    """Everything one outlet-week needs. The employee pool is the outlet's staff, anyone on the roster,
    and the staff of pool_outlet_ids (owner-authorized cross-outlet repair). Absences and commitments
    elsewhere are loaded for the whole pool, not only for people already on the roster."""
    outlets = {o.id: outlet_model(o) for o in session.scalars(select(OutletRow))}
    outlet = outlets[outlet_id]
    start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=outlet.tz)
    end = start + timedelta(days=7)

    pool_outlets = {outlet_id, *pool_outlet_ids}
    home_ids = set(session.scalars(select(EmployeeRow.id).where(EmployeeRow.outlet_id.in_(pool_outlets))))
    roster_ids = {sh.employee_id for sh in roster if sh.employee_id is not None}
    ids = home_ids | roster_ids
    rows = list(session.scalars(select(EmployeeRow).where(EmployeeRow.id.in_(ids)))) if ids else []
    skills: dict[uuid.UUID, set[uuid.UUID]] = {r.id: set() for r in rows}
    for es in session.scalars(select(EmployeeSkill).where(EmployeeSkill.employee_id.in_(ids))):
        skills[es.employee_id].add(es.skill_id)
    windows: dict[uuid.UUID, list[Window]] = {r.id: [] for r in rows}
    for w in session.scalars(
        select(EmployeeAvailability).where(
            EmployeeAvailability.employee_id.in_(ids), EmployeeAvailability.valid_to.is_(None)
        )
    ):
        windows[w.employee_id].append(Window(w.weekday, w.start_minute, w.end_minute, w.kind))
    employees = {
        r.id: Employee(
            id=r.id,
            name=r.name,
            home_outlet_id=r.outlet_id,
            status=r.status,
            skill_ids=frozenset(skills[r.id]),
            rate_paise_per_hour=int((Decimal(r.hourly_rate) * 100).to_integral_value()),
            regular_weekly_minutes=r.regular_weekly_minutes,
            preferred_weekly_minutes=r.preferred_weekly_minutes,
            max_weekly_minutes=r.max_weekly_minutes,
            overtime_allowed=r.overtime_allowed,
            windows=tuple(windows[r.id]),
            tags=frozenset(r.tags or ()),
        )
        for r in rows
    }

    policy_row = session.scalars(
        select(SchedulingPolicy)
        .where(SchedulingPolicy.outlet_id.is_(None))
        .order_by(SchedulingPolicy.revision.desc())
    ).first()
    policy = (
        Policy(policy_row.min_rest_minutes, policy_row.grid_minutes, policy_row.ot_multiplier_bp)
        if policy_row
        else Policy()
    )
    requirements = tuple(
        Requirement(
            r.outlet_id,
            r.skill_id,
            r.interval_start,
            r.interval_end,
            r.minimum_required,
            r.preferred_required,
        )
        for r in session.scalars(
            select(StaffingRequirement).where(
                StaffingRequirement.outlet_id == outlet_id,
                StaffingRequirement.interval_start >= start,
                StaffingRequirement.interval_start < end,
            )
        )
    )
    absences = tuple(
        Absence(a.employee_id, a.start_at, a.end_at, a.status)
        for a in session.scalars(
            select(AbsenceRow).where(
                AbsenceRow.employee_id.in_(ids or {uuid.UUID(int=0)}),
                AbsenceRow.start_at < end + MARGIN,
                AbsenceRow.end_at > start - MARGIN,
                AbsenceRow.status.in_(("requested", "confirmed")),
            )
        )
    )
    travel = {(t.from_outlet_id, t.to_outlet_id): t.minutes for t in session.scalars(select(TravelTime))}
    commitments = tuple(
        to_shift(r) for r in live_shifts(session, start - MARGIN, end + MARGIN, schedule_id, ids)
    )
    templates = tuple(
        Template(
            t.id, t.start_minute, t.duration_minutes, t.break_minutes, t.break_offset_minutes, t.skill_id
        )
        for t in session.scalars(
            select(ShiftTemplate)
            .where(ShiftTemplate.outlet_id == outlet_id, ShiftTemplate.active)
            .order_by(ShiftTemplate.start_minute, ShiftTemplate.duration_minutes)
        )
    )
    return Snapshot(
        outlet_id=outlet_id,
        week_start=week_start,
        policy=policy,
        outlets=outlets,
        employees=employees,
        skill_names={k.id: k.name for k in session.scalars(select(Skill))},
        requirements=requirements,
        absences=absences,
        travel_minutes=travel,
        commitments=commitments,
        templates=templates,
        rules=effective_rules(session, employees.values()),
    )


def active_rules(session: Session) -> list[rules.Rule]:
    return [
        rules.Rule(
            r.id,
            r.rule_type,
            r.scope_level,
            r.scope,
            r.parameters,
            r.hard,
            r.overrides_rule_id,
            r.source_text or "",
        )
        for r in session.scalars(select(SchedulingRule).where(SchedulingRule.status == "active"))
    ]


def effective_rules(
    session: Session, employees: Iterable[Employee]
) -> dict[uuid.UUID, tuple[rules.Rule, ...]]:
    """Each employee's active rules after precedence (architecture v3 section 21)."""
    active = active_rules(session)
    if not active:
        return {}
    out = {}
    for e in employees:
        mine = rules.effective(active, rules.Person(e.id, e.name, e.home_outlet_id, e.tags))
        if mine:
            out[e.id] = tuple(mine)
    return out


def with_base_locks(snap: Snapshot, locked: list[Shift], base: list[Shift] | None = None) -> Snapshot:
    """The same snapshot with the base version's locked shifts fixed for the solver and validator, and
    its other shifts available for the disruption term."""
    return replace(
        snap,
        base_locked={sh.logical_id: sh for sh in locked},
        base=tuple(sh for sh in (base or []) if not sh.locked),
    )
