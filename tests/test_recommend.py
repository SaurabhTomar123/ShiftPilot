"""A4.5: replacement recommendations (architecture v4 sections 11, 46)."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from scheduling import recommend, validator
from scheduling.rules import Rule
from seed.world_snapshot import build, greedy_roster


@pytest.fixture(scope="module")
def setting() -> tuple:  # type: ignore[type-arg]
    snap = build()
    roster = list(greedy_roster())
    return snap, roster, roster[5]


def test_every_recommendation_is_a_valid_direct_assignment(setting: tuple) -> None:  # type: ignore[type-arg]
    snap, roster, target = setting
    out = recommend.recommend(snap, roster, target.logical_id)
    assert out.options and out.eligible >= len(out.options)
    assert out.considered == out.eligible + len(out.rejected)
    for o in out.options:
        assert o.employee_id != target.employee_id
        after = [
            replace(sh, employee_id=o.employee_id) if sh.logical_id == target.logical_id else sh
            for sh in roster
        ]
        assert validator.validate(snap, after).valid, o.name
        assert {r.code for r in o.reasons} >= {
            "skill",
            "available",
            "rules",
            "incremental_cost",
            "disruption",
        }
    order = [(recommend.CLASS_ORDER[o.disruption_class], o.score) for o in out.options]
    assert order == sorted(order)


def test_lowest_cost_ranks_by_incremental_cost(setting: tuple) -> None:  # type: ignore[type-arg]
    snap, roster, target = setting
    out = recommend.recommend(snap, roster, target.logical_id, "lowest_cost", limit=10)
    direct = [o.incremental_cost_paise for o in out.options if o.disruption_class == "direct"]
    assert direct == sorted(direct)


def test_a_rule_blocks_with_provenance_and_is_never_ranked(setting: tuple) -> None:  # type: ignore[type-arg]
    snap, roster, target = setting
    first = recommend.recommend(snap, roster, target.logical_id).options[0]
    local = target.end_at.astimezone(snap.outlet.tz)
    rule = Rule(
        uuid.uuid4(),
        "max_shift_end_time",
        "employee",
        {},
        {"latest_end_minute": local.hour * 60 + local.minute - 30, "weekdays": list(range(7))},
        True,
        None,
        "",
    )
    ruled = replace(snap, rules={**snap.rules, first.employee_id: (rule,)})
    out = recommend.recommend(ruled, roster, target.logical_id, limit=10)
    assert first.employee_id not in {o.employee_id for o in out.options}
    (blocked,) = [a for a in out.rejected if a.employee_id == first.employee_id]
    assert [r.facts.get("rule_ids") for r in blocked.reasons if r.code == "rules"] == [[str(rule.id)]]


def test_other_outlets_only_when_asked(setting: tuple) -> None:  # type: ignore[type-arg]
    snap, roster, target = setting
    home = recommend.recommend(snap, roster, target.logical_id, limit=10)
    assert all(o.home_outlet_id == target.outlet_id for o in home.options)
    with pytest.raises(recommend.UnknownShift):
        recommend.recommend(snap, roster, uuid.uuid4())
