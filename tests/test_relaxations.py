"""A3.13 (architecture v3 section 13): business options instead of a bare INFEASIBLE."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from scheduling import solver
from scheduling.model import Requirement, Snapshot
from seed import world
from seed.world_snapshot import build

FRIDAY = world.NEXT_WEEK + timedelta(days=4)
GRILL = world.SKILL["Grill"]


def cooks(snap: Snapshot) -> int:
    return sum(
        1 for e in snap.employees.values() if GRILL in e.skill_ids and e.home_outlet_id == snap.outlet_id
    )


def five_grill_cooks(snap: Snapshot, need: int | None = None) -> Snapshot:
    """Friday 19:00-22:00 needs one grill cook more than Indiranagar has (or `need`)."""
    need = need or cooks(snap) + 1
    extra = tuple(
        Requirement(snap.outlet_id, GRILL, world.at(FRIDAY, m), world.at(FRIDAY, m + 30), need, need)
        for m in range(1140, 1320, 30)
    )
    kept = tuple(
        r
        for r in snap.requirements
        if not (r.skill_id == GRILL and r.interval_start in {x.interval_start for x in extra})
    )
    return replace(snap, requirements=(*kept, *extra))


def test_too_few_people_offers_reduced_minimum_and_names_it() -> None:
    out = solver.generate(five_grill_cooks(build()), "balanced", time_limit=6.0)
    assert out.status == "INFEASIBLE" and out.candidates == []
    kinds = [r.kind for r in out.relaxations]
    assert kinds[-1] == "reduced_minimum" and "overtime" not in kinds  # nobody's contract allows more hours
    reduced = out.relaxations[-1]
    need = cooks(build()) + 1
    assert reduced.shortages and reduced.shortages[0].minimum_required == need
    assert "Friday 19:00-22:00" in reduced.summary and f"instead of {need}" in reduced.summary


def test_borrowing_from_another_outlet_is_offered_with_names() -> None:
    home = five_grill_cooks(build())
    other = build("koramangala")
    snap = replace(
        home,
        employees={**home.employees, **other.employees},
        outlets={**home.outlets, **other.outlets},
    )
    assert solver.generate(snap, "balanced", time_limit=6.0).status == "INFEASIBLE"  # own staff only
    out = solver.generate(snap, "balanced", time_limit=6.0)
    borrow = next(r for r in out.relaxations if r.kind == "cross_outlet")
    homes = {o for _, _, o, _ in borrow.employees}
    assert homes == {other.outlet_id} and all(m > 0 for *_, m in borrow.employees)
    assert borrow.summary.startswith("Borrow ") and other.outlet.name in borrow.summary


def test_overtime_is_offered_when_contracts_cap_hours_below_need() -> None:
    snap = build()
    capped = {
        e.id: replace(e, regular_weekly_minutes=600, max_weekly_minutes=2880, overtime_allowed=False)
        for e in snap.employees.values()
    }
    out = solver.generate(replace(snap, employees=capped), "balanced", time_limit=6.0)
    assert out.status == "INFEASIBLE"
    overtime = next(r for r in out.relaxations if r.kind == "overtime")
    assert overtime.employees and all(m > 0 for *_, m in overtime.employees)
    assert overtime.summary.startswith("Allow ") and "overtime" in overtime.summary
    assert overtime.summary.isascii()


def test_normal_generation_never_uses_other_outlets_staff() -> None:
    other = build("koramangala")
    snap = build()
    wide = replace(
        snap, employees={**snap.employees, **other.employees}, outlets={**snap.outlets, **other.outlets}
    )
    out = solver.generate(wide, "balanced", time_limit=6.0, max_candidates=1)
    assert out.candidates
    assert {sh.employee_id for sh in out.candidates[0].roster} <= set(snap.employees)
