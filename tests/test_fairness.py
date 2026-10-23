"""A4.2 (architecture v4 section 12): true fairness burden."""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import replace
from datetime import timedelta

from scheduling import fairness, metrics, solver
from seed import world
from seed.world_snapshot import build, greedy_roster


def test_burden_counts_closing_weekend_split_and_overtime() -> None:
    snap = build()
    tz = snap.outlet.tz
    roster = greedy_roster()
    closing = next(
        s for s in roster if s.end_at.astimezone(tz).hour >= 22 and s.start_at.astimezone(tz).weekday() < 5
    )
    weekend_open = next(
        s for s in roster if s.start_at.astimezone(tz).weekday() == 5 and s.end_at.astimezone(tz).hour < 22
    )
    assert fairness.shift_burden(closing, tz) == 3 and fairness.shift_burden(weekend_open, tz) == 2
    who = closing.employee_id
    second = replace(
        closing,
        logical_id=uuid.uuid4(),
        start_at=closing.start_at - timedelta(hours=8),
        end_at=closing.start_at - timedelta(hours=5),
    )
    assert fairness.burden([closing, second], tz)[who] == 3 + 2  # the second shift that day adds a split
    assert fairness.burden([closing], tz, {who: 60})[who] == 3 + (closing.paid_minutes - 60) // 60  # type: ignore[index]


def test_deviation_is_zero_when_burden_is_proportional() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    assert fairness.deviation({a: 2400, b: 1200}, {a: 6, b: 3}) == 0
    assert fairness.deviation({a: 2400, b: 2400}, {a: 6, b: 0}) == 3.0
    assert fairness.deviation({a: 2400}, {a: 6}) is None


def test_history_shapes_who_gets_this_weeks_burden() -> None:
    """Someone who carried closings for weeks gets fewer this week under the fairness-weighted profile."""
    snap = build()
    tz = snap.outlet.tz
    base = solver.solve(snap, "staff_friendly", time_limit=6.0)[1]
    assert base is not None
    load = Counter({e: b for e, b in fairness.burden(base.roster, tz).items()})
    heavy = load.most_common(1)[0][0]
    carried = replace(snap, history_burden={heavy: 60})  # eight weeks of closings already
    after = solver.solve(carried, "staff_friendly", time_limit=6.0)[1]
    assert after is not None
    assert fairness.burden(after.roster, tz).get(heavy, 0) < load[heavy]
    m = metrics.compute(carried, after.roster)
    assert m.fairness_burden_deviation is not None and m.fairness_burden_deviation >= 0


def test_metric_matches_the_definition() -> None:
    snap = build()
    roster = greedy_roster()
    people = {
        e.id: e.regular_weekly_minutes for e in snap.employees.values() if e.home_outlet_id == world.HOME
    }
    expected = fairness.deviation(people, fairness.burden(roster, snap.outlet.tz, people))
    assert metrics.compute(snap, roster).fairness_burden_deviation == expected


def test_components_add_up_to_this_weeks_burden() -> None:
    snap = build()
    roster = greedy_roster()
    regular = {e.id: e.regular_weekly_minutes for e in snap.employees.values()}
    parts = fairness.components(roster, snap.outlet.tz, regular)
    assert sum(parts.values()) == sum(fairness.burden(roster, snap.outlet.tz, regular).values())
    shown = metrics.compute(snap, roster).fairness_components
    assert shown is not None and shown["policy_version"] == 1 and shown["closing"] == parts["closing"] > 0
