"""A3.9: StaffingRequirementService.expand (architecture v3 section 18)."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from scheduling import demand
from seed import world

IST = ZoneInfo("Asia/Kolkata")
GRILL, SERVER = world.SKILL["Grill"], world.SKILL["Server"]


def blocks() -> list[demand.Block]:
    return [
        demand.Block(wd, start, end, world.SKILL[skill], mn, pref)
        for wd, start, end, skill, mn, pref in world.staffing_template()
    ]


def test_the_seeded_template_reproduces_the_seeded_week() -> None:
    rows = demand.expand(world.WEEK, IST, blocks())
    expected = {
        (world.SKILL[skill], world.at(world.WEEK + timedelta(days=d), m)): world.requirement(
            skill, (world.WEEK + timedelta(days=d)).weekday(), m
        )
        for d in range(7)
        for skill in ("Grill", "Prep", "Server", "Cashier")
        for m in range(world.OPEN, world.CLOSE, world.INTERVAL)
        if world.requirement(skill, (world.WEEK + timedelta(days=d)).weekday(), m)[1]
    }
    assert {(r.skill_id, r.interval_start): (r.minimum, r.preferred) for r in rows} == expected
    assert {r.source for r in rows} == {"template"}
    assert all(r.interval_end - r.interval_start == timedelta(minutes=30) for r in rows)


def test_manual_overrides_are_never_regenerated() -> None:
    slot = world.at(world.WEEK, 720)
    rows = demand.expand(world.WEEK, IST, blocks(), manual={(GRILL, slot)})
    assert (GRILL, slot) not in {(r.skill_id, r.interval_start) for r in rows}
    assert (SERVER, slot) in {(r.skill_id, r.interval_start) for r in rows}


def test_overlapping_blocks_take_the_larger_need_and_are_detectable() -> None:
    a = demand.Block(0, 600, 900, GRILL, 1, 2)
    b = demand.Block(0, 780, 960, GRILL, 2, 3)
    rows = {r.interval_start: (r.minimum, r.preferred) for r in demand.expand(world.WEEK, IST, [a, b])}
    assert rows[world.at(world.WEEK, 600)] == (1, 2) and rows[world.at(world.WEEK, 840)] == (2, 3)
    assert demand.overlapping([a, b]) == [(a, b)]
    assert demand.overlapping([a, demand.Block(0, 900, 960, GRILL, 1, 1)]) == []  # touching is fine
    assert demand.overlapping([a, demand.Block(1, 600, 900, GRILL, 1, 1)]) == []  # another day


def test_bands_replace_the_template_where_orders_are_known() -> None:
    lunch = world.at(world.WEEK, 720)
    bands = [demand.Band(GRILL, 0, 30, 1, 2), demand.Band(GRILL, 31, None, 3, 4)]
    rows = demand.expand(world.WEEK, IST, blocks(), bands=bands, orders={lunch: 20})  # 40 orders/hour
    by_key = {(r.skill_id, r.interval_start): r for r in rows}
    assert (by_key[GRILL, lunch].minimum, by_key[GRILL, lunch].preferred, by_key[GRILL, lunch].source) == (
        3,
        4,
        "band",
    )
    assert by_key[SERVER, lunch].source == "template"  # no band for that role
    assert by_key[GRILL, world.at(world.WEEK, 750)].source == "template"  # no order count there


def test_intervals_needing_nobody_produce_no_rows() -> None:
    assert demand.expand(world.WEEK, IST, [demand.Block(0, 600, 660, GRILL, 0, 0)]) == []
