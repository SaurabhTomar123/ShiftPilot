"""A4.6: Scenario Lab overlays (architecture v4 sections 23, 42). Pure."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from scheduling import metrics, scenario, snapshot_json, solver, validator
from scheduling.scenario import Event, EventError
from seed.world_snapshot import build, greedy_roster


def test_demand_change_scales_matching_intervals_up() -> None:
    snap = build()
    out = scenario.apply(
        snap, [Event("demand_change", {"percent": 50, "weekdays": [5], "start_minute": 1080})]
    )
    tz = snap.outlet.tz
    for before, after in zip(snap.requirements, out.requirements, strict=True):
        local = before.interval_start.astimezone(tz)
        if local.weekday() == 5 and local.hour >= 18:
            assert after.minimum == -(-before.minimum * 150 // 100)
            assert after.preferred >= after.minimum
        else:
            assert after == before
    assert snap.requirements != out.requirements  # the original snapshot is untouched (frozen)


def test_closure_removes_the_day_and_the_solver_schedules_nothing_there() -> None:
    snap = build()
    saturday = snap.week_start + timedelta(days=5)
    out = scenario.apply(snap, [Event("outlet_closure", {"day": saturday.isoformat()})])
    tz = snap.outlet.tz
    assert out.closed_days == {saturday}
    assert all(r.interval_start.astimezone(tz).date() != saturday for r in out.requirements)
    gen = solver.generate(out, "balanced", time_limit=4.0, max_candidates=1)
    assert gen.candidates
    assert all(sh.start_at.astimezone(tz).date() != saturday for sh in gen.candidates[0].roster)
    assert scenario.baseline(out, list(greedy_roster())) == [
        sh for sh in greedy_roster() if sh.start_at.astimezone(tz).date() != saturday
    ]


def test_labour_cap_is_hard_and_an_impossible_cap_is_explained() -> None:
    snap = build()
    first = solver.generate(snap, "balanced", time_limit=4.0, max_candidates=1).candidates[0]
    m = metrics.compute(snap, first.roster)
    cap = int((m.labour_cost_paise + m.overtime_cost_paise) * 0.9)
    capped = scenario.apply(snap, [Event("labour_cap", {"max_cost_paise": cap})])
    out = solver.generate(capped, "balanced", time_limit=4.0, max_candidates=1)
    assert out.candidates
    m2 = metrics.compute(capped, out.candidates[0].roster)
    assert m2.labour_cost_paise + m2.overtime_cost_paise <= cap
    broke = solver.generate(
        scenario.apply(snap, [Event("labour_cap", {"max_cost_paise": 100})]), "balanced", time_limit=3.0
    )
    assert broke.status == "INFEASIBLE" and "labour cap" in (broke.summary or "")


def test_absence_and_rule_events_block_people_like_real_facts() -> None:
    snap = build()
    roster = list(greedy_roster())
    target = next(sh for sh in roster if sh.employee_id)
    local_end = target.end_at.astimezone(snap.outlet.tz)
    absent = scenario.apply(
        snap,
        [
            Event(
                "absence",
                {
                    "employee_id": str(target.employee_id),
                    "start_at": target.start_at.isoformat(),
                    "end_at": target.end_at.isoformat(),
                },
            )
        ],
    )
    assert "absent" in {v.code for v in validator.validate(absent, roster).violations}
    ruled = scenario.apply(
        snap,
        [
            Event(
                "rule",
                {
                    "rule_type": "max_shift_end_time",
                    "parameters": {
                        "latest_end_minute": local_end.hour * 60 + local_end.minute - 30,
                        "weekdays": list(range(7)),
                    },
                    "employee_ids": [str(target.employee_id)],
                },
            )
        ],
    )
    assert "rule" in {v.code for v in validator.validate(ruled, roster).violations}


@pytest.mark.parametrize(
    ("event", "path"),
    [
        (Event("weather", {}), ["type"]),
        (Event("demand_change", {"percent": 900}), ["payload", "percent"]),
        (Event("absence", {"employee_id": str(uuid.uuid4()), "start_at": "x"}), ["payload", "employee_id"]),
        (Event("outlet_closure", {"day": "2030-01-01"}), ["payload", "day"]),
        (Event("rule", {"rule_type": "max_shift_end_time", "employee_ids": []}), ["payload", "employee_ids"]),
    ],
)
def test_unsupported_or_invalid_events_are_refused(event: Event, path: list[str]) -> None:
    with pytest.raises(EventError) as exc:
        scenario.apply(build(), [event])
    assert exc.value.path == path


def test_overlay_fields_survive_the_snapshot_round_trip() -> None:
    snap = build()
    saturday = snap.week_start + timedelta(days=5)
    out = scenario.apply(
        snap,
        [
            Event("outlet_closure", {"day": saturday.isoformat()}),
            Event("labour_cap", {"max_cost_paise": 5_000_000}),
        ],
    )
    back = snapshot_json.load(snapshot_json.dump(out))
    assert back.closed_days == {saturday} and back.labour_cap_paise == 5_000_000
    assert "closed_days" not in snapshot_json.dump(snap)  # real snapshots (and their hashes) are unchanged
