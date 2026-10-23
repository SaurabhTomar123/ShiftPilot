"""Candidate Portfolio (architecture v4 section 16). Pure.

Generation runs explicit decision strategies, then this selector keeps only plans that materially differ
and that are not dominated on the metrics a manager sees:

    1. the requested strategy's plan is kept first (it is what the manager asked for);
    2. a plan with the same assignments as one already kept is a duplicate;
    3. a plan that breaks its strategy's guardrail, measured against the requested plan, is dropped;
    4. plan B is dominated when another kept plan is no worse on every displayed metric and strictly
       better on at least one;
    5. at most three plans by default.

Every dropped plan is recorded with its reason, so the run can say why only two options came back.
Guardrails are versioned policy, like the fairness weights.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from scheduling.model import Shift

POLICY_VERSION = 1
PORTFOLIO = ("stability", "lowest_cost", "fairness", "max_coverage")
LABELS = {
    "stability": "Stability",
    "lowest_cost": "Lowest cost",
    "fairness": "Employee fairness",
    "max_coverage": "Maximum coverage",
    "balanced": "Balanced",
    "staff_friendly": "Staff friendly",
}


@dataclass(frozen=True)
class Displayed:
    """The metrics a manager compares plans on. Lower is better for every one of them."""

    cost_paise: int  # labour plus the overtime premium
    preferred_deficit_minutes: int  # staff-minutes below preferred coverage
    overtime_minutes: int
    changed_shifts: int | None  # against the published base; None for an empty week (not comparable)
    fairness: float | None  # fairness burden deviation; None with fewer than two people

    def pairs(self, other: Displayed) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = [
            (self.cost_paise, other.cost_paise),
            (self.preferred_deficit_minutes, other.preferred_deficit_minutes),
            (self.overtime_minutes, other.overtime_minutes),
        ]
        if self.changed_shifts is not None and other.changed_shifts is not None:
            out.append((self.changed_shifts, other.changed_shifts))
        if self.fairness is not None and other.fairness is not None:
            out.append((self.fairness, other.fairness))
        return out


def dominates(a: Displayed, b: Displayed) -> bool:
    """a is no worse than b on every displayed metric and strictly better on at least one."""
    pairs = a.pairs(b)
    return all(x <= y for x, y in pairs) and any(x < y for x, y in pairs)


@dataclass(frozen=True)
class Guardrails:
    """Policy 1. Bounds are relative to the requested plan, which the manager already accepts."""

    version: int = POLICY_VERSION
    cost_ratio_bp: dict[str, int] | None = None  # max cost as basis points of the reference
    overtime_slack_minutes: dict[str, int] | None = None
    coverage_ratio_bp: dict[str, int] | None = None  # max preferred deficit, basis points of reference
    coverage_slack_minutes: int = 240
    disruption_slack_shifts: int = 4  # plus disruption_slack_share of the base
    disruption_slack_share_bp: int = 2000
    fairness_slack: float = 1.0  # burden points per 40 h

    def limits(self, strategy: str) -> dict[str, bool]:
        """Which guardrails apply to a strategy (v4 section 16 table)."""
        return {
            "stability": {"cost": True, "overtime": True},
            "lowest_cost": {"disruption": True, "coverage": True, "fairness": True},
            "fairness": {"coverage": True, "disruption": True},
            "max_coverage": {"cost": True, "overtime": True, "disruption": True},
        }.get(strategy, {})


# Guardrails stop runaway plans, not ordinary trade-offs: Lowest cost may leave up to 3x the requested
# plan's preferred-coverage gap (minimum staffing is always hard), Maximum coverage may cost 1.4x.
GUARDRAILS = Guardrails(
    cost_ratio_bp={"stability": 11000, "max_coverage": 14000},
    overtime_slack_minutes={"stability": 240, "max_coverage": 480},
    coverage_ratio_bp={"lowest_cost": 30000, "fairness": 12500},
)


def breaches(
    strategy: str, plan: Displayed, ref: Displayed, base_size: int, g: Guardrails = GUARDRAILS
) -> list[str]:
    """The guardrails this plan breaks, measured against the reference (requested) plan."""
    out = []
    on = g.limits(strategy)
    cost_cap = ref.cost_paise * (g.cost_ratio_bp or {}).get(strategy, 10000)
    if on.get("cost") and plan.cost_paise * 10000 > cost_cap:
        out.append("cost")
    if on.get("overtime") and plan.overtime_minutes > ref.overtime_minutes + (
        g.overtime_slack_minutes or {}
    ).get(strategy, 0):
        out.append("overtime")
    if on.get("coverage"):
        cap = ref.preferred_deficit_minutes * (g.coverage_ratio_bp or {}).get(strategy, 10000) // 10000
        if plan.preferred_deficit_minutes > cap + g.coverage_slack_minutes:
            out.append("coverage")
    if on.get("disruption") and plan.changed_shifts is not None and ref.changed_shifts is not None:
        slack = g.disruption_slack_shifts + base_size * g.disruption_slack_share_bp // 10000
        if plan.changed_shifts > ref.changed_shifts + slack:
            out.append("disruption")
    if (
        on.get("fairness")
        and plan.fairness is not None
        and ref.fairness is not None
        and plan.fairness > ref.fairness + g.fairness_slack
    ):
        out.append("fairness")
    return out


def assignment_key(roster: Iterable[Shift]) -> frozenset[tuple[object, ...]]:
    """Two plans with the same assignments are the same plan, whatever their logical ids."""
    return frozenset((sh.employee_id, sh.skill_id, sh.outlet_id, sh.start_at, sh.end_at) for sh in roster)


def changed_shifts(base: Sequence[Shift], roster: Iterable[Shift]) -> int:
    """Logical shifts added, removed or reassigned/retimed against the base version."""
    before = {sh.logical_id: (sh.employee_id, sh.skill_id, sh.start_at, sh.end_at) for sh in base}
    after = {sh.logical_id: (sh.employee_id, sh.skill_id, sh.start_at, sh.end_at) for sh in roster}
    return sum(before.get(k) != after.get(k) for k in {*before, *after})


@dataclass(frozen=True)
class Entry:
    strategy: str
    key: frozenset[tuple[object, ...]]
    displayed: Displayed


@dataclass(frozen=True)
class Dropped:
    strategy: str
    reason: str  # duplicate | guardrail | dominated | limit
    detail: list[str]  # the guardrails broken, or the strategy that duplicates/dominates it

    def as_json(self) -> dict[str, object]:
        return {"strategy": self.strategy, "reason": self.reason, "detail": self.detail}


def select(
    entries: Sequence[Entry], base_size: int, limit: int = 3, g: Guardrails = GUARDRAILS
) -> tuple[list[int], list[Dropped]]:
    """Indexes of the plans to show, in order, and why the others were dropped. entries[0] is the
    requested plan: always kept, and the reference for guardrails."""
    if not entries:
        return [], []
    ref = entries[0].displayed
    kept: list[int] = [0]
    dropped: list[Dropped] = []
    for i, e in enumerate(entries[1:], start=1):
        twin = next((entries[k].strategy for k in kept if entries[k].key == e.key), None)
        if twin is not None:
            dropped.append(Dropped(e.strategy, "duplicate", [twin]))
            continue
        broken = breaches(e.strategy, e.displayed, ref, base_size, g)
        if broken:
            dropped.append(Dropped(e.strategy, "guardrail", broken))
            continue
        kept.append(i)
    # Dominance among the survivors; the requested plan is never removed.
    final = [0]
    for i in kept[1:]:
        by = next(
            (
                entries[k].strategy
                for k in kept
                if k != i and dominates(entries[k].displayed, entries[i].displayed)
            ),
            None,
        )
        if by is not None:
            dropped.append(Dropped(entries[i].strategy, "dominated", [by]))
        else:
            final.append(i)
    for i in final[limit:]:
        dropped.append(Dropped(entries[i].strategy, "limit", []))
    return final[:limit], dropped
