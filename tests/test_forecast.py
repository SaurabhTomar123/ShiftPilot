"""A4.8: forecast producer and labour model (architecture v4 sections 21, 22). Pure."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from scheduling import demand, forecast

TZ = ZoneInfo("Asia/Kolkata")
WEEK = date(2026, 10, 19)
GRILL = uuid.uuid4()


def history(
    weeks: int, orders: Callable[[int, int, int], int] = lambda w, d, m: 10 + d
) -> dict[datetime, int]:
    out = {}
    for w in range(1, weeks + 1):
        for d in range(7):
            day = WEEK - timedelta(weeks=w) + timedelta(days=d)
            for m in (600, 630, 1140):
                at = datetime(day.year, day.month, day.day, tzinfo=TZ) + timedelta(minutes=m)
                out[at] = orders(w, d, m)
    return out


def test_median_of_the_same_weekday_and_time() -> None:
    hist = history(5, lambda w, d, m: [3, 9, 4, 100, 5][w - 1] if m == 1140 else 10)
    points = {p.interval_start: p for p in forecast.predict(hist, WEEK, TZ)}
    friday_7pm = datetime(2026, 10, 23, 19, 0, tzinfo=TZ)
    p = points[friday_7pm]
    assert (p.predicted, p.lower, p.upper, p.samples) == (5, 3, 100, 5)  # the outlier does not move it
    assert len(points) == 7 * 3


def test_too_little_history_is_refused() -> None:
    with pytest.raises(forecast.NotEnoughHistory):
        forecast.backtest(history(1), WEEK, TZ)
    assert forecast.predict(history(1), WEEK, TZ) == []  # one sample is not a forecast


def test_a_stable_pattern_passes_the_backtest_and_a_noisy_one_does_not() -> None:
    good = forecast.backtest(history(4), WEEK, TZ)
    assert good["passed"] and good["wape"] == 0 and good["weeks_evaluated"] == ["2026-10-05", "2026-10-12"]
    noisy = forecast.backtest(history(4, lambda w, d, m: 40 if w == 1 else 5), WEEK, TZ)
    assert not noisy["passed"] and noisy["wape"] > forecast.MAX_WAPE


def test_the_labour_model_explains_each_forecast_row_and_skips_manual_intervals() -> None:
    points = forecast.predict(history(4, lambda w, d, m: 21 if m == 1140 else 4), WEEK, TZ)
    blocks = [demand.Block(d, 600, 1200, GRILL, 1, 1) for d in range(7)]
    bands = [demand.Band(GRILL, 0, 39, 1, 2), demand.Band(GRILL, 40, None, 3, 4)]
    manual = {(GRILL, datetime(2026, 10, 19, 19, 0, tzinfo=TZ))}
    rows = forecast.propose(points, WEEK, TZ, blocks, bands, manual)
    by = {(r["interval_start"]): r for r in rows}
    busy = by[datetime(2026, 10, 20, 19, 0, tzinfo=TZ).isoformat()]
    assert busy["source"] == "forecast" and (busy["minimum"], busy["preferred"]) == (3, 4)
    assert busy["explanation"] == {
        "forecast_orders": 21,
        "orders_per_hour": 42,
        "band_min_orders": 40,
        "band_max_orders": None,
    }
    assert datetime(2026, 10, 19, 19, 0, tzinfo=TZ).isoformat() not in by  # the manual override survives
    quiet = by[datetime(2026, 10, 20, 11, 0, tzinfo=TZ).isoformat()]
    assert quiet["source"] == "template" and "explanation" not in quiet  # no forecast for 11:00
