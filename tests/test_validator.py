"""B2.1: the independent validator and metrics.

1. Parity: the published Indiranagar week, rebuilt from the shared world, must reproduce the contract
   fixture's metrics, coverage and violations (computed by separate code in api.v2.contract_build).
2. One focused scenario per rule, with the boundaries that matter (9h59m vs 10h rest, 34 vs 35
   minutes travel, regular vs absolute weekly limit, overnight availability).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from scheduling import metrics, validator
from scheduling.model import Absence, Employee, Outlet, Policy, Requirement, Shift, Snapshot, Window
from seed import world

FIXTURES = Path(__file__).resolve().parents[1] / "contracts" / "v2" / "fixtures"


# ---------------------------------------------------------------- parity with the contract fixture


def world_snapshot(outlet_key: str = "indiranagar") -> tuple[Snapshot, list[Shift]]:
    outlet_id = world.uid("outlet", outlet_key)
    staff = world.STAFF[outlet_key]
    employees = {
        world.uid("employee", e.key): Employee(
            id=world.uid("employee", e.key),
            name=e.name,
            home_outlet_id=outlet_id,
            status="active",
            skill_ids=frozenset(world.SKILL[k] for k in e.skills),
            rate_paise_per_hour=e.rate_rupees * 100,
            regular_weekly_minutes=2880,
            max_weekly_minutes=2880,
            overtime_allowed=False,
            windows=tuple(Window(*w) for w in world.availability_windows(e)),
        )
        for e in staff
    }
    outlet = Outlet(
        outlet_id, outlet_key.title(), world.TZ, {d: ((world.OPEN, world.CLOSE),) for d in range(7)}
    )
    requirements = []
    for d in range(7):
        day = world.WEEK + timedelta(days=d)
        for skill in ("Grill", "Prep", "Server", "Cashier"):
            for m in range(world.OPEN, world.CLOSE, world.INTERVAL):
                mn, pref = world.requirement(skill, day.weekday(), m)
                if pref:
                    requirements.append(
                        Requirement(
                            outlet_id,
                            world.SKILL[skill],
                            world.at(day, m),
                            world.at(day, m + world.INTERVAL),
                            mn,
                            pref,
                        )
                    )
    roster = []
    for sh in world.build_roster(world.WEEK, with_preferred_extras=True, staff=staff):
        _, logical = world.shift_identity(outlet_key, "parity", sh.key)
        t = sh.template
        roster.append(
            Shift(
                logical,
                outlet_id,
                world.uid("employee", sh.employee) if sh.employee else None,
                world.SKILL[sh.skill],
                world.at(sh.day, t.start),
                world.at(sh.day, t.end),
                30 if t.break_start is not None else 0,
                world.at(sh.day, t.break_start) if t.break_start is not None else None,
            )
        )
    snap = Snapshot(
        outlet_id,
        world.WEEK,
        Policy(),
        {outlet_id: outlet},
        employees,
        {v: k for k, v in world.SKILL.items()},
        tuple(requirements),
    )
    return snap, roster


def test_validator_and_metrics_reproduce_the_published_fixture() -> None:
    version = json.loads((FIXTURES / "schedule_week.published.json").read_text())["response"]["body"][
        "current_version"
    ]
    snap, roster = world_snapshot()
    result = validator.validate(snap, roster)
    m = metrics.compute(snap, roster)
    expected = version["metrics"]
    assert result.hard == version["validation"]["hard_violations"] == 0
    assert (
        m.coverage_ratio,
        m.minimum_deficit_minutes,
        m.preferred_deficit_minutes,
        m.labour_cost_paise,
        m.overtime_cost_paise,
        m.overtime_minutes,
        m.preference_match_ratio,
        m.open_shifts,
        m.assigned_minutes,
    ) == (
        expected["coverage_ratio"],
        expected["minimum_deficit_minutes"],
        expected["preferred_deficit_minutes"],
        expected["labour_cost"]["amount_paise"],
        expected["overtime_cost"]["amount_paise"],
        expected["overtime_minutes"],
        expected["preference_match_ratio"],
        expected["open_shifts"],
        expected["assigned_minutes"],
    )
    live_cells = {
        (str(c.skill_id), c.interval_start, c.minimum_required, c.preferred_required, c.scheduled)
        for c in m.cells
    }
    fixture_cells = {
        (
            c["skill_id"],
            datetime.fromisoformat(c["interval_start"]),
            c["minimum_required"],
            c["preferred_required"],
            c["scheduled"],
        )
        for c in version["coverage"]
        if c["preferred_required"]
    }
    assert live_cells == fixture_cells
    live_soft = {(v.code, v.message, json.dumps(v.facts, sort_keys=True)) for v in result.violations}
    fixture_soft = {
        (v["code"], v["message"], json.dumps(v["facts"], sort_keys=True))
        for v in version["validation"]["violations"]
    }
    assert live_soft == fixture_soft


# ---------------------------------------------------------------- a tiny world for rule tests

IST = world.IST
OUT_A, OUT_B = uuid.uuid4(), uuid.uuid4()
GRILL, PREP = uuid.uuid4(), uuid.uuid4()
MON = date(2026, 10, 19)
ANY_TIME = tuple(Window(d, 0, 1440, "available") for d in range(7))


def emp(name: str = "Ravi", **kw: Any) -> Employee:
    base: dict[str, Any] = dict(
        id=uuid.uuid4(),
        name=name,
        home_outlet_id=OUT_A,
        status="active",
        skill_ids=frozenset({GRILL}),
        rate_paise_per_hour=21000,
        regular_weekly_minutes=2400,
        max_weekly_minutes=2880,
        overtime_allowed=False,
        windows=ANY_TIME,
    )
    return Employee(**{**base, **kw})


def at(day: int, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, 19, h, m, tzinfo=IST) + timedelta(days=day)


def shift(
    e: Employee | None,
    day: int,
    start: str,
    end: str,
    *,
    outlet: uuid.UUID = OUT_A,
    skill: uuid.UUID = GRILL,
    end_day: int | None = None,
    **kw: Any,
) -> Shift:
    return Shift(
        uuid.uuid4(),
        outlet,
        e.id if e else None,
        skill,
        at(day, start),
        at(end_day if end_day is not None else day, end),
        **kw,
    )


def snap(*employees: Employee, **kw: Any) -> Snapshot:
    outlets = {
        OUT_A: Outlet(OUT_A, "Indiranagar", world.TZ, {}),
        OUT_B: Outlet(OUT_B, "Koramangala", world.TZ, {}),
    }
    base: dict[str, Any] = dict(
        outlet_id=OUT_A,
        week_start=MON,
        policy=Policy(),
        outlets=outlets,
        employees={e.id: e for e in employees},
        skill_names={GRILL: "Grill", PREP: "Prep"},
        travel_minutes={(OUT_A, OUT_B): 35, (OUT_B, OUT_A): 35},
    )
    return Snapshot(**{**base, **kw})


def codes(snapshot: Snapshot, roster: list[Shift]) -> list[tuple[str, str]]:
    return sorted((v.code, v.severity) for v in validator.validate(snapshot, roster).violations)


def test_a_simple_valid_roster_has_no_violations() -> None:
    r = emp()
    assert codes(snap(r), [shift(r, 0, "10:00", "18:00"), shift(r, 1, "10:00", "18:00")]) == []


def test_skill_status_and_unknown_employee() -> None:
    r, gone = emp(), emp("Gone", status="inactive")
    stranger = emp("Stranger")
    assert codes(snap(r), [shift(r, 0, "10:00", "14:00", skill=PREP)]) == [("missing_skill", "hard")]
    assert codes(snap(gone), [shift(gone, 0, "10:00", "14:00")]) == [("inactive_employee", "hard")]
    assert codes(snap(r), [shift(stranger, 0, "10:00", "14:00")]) == [("inactive_employee", "hard")]


def test_availability_windows_including_past_midnight() -> None:
    evenings = emp(windows=(Window(0, 1020, 1500, "available"), Window(1, 0, 60, "unavailable")))
    assert codes(snap(evenings), [shift(evenings, 0, "17:00", "23:00")]) == []
    assert codes(snap(evenings), [shift(evenings, 0, "16:00", "23:00")]) == [("unavailable", "hard")]
    # Window allows until 01:00 next day, but Tuesday 00:00-01:00 is marked unavailable.
    assert codes(snap(evenings), [shift(evenings, 0, "20:00", "00:30", end_day=1)]) == [
        ("unavailable", "hard")
    ]
    nobody = emp(windows=())
    assert codes(snap(nobody), [shift(nobody, 0, "10:00", "12:00")]) == [("unavailable", "hard")]


def test_only_confirmed_absences_invalidate_shifts_even_locked_ones() -> None:
    r = emp()
    s = shift(r, 0, "10:00", "18:00", locked=True)
    requested = (Absence(r.id, at(0, "00:00"), at(1, "00:00"), "requested"),)
    confirmed = (Absence(r.id, at(0, "00:00"), at(1, "00:00"), "confirmed"),)
    assert codes(snap(r, absences=requested), [s]) == []
    result = validator.validate(snap(r, absences=confirmed), [s])
    assert [(v.code, v.facts["locked"]) for v in result.violations] == [("absent", True)]


def test_overlap_including_commitments_elsewhere() -> None:
    r = emp()
    assert codes(snap(r), [shift(r, 0, "10:00", "18:00"), shift(r, 0, "17:30", "20:00")]) == [
        ("overlap", "hard")
    ]
    elsewhere = (shift(r, 0, "12:00", "16:00", outlet=OUT_B),)
    assert codes(snap(r, commitments=elsewhere), [shift(r, 0, "10:00", "13:00")]) == [("overlap", "hard")]
    # Commitments that only clash with each other are not this roster's problem.
    clash = (shift(r, 3, "10:00", "14:00", outlet=OUT_B), shift(r, 3, "12:00", "16:00", outlet=OUT_B))
    assert codes(snap(r, commitments=clash), [shift(r, 0, "10:00", "13:00")]) == []


def test_rest_between_workdays_boundary() -> None:
    r = emp()
    nine_59 = [shift(r, 0, "13:00", "23:00"), shift(r, 1, "08:59", "12:00")]
    ten = [shift(r, 0, "13:00", "23:00"), shift(r, 1, "09:00", "12:00")]
    assert codes(snap(r, policy=Policy(grid_minutes=1)), nine_59) == [("insufficient_rest", "hard")]
    assert codes(snap(r, policy=Policy(grid_minutes=1)), ten) == []


def test_rest_across_the_week_boundary_uses_commitments() -> None:
    r = emp()
    last_week = (shift(r, -1, "15:00", "23:00"),)  # Sunday before the roster week
    assert codes(snap(r, commitments=last_week), [shift(r, 0, "08:00", "12:00")]) == [
        ("insufficient_rest", "hard")
    ]


def test_split_shift_same_day_uses_travel_time_not_rest() -> None:
    r = emp()
    p = Policy(grid_minutes=1)
    tight = [shift(r, 0, "10:00", "17:00"), shift(r, 0, "17:34", "21:00", outlet=OUT_B)]
    enough = [shift(r, 0, "10:00", "17:00"), shift(r, 0, "17:35", "21:00", outlet=OUT_B)]
    same_outlet = [shift(r, 0, "10:00", "14:00"), shift(r, 0, "14:00", "18:00")]
    assert codes(snap(r, policy=p), tight) == [("travel_time", "hard")]
    assert codes(snap(r, policy=p), enough) == []
    assert codes(snap(r, policy=p), same_outlet) == []


def week_of(e: Employee, hours_per_day: int, days: int) -> list[Shift]:
    return [shift(e, d, "08:00", f"{8 + hours_per_day:02d}:00") for d in range(days)]


def test_regular_threshold_permission_and_absolute_cap() -> None:
    strict = emp(regular_weekly_minutes=2400, max_weekly_minutes=2880, overtime_allowed=False)
    allowed = emp(regular_weekly_minutes=2400, max_weekly_minutes=2880, overtime_allowed=True)
    assert codes(snap(strict), week_of(strict, 9, 5)) == [("overtime", "hard")]  # 45h > 40h, no permission
    assert codes(snap(allowed), week_of(allowed, 9, 5)) == [("overtime", "soft")]
    # Exactly at the 48h absolute cap: still only (permitted) overtime.
    assert codes(snap(allowed), week_of(allowed, 8, 6)) == [("overtime", "soft")]
    # One hour over the cap: hard, and overtime permission does not lift it (decision 2).
    over = week_of(allowed, 8, 6) + [shift(allowed, 6, "08:00", "09:00")]
    assert codes(snap(allowed), over) == [("weekly_cap", "hard")]


def test_locked_shift_must_survive_unchanged() -> None:
    r, other = emp(), emp("Arjun")
    base = shift(r, 0, "10:00", "18:00", locked=True)
    moved = Shift(base.logical_id, OUT_A, other.id, GRILL, base.start_at, base.end_at, locked=True)
    s = snap(r, other, base_locked={base.logical_id: base})
    assert codes(s, [base]) == []
    assert codes(s, [moved]) == [("locked_changed", "hard")]
    assert codes(s, []) == [("locked_changed", "hard")]


def test_coverage_minimum_is_hard_preferred_is_soft_and_overstaffing_is_capped() -> None:
    r, k = emp(), emp("Karan")
    req = (Requirement(OUT_A, GRILL, at(0, "18:00"), at(0, "18:30"), 1, 2),)
    assert codes(snap(r, k, requirements=req), []) == [
        ("minimum_coverage", "hard"),
        ("preferred_coverage", "soft"),
    ]
    assert codes(snap(r, k, requirements=req), [shift(r, 0, "18:00", "20:00")]) == [
        ("preferred_coverage", "soft")
    ]
    extra = emp("Extra")
    full = [shift(e, 0, "18:00", "20:00") for e in (r, k, extra)]
    m = metrics.compute(snap(r, k, extra, requirements=req), full)
    assert m.coverage_ratio == 1.0 and m.preferred_deficit_minutes == 0


def test_breaks_reduce_productive_coverage() -> None:
    r = emp()
    req = (Requirement(OUT_A, GRILL, at(0, "14:00"), at(0, "14:30"), 1, 1),)
    on_break = shift(r, 0, "10:00", "18:00", break_minutes=30, break_start_at=at(0, "14:00"))
    assert codes(snap(r, requirements=req), [on_break]) == [
        ("minimum_coverage", "hard"),
        ("preferred_coverage", "soft"),
    ]


def test_grid_and_operating_hours() -> None:
    r = emp()
    assert codes(snap(r), [shift(r, 0, "10:15", "18:00")]) == [("outside_grid", "hard")]
    hours = {d: ((600, 1380),) for d in range(7)}
    outlets = {OUT_A: Outlet(OUT_A, "Indiranagar", world.TZ, hours), OUT_B: Outlet(OUT_B, "K", world.TZ, {})}
    assert codes(snap(r, outlets=outlets), [shift(r, 0, "09:00", "12:00")]) == [
        ("outside_operating_hours", "hard")
    ]


def test_open_shifts_are_counted_not_violations() -> None:
    m = metrics.compute(snap(), [shift(None, 0, "10:00", "18:00")])
    assert m.open_shifts == 1 and m.assigned_minutes == 0


def test_cost_rounding_and_overtime_premium() -> None:
    odd = emp(
        rate_paise_per_hour=17500, regular_weekly_minutes=60, max_weekly_minutes=2880, overtime_allowed=True
    )
    m = metrics.compute(snap(odd), [shift(odd, 0, "10:00", "11:30")])  # 90 min at Rs 175/h
    assert m.labour_cost_paise == 26250  # 90 * 17500 / 60
    assert m.overtime_minutes == 30
    assert m.overtime_cost_paise == 8750  # 30 min premium at 1.0x extra (2.0x multiplier)


def test_timestamps_in_any_offset_mean_the_same_instant() -> None:
    r = emp()
    utc = Shift(
        uuid.uuid4(), OUT_A, r.id, GRILL, at(0, "10:00").astimezone(UTC), at(0, "18:00").astimezone(UTC)
    )
    assert codes(snap(r), [utc]) == []
