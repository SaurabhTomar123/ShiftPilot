"""Typed differences between two rosters, keyed on logical shift identity (contract ShiftChange)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from scheduling.model import Shift


@dataclass(frozen=True)
class Change:
    logical_id: UUID
    kinds: tuple[str, ...]
    before: Shift | None
    after: Shift | None


def kinds(before: Shift, after: Shift) -> tuple[str, ...]:
    out = []
    if before.employee_id != after.employee_id:
        out.append("reassigned")
    duration_before = before.end_at - before.start_at
    duration_after = after.end_at - after.start_at
    if before.start_at != after.start_at and duration_before == duration_after:
        out.append("moved")
    elif (before.start_at, before.end_at) != (after.start_at, after.end_at):
        out.append("resized")
    if before.skill_id != after.skill_id:
        out.append("role_changed")
    if before.locked != after.locked:
        out.append("lock_changed")
    if (
        (before.break_start_at, before.break_minutes) != (after.break_start_at, after.break_minutes)
        and "moved" not in out
        and "resized" not in out
    ):
        out.append("break_changed")
    return tuple(out)


def diff(before: list[Shift] | tuple[Shift, ...], after: list[Shift] | tuple[Shift, ...]) -> list[Change]:
    """Changes turning `before` into `after`, ordered by time (removed shifts by their old time)."""
    old = {s.logical_id: s for s in before}
    new = {s.logical_id: s for s in after}
    changes = []
    for lid in old.keys() | new.keys():
        a, b = old.get(lid), new.get(lid)
        if a is None and b is not None:
            changes.append(Change(lid, ("added",), None, b))
        elif b is None and a is not None:
            changes.append(Change(lid, ("removed",), a, None))
        elif a is not None and b is not None and (k := kinds(a, b)):
            changes.append(Change(lid, k, a, b))
    changes.sort(key=lambda c: ((c.after or c.before).start_at, str(c.logical_id)))  # type: ignore[union-attr]
    return changes
