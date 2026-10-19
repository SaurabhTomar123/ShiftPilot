"""Apply manual edits to a roster (pure). The API maps contract ShiftEdit models onto these ops.

Edits never decide validity: a rule-breaking edit is applied and the independent validator reports it.
Only structural problems are refused here (unknown shift, end before start, break outside the shift).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from scheduling.model import Shift


class EditError(ValueError):
    def __init__(self, index: int, message: str) -> None:
        super().__init__(message)
        self.index, self.message = index, message


@dataclass(frozen=True)
class Edit:
    op: str  # add | update | remove | lock | unlock
    logical_id: uuid.UUID | None = None
    fields: dict[str, Any] | None = None  # add: full shift; update: only the changed fields


def _check(index: int, sh: Shift) -> Shift:
    if sh.end_at <= sh.start_at:
        raise EditError(index, "A shift must end after it starts.")
    if sh.end_at - sh.start_at > timedelta(hours=16):
        raise EditError(index, "A shift can be at most 16 hours long.")
    if (
        sh.break_minutes
        and sh.break_start_at is not None
        and not (
            sh.start_at <= sh.break_start_at
            and sh.break_start_at + timedelta(minutes=sh.break_minutes) <= sh.end_at
        )
    ):
        raise EditError(index, "The break must fall inside the shift.")
    if not sh.break_minutes and sh.break_start_at is not None:
        return replace(sh, break_start_at=None)
    return sh


def apply(
    roster: Iterable[Shift],
    edits: list[Edit],
    outlet_id: uuid.UUID,
    new_id: Callable[[], uuid.UUID] = uuid.uuid7,
) -> list[Shift]:
    shifts = {s.logical_id: s for s in roster}
    for i, e in enumerate(edits):
        if e.op == "add":
            f = e.fields or {}
            sh = Shift(
                new_id(),
                outlet_id,
                f.get("employee_id"),
                f["skill_id"],
                f["start_at"],
                f["end_at"],
                f.get("break_minutes", 0),
                f.get("break_start_at"),
                bool(f.get("locked", False)),
            )
            shifts[sh.logical_id] = _check(i, sh)
            continue
        current = shifts.get(e.logical_id) if e.logical_id else None
        if current is None:
            raise EditError(i, "That shift is not in this draft.")
        if e.op == "remove":
            del shifts[current.logical_id]
        elif e.op in ("lock", "unlock"):
            shifts[current.logical_id] = replace(current, locked=e.op == "lock")
        elif e.op == "update":
            changes = dict(e.fields or {})
            moved_by = None
            if (
                "start_at" in changes
                and "break_start_at" not in changes
                and current.break_start_at is not None
            ):
                start: datetime = changes["start_at"]
                moved_by = start - current.start_at
            if moved_by is not None and current.break_start_at is not None:
                changes["break_start_at"] = current.break_start_at + moved_by
            shifts[current.logical_id] = _check(i, replace(current, **changes))
        else:
            raise EditError(i, f"Unknown edit {e.op!r}.")
    return sorted(shifts.values(), key=lambda s: (s.start_at, str(s.logical_id)))
