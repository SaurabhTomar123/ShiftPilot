"""Replacement recommendations: "who can cover this shift?" (architecture v4 sections 11, 46). Pure.

Eligibility first: each qualified person is checked by the independent validator as if they took the
shift and nothing else changed (a direct assignment). Anyone a concrete rule blocks is listed with that
rule and its provenance, never ranked. Eligible people are then ranked:

    1. disruption class: direct, then overtime, then cross-outlet;
    2. the manager's profile, on the solver's own scale: incremental cost, fairness penalty, working
       outside a preferred window and hours-preference alignment, weighted as the profile weighs them;
    3. name, for a stable order.

The check is bounded: someone blocked only because of another shift might become available if that
shift moved. That is a repair, not a recommendation, and is never presented as one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from scheduling import metrics, repair, solver
from scheduling.model import Shift, Snapshot

POLICY_VERSION = 1
CLASS_ORDER = {"direct": 0, "overtime": 1, "cross_outlet": 2}
MAX_REJECTED = 10


@dataclass(frozen=True)
class Option:
    employee_id: UUID
    name: str
    home_outlet_id: UUID
    disruption_class: str  # direct | overtime | cross_outlet
    incremental_cost_paise: int  # labour plus overtime premium, against leaving the shift open
    overtime_minutes_added: int
    fairness_delta: float | None  # fairness burden deviation; negative = fairer
    weekly_minutes_after: int
    within_preferred_window: bool | None  # None: the person states no preferred windows
    reasons: tuple[repair.Reason, ...]
    score: int  # the profile's weighted sum; ranking only, not shown


@dataclass(frozen=True)
class Result:
    target: Shift
    options: list[Option]
    rejected: list[repair.Alternative]
    considered: int
    eligible: int


class UnknownShift(LookupError):
    pass


def recommend(
    snap: Snapshot,
    roster: list[Shift],
    logical_id: UUID,
    profile: str = "balanced",
    *,
    limit: int = 5,
    cross_outlet: bool = False,
) -> Result:
    target = next((sh for sh in roster if sh.logical_id == logical_id), None)
    if target is None:
        raise UnknownShift(str(logical_id))
    opened = replace(target, employee_id=None)
    others = [sh for sh in roster if sh.logical_id != logical_id]
    before = [*others, opened]
    m0 = metrics.compute(snap, before)
    pen0 = metrics.fairness_penalty(snap, [sh for sh in before if sh.employee_id])
    align0 = metrics.hours_preference_deviation(snap, [sh for sh in before if sh.employee_id]) or 0
    coef = solver.STRATEGIES[profile].coefficients()
    week_start, week_end = snap.week_bounds()
    options: list[Option] = []
    rejected: list[repair.Alternative] = []
    considered = 0
    for e in sorted(snap.employees.values(), key=lambda e: e.name):
        if e.id == target.employee_id or target.skill_id not in e.skill_ids:
            continue
        if e.home_outlet_id != target.outlet_id and not cross_outlet:
            continue
        considered += 1
        facts = repair._facts(snap, opened, e.id, others, week_start, week_end)
        blocked = tuple(r for r in facts if not r.ok)
        if blocked:
            rejected.append(repair.Alternative(e.id, e.name, "rejected", blocked))
            continue
        taken = replace(target, employee_id=e.id)
        after = [*others, taken]
        assigned = [sh for sh in after if sh.employee_id]
        m1 = metrics.compute(snap, after)
        cost = m1.labour_cost_paise + m1.overtime_cost_paise - m0.labour_cost_paise - m0.overtime_cost_paise
        overtime = m1.overtime_minutes - m0.overtime_minutes
        fair = (
            round(m1.fairness_burden_deviation - m0.fairness_burden_deviation, 2)
            if m1.fairness_burden_deviation is not None and m0.fairness_burden_deviation is not None
            else None
        )
        has_windows = any(w.kind == "preferred" for w in e.windows)
        inside = metrics._inside_preferred(snap, taken) if has_windows else None
        align = (metrics.hours_preference_deviation(snap, assigned) or 0) - align0
        score = (
            coef["cost"] * cost
            + coef.get("fairness", 0) * (metrics.fairness_penalty(snap, assigned) - pen0)
            + coef["preferences"] * (inside is False)
            + coef["hours_alignment"] * align
        )
        cls = "direct" if overtime <= 0 else "overtime"
        if e.home_outlet_id != target.outlet_id:
            cls = "cross_outlet"
        week = next((r.facts["weekly_minutes"] for r in facts if r.code == "weekly_hours"), 0)
        options.append(
            Option(
                e.id,
                e.name,
                e.home_outlet_id,
                cls,
                cost,
                overtime,
                fair,
                week,
                inside,
                facts + repair._choice(snap, taken, target),
                score,
            )
        )
    options.sort(key=lambda o: (CLASS_ORDER[o.disruption_class], o.score, o.name))
    return Result(target, options[:limit], rejected[:MAX_REJECTED], considered, len(options))
