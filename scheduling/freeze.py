"""Run-scoped freeze sets and pinning (architecture v4 section 13). Pure.

A manager protects commitments before optimizing: a pinned shift, an employee's week, or a whole day is
held exactly as published for this run. The freeze set is compiled to fixed assignments (the solver
treats frozen base shifts like locked ones) and stored on the run, but nothing is persisted as a lock.

A hard fact can invalidate a pin (the pinned person is now absent): that conflict is surfaced and needs
explicit authorization; it is never silently ignored.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling import validator
from scheduling.model import Shift, Snapshot

# Per-shift facts that make a frozen assignment unworkable (coverage and weekly totals are not per-shift).
BREAKING = frozenset({"absent", "unavailable", "missing_skill", "inactive_employee", "rule"})


@dataclass(frozen=True)
class Spec:
    """What the manager asked to protect. Every field selects base (published) shifts."""

    shift_ids: frozenset[UUID] = field(default_factory=frozenset)  # logical shift ids
    employee_ids: frozenset[UUID] = field(default_factory=frozenset)
    days: frozenset[date] = field(default_factory=frozenset)  # outlet-local

    @property
    def empty(self) -> bool:
        return not (self.shift_ids or self.employee_ids or self.days)


def resolve(spec: Spec, base: Iterable[Shift], tz: ZoneInfo) -> frozenset[UUID]:
    """The logical ids of the base shifts the spec protects."""
    return frozenset(
        s.logical_id
        for s in base
        if s.logical_id in spec.shift_ids
        or (s.employee_id is not None and s.employee_id in spec.employee_ids)
        or s.start_at.astimezone(tz).date() in spec.days
    )


def unknown(spec: Spec, base: Iterable[Shift]) -> frozenset[UUID]:
    """Pinned shift ids that are not in the base version."""
    return spec.shift_ids - {s.logical_id for s in base}


def conflicts(snap: Snapshot, base: Iterable[Shift], frozen: frozenset[UUID]) -> list[Shift]:
    """Frozen shifts that current facts already break, e.g. a pinned employee with a confirmed absence."""
    shifts = [s for s in base if s.logical_id in frozen]
    bad = {
        lid
        for v in validator.validate(snap, shifts).violations
        if v.severity == "hard" and v.code in BREAKING
        for lid in v.logical_shift_ids
    }
    return [s for s in shifts if s.logical_id in bad]
