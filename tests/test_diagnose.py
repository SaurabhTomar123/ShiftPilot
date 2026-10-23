"""A4.7: assumption-assisted infeasibility diagnosis (architecture v4 section 17)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta

from scheduling import scenario, solver
from scheduling.model import Absence
from scheduling.rules import Rule
from scheduling.scenario import Event
from seed import world
from seed.world_snapshot import build

GRILL = world.SKILL["Grill"]
FRIDAY = world.NEXT_WEEK + timedelta(days=4)
ALLOWED = set(solver.RELAX)


def late_rule(emp_id: uuid.UUID) -> Rule:
    return Rule(
        uuid.uuid4(),
        "max_shift_end_time",
        "employee",
        {"employee_id": str(emp_id)},
        {"latest_end_minute": 1200, "weekdays": [4]},
        True,
        None,
        "",
    )


def test_a_feasible_week_has_no_conflict_set() -> None:
    assert solver.diagnose(build()) == []


def test_rules_that_starve_a_shift_are_named_with_the_shift() -> None:
    snap = build()
    cooks = [
        e for e in snap.employees.values() if GRILL in e.skill_ids and e.home_outlet_id == snap.outlet_id
    ]
    ruled = replace(snap, rules={**snap.rules, **{e.id: (late_rule(e.id),) for e in cooks}})
    found = solver.diagnose(ruled)
    assert found and {d["kind"] for d in found} <= ALLOWED
    assert any(d["kind"] == "minimum_coverage" and d["skill_id"] == str(GRILL) for d in found)
    named = {d["employee_id"] for d in found if d["kind"] == "rule"}
    assert named and named <= {str(e.id) for e in cooks}
    # Sufficient: lifting the diagnosed rules (only those) makes the week solvable again.
    lifted = replace(
        ruled,
        rules={e: r for e, r in ruled.rules.items() if str(e) not in named}
        | {e: snap.rules.get(e, ()) for e in map(uuid.UUID, named)},
    )
    assert solver.solve(lifted, "balanced", time_limit=4.0)[0] in ("OPTIMAL", "FEASIBLE")


def test_an_impossible_labour_cap_is_in_the_set() -> None:
    capped = scenario.apply(build(), [Event("labour_cap", {"max_cost_paise": 100})])
    found = solver.diagnose(capped)
    assert "labour_cap" in {d["kind"] for d in found}
    assert all(d["relaxation"] == solver.RELAX[d["kind"]] for d in found)


def test_facts_are_never_offered_as_relaxations() -> None:
    snap = build()
    week_start, week_end = snap.week_bounds()
    cooks = [e for e in snap.employees.values() if GRILL in e.skill_ids]
    everyone_off = replace(
        snap, absences=(*snap.absences, *(Absence(e.id, week_start, week_end, "confirmed") for e in cooks))
    )
    found = solver.diagnose(everyone_off)
    assert found and {d["kind"] for d in found} == {"minimum_coverage"}  # absences are facts


def test_generation_reports_the_conflict_set_with_infeasibility() -> None:
    snap = build()
    cooks = [
        e for e in snap.employees.values() if GRILL in e.skill_ids and e.home_outlet_id == snap.outlet_id
    ]
    ruled = replace(snap, rules={**snap.rules, **{e.id: (late_rule(e.id),) for e in cooks}})
    out = solver.generate(ruled, "balanced", time_limit=4.0)
    assert out.status == "INFEASIBLE" and out.stats["conflict_set"]
    assert "conflict_set" not in solver.solve(snap, "balanced", time_limit=2.0)[2]  # normal solves unchanged
