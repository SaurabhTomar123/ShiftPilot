"""Availability-change impact (architecture v4 section 29). Pure.

Recurring availability is not silently replaced: a requested change can invalidate shifts that are
already published. impact() lists exactly those shifts, using the validator's own availability rule, so
the manager sees what accepting would break before deciding.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import tzinfo

from scheduling.model import Shift, Window
from scheduling.validator import available_in


def impact(windows: Iterable[Window], shifts: Iterable[Shift], tz: tzinfo) -> list[Shift]:
    """Shifts the person could no longer work under `windows` (outlet-local), in time order."""
    windows = tuple(windows)
    out = []
    for sh in shifts:
        local = sh.start_at.astimezone(tz)
        s = local.hour * 60 + local.minute
        e = s + int((sh.end_at - sh.start_at).total_seconds() // 60)
        if not available_in(windows, local.weekday(), s, e):
            out.append(sh)
    return sorted(out, key=lambda sh: (sh.start_at, str(sh.logical_id)))
