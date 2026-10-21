"""True fairness: historical burden (architecture v4 section 12). Pure.

Revision 3 rightly refused to call hours alignment "fairness". Revision 4 measures who carries the
undesirable work over a rolling window, the history plus the candidate week:

    burden[e]            = weighted count of undesirable assignment components (POLICY)
    normalized_burden[e] = burden[e] per 40 hours of regular capacity
    fairness_penalty     = sum_e |normalized_burden[e] - mean|      (absolute deviation: solver-friendly)

Protected attributes are never used. The component weights are versioned policy, not hidden model
behaviour. Last-minute changes are a v4 component that needs change timestamps; they are not counted
yet.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling.model import Shift


@dataclass(frozen=True)
class Policy:
    version: int = 1
    closing: int = 3  # the shift ends at or after 22:00, or crosses midnight
    weekend: int = 2  # the shift starts on a Saturday or Sunday
    split: int = 2  # a second shift on the same day
    overtime_hour: int = 1  # each full hour beyond the regular week (metric only; the solver costs it)
    closing_minute: int = 22 * 60


POLICY = Policy()
WINDOW_WEEKS = 8
PER_MINUTES = 2400  # normalize to burden per 40 hours of regular capacity


def shift_burden(sh: Shift, tz: ZoneInfo, policy: Policy = POLICY) -> int:
    """The per-shift components (closing, weekend); split and overtime need the whole week."""
    start, end = sh.start_at.astimezone(tz), sh.end_at.astimezone(tz)
    closing = end.date() > start.date() or end.hour * 60 + end.minute >= policy.closing_minute
    return policy.closing * closing + policy.weekend * (start.weekday() >= 5)


def burden(
    shifts: Iterable[Shift], tz: ZoneInfo, regular: Mapping[UUID, int] | None = None, policy: Policy = POLICY
) -> dict[UUID, int]:
    """Burden per employee for a set of shifts (one or more weeks)."""
    out: dict[UUID, int] = defaultdict(int)
    per_day: dict[tuple[UUID, object], int] = defaultdict(int)
    per_week: dict[tuple[UUID, object], int] = defaultdict(int)
    for sh in shifts:
        if sh.employee_id is None:
            continue
        local = sh.start_at.astimezone(tz)
        out[sh.employee_id] += shift_burden(sh, tz, policy)
        per_day[sh.employee_id, local.date()] += 1
        per_week[sh.employee_id, local.isocalendar()[:2]] += sh.paid_minutes
    for (emp, _), count in per_day.items():
        out[emp] += policy.split * max(0, count - 1)
    if regular is not None:
        for (emp, _), minutes in per_week.items():
            over = minutes - regular.get(emp, minutes)
            out[emp] += policy.overtime_hour * max(0, over // 60)
    return dict(out)


def deviation(people: Mapping[UUID, int], burdens: Mapping[UUID, int]) -> float | None:
    """Mean absolute deviation of burden per 40 hours. people: employee -> regular weekly minutes."""
    if len(people) < 2:
        return None
    norm = {e: burdens.get(e, 0) * PER_MINUTES / max(1, cap) for e, cap in people.items()}
    mean = sum(norm.values()) / len(norm)
    return round(sum(abs(v - mean) for v in norm.values()) / len(norm), 2)


def merged(history: Mapping[UUID, int], current: Mapping[UUID, int]) -> dict[UUID, int]:
    return {e: history.get(e, 0) + current.get(e, 0) for e in {*history, *current}}
