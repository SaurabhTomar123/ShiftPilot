"""A4.4: decision trace and change taxonomy (architecture v4 section 18)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta

from scheduling import diff, repair, trace
from scheduling.model import Absence, Shift
from scheduling.rules import Rule
from seed.world_snapshot import build, greedy_roster


def shift(emp: uuid.UUID | None, hour: int = 10, lid: uuid.UUID | None = None) -> Shift:
    base = greedy_roster()[0]
    start = base.start_at.replace(hour=hour)
    return replace(
        base,
        logical_id=lid or uuid.uuid4(),
        employee_id=emp,
        start_at=start,
        end_at=start + timedelta(hours=8),
    )


def test_taxonomy() -> None:
    a, b, lid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    before = shift(a, lid=lid)
    cases = {
        "CREATED": diff.Change(lid, ("added",), None, before),
        "UNFILLED": diff.Change(lid, ("reassigned",), before, replace(before, employee_id=None)),
        "REMOVED": diff.Change(lid, ("removed",), before, None),
        "REASSIGNED": diff.Change(lid, ("reassigned", "moved"), before, shift(b, 12, lid)),
        "MOVED_TIME": diff.Change(lid, ("moved",), before, shift(a, 12, lid)),
        "KEPT": diff.Change(lid, ("break_changed",), before, before),
    }
    assert {k: trace.classify(c) for k, c in cases.items()} == {k: k for k in cases}
    assert trace.classify(diff.Change(lid, ("added",), None, replace(before, employee_id=None))) == "UNFILLED"


def test_counts_and_summary_against_a_base() -> None:
    snap = build()
    base = list(greedy_roster())
    people = sorted({sh.employee_id for sh in base if sh.employee_id}, key=str)
    first, second, third = base[0], base[1], base[2]
    other = next(p for p in people if p != first.employee_id)
    after = [
        replace(first, employee_id=other),  # REASSIGNED
        replace(
            second,
            start_at=second.start_at + timedelta(minutes=30),
            end_at=second.end_at + timedelta(minutes=30),
        ),
        *base[3:],  # third is REMOVED
        replace(third, logical_id=uuid.uuid4()),  # CREATED (same work, new identity)
    ]
    found, counts = trace.changes(base, after)
    assert counts == {
        "KEPT": len(base) - 3,
        "MOVED_TIME": 1,
        "REASSIGNED": 1,
        "CREATED": 1,
        "REMOVED": 1,
        "UNFILLED": 0,
    }
    assert [c.change for c in found if c.logical_id == first.logical_id] == ["REASSIGNED"]
    doc, rows, why = trace.build(snap, "stability", base, after)
    assert doc["summary"]["compared_to"] == "base_version"
    assert doc["summary"]["changed_commitments"] == 3
    assert len(rows) == 4 and "KEPT" not in {r["change"] for r in rows}
    # Explanations cover reassigned and created shifts, never kept ones.
    assert {e["logical_shift_id"] for e in why} == {str(first.logical_id), str(after[-1].logical_id)}
    assert doc["explained_shifts"] == 2 and not doc["explanations_truncated"]
    chosen = {r["code"] for r in why[0]["reasons"]}
    assert {"incremental_cost", "fairness_burden", "disruption", "rules"} <= chosen


def test_empty_week_compares_with_the_requested_plan() -> None:
    snap = build()
    roster = list(greedy_roster())
    doc, rows, why = trace.build(snap, "balanced", [], roster)
    assert doc["summary"]["compared_to"] is None and doc["summary"]["cost_delta_paise"] is None
    assert doc["counts"]["CREATED"] == len(roster) and why == []
    cheaper = roster[:-1]
    doc2, _, _ = trace.build(snap, "lowest_cost", [], cheaper, roster)
    assert doc2["summary"]["compared_to"] == "requested_plan"
    assert doc2["summary"]["cost_delta_paise"] < 0


def test_alternatives_name_the_rule_or_absence_that_blocks_them() -> None:
    snap = build()
    roster = list(greedy_roster())
    target = roster[0]
    qualified = [
        e
        for e in snap.employees.values()
        if target.skill_id in e.skill_ids
        and e.id != target.employee_id
        and e.home_outlet_id == snap.outlet_id
    ]
    ruled, absent = qualified[0], qualified[1]
    local = target.end_at.astimezone(snap.outlet.tz)
    cutoff = local.hour * 60 + local.minute - 30
    rule = Rule(
        uuid.uuid4(),
        "max_shift_end_time",
        "employee",
        {},
        {"latest_end_minute": cutoff, "weekdays": list(range(7))},
        True,
        None,
        "",
    )
    absence_id = uuid.uuid4()
    snap = replace(
        snap,
        rules={**snap.rules, ruled.id: (rule,)},
        absences=(
            *snap.absences,
            Absence(absent.id, target.start_at, target.end_at, "confirmed", absence_id),
        ),
    )
    (expl,) = repair.explain_shifts(snap, [], roster, [target], max_alternatives=50)
    alts = {a.employee_id: a for a in expl.alternatives}
    blocked = {r.code: r for r in alts[ruled.id].reasons}
    assert alts[ruled.id].status == "rejected" and blocked["rules"].facts["rule_ids"] == [str(rule.id)]
    blocked = {r.code: r for r in alts[absent.id].reasons}
    assert alts[absent.id].status == "rejected" and blocked["available"].facts["absence_ids"] == [
        str(absence_id)
    ]
