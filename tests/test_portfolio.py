"""A4.3: Candidate Portfolio (architecture v4 section 16)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from scheduling import portfolio, solver, validator
from scheduling.portfolio import Displayed, Entry
from seed.world_snapshot import build


def plan(cost: int, gap: int, ot: int = 0, changed: int | None = None, fair: float | None = 2.0) -> Displayed:
    return Displayed(cost, gap, ot, changed, fair)


def entry(strategy: str, d: Displayed, key: str | None = None) -> Entry:
    return Entry(strategy, frozenset({(key or strategy,)}), d)


def test_dominance_needs_no_worse_everywhere_and_better_somewhere() -> None:
    assert portfolio.dominates(plan(100, 50), plan(120, 50))
    assert not portfolio.dominates(plan(100, 50), plan(100, 50))  # equal is not dominance
    assert not portfolio.dominates(plan(100, 60), plan(120, 50))  # a trade-off
    # A metric missing on either side (no base, too few people) is not compared.
    assert portfolio.dominates(plan(100, 50, fair=None), plan(120, 50, fair=1.0))


def test_requested_plan_is_kept_even_when_dominated() -> None:
    keep, dropped = portfolio.select(
        [entry("balanced", plan(200, 100)), entry("lowest_cost", plan(150, 90))], base_size=0
    )
    assert keep == [0, 1] and dropped == []


def test_duplicates_dominated_guardrails_and_limit_are_explained() -> None:
    entries = [
        entry("balanced", plan(1000, 500, changed=2)),
        entry("stability", plan(1000, 500, changed=2), key="balanced"),  # same assignments
        entry("lowest_cost", plan(800, 700, changed=3)),
        entry("max_coverage", plan(2000, 0, changed=3)),  # 2x cost breaks the 1.4x guardrail
        entry("fairness", plan(1100, 600, changed=4, fair=2.5)),  # worse than balanced everywhere
    ]
    keep, dropped = portfolio.select(entries, base_size=10)
    assert [entries[i].strategy for i in keep] == ["balanced", "lowest_cost"]
    assert [d.as_json() for d in dropped] == [
        {"strategy": "stability", "reason": "duplicate", "detail": ["balanced"]},
        {"strategy": "max_coverage", "reason": "guardrail", "detail": ["cost"]},
        {"strategy": "fairness", "reason": "dominated", "detail": ["balanced"]},
    ]


def test_disruption_guardrail_scales_with_the_base() -> None:
    ref = plan(1000, 500, changed=2)
    # Slack is 4 shifts plus 20% of the base: 4 + 10 = 14 for a base of 50.
    assert portfolio.breaches("lowest_cost", plan(900, 500, changed=16), ref, 50) == []
    assert portfolio.breaches("lowest_cost", plan(900, 500, changed=17), ref, 50) == ["disruption"]


def test_at_most_three_plans() -> None:
    entries = [
        entry("balanced", plan(1000, 500, fair=3.0)),
        entry("lowest_cost", plan(800, 900, fair=3.0)),
        entry("max_coverage", plan(1300, 0, fair=3.0)),
        entry("fairness", plan(1100, 550, fair=1.0)),
    ]
    keep, dropped = portfolio.select(entries, base_size=0)
    assert len(keep) == 3 and dropped[-1].reason == "limit"


@pytest.fixture(scope="module")
def generated() -> solver.Outcome:
    return solver.generate(build(), "balanced", time_limit=8.0)


def test_generated_portfolio_is_valid_distinct_and_non_dominated(generated: solver.Outcome) -> None:
    snap = build()
    info = generated.stats["portfolio"]
    assert info["policy_version"] == portfolio.POLICY_VERSION
    assert info["considered"][0] == "balanced" and "stability" not in info["considered"]  # empty week
    cands = generated.candidates
    assert 1 <= len(cands) <= 3 and cands[0].strategy == "balanced"
    assert all(validator.validate(snap, c.roster).valid for c in cands)
    assert len({portfolio.assignment_key(c.roster) for c in cands}) == len(cands)
    shown = [solver.displayed(snap, c.roster, []) for c in cands]
    for i, a in enumerate(shown[1:], start=1):
        assert not any(portfolio.dominates(b, a) for j, b in enumerate(shown) if j != i)


def test_stability_joins_over_a_published_week(generated: solver.Outcome) -> None:
    base = generated.candidates[0].roster
    snap = replace(build(), base=base)
    out = solver.generate(snap, "lowest_cost", time_limit=8.0)
    assert out.stats["portfolio"]["considered"][:2] == ["lowest_cost", "stability"]
    assert out.candidates[0].strategy == "lowest_cost"
