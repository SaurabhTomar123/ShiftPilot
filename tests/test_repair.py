"""B4.2/B4.3: minimal-disruption absence repair with deterministic explanations."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta

import pytest

from scheduling import metrics, repair, validator
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
    stage = next(r["stage"] for r in outcome.widening if r["result"] == "selected")
    best = outcome.stats[stage]["least_disruption"]["best_disruption"]
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


def test_local_repair_stops_at_the_first_stage_that_keeps_minimum_staffing(
    outcome: repair.RepairOutcome,
) -> None:
    """v3 section 12: local first; later stages are not even tried."""
    assert [r["stage"] for r in outcome.widening] == ["impact"]  # v4 section 15: impact scope first
    assert outcome.widening[0]["result"] == "selected"
    assert outcome.widening[0]["minimum_shortfall_minutes"] == 0


def tight(snap: object, base: list[Shift]) -> object:
    """Everyone's regular week is exactly the hours the published roster gives them, and nobody may work
    overtime: covering an absence means moving hours, not adding them."""
    promised: dict[object, int] = {}
    for sh in base:
        if sh.employee_id:
            promised[sh.employee_id] = promised.get(sh.employee_id, 0) + sh.paid_minutes
    employees = {
        e.id: replace(e, regular_weekly_minutes=promised.get(e.id, 0), overtime_allowed=False)
        for e in snap.employees.values()  # type: ignore[attr-defined]
    }
    return replace(snap, employees=employees)  # type: ignore[type-var]


def test_a_wider_stage_counts_the_gaps_it_opens_on_neighbouring_days() -> None:
    """Regression (found by the B4.5 acceptance test): adjacent and wider stages may move people off the
    day before or after, so their coverage must be measured on those days too. Hours are tight here, so
    moving someone only shifts the gap; no stage may report success it does not deliver."""
    snap, base, absence, _ = setting()
    out = repair.repair(tight(snap, base), base, absence, time_limit=4.0)  # type: ignore[arg-type]
    selected = next(r for r in out.widening if r["result"] == "selected")
    week_gap = metrics.compute(replace(snap, absences=(absence,)), list(out.plans[0].roster))  # type: ignore[type-var]
    assert selected["minimum_shortfall_minutes"] == week_gap.minimum_deficit_minutes > 0
    assert all(r["result"] in ("insufficient", "selected", "skipped") for r in out.widening)


def test_every_stage_is_recorded_when_none_keeps_minimum_staffing() -> None:
    snap, base, absence, _ = setting()
    # Every other Grill cook is off sick that day too: no stage can keep minimum Grill staffing.
    day = absence.start_at.astimezone(world.IST).replace(hour=0, minute=0)
    grill = world.SKILL["Grill"]
    sick = tuple(
        Absence(e.id, day, day + timedelta(days=1), "confirmed")
        for e in snap.employees.values()  # type: ignore[attr-defined]
        if grill in e.skill_ids and e.id != absence.employee_id
    )
    snap = replace(snap, absences=sick)  # type: ignore[type-var]
    out = repair.repair(tight(snap, base), base, absence, time_limit=4.0)  # type: ignore[arg-type]
    stages = {r["stage"]: r for r in out.widening}
    assert list(stages) == list(repair.STAGES)
    assert (
        stages["other_outlets"]["result"] == "skipped"
        and stages["other_outlets"]["reason"] == "not_authorized"
    )
    attempted = [r for r in out.widening if r["result"] != "skipped"]
    assert all(r["minimum_shortfall_minutes"] > 0 for r in attempted)
    [selected] = [r for r in out.widening if r["result"] == "selected"]
    assert selected["minimum_shortfall_minutes"] == min(r["minimum_shortfall_minutes"] for r in attempted)
    assert out.plans  # the best effort is still returned; the worker reports its gaps


def test_cross_outlet_stage_needs_authorization_and_other_outlets_staff() -> None:
    snap, base, absence, _ = setting()
    authorized = repair.repair(tight(snap, base), base, absence, time_limit=2.0, allow_cross_outlet=True)  # type: ignore[arg-type]
    stages = {r["stage"]: r for r in authorized.widening}
    # Authorized, but this snapshot has no other outlets' staff, so the pool is unchanged.
    assert stages.get("other_outlets", {}).get("reason") in (None, "same_scope")
    borrowed = next(e for e in snap.employees.values() if e.home_outlet_id == world.HOME)  # type: ignore[attr-defined]
    away = replace(borrowed, id=uuid.uuid4(), home_outlet_id=uuid.uuid4())
    wider = replace(snap, employees={**snap.employees, away.id: away})  # type: ignore[attr-defined,type-var]
    scope = next(x for x in repair.scopes(wider, base, absence, True) if x.name == "other_outlets")  # type: ignore[arg-type]
    _, pool = repair._scope_sets(wider, base, absence, set(), scope)  # type: ignore[arg-type]
    local = next(x for x in repair.scopes(wider, base, absence, True) if x.name == "adjacent_shifts")  # type: ignore[arg-type]
    _, home_pool = repair._scope_sets(wider, base, absence, set(), local)  # type: ignore[arg-type]
    assert away.id in pool and away.id not in home_pool


def test_frozen_shifts_are_never_changed_by_a_repair() -> None:
    """v4 section 13: an employee freeze holds their published shifts even where a wider stage would move
    them; a frozen shift the absence itself breaks is a conflict to authorize, not ignored."""
    snap, base, absence, victim = setting()
    same_day = [
        s
        for s in base
        if s.employee_id
        and s.start_at.astimezone(world.IST).date() == victim.start_at.astimezone(world.IST).date()
    ]
    keep = frozenset(s.logical_id for s in same_day if s.logical_id != victim.logical_id)
    out = repair.repair(replace(snap, frozen=keep), base, absence, time_limit=4.0)  # type: ignore[arg-type]
    assert out.plans
    for plan in out.plans:
        by_id = {s.logical_id: s for s in plan.roster}
        assert all(
            by_id[i].employee_id == next(b for b in base if b.logical_id == i).employee_id for i in keep
        )
    clash = repair.repair(replace(snap, frozen=frozenset({victim.logical_id})), base, absence, time_limit=2.0)  # type: ignore[arg-type]
    assert clash.status == "LOCK_CONFLICT" and [s.logical_id for s in clash.locked_conflicts] == [
        victim.logical_id
    ]


def test_widening_records_what_was_released_and_why() -> None:
    snap, base, absence, _ = setting()
    out = repair.repair(tight(snap, base), base, absence, time_limit=4.0)  # type: ignore[arg-type]
    assert out.widening[0]["stage"] == "impact" and out.widening[0]["released"].startswith("only the shifts")
    later = [r for r in out.widening[1:] if r["result"] != "skipped"]
    assert later and all("below minimum staffing" in r["widened_because"] for r in later)
