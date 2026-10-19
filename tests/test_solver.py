"""B2.2: CP-SAT generation, checked by the independent validator and against the greedy baseline."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta

import pytest

from scheduling import metrics, solver, validator
from scheduling.model import Requirement, Shift
from seed import world
from seed.world_snapshot import build, greedy_roster

FRIDAY = world.NEXT_WEEK + timedelta(days=4)
GRILL = world.SKILL["Grill"]


@pytest.fixture(scope="module")
def balanced() -> solver.Outcome:
    return solver.generate(build(), "balanced", time_limit=8.0)


def test_generation_finds_valid_candidates(balanced: solver.Outcome) -> None:
    assert balanced.status in ("OPTIMAL", "FEASIBLE")
    assert balanced.candidates and balanced.stats["rejected_by_validator"] == []
    snap = build()
    for cand in balanced.candidates:
        assert validator.validate(snap, cand.roster).valid, cand.strategy
        assert cand.proven_optimal == (cand.status == "OPTIMAL")
    # Budget is split across strategy solves; allow model-building time on top of the 8 s limit.
    assert balanced.wall_ms < 8_000 + 3_000


def test_optimizer_beats_the_greedy_baseline_on_coverage(balanced: solver.Outcome) -> None:
    snap = build()
    baseline = metrics.compute(snap, greedy_roster())
    best = metrics.compute(snap, balanced.candidates[0].roster)
    assert validator.validate(snap, greedy_roster()).valid  # the baseline is a fair, feasible comparison
    assert best.coverage_ratio is not None and baseline.coverage_ratio is not None
    assert best.coverage_ratio >= baseline.coverage_ratio
    assert best.minimum_deficit_minutes == 0


def test_alternatives_are_distinct_and_trade_off(balanced: solver.Outcome) -> None:
    strategies = [c.strategy for c in balanced.candidates]
    assert strategies[0] == "balanced" and len(set(strategies)) == len(strategies)
    rosters = [
        frozenset((s.employee_id, s.start_at, s.skill_id) for s in c.roster) for c in balanced.candidates
    ]
    assert len(set(rosters)) == len(rosters)  # deduplicated
    snap = build()
    by = {c.strategy: metrics.compute(snap, c.roster) for c in balanced.candidates}
    if "lowest_cost" in by:
        assert by["lowest_cost"].labour_cost_paise <= by["balanced"].labour_cost_paise
    if "max_coverage" in by:
        assert by["max_coverage"].coverage_ratio >= by["balanced"].coverage_ratio  # type: ignore[operator]


def test_impossible_minimum_is_reported_as_infeasible_with_the_shortage() -> None:
    base = build()
    raised = tuple(
        replace(r, minimum=6, preferred=6)
        if r.skill_id == GRILL and r.interval_start == world.at(FRIDAY, 1140)
        else r
        for r in base.requirements
    )
    out = solver.generate(build(requirements=raised), "balanced", time_limit=4.0)
    assert out.status == "INFEASIBLE" and not out.candidates
    assert [(s.skill_id, s.minimum_required, s.max_assignable) for s in out.shortages] == [(GRILL, 6, 5)]
    assert out.summary == "Friday 19:00-19:30 needs 6 Grill; only 5 qualified employees are available."


def test_locked_base_shift_is_kept_exactly() -> None:
    ravi = world.uid("employee", "ravi")
    sat = world.NEXT_WEEK + timedelta(days=5)
    lock = Shift(
        uuid.uuid4(),
        world.uid("outlet", "indiranagar"),
        ravi,
        GRILL,
        world.at(sat, 600),
        world.at(sat, 1080),
        30,
        world.at(sat, 930),
        locked=True,
    )
    snap = build(base_locked={lock.logical_id: lock})
    out = solver.generate(snap, "balanced", time_limit=6.0, max_candidates=1)
    roster = out.candidates[0].roster
    assert lock in roster
    assert validator.validate(snap, roster).valid
    assert not [s for s in roster if s.employee_id == ravi and s.start_at.date() == sat and s is not lock]


def test_commitments_elsewhere_are_respected() -> None:
    arjun = world.uid("employee", "arjun")
    wed = world.NEXT_WEEK + timedelta(days=2)
    elsewhere = world.uid("outlet", "koramangala")
    busy = Shift(uuid.uuid4(), elsewhere, arjun, GRILL, world.at(wed, 600), world.at(wed, 1380))
    outlets = {**build().outlets, elsewhere: replace(build().outlet, id=elsewhere, name="Koramangala")}
    snap = build(commitments=(busy,), outlets=outlets)
    out = solver.generate(snap, "balanced", time_limit=6.0, max_candidates=1)
    roster = out.candidates[0].roster
    # No Wednesday shift for Arjun; rest around the 10:00-23:00 commitment is the validator's call.
    assert not [
        s for s in roster if s.employee_id == arjun and s.start_at.astimezone(world.IST).date() == wed
    ]
    assert validator.validate(snap, roster).valid


def test_single_worker_solves_are_reproducible() -> None:
    snap = build()
    a = solver.solve(snap, "lowest_cost", time_limit=6.0, workers=1, seed=11)[1]
    b = solver.solve(snap, "lowest_cost", time_limit=6.0, workers=1, seed=11)[1]
    assert a is not None and b is not None
    key = lambda c: sorted((str(s.employee_id), s.start_at, str(s.skill_id)) for s in c.roster)  # noqa: E731
    assert key(a) == key(b) and a.objective == b.objective


def test_no_demand_means_no_shifts() -> None:
    out = solver.generate(build(requirements=()), "balanced", time_limit=2.0, max_candidates=1)
    assert out.status == "OPTIMAL" and out.candidates[0].roster == ()


def test_requirement_type_is_unchanged() -> None:  # guards the helper's assumptions
    assert all(isinstance(r, Requirement) for r in build().requirements)


def test_matched_coverage_is_never_more_expensive_than_the_baseline() -> None:
    """B2.4 regression guard: at the baseline's coverage the optimizer must not cost more."""
    snap = build()
    baseline = metrics.compute(snap, greedy_roster())
    _, matched, _ = solver.solve(
        snap, "lowest_cost", time_limit=6.0, max_shortfall_staff_minutes=baseline.preferred_deficit_minutes
    )
    assert matched is not None
    result = metrics.compute(snap, matched.roster)
    assert validator.validate(snap, matched.roster).valid
    assert result.preferred_deficit_minutes <= baseline.preferred_deficit_minutes
    assert result.labour_cost_paise <= baseline.labour_cost_paise
