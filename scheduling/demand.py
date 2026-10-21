"""StaffingRequirementService.expand (architecture v3 section 18). Pure.

    weekly staffing template (weekday x block x skill -> minimum / preferred)
        + optional demand bands (orders/hour -> staff), when the outlet tracks orders
        -> date-specific 30-minute requirements (source template | band)
        -> manual overrides per interval win and are never regenerated

Overlapping template blocks for the same skill take the larger requirement. A band replaces the template
value for its skill in intervals that have an order count. Intervals that need nobody produce no row.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

GRID = 30


@dataclass(frozen=True)
class Block:
    weekday: int  # Monday = 0
    start_minute: int
    end_minute: int
    skill_id: UUID
    minimum: int
    preferred: int


@dataclass(frozen=True)
class Band:
    skill_id: UUID
    min_orders: int  # orders per hour, inclusive
    max_orders: int | None  # inclusive; None = no upper bound
    minimum: int
    preferred: int

    def covers(self, orders_per_hour: int) -> bool:
        return self.min_orders <= orders_per_hour and (
            self.max_orders is None or orders_per_hour <= self.max_orders
        )


@dataclass(frozen=True)
class Requirement:
    skill_id: UUID
    interval_start: datetime
    interval_end: datetime
    minimum: int
    preferred: int
    source: str  # template | band


def overlapping(blocks: Iterable[Block]) -> list[tuple[Block, Block]]:
    """Pairs of blocks on the same weekday and skill whose times overlap (rejected when saving a set)."""
    out = []
    items = sorted(blocks, key=lambda b: (b.weekday, str(b.skill_id), b.start_minute))
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if (b.weekday, b.skill_id) != (a.weekday, a.skill_id) or b.start_minute >= a.end_minute:
                break
            out.append((a, b))
    return out


def expand(
    week_start: date,
    tz: ZoneInfo,
    blocks: Iterable[Block],
    *,
    bands: Iterable[Band] = (),
    orders: Mapping[datetime, int] | None = None,
    manual: set[tuple[UUID, datetime]] | None = None,
) -> list[Requirement]:
    """orders: order count per 30-minute interval start. manual: (skill, interval start) kept as is."""
    manual = manual or set()
    wanted: dict[tuple[UUID, datetime], tuple[int, int, str]] = {}
    for day in (week_start + timedelta(days=d) for d in range(7)):
        midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
        for b in blocks:
            if b.weekday != day.weekday():
                continue
            for m in range(b.start_minute, b.end_minute, GRID):
                key = (b.skill_id, midnight + timedelta(minutes=m))
                old = wanted.get(key)
                if old is None or (b.minimum, b.preferred) > old[:2]:
                    wanted[key] = (b.minimum, b.preferred, "template")
    by_skill: dict[UUID, list[Band]] = {}
    for band in bands:
        by_skill.setdefault(band.skill_id, []).append(band)
    week_end = datetime(week_start.year, week_start.month, week_start.day, tzinfo=tz) + timedelta(days=7)
    for start, count in (orders or {}).items():
        if not (week_end - timedelta(days=7) <= start < week_end):
            continue
        per_hour = count * 60 // GRID
        for skill, skill_bands in by_skill.items():
            match = next((b for b in skill_bands if b.covers(per_hour)), None)
            if match is not None:
                wanted[skill, start] = (match.minimum, match.preferred, "band")
    return [
        Requirement(skill, start, start + timedelta(minutes=GRID), mn, pref, source)
        for (skill, start), (mn, pref, source) in sorted(
            wanted.items(), key=lambda kv: (kv[0][1], str(kv[0][0]))
        )
        if (skill, start) not in manual and (mn or pref)
    ]
