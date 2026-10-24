"""Demand forecast producer and labour model (architecture v4 sections 21, 22). Pure.

Forecasting is advisory: a forecast predicts orders, the labour model (the outlet's demand bands) turns
predicted orders into proposed staffing, and a manager accepts or rejects that proposal. Nothing here
writes staffing requirements.

Model weekday-median-v1: for each 30-minute interval of the target week, the median of the same weekday
and local time over the last WINDOW_WEEKS weeks of history (at least MIN_WEEKS samples). The interval is
[min, max] of those samples: with eight samples an honest range, not a fitted distribution.

Quality is measured by backtest before anyone sees a proposal: each of the last BACKTEST_WEEKS weeks is
forecast from the weeks before it and compared with what happened (WAPE, MAE, bias). A forecast that
misses the gate is kept for inspection but produces no proposal.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduling import demand

MODEL_VERSION = "weekday-median-v1"
WINDOW_WEEKS = 8
MIN_WEEKS = 2
BACKTEST_WEEKS = 2
MAX_WAPE = 0.35  # weighted absolute percentage error across the backtest weeks
MAX_BIAS = 0.15  # |sum(forecast - actual)| / sum(actual)


@dataclass(frozen=True)
class Point:
    interval_start: datetime
    predicted: int
    lower: int
    upper: int
    samples: int


class NotEnoughHistory(ValueError):
    pass


def _key(t: datetime, tz: ZoneInfo) -> tuple[int, int]:
    local = t.astimezone(tz)
    return local.weekday(), local.hour * 60 + local.minute


def _midnight(day: date, tz: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=tz)


def predict(
    history: Mapping[datetime, int], week_start: date, tz: ZoneInfo, window: int = WINDOW_WEEKS
) -> list[Point]:
    """Points for the target week from the `window` weeks of history before it."""
    start = _midnight(week_start, tz)
    since = start - timedelta(weeks=window)
    samples: dict[tuple[int, int], list[int]] = defaultdict(list)
    for t, orders in history.items():
        if since <= t < start:
            samples[_key(t, tz)].append(orders)
    out = []
    for (weekday, minute), values in sorted(samples.items()):
        if len(values) < MIN_WEEKS:
            continue
        at = _midnight(week_start + timedelta(days=weekday), tz) + timedelta(minutes=minute)
        out.append(Point(at, round(statistics.median(values)), min(values), max(values), len(values)))
    return out


def backtest(
    history: Mapping[datetime, int], week_start: date, tz: ZoneInfo, weeks: int = BACKTEST_WEEKS
) -> dict[str, Any]:
    """Forecast each of the last `weeks` weeks from the weeks before it; compare with the actuals."""
    abs_err = signed = actual_total = n = 0
    evaluated = []
    for back in range(weeks, 0, -1):
        target = week_start - timedelta(weeks=back)
        actual = {
            t: v
            for t, v in history.items()
            if _midnight(target, tz) <= t < _midnight(target, tz) + timedelta(days=7)
        }
        points = {p.interval_start: p.predicted for p in predict(history, target, tz)}
        common = [t for t in actual if t in points]
        if not common:
            continue
        evaluated.append(target.isoformat())
        for t in common:
            abs_err += abs(points[t] - actual[t])
            signed += points[t] - actual[t]
            actual_total += actual[t]
            n += 1
    if not n:
        raise NotEnoughHistory(
            f"Needs at least {MIN_WEEKS + 1} weeks of order history before this week to forecast and test it."
        )
    wape = abs_err / actual_total if actual_total else 0.0
    bias = signed / actual_total if actual_total else 0.0
    return {
        "model_version": MODEL_VERSION,
        "weeks_evaluated": evaluated,
        "intervals": n,
        "wape": round(wape, 4),
        "mae": round(abs_err / n, 2),
        "bias": round(bias, 4),
        "passed": wape <= MAX_WAPE and abs(bias) <= MAX_BIAS,
        "thresholds": {"max_wape": MAX_WAPE, "max_bias": MAX_BIAS},
    }


def propose(
    points: Iterable[Point],
    week_start: date,
    tz: ZoneInfo,
    blocks: Iterable[demand.Block],
    bands: Iterable[demand.Band],
    manual: set[tuple[UUID, datetime]],
) -> list[dict[str, Any]]:
    """The labour model: template blocks, with each band skill replaced where orders are forecast.
    Rows carry their explanation ("42 orders/30 min -> 84/h -> band 60-99 -> 3 / 4"). Manual intervals
    are left out: they survive acceptance untouched."""
    bands = list(bands)
    predicted = {p.interval_start: p.predicted for p in points}
    rows = demand.expand(week_start, tz, list(blocks), bands=bands, orders=predicted, manual=manual)
    out = []
    for r in rows:
        row: dict[str, Any] = {
            "skill_id": str(r.skill_id),
            "interval_start": r.interval_start.isoformat(),
            "interval_end": r.interval_end.isoformat(),
            "minimum": r.minimum,
            "preferred": r.preferred,
            "source": "forecast" if r.source == "band" else r.source,
        }
        if r.source == "band":
            orders = predicted[r.interval_start]
            per_hour = orders * 60 // demand.GRID
            band = next(b for b in bands if b.skill_id == r.skill_id and b.covers(per_hour))
            row["explanation"] = {
                "forecast_orders": orders,
                "orders_per_hour": per_hour,
                "band_min_orders": band.min_orders,
                "band_max_orders": band.max_orders,
            }
        out.append(row)
    return out
