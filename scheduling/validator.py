"""Independent roster validator (B2.1).

Judges any roster (manual edit, solver candidate, restore) against a Snapshot. It is written
separately from the CP-SAT model on purpose: both must not pass by sharing one mistake. Pure
functions, no database, no solver.

Rule decisions implemented here (docs/SCHEDULING_V2_ROADMAP.md):
- Minimum staffing is hard; preferred staffing is soft (decision 1).
- Regular threshold, overtime permission and the absolute weekly cap are separate; permission
  never lifts the cap (decision 2).
- Between workdays the rest rule applies; within one workday (split shifts) the travel time
  between outlets applies instead (decision 4). Commitments outside the roster count.
- Locked shifts of the base version must survive unchanged (decision 5); a confirmed absence
  still makes a locked shift invalid, and that is reported, never silently fixed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from scheduling import rules
from scheduling.model import Employee, Outlet, Shift, Snapshot, Window

HARD, SOFT = "hard", "soft"


@dataclass(frozen=True)
class Violation:
    code: str
    severity: str
    message: str
    employee_id: UUID | None = None
    logical_shift_ids: tuple[UUID, ...] = ()
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Result:
    violations: tuple[Violation, ...]

    @property
    def hard(self) -> int:
        return sum(v.severity == HARD for v in self.violations)

    @property
    def soft(self) -> int:
        return sum(v.severity == SOFT for v in self.violations)

    @property
    def valid(self) -> bool:
        return self.hard == 0


def _local(dt: datetime, outlet: Outlet) -> datetime:
    return dt.astimezone(outlet.tz)


def _span(shift: Shift, outlet: Outlet) -> tuple[date, int, int]:
    """(local workday, start minute, end minute) where end may exceed 1440."""
    start = _local(shift.start_at, outlet)
    minutes = int((shift.end_at - shift.start_at).total_seconds() // 60)
    s = start.hour * 60 + start.minute
    return start.date(), s, s + minutes


def _hhmm(minute: int) -> str:
    return f"{(minute // 60) % 24:02d}:{minute % 60:02d}"


def _day(d: date) -> str:
    return d.strftime("%a %d %b")


def _per_shift(snap: Snapshot, shift: Shift) -> Iterable[Violation]:
    if shift.employee_id is None:
        return
    emp = snap.employees.get(shift.employee_id)
    outlet = snap.outlets[shift.outlet_id]
    ids = (shift.logical_id,)
    if emp is None:
        yield Violation(
            "inactive_employee",
            HARD,
            "The assigned employee does not exist in this organization.",
            shift.employee_id,
            ids,
        )
        return
    who = emp.name
    if emp.status != "active":
        yield Violation(
            "inactive_employee", HARD, f"{who} is not active.", emp.id, ids, {"status": emp.status}
        )
    if shift.skill_id not in emp.skill_ids:
        skill = snap.skill_names.get(shift.skill_id, "this role")
        yield Violation(
            "missing_skill",
            HARD,
            f"{who} is not qualified for {skill}.",
            emp.id,
            ids,
            {"skill_id": str(shift.skill_id)},
        )
    day, s, e = _span(shift, outlet)
    when = f"{_day(day)} {_hhmm(s)}-{_hhmm(e)}"
    if not _available(emp, day.weekday(), s, e):
        yield Violation(
            "unavailable",
            HARD,
            f"{who} is not available {when}.",
            emp.id,
            ids,
            {"weekday": day.weekday(), "start_minute": s, "end_minute": e},
        )
    broken = rules.end_allowed(snap.rules.get(emp.id, ()), shift.start_at, shift.end_at, outlet.tz)
    if broken is not None:
        yield Violation(
            "rule",
            HARD,
            f"{who}: {broken.name or rules.describe(broken)} ({when}).",
            emp.id,
            ids,
            {"rule_id": str(broken.id), "rule_type": broken.rule_type, **broken.parameters},
        )
    for absence in snap.absences:
        if (
            absence.employee_id == emp.id
            and absence.status == "confirmed"
            and absence.start_at < shift.end_at
            and shift.start_at < absence.end_at
        ):
            yield Violation(
                "absent",
                HARD,
                f"{who} has a confirmed absence during {when}.",
                emp.id,
                ids,
                {
                    "absence_start": absence.start_at.isoformat(),
                    "absence_end": absence.end_at.isoformat(),
                    "locked": shift.locked,
                    **({"absence_id": str(absence.id)} if absence.id else {}),
                },
            )
    grid = snap.policy.grid_minutes
    if s % grid or e % grid:
        yield Violation(
            "outside_grid",
            HARD,
            f"Shift times must fall on the {grid}-minute grid ({when}).",
            emp.id,
            ids,
            {"grid_minutes": grid},
        )
    hours = outlet.operating_hours.get(day.weekday())
    if hours is not None and not any(open_ <= s and e <= close for open_, close in hours):
        yield Violation(
            "outside_operating_hours",
            HARD,
            f"{when} is outside {outlet.name}'s opening hours.",
            emp.id,
            ids,
            {"weekday": day.weekday()},
        )


def _available(emp: Employee, weekday: int, s: int, e: int) -> bool:
    return available_in(emp.windows, weekday, s, e)


def available_in(all_windows: Iterable[Window], weekday: int, s: int, e: int) -> bool:
    """Inside an available or preferred window and touching no unavailable one (outlet-local minutes)."""
    all_windows = tuple(all_windows)
    windows = [w for w in all_windows if w.weekday == weekday]
    inside = any(
        w.kind in ("available", "preferred") and w.start_minute <= s and e <= w.end_minute for w in windows
    )
    blocked = any(w.kind == "unavailable" and w.start_minute < e and s < w.end_minute for w in windows)
    # An unavailable window on the next day can be hit by a shift running past midnight.
    if e > 1440:
        nxt = [w for w in all_windows if w.weekday == (weekday + 1) % 7 and w.kind == "unavailable"]
        blocked = blocked or any(w.start_minute < e - 1440 for w in nxt)
    return inside and not blocked


def _per_employee(snap: Snapshot, roster: list[Shift]) -> Iterable[Violation]:
    in_roster = {id(s) for s in roster}
    by_employee: dict[UUID, list[Shift]] = defaultdict(list)
    for sh in [*roster, *snap.commitments]:
        if sh.employee_id is not None:
            by_employee[sh.employee_id].append(sh)
    week_start, week_end = snap.week_bounds()
    for emp_id, shifts in by_employee.items():
        if not any(id(s) in in_roster for s in shifts):
            continue
        emp = snap.employees.get(emp_id)
        name = emp.name if emp else "This employee"
        shifts.sort(key=lambda sh: sh.start_at)
        for a, b in zip(shifts, shifts[1:], strict=False):
            if id(a) not in in_roster and id(b) not in in_roster:
                continue
            ids = (a.logical_id, b.logical_id)
            gap = int((b.start_at - a.end_at).total_seconds() // 60)
            if gap < 0:
                yield Violation(
                    "overlap", HARD, f"{name} has overlapping shifts.", emp_id, ids, {"overlap_minutes": -gap}
                )
                continue
            out_a = snap.outlets[a.outlet_id]
            same_workday = _local(a.start_at, out_a).date() == _local(b.start_at, out_a).date()
            if same_workday:
                need = (
                    0
                    if a.outlet_id == b.outlet_id
                    else snap.travel_minutes.get((a.outlet_id, b.outlet_id), 0)
                )
                if gap < need:
                    yield Violation(
                        "travel_time",
                        HARD,
                        f"{name} needs {need} minutes to travel from {out_a.name} to "
                        f"{snap.outlets[b.outlet_id].name}; the shifts are {gap} minutes apart.",
                        emp_id,
                        ids,
                        {"travel_minutes": need, "gap_minutes": gap},
                    )
            elif gap < snap.policy.min_rest_minutes:
                yield Violation(
                    "insufficient_rest",
                    HARD,
                    f"{name} gets {gap // 60}h{gap % 60:02d}m rest between shifts; "
                    f"{snap.policy.min_rest_minutes // 60}h is required.",
                    emp_id,
                    ids,
                    {"rest_minutes": gap, "required_rest_minutes": snap.policy.min_rest_minutes},
                )
        if emp is None:
            continue
        week = [sh for sh in shifts if week_start <= sh.start_at < week_end]
        cap = rules.max_days(snap.rules.get(emp_id, ()))
        if cap is not None:
            days = {sh.start_at.astimezone(snap.outlet.tz).date() for sh in week}
            if len(days) > cap.parameters["days"]:
                yield Violation(
                    "rule",
                    HARD,
                    f"{name} would work {len(days)} days this week: {cap.name or rules.describe(cap)}.",
                    emp_id,
                    tuple(sh.logical_id for sh in week if id(sh) in in_roster),
                    {"rule_id": str(cap.id), "rule_type": cap.rule_type, "days": len(days), **cap.parameters},
                )
        total = sum(sh.paid_minutes for sh in week)
        week_ids = tuple(sh.logical_id for sh in week if id(sh) in in_roster)
        facts = {
            "weekly_minutes": total,
            "regular_weekly_minutes": emp.regular_weekly_minutes,
            "max_weekly_minutes": emp.max_weekly_minutes,
        }
        if total > emp.max_weekly_minutes:
            yield Violation(
                "weekly_cap",
                HARD,
                f"{name} would work {total / 60:g}h this week; the limit is "
                f"{emp.max_weekly_minutes / 60:g}h.",
                emp.id,
                week_ids,
                facts,
            )
        elif total > emp.regular_weekly_minutes:
            severity = SOFT if emp.overtime_allowed else HARD
            yield Violation(
                "overtime",
                severity,
                f"{name} would work {(total - emp.regular_weekly_minutes) / 60:g}h overtime"
                + ("." if emp.overtime_allowed else " without overtime permission."),
                emp.id,
                week_ids,
                facts,
            )


def _coverage(snap: Snapshot, roster: list[Shift]) -> Iterable[Violation]:
    outlet = snap.outlet
    deficits: dict[tuple[date, UUID], list[int]] = defaultdict(lambda: [0, 0])
    for req in snap.requirements:
        if req.outlet_id != snap.outlet_id:
            continue
        on = scheduled(roster, req.skill_id, req.outlet_id, req.interval_start)
        minutes = int((req.interval_end - req.interval_start).total_seconds() // 60)
        key = (_local(req.interval_start, outlet).date(), req.skill_id)
        deficits[key][0] += max(0, req.minimum - on) * minutes
        deficits[key][1] += max(0, req.preferred - on) * minutes
    for (day, skill_id), (minimum, preferred) in sorted(
        deficits.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))
    ):
        skill = snap.skill_names.get(skill_id, "This role")
        if minimum:
            yield Violation(
                "minimum_coverage",
                HARD,
                f"{skill} is below minimum staffing for {minimum} staff-minutes on {_day(day)}.",
                facts={"date": day.isoformat(), "skill_id": str(skill_id), "deficit_minutes": minimum},
            )
        if preferred:
            yield Violation(
                "preferred_coverage",
                SOFT,
                f"{skill} is below preferred staffing for {preferred} staff-minutes on {_day(day)}.",
                facts={"date": day.isoformat(), "skill_id": str(skill_id), "deficit_minutes": preferred},
            )


def scheduled(roster: Iterable[Shift], skill_id: UUID, outlet_id: UUID, instant: datetime) -> int:
    """Staff productively on shift at `instant` (assigned, matching skill and outlet, not on break)."""
    return sum(
        1
        for sh in roster
        if sh.employee_id is not None
        and sh.skill_id == skill_id
        and sh.outlet_id == outlet_id
        and sh.start_at <= instant < sh.end_at
        and not sh.on_break(instant)
    )


def _locks(snap: Snapshot, roster: list[Shift]) -> Iterable[Violation]:
    current = {sh.logical_id: sh for sh in roster}
    for logical_id, base in snap.base_locked.items():
        now = current.get(logical_id)
        same = now is not None and (
            now.employee_id,
            now.skill_id,
            now.outlet_id,
            now.start_at,
            now.end_at,
        ) == (base.employee_id, base.skill_id, base.outlet_id, base.start_at, base.end_at)
        if not same:
            yield Violation(
                "locked_changed",
                HARD,
                "A locked shift was changed or removed.",
                base.employee_id,
                (logical_id,),
                {"removed": now is None},
            )


def validate(snap: Snapshot, roster: Iterable[Shift]) -> Result:
    shifts = list(roster)
    found: list[Violation] = []
    for sh in shifts:
        found.extend(_per_shift(snap, sh))
    found.extend(_per_employee(snap, shifts))
    found.extend(_locks(snap, shifts))
    found.extend(_coverage(snap, shifts))
    return Result(tuple(found))


def as_contract(result: Result) -> dict[str, Any]:
    """The contract's ValidationResult shape (api.v2.schemas.ValidationResult)."""
    return {
        "hard_violations": result.hard,
        "soft_violations": result.soft,
        "violations": [
            {
                "code": v.code,
                "severity": v.severity,
                "message": v.message,
                "employee_id": str(v.employee_id) if v.employee_id else None,
                "logical_shift_ids": [str(i) for i in v.logical_shift_ids],
                "facts": v.facts,
            }
            for v in result.violations
        ],
    }
