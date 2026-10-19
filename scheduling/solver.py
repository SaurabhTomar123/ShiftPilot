"""CP-SAT roster generation (B2.2). Pure function of (Snapshot, config): no database access.

Model: candidate shifts = active templates x days x demanded skills, inside opening hours. One
boolean per (eligible employee, candidate). Hard: no overlap; rest between workdays and travel within
a workday (including commitments elsewhere); absolute weekly cap, and the regular threshold unless
overtime is permitted (decision 2); minimum staffing (decision 1); locked base shifts stay fixed.
Soft, weighted by strategy: preferred shortfall, labour cost, overtime premium, shifts outside
preferred windows. Every candidate is re-checked by the independent validator before it is returned;
eligibility is implemented here separately on purpose.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from ortools.sat.python import cp_model

from scheduling import validator
from scheduling.model import Employee, Shift, Snapshot

STATUS = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


@dataclass(frozen=True)
class Weights:
    """A profile as architecture v3 section 9 states it: shares of the objective that sum to 1. Users pick
    a profile, never weights."""

    cost: float  # labour cost including the overtime premium, paise
    understaffing: float  # staff-minutes below preferred coverage
    preferences: float  # shifts outside an employee's preferred windows
    disruption: float  # base assignments not kept when regenerating over a published version
    hours_alignment: float  # |worked - preferred weekly minutes|, summed over employees

    def coefficients(self) -> dict[str, int]:
        return {k: round(getattr(self, k) * UNIT[k]) for k in UNIT}


# Exchange rates turning each term's unit into the objective's integer scale. They are set so that, at
# Balanced, one staff-minute below preferred is worth INR 4 of labour, a shift outside preferred windows
# INR 20, a changed base assignment INR 50 and a minute away from someone's preferred week 20 paise.
UNIT = {
    "cost": 100,  # per paise
    "understaffing": 100 * 400 * 0.25 / 0.30,
    "preferences": 100 * 2_000 * 0.25 / 0.15,
    "disruption": 100 * 5_000 * 0.25 / 0.20,
    "hours_alignment": 100 * 20 * 0.25 / 0.10,
}


STRATEGIES: dict[str, Weights] = {
    "balanced": Weights(
        cost=0.25, understaffing=0.30, preferences=0.15, disruption=0.20, hours_alignment=0.10
    ),
    "lowest_cost": Weights(
        cost=0.55, understaffing=0.20, preferences=0.05, disruption=0.15, hours_alignment=0.05
    ),
    "max_coverage": Weights(
        cost=0.10, understaffing=0.60, preferences=0.10, disruption=0.15, hours_alignment=0.05
    ),
    "staff_friendly": Weights(
        cost=0.20, understaffing=0.25, preferences=0.30, disruption=0.10, hours_alignment=0.15
    ),
}
ALTERNATIVES = ("balanced", "lowest_cost", "max_coverage", "staff_friendly")


@dataclass(frozen=True)
class Candidate:
    strategy: str
    status: str  # OPTIMAL | FEASIBLE
    roster: tuple[Shift, ...]
    objective: int
    bound: int
    components: dict[str, int]

    @property
    def proven_optimal(self) -> bool:
        return self.status == "OPTIMAL"


@dataclass(frozen=True)
class Shortage:
    skill_id: uuid.UUID
    interval_start: datetime
    interval_end: datetime
    minimum_required: int
    max_assignable: int


@dataclass
class Outcome:
    status: str
    candidates: list[Candidate] = field(default_factory=list)
    shortages: list[Shortage] = field(default_factory=list)
    summary: str | None = None
    wall_ms: int = 0
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Slot:
    """A candidate shift (not yet assigned)."""

    day: date
    template_id: uuid.UUID
    skill_id: uuid.UUID
    start: datetime
    end: datetime
    break_start: datetime | None
    break_minutes: int

    @property
    def paid_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60) - self.break_minutes

    def productive_at(self, t: datetime) -> bool:
        if not (self.start <= t < self.end):
            return False
        return not (
            self.break_start is not None
            and self.break_start <= t < self.break_start + timedelta(minutes=self.break_minutes)
        )


# ---------------------------------------------------------------- candidate slots and eligibility


def slots(snap: Snapshot) -> list[Slot]:
    outlet = snap.outlet
    demanded = sorted({r.skill_id for r in snap.requirements if r.outlet_id == snap.outlet_id}, key=str)
    out: list[Slot] = []
    for d in range(7):
        day = snap.week_start + timedelta(days=d)
        midnight = datetime(day.year, day.month, day.day, tzinfo=outlet.tz)
        hours = outlet.operating_hours.get(day.weekday())
        for t in snap.templates:
            s, e = t.start_minute, t.start_minute + t.duration_minutes
            if hours is not None and not any(o <= s and e <= c for o, c in hours):
                continue
            offset = t.break_offset(snap.policy.grid_minutes)
            for skill in demanded:
                if t.skill_id is not None and t.skill_id != skill:
                    continue
                out.append(
                    Slot(
                        day,
                        t.id,
                        skill,
                        midnight + timedelta(minutes=s),
                        midnight + timedelta(minutes=e),
                        midnight + timedelta(minutes=s + offset) if offset is not None else None,
                        t.break_minutes,
                    )
                )
    return out


def eligible(snap: Snapshot, emp: Employee, slot: Slot) -> bool:
    if emp.status != "active" or slot.skill_id not in emp.skill_ids:
        return False
    local = slot.start.astimezone(snap.outlet.tz)
    s = local.hour * 60 + local.minute
    e = s + int((slot.end - slot.start).total_seconds() // 60)
    wd = local.weekday()
    ok = any(
        w.weekday == wd and w.kind in ("available", "preferred") and w.start_minute <= s and e <= w.end_minute
        for w in emp.windows
    )
    if not ok or any(
        w.weekday == wd and w.kind == "unavailable" and w.start_minute < e and s < w.end_minute
        for w in emp.windows
    ):
        return False
    if e > 1440 and any(
        w.weekday == (wd + 1) % 7 and w.kind == "unavailable" and w.start_minute < e - 1440
        for w in emp.windows
    ):
        return False
    return not any(
        a.employee_id == emp.id
        and a.status == "confirmed"
        and a.start_at < slot.end
        and slot.start < a.end_at
        for a in snap.absences
    )


def _preferred(snap: Snapshot, emp: Employee, slot: Slot) -> bool:
    local = slot.start.astimezone(snap.outlet.tz)
    s = local.hour * 60 + local.minute
    e = s + int((slot.end - slot.start).total_seconds() // 60)
    return any(
        w.weekday == local.weekday() and w.kind == "preferred" and w.start_minute <= s and e <= w.end_minute
        for w in emp.windows
    )


def _conflict(
    snap: Snapshot,
    a_start: datetime,
    a_end: datetime,
    a_outlet: uuid.UUID,
    b_start: datetime,
    b_end: datetime,
    b_outlet: uuid.UUID,
) -> bool:
    """True when one person cannot work both (order-independent)."""
    if b_start < a_start:
        a_start, a_end, a_outlet, b_start, b_end, b_outlet = (
            b_start,
            b_end,
            b_outlet,
            a_start,
            a_end,
            a_outlet,
        )
    gap = int((b_start - a_end).total_seconds() // 60)
    if gap < 0:
        return True
    tz = snap.outlets[a_outlet].tz
    if a_start.astimezone(tz).date() == b_start.astimezone(tz).date():
        need = 0 if a_outlet == b_outlet else snap.travel_minutes.get((a_outlet, b_outlet), 0)
        return gap < need
    return gap < snap.policy.min_rest_minutes


# ---------------------------------------------------------------- infeasibility diagnosis


def shortages(snap: Snapshot, candidates: list[Slot]) -> list[Shortage]:
    """Deterministic check (decision 9): intervals whose minimum exceeds the qualified, available people."""
    locked = list(snap.base_locked.values())
    found: list[Shortage] = []
    for req in sorted(snap.requirements, key=lambda r: (r.interval_start, str(r.skill_id))):
        if req.outlet_id != snap.outlet_id or req.minimum == 0:
            continue
        t = req.interval_start
        people = {
            e.id
            for e in snap.employees.values()
            if any(
                c.skill_id == req.skill_id and c.productive_at(t) and eligible(snap, e, c) for c in candidates
            )
        }
        people |= {
            sh.employee_id
            for sh in locked
            if sh.employee_id and sh.skill_id == req.skill_id and sh.start_at <= t < sh.end_at
        }
        if len(people) < req.minimum:
            last = found[-1] if found else None
            if (
                last
                and last.skill_id == req.skill_id
                and last.interval_end == req.interval_start
                and last.minimum_required == req.minimum
                and last.max_assignable == len(people)
            ):
                found[-1] = Shortage(
                    req.skill_id, last.interval_start, req.interval_end, req.minimum, len(people)
                )
            else:
                found.append(
                    Shortage(req.skill_id, req.interval_start, req.interval_end, req.minimum, len(people))
                )
    return found


def describe(snap: Snapshot, s: Shortage) -> str:
    tz = snap.outlet.tz
    a, b = s.interval_start.astimezone(tz), s.interval_end.astimezone(tz)
    skill = snap.skill_names.get(s.skill_id, "staff")
    return (
        f"{a:%A} {a:%H:%M}-{b:%H:%M} needs {s.minimum_required} {skill}; only {s.max_assignable} qualified "
        f"employee{'s are' if s.max_assignable != 1 else ' is'} available."
    )


# ---------------------------------------------------------------- one solve


def solve(
    snap: Snapshot,
    strategy: str,
    *,
    time_limit: float,
    seed: int = 7,
    workers: int = 8,
    max_shortfall_staff_minutes: int | None = None,
    deterministic_time: float | None = None,
) -> tuple[str, Candidate | None, dict[str, Any]]:
    """max_shortfall_staff_minutes caps preferred shortfall (equal shortfall = equal coverage), which
    gives matched-coverage comparisons: the cheapest roster covering at least as well as a reference.

    deterministic_time bounds the search in CP-SAT's deterministic work units instead of wall time, so
    one worker with a fixed seed returns the same roster however loaded the machine is (evaluation
    mode; time_limit stays as a wall-clock safety net)."""
    coef = STRATEGIES[strategy].coefficients()
    cands = slots(snap)
    model = cp_model.CpModel()
    x: dict[tuple[uuid.UUID, int], cp_model.IntVar] = {}
    for i, c in enumerate(cands):
        for e in snap.employees.values():
            if eligible(snap, e, c):
                x[e.id, i] = model.new_bool_var(f"x_{i}_{e.id.hex[:6]}")

    week_start, week_end = snap.week_bounds()
    locked = [sh for sh in snap.base_locked.values() if sh.employee_id is not None]
    fixed_by_emp: dict[uuid.UUID, list[Shift]] = defaultdict(list)
    for sh in [*locked, *snap.commitments]:
        if sh.employee_id is not None:
            fixed_by_emp[sh.employee_id].append(sh)
    by_emp: dict[uuid.UUID, list[int]] = defaultdict(list)
    for emp_id, i in x:
        by_emp[emp_id].append(i)

    cost_terms, ot_terms, pref_terms, align_terms = [], [], [], []
    for emp_id, idx in by_emp.items():
        emp = snap.employees[emp_id]
        idx.sort(key=lambda i: cands[i].start)
        for n, i in enumerate(idx):
            ci = cands[i]
            for fixed in fixed_by_emp[emp_id]:
                if _conflict(
                    snap, ci.start, ci.end, snap.outlet_id, fixed.start_at, fixed.end_at, fixed.outlet_id
                ):
                    model.add(x[emp_id, i] == 0)
            for j in idx[n + 1 :]:
                cj = cands[j]
                if cj.start - ci.end > timedelta(minutes=snap.policy.min_rest_minutes):
                    break
                if _conflict(snap, ci.start, ci.end, snap.outlet_id, cj.start, cj.end, snap.outlet_id):
                    model.add(x[emp_id, i] + x[emp_id, j] <= 1)
        fixed_minutes = sum(
            sh.paid_minutes for sh in fixed_by_emp[emp_id] if week_start <= sh.start_at < week_end
        )
        total = sum(cands[i].paid_minutes * x[emp_id, i] for i in idx) + fixed_minutes
        model.add(total <= emp.max_weekly_minutes)
        if emp.overtime_allowed:
            over = model.new_int_var(
                0, max(0, emp.max_weekly_minutes - emp.regular_weekly_minutes), f"ot_{emp_id.hex[:6]}"
            )
            model.add(over >= total - emp.regular_weekly_minutes)
            ot_terms.append(over * (emp.rate_paise_per_hour // 60))
        else:
            model.add(total <= emp.regular_weekly_minutes)
        if emp.preferred_weekly_minutes is not None:
            gap = model.new_int_var(
                0, emp.max_weekly_minutes + emp.preferred_weekly_minutes, f"gap_{emp_id.hex[:6]}"
            )
            model.add(gap >= total - emp.preferred_weekly_minutes)
            model.add(gap >= emp.preferred_weekly_minutes - total)
            align_terms.append(gap)
        has_prefs = any(w.kind == "preferred" for w in emp.windows)
        for i in idx:
            cost_terms.append(x[emp_id, i] * ((cands[i].paid_minutes * emp.rate_paise_per_hour + 30) // 60))
            if has_prefs and not _preferred(snap, emp, cands[i]):
                pref_terms.append(x[emp_id, i])

    short_terms = []
    for k, req in enumerate(r for r in snap.requirements if r.outlet_id == snap.outlet_id):
        t = req.interval_start
        covering = [
            x[e, i] for (e, i) in x if cands[i].skill_id == req.skill_id and cands[i].productive_at(t)
        ]
        locked_on = sum(
            1
            for sh in locked
            if sh.skill_id == req.skill_id
            and sh.outlet_id == req.outlet_id
            and sh.start_at <= t < sh.end_at
            and not sh.on_break(t)
        )
        covered = cp_model.LinearExpr.sum(covering)
        model.add(covered + locked_on >= req.minimum)
        if req.preferred > req.minimum:
            short = model.new_int_var(0, req.preferred, f"short_{k}")
            model.add(short >= req.preferred - locked_on - covered)
            minutes = int((req.interval_end - req.interval_start).total_seconds() // 60)
            short_terms.append(short * minutes)

    # Disruption: an unlocked base assignment survives if the same person takes the same slot again.
    kept_ids: dict[tuple[uuid.UUID, int], uuid.UUID] = {}
    slot_of = {(c.skill_id, c.start, c.end): i for i, c in enumerate(cands)}
    for b in snap.base:
        same = slot_of.get((b.skill_id, b.start_at, b.end_at))
        if b.employee_id is not None and same is not None and (b.employee_id, same) in x:
            kept_ids[b.employee_id, same] = b.logical_id
    base_assigned = sum(1 for b in snap.base if b.employee_id is not None)
    changed = base_assigned - sum(x[k] for k in kept_ids)

    cost, ot, shortfall, off_pref = sum(cost_terms), sum(ot_terms), sum(short_terms), sum(pref_terms)
    alignment = sum(align_terms)
    if max_shortfall_staff_minutes is not None:
        model.add(shortfall <= max_shortfall_staff_minutes)
    model.minimize(
        coef["cost"] * (cost + ot)
        + coef["understaffing"] * shortfall
        + coef["preferences"] * off_pref
        + coef["disruption"] * changed
        + coef["hours_alignment"] * alignment
    )
    stats = {
        "candidate_slots": len(cands),
        "assignment_variables": len(x),
        "constraints": len(model.proto.constraints),
    }

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    if deterministic_time is not None:  # evaluation mode (v3 section 15)
        solver.parameters.max_deterministic_time = deterministic_time
        solver.parameters.interleave_search = workers > 1  # parallel search is otherwise nondeterministic
    status = STATUS[solver.solve(model)]
    stats["solver_wall_ms"] = int(solver.wall_time * 1000)
    if status not in ("OPTIMAL", "FEASIBLE"):
        return status, None, stats
    roster: list[Shift] = list(snap.base_locked.values())
    for (emp_id, i), var in sorted(x.items(), key=lambda kv: (cands[kv[0][1]].start, str(kv[0][0]))):
        if solver.value(var):
            c = cands[i]
            roster.append(
                Shift(
                    kept_ids.get((emp_id, i)) or uuid.uuid7(),  # a kept assignment keeps its identity
                    snap.outlet_id,
                    emp_id,
                    c.skill_id,
                    c.start,
                    c.end,
                    c.break_minutes,
                    c.break_start,
                )
            )
    components = {
        "cost": int(solver.value(cost)),
        "overtime_premium": int(solver.value(ot)),
        "shortfall_staff_minutes": int(solver.value(shortfall)),
        "off_preference_shifts": int(solver.value(off_pref)),
        "changed_base_assignments": int(solver.value(changed)),
        "hours_preference_deviation_minutes": int(solver.value(alignment)),
    }
    return (
        status,
        Candidate(
            strategy,
            status,
            tuple(roster),
            int(solver.objective_value),
            int(solver.best_objective_bound),
            components,
        ),
        stats,
    )


# ---------------------------------------------------------------- generation with alternatives


def generate(
    snap: Snapshot,
    strategy: str = "balanced",
    *,
    time_limit: float = 10.0,
    seed: int = 7,
    workers: int = 8,
    max_candidates: int = 3,
    deterministic_time: float | None = None,
) -> Outcome:
    """Requested strategy first, then other profiles; deduplicated; each independently validated."""
    started = time.perf_counter()
    order = [strategy, *[s for s in ALTERNATIVES if s != strategy]][:max_candidates]
    budget = time_limit / len(order)
    outcome = Outcome(status="UNKNOWN", stats={"strategies": {}, "rejected_by_validator": []})
    seen: set[frozenset[tuple[Any, ...]]] = set()
    for name in order:
        status, cand, stats = solve(
            snap,
            name,
            time_limit=budget,
            seed=seed,
            workers=workers,
            deterministic_time=deterministic_time / len(order) if deterministic_time else None,
        )
        outcome.stats["strategies"][name] = {"status": status, **stats}
        if status == "INFEASIBLE":
            outcome.status = "INFEASIBLE"
            outcome.shortages = shortages(snap, slots(snap))
            outcome.summary = (
                describe(snap, outcome.shortages[0])
                if outcome.shortages
                else "No roster satisfies every rule at once: minimum staffing conflicts with "
                "availability, rest or weekly limits."
            )
            break
        if status == "MODEL_INVALID":
            outcome.status = "MODEL_INVALID"
            break
        if cand is None:
            continue
        check = validator.validate(snap, cand.roster)
        if not check.valid:
            outcome.stats["rejected_by_validator"].append(
                {
                    "strategy": name,
                    "codes": sorted({v.code for v in check.violations if v.severity == "hard"}),
                }
            )
            continue
        key = frozenset((sh.employee_id, sh.skill_id, sh.start_at, sh.end_at) for sh in cand.roster)
        if key in seen:
            continue
        seen.add(key)
        outcome.candidates.append(cand)
    if outcome.candidates:
        outcome.status = outcome.candidates[0].status
    outcome.wall_ms = int((time.perf_counter() - started) * 1000)
    return outcome
