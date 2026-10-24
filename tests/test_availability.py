"""A4.8: availability-change impact (architecture v4 section 29). Pure."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scheduling import availability
from scheduling.model import Shift, Window

TZ = ZoneInfo("Asia/Kolkata")


def shift(day: int, start: int, minutes: int = 480) -> Shift:
    at = datetime(2026, 10, 26, tzinfo=TZ) + timedelta(days=day, minutes=start)
    return Shift(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), at, at + timedelta(minutes=minutes))


def test_only_shifts_outside_the_new_windows_are_affected() -> None:
    windows = [Window(d, 540, 1320, "available") for d in range(7) if d != 2]  # no longer Wednesdays
    windows.append(Window(4, 1080, 1320, "unavailable"))  # nor Friday evenings
    monday, wednesday, friday_day, friday_late = (
        shift(0, 600),
        shift(2, 600),
        shift(4, 600, 420),
        shift(4, 720),
    )
    hit = availability.impact(windows, [friday_late, monday, wednesday, friday_day], TZ)
    assert hit == [wednesday, friday_late]  # in time order; Monday and Friday daytime still fit
