"""B4.2/B4.3: minimal-disruption absence repair with deterministic explanations."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from scheduling import repair, validator
from scheduling.model import Absence, Shift
from seed import world
from seed.world_snapshot import build, greedy_roster

WEEK = world.WEEK


def setting() -> tuple[object, list[Shift], Absence, Shift]:
    snap = build("indiranagar", WEEK)
    base = greedy_roster("indiranagar", WEEK)
    victim = next(
        s
        for s in base
        if s.skill_id == world.SKILL["Grill"]
        and s.employee_id
        and not s.locked
        and s.start_at.astimezone(world.IST).weekday() == 2
    )  # a Wednesday Grill shift
    absence = Absence(victim.employee_id, victim.start_at - timedelta(hours=1), victim.end_at, "confirmed")  # type: ignore[arg-type]
    return snap, base, absence, victim


@pytest.fixture(scope="module")
def outcome() -> repair.RepairOutcome:
    snap, base, absence, _ = setting()
    return repair.repair(snap, base, absence, time_limit=6.0)  # type: ignore[arg-type]


def test_repair_covers_the_absence_with_valid_plans(outcome: repair.RepairOutcome) -> None:
    snap, base, absence, victim = setting()
    assert outcome.status in ("OPTIMAL", "FEASIBLE") and outcome.plans
    assert [s.logical_id for s in outcome.affected] == [victim.logical_id]
    for plan in outcome.plans:
        fixed = next(s for s in plan.roster if s.logical_id == victim.logical_id)
        assert fixed.employee_id != victim.employee_id
        hard = {
            v.code
            for v in validator.validate(replace(snap, absences=(absence,)), plan.roster).violations  # type: ignore[arg-type]
            if v.severity == "hard"
        }
        assert hard <= {"minimum_coverage"}  # reported, never hidden


def test_unrelated_days_are_untouched(outcome: repair.RepairOutcome) -> None:
    _, base, _, victim = setting()
    day = victim.start_at.astimezone(world.IST).date()
    base_other = {s for s in base if s.start_at.astimezone(world.IST).date() != day}
    for plan in outcome.plans:
        assert base_other <= set(plan.roster)


def test_least_disruption_comes_first_and_alternatives_stay_in_guardrails(
    outcome: repair.RepairOutcome,
) -> None:
    first = outcome.plans[0]
    assert first.profile == "least_disruption" and first.disruption["changed_shifts"] >= 1
    best = outcome.stats["least_disruption"]["best_disruption"]
    for plan in outcome.plans:
        total = (
            plan.disruption["changed_shifts"]
            + plan.disruption["added_shifts"]
            + 2 * plan.disruption["cross_outlet_moves"]
        )
        assert total <= best + repair.DISRUPTION_SLACK[plan.profile]
        assert (
            plan.stages["minimum_shortfall"]["proven_optimal"] if "minimum_shortfall" in plan.stages else True
        )
    rosters = [frozenset((s.logical_id, s.employee_id) for s in p.roster) for p in outcome.plans]
    assert len(set(rosters)) == len(rosters)


def test_explanations_are_factual(outcome: repair.RepairOutcome) -> None:
    _, _, _, victim = setting()
    exp = next(e for e in outcome.plans[0].explanations if e.logical_id == victim.logical_id)
    if exp.chosen_employee_id is not None:
        assert all(
            r.ok for r in exp.chosen if r.code in ("skill", "available", "no_conflict", "weekly_hours")
        )
    for alt in exp.alternatives:
        if alt.status == "rejected":
            assert alt.reasons and all(not r.ok for r in alt.reasons)  # a concrete blocking rule, always
        else:
            assert alt.status == "eligible_not_selected"


def test_locked_affected_shift_needs_explicit_authorization() -> None:
    snap, base, absence, victim = setting()
    locked_base = [replace(s, locked=True) if s.logical_id == victim.logical_id else s for s in base]
    blocked = repair.repair(snap, locked_base, absence, time_limit=3.0)  # type: ignore[arg-type]
    assert blocked.status == "LOCK_CONFLICT" and [s.logical_id for s in blocked.locked_conflicts] == [
        victim.logical_id
    ]
    allowed = repair.repair(
        snap,
        locked_base,
        absence,
        unlocked={victim.logical_id},
        time_limit=3.0,  # type: ignore[arg-type]
        profiles=("least_disruption",),
    )
    assert allowed.plans and allowed.plans[0].roster


def test_an_absence_without_affected_shifts_changes_nothing() -> None:
    snap, base, _, victim = setting()
    free_day = Absence(
        victim.employee_id,
        victim.start_at - timedelta(days=30),
        victim.end_at - timedelta(days=30),  # type: ignore[arg-type]
        "confirmed",
    )
    out = repair.repair(snap, base, free_day, time_limit=2.0, profiles=("least_disruption",))  # type: ignore[arg-type]
    assert out.affected == [] and out.plans[0].disruption["changed_shifts"] == 0
