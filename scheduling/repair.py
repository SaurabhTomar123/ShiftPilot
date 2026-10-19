"""Absence repair (B4.2/B4.3): minimal-disruption re-optimization of a published roster. Pure.

Scope: local first, then widen (architecture v3 section 12). Each stage frees more of the published
roster, and the first stage that keeps minimum staffing wins; every stage tried is recorded:
  1. same_day         this outlet, the affected days from the absence onward, home staff, no overtime
  2. adjacent_shifts  the affected days and the day either side
  3. other_outlets    staff from other outlets too (only when the owner authorized it)
  4. overtime         overtime up to each employee's cap where their contract allows it
Shifts outside the stage's scope are fixed and count as commitments for rest, overlap, travel and weekly
limits. Shifts of the absent employee during the absence must be reassigned or left open. Locked shifts
stay exactly as they are unless the manager authorized unlocking them (decision 5). A no-overtime stage
never forbids hours the published roster already gave someone.

Staged objective (decision 6), each stage bounded and recorded:
  1. hard-minimum shortfall (soft here, so a repair always returns its best effort and reports gaps)
  2. disruption: changed base shifts + added shifts + 2 x cross-outlet assignments
  3. cost and preferred shortfall
Profiles differ only within guardrails: same minimum shortfall, disruption at most +2 over the best.
Every plan is re-checked by the independent validator against the absence.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any

from ortools.sat.python import cp_model

from scheduling import validator
from scheduling.model import Absence, Employee, Shift, Snapshot
from scheduling.solver import STATUS, Slot, _conflict, eligible, slots

PROFILES = ("least_disruption", "lowest_cost", "best_coverage")
STAGES = ("same_day", "adjacent_shifts", "other_outlets", "overtime")


@dataclass(frozen=True)
class Scope:
    """One widening stage: which base shifts may change, who may take them, and whether overtime may."""

    name: str
    free_days: frozenset[date]
    from_instant: datetime | None  # same_day: only shifts still running after the absence starts
    cross_outlet: bool
    overtime: bool
    forced: frozenset[uuid.UUID] = frozenset()  # broken shifts: always free, never kept as they are


# Per-shift facts that make a published shift unworkable now (not coverage or weekly totals).
BROKEN_CODES = frozenset({"absent", "unavailable", "missing_skill"})


def broken_shifts(snap: Snapshot, base: list[Shift], unlocked: set[uuid.UUID]) -> list[Shift]:
    """Published shifts that current facts already break, such as an earlier absence nobody has repaired
    yet. A repair takes them on too, so every candidate it offers is valid and publishable as a whole.
    Locked ones need the same explicit authorization as a locked affected shift (decision 5)."""
    ids = {
        lid
        for v in validator.validate(replace(snap, requirements=()), base).violations
        if v.severity == "hard" and v.code in BROKEN_CODES
        for lid in v.logical_shift_ids
    }
    return [s for s in base if s.logical_id in ids]


def scopes(
    snap: Snapshot,
    base: list[Shift],
    absence: Absence,
    allow_cross_outlet: bool,
    broken: list[Shift] | None = None,
) -> list[Scope]:
    must = [*affected_shifts(base, absence), *(broken or [])]
    days = frozenset(_days(snap, must))
    wide = frozenset(d + timedelta(days=k) for d in days for k in (-1, 0, 1))
    forced = frozenset(s.logical_id for s in must)
    return [
        Scope("same_day", days, absence.start_at, False, False, forced),
        Scope("adjacent_shifts", wide, None, False, False, forced),
        Scope("other_outlets", wide, None, True, False, forced),
        Scope("overtime", wide, None, allow_cross_outlet, True, forced),
    ]


DISRUPTION_SLACK = {"least_disruption": 0, "lowest_cost": 2, "best_coverage": 2}
SHORTFALL_WEIGHT = {"least_disruption": 300, "lowest_cost": 50, "best_coverage": 5000}


@dataclass(frozen=True)
class Reason:
    code: str
    ok: bool
    message: str
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Alternative:
    employee_id: uuid.UUID
    name: str
    status: str  # "rejected" (a rule blocks it) | "eligible_not_selected"
    reasons: tuple[Reason, ...]


@dataclass(frozen=True)
class Explanation:
    logical_id: uuid.UUID
    chosen_employee_id: uuid.UUID | None
    chosen: tuple[Reason, ...]
    alternatives: tuple[Alternative, ...]


@dataclass(frozen=True)
class Plan:
    profile: str
    status: str
    roster: tuple[Shift, ...]
    disruption: dict[str, int]
    stages: dict[str, dict[str, Any]]
    explanations: tuple[Explanation, ...]


@dataclass
class RepairOutcome:
    status: str
    plans: list[Plan] = field(default_factory=list)
    affected: list[Shift] = field(default_factory=list)
    widening: list[dict[str, Any]] = field(default_factory=list)
    locked_conflicts: list[Shift] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def affected_shifts(base: list[Shift], absence: Absence) -> list[Shift]:
    return [
        s
        for s in base
        if s.employee_id == absence.employee_id
        and s.start_at < absence.end_at
        and absence.start_at < s.end_at
    ]


def _days(snap: Snapshot, shifts: list[Shift]) -> set[date]:
    tz = snap.outlet.tz
    return {s.start_at.astimezone(tz).date() for s in shifts}


def _sum(terms: list[Any]) -> Any:
    return cp_model.LinearExpr.sum(terms) if terms else 0


def _scope_sets(
    snap: Snapshot, base: list[Shift], absence: Absence, unlocked: set[uuid.UUID], scope: Scope
) -> tuple[list[Shift], dict[uuid.UUID, Employee]]:
    """(base shifts free to change, employees who may take them) for one stage."""
    tz = snap.outlet.tz
    affected = {s.logical_id for s in affected_shifts(base, absence)} | scope.forced
    free = [
        s
        for s in base
        if s.start_at.astimezone(tz).date() in scope.free_days
        and (not s.locked or s.logical_id in unlocked)
        and (scope.from_instant is None or s.end_at > scope.from_instant or s.logical_id in affected)
    ]
    rostered = {s.employee_id for s in base}
    pool = {
        e.id: e
        for e in snap.employees.values()
        if e.id != absence.employee_id
        and (scope.cross_outlet or e.home_outlet_id == snap.outlet_id or e.id in rostered)
    }
    return free, pool


def _solve_profile(
    snap: Snapshot,
    base: list[Shift],
    absence: Absence,
    unlocked: set[uuid.UUID],
    profile: str,
    *,
    scope: Scope,
    time_limit: float,
    workers: int,
    best_minimum: int | None,
    best_disruption: int | None,
) -> tuple[str, Plan | None, dict[str, Any]]:
    # Added shifts only on the days where something must change (the absence and broken shifts).
    days = _days(snap, [s for s in base if s.logical_id in scope.forced] or affected_shifts(base, absence))
    tz = snap.outlet.tz
    free, pool = _scope_sets(snap, base, absence, unlocked, scope)
    fixed = [s for s in base if s not in free]
    new_slots = [c for c in slots(snap) if c.day in days]

    model = cp_model.CpModel()
    keep: dict[uuid.UUID, cp_model.IntVar] = {}
    y: dict[tuple[uuid.UUID, uuid.UUID], cp_model.IntVar] = {}  # (logical, employee) for free base shifts
    x: dict[tuple[uuid.UUID, int], cp_model.IntVar] = {}  # (employee, slot index) for added shifts

    def as_slot(s: Shift) -> Slot:
        return Slot(
            s.start_at.astimezone(tz).date(),
            uuid.UUID(int=0),
            s.skill_id,
            s.start_at,
            s.end_at,
            s.break_start_at,
            s.break_minutes,
        )

    for s in free:
        for e in pool.values():
            if eligible(snap, e, as_slot(s)):
                y[s.logical_id, e.id] = model.new_bool_var("")
        model.add(_sum([v for (lid, _), v in y.items() if lid == s.logical_id]) <= 1)
        if s.employee_id in pool and (s.logical_id, s.employee_id) in y:
            keep[s.logical_id] = y[s.logical_id, s.employee_id]
    for i, c in enumerate(new_slots):
        for e in pool.values():
            if eligible(snap, e, c):
                x[e.id, i] = model.new_bool_var("")

    # Per-employee feasibility against fixed shifts, commitments and each other.
    items: dict[uuid.UUID, list[tuple[Any, Any, Any, uuid.UUID]]] = defaultdict(
        list
    )  # (var, start, end, outlet)
    for (lid, emp_id), v in y.items():
        s = next(f for f in free if f.logical_id == lid)
        items[emp_id].append((v, s.start_at, s.end_at, s.outlet_id))
    for (emp_id, i), v in x.items():
        items[emp_id].append((v, new_slots[i].start, new_slots[i].end, snap.outlet_id))
    fixed_by_emp: dict[uuid.UUID, list[Shift]] = defaultdict(list)
    for s in [*fixed, *snap.commitments]:
        if s.employee_id is not None:
            fixed_by_emp[s.employee_id].append(s)
    week_start, week_end = snap.week_bounds()
    cost_terms, cross_terms = [], []
    for e_id, its in items.items():
        emp = pool[e_id]
        its.sort(key=lambda t: t[1])
        for n, (v, a, b, o) in enumerate(its):
            for f in fixed_by_emp[e_id]:
                if _conflict(snap, a, b, o, f.start_at, f.end_at, f.outlet_id):
                    model.add(v == 0)
            for w, c, d, p in its[n + 1 :]:
                if _conflict(snap, a, b, o, c, d, p):
                    model.add(v + w <= 1)
            minutes = int((b - a).total_seconds() // 60)
            cost_terms.append(v * ((minutes * emp.rate_paise_per_hour + 30) // 60))
            if emp.home_outlet_id != snap.outlet_id:
                cross_terms.append(v)
        fixed_minutes = sum(f.paid_minutes for f in fixed_by_emp[e_id] if week_start <= f.start_at < week_end)
        var_minutes = [v * int((b - a).total_seconds() // 60) for v, a, b, _ in its]
        limit = (
            emp.max_weekly_minutes if scope.overtime and emp.overtime_allowed else emp.regular_weekly_minutes
        )
        promised = sum(
            s.paid_minutes
            for s in [*base, *snap.commitments]
            if s.employee_id == e_id and week_start <= s.start_at < week_end
        )
        model.add(_sum(var_minutes) + fixed_minutes <= max(limit, promised, fixed_minutes))

    # Coverage on the affected days.
    min_terms, pref_terms = [], []
    for k, req in enumerate(r for r in snap.requirements if r.outlet_id == snap.outlet_id):
        if req.interval_start.astimezone(tz).date() not in days:
            continue
        t = req.interval_start
        fixed_on = sum(
            1
            for f in fixed
            if f.employee_id
            and f.skill_id == req.skill_id
            and f.start_at <= t < f.end_at
            and not f.on_break(t)
        )
        on = [
            v
            for (lid, _), v in y.items()
            if (s := next(f for f in free if f.logical_id == lid)).skill_id == req.skill_id
            and s.start_at <= t < s.end_at
            and not s.on_break(t)
        ]
        on += [
            v
            for (_, i), v in x.items()
            if new_slots[i].skill_id == req.skill_id and new_slots[i].productive_at(t)
        ]
        minutes = int((req.interval_end - req.interval_start).total_seconds() // 60)
        short_min = model.new_int_var(0, req.minimum, f"m{k}")
        model.add(short_min >= req.minimum - fixed_on - _sum(on))
        min_terms.append(short_min * minutes)
        if req.preferred > req.minimum:
            short_pref = model.new_int_var(0, req.preferred, f"p{k}")
            model.add(short_pref >= req.preferred - fixed_on - _sum(on))
            pref_terms.append(short_pref * minutes)

    changed = [
        1 - keep[s.logical_id] if s.logical_id in keep else 1 for s in free if s.employee_id is not None
    ]
    disruption = _sum([*changed, *x.values(), *[2 * c for c in cross_terms]])
    minimum, preferred, cost = _sum(min_terms), _sum(pref_terms), _sum(cost_terms)

    stats: dict[str, Any] = {
        "free_shifts": len(free),
        "new_slots": len(new_slots),
        "variables": len(y) + len(x),
    }
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = 7
    stages: dict[str, dict[str, Any]] = {}

    def stage(name: str, objective: Any, limit: float) -> str:
        model.minimize(objective)
        solver.parameters.max_time_in_seconds = limit
        status = STATUS[solver.solve(model)]
        stages[name] = {
            "status": status,
            "value": int(solver.objective_value) if status in ("OPTIMAL", "FEASIBLE") else None,
            "proven_optimal": status == "OPTIMAL",
        }
        return status

    third = time_limit / 3
    if best_minimum is None:
        if stage("minimum_shortfall", minimum, third) not in ("OPTIMAL", "FEASIBLE"):
            return stages["minimum_shortfall"]["status"], None, stats
        best_minimum = stages["minimum_shortfall"]["value"]
    model.add(minimum <= best_minimum)
    if best_disruption is None:
        if stage("disruption", disruption, third) not in ("OPTIMAL", "FEASIBLE"):
            return stages["disruption"]["status"], None, stats
        best_disruption = stages["disruption"]["value"]
    model.add(disruption <= best_disruption + DISRUPTION_SLACK[profile])
    final = stage("cost_and_coverage", cost + SHORTFALL_WEIGHT[profile] * preferred + 50 * disruption, third)
    if final not in ("OPTIMAL", "FEASIBLE"):
        return final, None, stats
    stats["best_minimum"], stats["best_disruption"] = best_minimum, best_disruption

    roster: list[Shift] = list(fixed)
    for s in free:
        chosen = next(
            (emp_id for (lid, emp_id), v in y.items() if lid == s.logical_id and solver.value(v)), None
        )
        roster.append(replace(s, employee_id=chosen))
    for (emp_id, i), v in x.items():
        if solver.value(v):
            c = new_slots[i]
            roster.append(
                Shift(
                    uuid.uuid7(),
                    snap.outlet_id,
                    emp_id,
                    c.skill_id,
                    c.start,
                    c.end,
                    c.break_minutes,
                    c.break_start,
                )
            )
    roster.sort(key=lambda s: (s.start_at, str(s.logical_id)))
    base_ids = {s.logical_id: s for s in base}
    changed_n = sum(
        1 for s in roster if s.logical_id in base_ids and s.employee_id != base_ids[s.logical_id].employee_id
    )
    added_n = sum(1 for s in roster if s.logical_id not in base_ids)
    cross_n = sum(
        1
        for s in roster
        if s.employee_id
        and s.employee_id in pool
        and pool[s.employee_id].home_outlet_id != snap.outlet_id
        and (s.logical_id not in base_ids or base_ids[s.logical_id].employee_id != s.employee_id)
    )
    plan = Plan(
        profile,
        final,
        tuple(roster),
        {
            "changed_shifts": changed_n,
            "added_shifts": added_n,
            "cross_outlet_moves": cross_n,
            "open_shifts": sum(1 for s in roster if s.employee_id is None),
        },
        stages,
        (),
    )
    return final, plan, stats


def explain(
    snap: Snapshot,
    base: list[Shift],
    plan_roster: tuple[Shift, ...],
    absence: Absence,
    max_alternatives: int = 4,
) -> tuple[Explanation, ...]:
    """Deterministic facts per changed shift. Alternatives get the concrete rule that blocks them, or
    'eligible_not_selected' -- non-selection alone is never presented as a rejection reason."""
    base_by_id = {s.logical_id: s for s in base}
    out = []
    week_start, week_end = snap.week_bounds()
    for s in plan_roster:
        before = base_by_id.get(s.logical_id)
        if before is not None and before.employee_id == s.employee_id:
            continue
        others = [o for o in plan_roster if o is not s]
        chosen = _facts(snap, s, s.employee_id, others, week_start, week_end) if s.employee_id else ()
        alts = []
        for e in sorted(snap.employees.values(), key=lambda e: e.name):
            if e.id in (s.employee_id, absence.employee_id) or s.skill_id not in e.skill_ids:
                continue
            reasons = _facts(snap, s, e.id, others, week_start, week_end)
            blocked = [r for r in reasons if not r.ok]
            alts.append(
                Alternative(
                    e.id,
                    e.name,
                    "rejected" if blocked else "eligible_not_selected",
                    tuple(blocked) if blocked else tuple(reasons),
                )
            )
        alts.sort(key=lambda a: (a.status != "eligible_not_selected", a.name))
        out.append(Explanation(s.logical_id, s.employee_id, chosen, tuple(alts[:max_alternatives])))
    return tuple(out)


def _facts(
    snap: Snapshot,
    s: Shift,
    employee_id: uuid.UUID | None,
    others: list[Shift],
    week_start: Any,
    week_end: Any,
) -> tuple[Reason, ...]:
    if employee_id is None:
        return ()
    emp: Employee = snap.employees[employee_id]
    trial = replace(s, employee_id=employee_id)
    hard = {
        v.code
        for v in validator.validate(
            replace(snap, requirements=()), [trial, *[o for o in others if o.employee_id == employee_id]]
        ).violations
        if v.severity == "hard"
    }
    week = (
        sum(
            o.paid_minutes
            for o in [*others, *snap.commitments]
            if o.employee_id == employee_id and week_start <= o.start_at < week_end
        )
        + trial.paid_minutes
    )
    travel = (
        snap.travel_minutes.get((emp.home_outlet_id, s.outlet_id), 0)
        if emp.home_outlet_id != s.outlet_id
        else 0
    )
    skill = snap.skill_names.get(s.skill_id, "this role")
    return (
        Reason(
            "skill",
            "missing_skill" not in hard,
            f"{'Qualified' if 'missing_skill' not in hard else 'Not qualified'} for {skill}",
            {"skill_id": str(s.skill_id)},
        ),
        Reason(
            "available",
            not hard & {"unavailable", "absent"},
            "Available for the shift"
            if not hard & {"unavailable", "absent"}
            else "Not available for the shift",
        ),
        Reason(
            "no_conflict",
            not hard & {"overlap", "insufficient_rest", "travel_time"},
            "No overlapping shift and rest rules met"
            if not hard & {"overlap", "insufficient_rest", "travel_time"}
            else "Would break overlap, rest or travel rules",
        ),
        Reason(
            "weekly_hours",
            not hard & {"weekly_cap", "overtime"},
            f"{week / 60:g}h this week after the change",
            {"weekly_minutes": week, "regular_weekly_minutes": emp.regular_weekly_minutes},
        ),
        Reason(
            "travel",
            True,
            f"{travel} minutes from home outlet" if travel else "Works at this outlet",
            {"travel_minutes": travel},
        ),
    )


def _attempt(
    snap: Snapshot,
    base: list[Shift],
    absence: Absence,
    unlocked: set[uuid.UUID],
    scope: Scope,
    *,
    time_limit: float,
    workers: int,
    profiles: tuple[str, ...],
) -> tuple[list[Plan], dict[str, Any], int | None]:
    """All profiles within one stage: (valid distinct plans, stats, best minimum shortfall)."""
    plans: list[Plan] = []
    stats: dict[str, Any] = {}
    best_min = best_dis = None
    seen = set()
    for profile in profiles:
        status, plan, pstats = _solve_profile(
            snap,
            base,
            absence,
            unlocked,
            profile,
            scope=scope,
            time_limit=time_limit / len(profiles),
            workers=workers,
            best_minimum=best_min,
            best_disruption=best_dis,
        )
        stats[profile] = {"status": status, **pstats}
        if plan is None:
            continue
        best_min = pstats.get("best_minimum", best_min)
        best_dis = pstats.get("best_disruption", best_dis)
        key = frozenset((s.logical_id, s.employee_id, s.start_at) for s in plan.roster)
        check = validator.validate(snap, plan.roster)
        hard = {v.code for v in check.violations if v.severity == "hard"} - {"minimum_coverage"}
        if hard:
            stats.setdefault("rejected_by_validator", []).append({"profile": profile, "codes": sorted(hard)})
            continue
        if key in seen:
            continue
        seen.add(key)
        plans.append(replace(plan, explanations=explain(snap, base, plan.roster, absence)))
    return plans, stats, best_min


def repair(
    snap: Snapshot,
    base: list[Shift],
    absence: Absence,
    *,
    unlocked: set[uuid.UUID] | None = None,
    time_limit: float = 3.0,
    workers: int = 8,
    profiles: tuple[str, ...] = PROFILES,
    allow_cross_outlet: bool = False,
) -> RepairOutcome:
    """Widen stage by stage until minimum staffing holds (v3 section 12). If no stage manages it, the
    stage with the smallest shortfall (the earliest on a tie) is returned and its gaps are reported."""
    unlocked = unlocked or set()
    affected = affected_shifts(base, absence)
    outcome = RepairOutcome(
        "UNKNOWN",
        affected=affected,
        locked_conflicts=[s for s in affected if s.locked and s.logical_id not in unlocked],
    )
    if outcome.locked_conflicts:
        outcome.status = "LOCK_CONFLICT"
        return outcome
    snap = replace(
        snap,
        absences=(*snap.absences, absence),
        base_locked={s.logical_id: s for s in base if s.locked and s.logical_id not in unlocked},
    )
    broken = broken_shifts(snap, base, unlocked)
    outcome.stats["broken_shifts"] = len(broken)
    outcome.locked_conflicts = [s for s in broken if s.locked and s.logical_id not in unlocked]
    if outcome.locked_conflicts:  # an earlier absence hit a locked shift that nobody authorized changing
        outcome.status = "LOCK_CONFLICT"
        return outcome
    best: tuple[int, list[Plan], dict[str, Any]] | None = None
    tried: set[tuple[frozenset[uuid.UUID], frozenset[uuid.UUID], bool]] = set()
    for scope in scopes(snap, base, absence, allow_cross_outlet, broken):
        free, pool = _scope_sets(snap, base, absence, unlocked, scope)
        record: dict[str, Any] = {"stage": scope.name, "free_shifts": len(free), "pool": len(pool)}
        outcome.widening.append(record)
        if scope.cross_outlet and not allow_cross_outlet:
            record |= {"result": "skipped", "reason": "not_authorized"}
            continue
        signature = (frozenset(s.logical_id for s in free), frozenset(pool), scope.overtime)
        if signature in tried:
            record |= {"result": "skipped", "reason": "same_scope"}
            continue
        tried.add(signature)
        plans, stats, shortfall = _attempt(
            snap,
            base,
            absence,
            unlocked,
            scope,
            time_limit=time_limit,
            workers=workers,
            profiles=profiles,
        )
        outcome.stats[scope.name] = stats
        record["minimum_shortfall_minutes"] = shortfall
        if not plans or shortfall is None:
            record["result"] = "no_plan"
            continue
        record["result"] = "insufficient"
        if best is None or shortfall < best[0]:
            best = (shortfall, plans, record)
        if shortfall == 0:
            break
    if best is not None:
        best[2]["result"] = "selected"
        outcome.plans = best[1]
        outcome.status = outcome.plans[0].status
    return outcome
