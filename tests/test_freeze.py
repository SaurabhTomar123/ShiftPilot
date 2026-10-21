"""A4.1 (architecture v4 section 13): run-scoped freeze sets and pinning."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from scheduling import freeze, solver
from scheduling.model import Absence
from seed import world
from seed.world_snapshot import build, greedy_roster


def test_a_spec_resolves_to_base_shifts() -> None:
    snap, base = build(), greedy_roster()
    tz = snap.outlet.tz
    first = next(s for s in base if s.employee_id)
    monday = world.NEXT_WEEK
    spec = freeze.Spec(
        shift_ids=frozenset({first.logical_id}),
        employee_ids=frozenset({first.employee_id}),  # type: ignore[arg-type]
        days=frozenset({monday}),
    )
    got = freeze.resolve(spec, base, tz)
    assert first.logical_id in got
    assert {s.logical_id for s in base if s.employee_id == first.employee_id} <= got
    assert {s.logical_id for s in base if s.start_at.astimezone(tz).date() == monday} <= got
    assert freeze.unknown(freeze.Spec(shift_ids=frozenset({world.uid("x", "y")})), base) == {
        world.uid("x", "y")
    }


def test_regeneration_holds_frozen_shifts_exactly() -> None:
    snap, base = build(), tuple(greedy_roster())
    frozen = frozenset(s.logical_id for s in base[::5])
    out = solver.generate(
        replace(snap, base=base, frozen=frozen), "lowest_cost", time_limit=6.0, max_candidates=1
    )
    assert out.candidates
    kept = {(s.logical_id, s.employee_id, s.start_at, s.end_at) for s in out.candidates[0].roster}
    assert all(
        (s.logical_id, s.employee_id, s.start_at, s.end_at) in kept for s in base if s.logical_id in frozen
    )


def test_a_fact_that_breaks_a_pin_is_surfaced() -> None:
    snap, base = build(), greedy_roster()
    pinned = next(s for s in base if s.employee_id)
    sick = Absence(pinned.employee_id, pinned.start_at - timedelta(hours=1), pinned.end_at, "confirmed")  # type: ignore[arg-type]
    assert freeze.conflicts(replace(snap, absences=(sick,)), base, frozenset({pinned.logical_id})) == [pinned]
    assert freeze.conflicts(snap, base, frozenset({pinned.logical_id})) == []
