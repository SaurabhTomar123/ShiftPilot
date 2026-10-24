"""Forecast worker (architecture v4 sections 21, 37): claims forecast_runs, forecasts, backtests and, when
the backtest passes, proposes staffing requirements.

    python -m jobs.forecast_worker           # serve
    python -m jobs.forecast_worker --once    # claim and process one run

It is separate from the optimization worker so a forecast failure can never stop scheduling, and it
shares the same discipline: claim with SKIP LOCKED, a lease, and an attempt-fenced write so a late or
duplicate worker writes nothing. The run carries its own input; the worker reads no other table and
never touches staffing_requirements.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, text

from db.session import worker_engine
from scheduling import demand, forecast
from scheduling.worker import LEASE_SECONDS, MAX_ATTEMPTS, worker_id

log = logging.getLogger("shiftpilot.forecast_worker")
IDLE_SECONDS = 2.0

CLAIM = text("""
    UPDATE forecast_runs r
       SET job_state = 'running', lease_owner = :me, lease_until = now() + make_interval(secs => :lease),
           attempts = r.attempts + 1, started_at = coalesce(r.started_at, now())
     WHERE r.id = (
             SELECT id FROM forecast_runs
              WHERE (job_state = 'queued' OR (job_state = 'running' AND lease_until < now()))
                AND attempts < :max_attempts
              ORDER BY queued_at
              FOR UPDATE SKIP LOCKED
              LIMIT 1)
 RETURNING r.id, r.org_id, r.outlet_id, r.week_start, r.attempts, r.input
""")
FINISH = text("""UPDATE forecast_runs
                    SET job_state = :state, metrics = CAST(:metrics AS jsonb), quality = :quality,
                        error = CAST(:error AS jsonb), finished_at = now(), lease_until = NULL
                  WHERE id = :id AND lease_owner = :me AND attempts = :attempt AND job_state = 'running'
              RETURNING id""")
SWEEP = text("""UPDATE forecast_runs SET job_state = 'failed', finished_at = now(), lease_until = NULL,
                       error = '{"code": "internal", "message": "The forecast stopped repeatedly. Try again.",
                                 "retryable": true, "details": {"reason": "ATTEMPTS_EXHAUSTED"}}'::jsonb
                 WHERE job_state = 'running' AND lease_until < now() AND attempts >= :max""")


def compute(doc: dict[str, Any]) -> dict[str, Any]:
    """Pure: forecast points, backtest metrics and (if the gate passes) proposal rows."""
    tz = ZoneInfo(doc["tz"])
    week_start = date.fromisoformat(doc["week_start"])
    history = {datetime.fromisoformat(t): int(v) for t, v in doc["history"]}
    try:
        metrics = forecast.backtest(history, week_start, tz)
    except forecast.NotEnoughHistory as exc:
        return {
            "state": "failed",
            "error": {
                "code": "validation_failed",
                "message": str(exc),
                "retryable": False,
                "details": {"reason": "NOT_ENOUGH_HISTORY"},
            },
        }
    points = forecast.predict(history, week_start, tz)
    rows = None
    if metrics["passed"]:
        rows = forecast.propose(
            points,
            week_start,
            tz,
            [demand.Block(wd, s, e, uuid.UUID(k), mn, pf) for wd, s, e, k, mn, pf in doc["blocks"]],
            [demand.Band(uuid.UUID(k), lo, hi, mn, pf) for k, lo, hi, mn, pf in doc["bands"]],
            {(uuid.UUID(k), datetime.fromisoformat(t)) for k, t in doc["manual"]},
        )
    return {"state": "succeeded", "metrics": metrics, "points": points, "rows": rows}


def process(engine: Engine, row: Any, me: str) -> str:
    try:
        result = compute(row.input)
    except Exception:  # recorded, not raised into the loop
        log.exception("forecast run %s failed", row.id)
        result = {
            "state": "failed",
            "error": {
                "code": "internal",
                "message": "The forecast stopped unexpectedly. Try again.",
                "retryable": True,
                "details": {},
            },
        }
    metrics = result.get("metrics")
    with engine.begin() as conn:
        won = conn.execute(
            FINISH,
            {
                "state": result["state"],
                "metrics": json.dumps(metrics) if metrics else None,
                "quality": ("passed" if metrics["passed"] else "failed") if metrics else None,
                "error": json.dumps(result["error"]) if result.get("error") else None,
                "id": row.id,
                "me": me,
                "attempt": row.attempts,
            },
        ).first()
        if won is None:
            conn.rollback()
            log.warning("forecast run %s: lease lost; discarding this attempt's output", row.id)
            return "lost_lease"
        points = result.get("points") or []
        if points:
            conn.execute(
                text("""INSERT INTO demand_forecasts
                               (org_id, run_id, interval_start, predicted, lower, upper, samples)
                        VALUES (:org, :run, :t, :p, :lo, :hi, :n)"""),
                [
                    {
                        "org": row.org_id,
                        "run": row.id,
                        "t": p.interval_start,
                        "p": p.predicted,
                        "lo": p.lower,
                        "hi": p.upper,
                        "n": p.samples,
                    }
                    for p in points
                ],
            )
        if result.get("rows") is not None:
            conn.execute(
                text("""INSERT INTO staffing_requirement_proposals
                               (id, org_id, outlet_id, week_start, forecast_run_id,
                                base_demand_revision, rows)
                        VALUES (:id, :org, :outlet, :week, :run, :rev, CAST(:rows AS jsonb))"""),
                {
                    "id": uuid.uuid7(),
                    "org": row.org_id,
                    "outlet": row.outlet_id,
                    "week": row.week_start,
                    "run": row.id,
                    "rev": int(row.input["base_demand_revision"]),
                    "rows": json.dumps(result["rows"]),
                },
            )
    return str(result["state"])


def run_once(engine: Engine | None = None, me: str | None = None) -> uuid.UUID | None:
    engine = engine or worker_engine()
    me = me or worker_id()
    with engine.begin() as conn:
        conn.execute(SWEEP, {"max": MAX_ATTEMPTS})
        row = conn.execute(CLAIM, {"me": me, "lease": LEASE_SECONDS, "max_attempts": MAX_ATTEMPTS}).first()
    if row is None:
        return None
    process(engine, row, me)
    return uuid.UUID(str(row.id))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.once:
        run_once()
        return 0
    me = worker_id()
    log.info("forecast worker %s serving", me)
    while True:
        if run_once(me=me) is None:
            time.sleep(IDLE_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
