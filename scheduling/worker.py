"""Optimization worker (B2.3; architecture sections 7-11).

    python -m scheduling.worker                  # serve interactive, then batch, forever
    python -m scheduling.worker --once           # process at most one run, then exit (tests, cron)

Claims runs with SKIP LOCKED leases (database clock only), renews the lease while solving, and writes
results in one transaction fenced by (lease_owner, attempts, job_state='running'): a worker that lost its
lease discards its output and writes nothing. Exhausted retries are failed by the sweeper.

Uses the admin connection because it works across tenants; a dedicated least-privilege worker role is a
deployment follow-up (B6.3).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import socket
import threading
import time
import uuid
from typing import Any

from sqlalchemy import Engine, text

from db.session import admin_engine
from scheduling import metrics, snapshot_json, solver, validator
from scheduling.model import Snapshot

log = logging.getLogger("shiftpilot.worker")
LEASE_SECONDS = 30
RENEW_SECONDS = 10
MAX_ATTEMPTS = 3
LANES = ("interactive", "batch")

CLAIM = text("""
    UPDATE optimization_runs r
       SET job_state = 'running', lease_owner = :me, lease_until = now() + make_interval(secs => :lease),
           attempts = r.attempts + 1, started_at = coalesce(r.started_at, now())
     WHERE r.id = (
             SELECT id FROM optimization_runs
              WHERE lane = :lane
                AND (job_state = 'queued' OR (job_state = 'running' AND lease_until < now()))
                AND attempts < :max_attempts
              ORDER BY priority, queued_at
              FOR UPDATE SKIP LOCKED
              LIMIT 1)
 RETURNING r.id, r.org_id, r.attempts, r.input_snapshot, r.config, r.strategy, r.base_version_ids, r.input_hash
""")
RENEW = text("""UPDATE optimization_runs SET lease_until = now() + make_interval(secs => :lease)
                 WHERE id = :id AND lease_owner = :me AND attempts = :attempt AND job_state = 'running'""")
FENCE = text("""UPDATE optimization_runs
                   SET job_state = :state, solver_status = :status, finished_at = now(), solver_wall_ms = :wall,
                       objective = :objective, best_bound = :bound, stats = CAST(:stats AS jsonb),
                       error = CAST(:error AS jsonb), lease_until = NULL
                 WHERE id = :id AND lease_owner = :me AND attempts = :attempt AND job_state = 'running'
             RETURNING id""")


def worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


class Lease:
    """Renews the lease on its own connection while the solver runs."""

    def __init__(self, engine: Engine, run_id: uuid.UUID, me: str, attempt: int) -> None:
        self.engine, self.run_id, self.me, self.attempt = engine, run_id, me, attempt
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self.stop.wait(RENEW_SECONDS):
            with self.engine.begin() as conn:
                conn.execute(
                    RENEW, {"lease": LEASE_SECONDS, "id": self.run_id, "me": self.me, "attempt": self.attempt}
                )

    def __enter__(self) -> Lease:
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop.set()
        self.thread.join()


def sweep(engine: Engine) -> int:
    """Fail runs whose lease expired after the last allowed attempt, releasing their slots."""
    with engine.begin() as conn:
        ids = list(
            conn.execute(
                text("""
            UPDATE optimization_runs SET job_state = 'failed', finished_at = now(), lease_until = NULL,
                   error = '{"code": "internal", "message": "The optimizer stopped repeatedly. Try again.",
                             "retryable": true, "details": {"reason": "ATTEMPTS_EXHAUSTED"}}'::jsonb
             WHERE job_state = 'running' AND lease_until < now() AND attempts >= :max
         RETURNING id, org_id"""),
                {"max": MAX_ATTEMPTS},
            )
        )
        for run_id, org_id in ids:
            _release(conn, run_id, org_id, "failed")
    return len(ids)


def _release(conn: Any, run_id: uuid.UUID, org_id: uuid.UUID, state: str) -> None:
    conn.execute(text("DELETE FROM schedule_run_slots WHERE run_id = :id"), {"id": run_id})
    conn.execute(
        text("""INSERT INTO outbox_events (id, org_id, topic, aggregate_type, aggregate_id, payload)
                         VALUES (:id, :org, 'run.finished', 'optimization_run', :run, CAST(:payload AS jsonb))"""),
        {"id": uuid.uuid7(), "org": org_id, "run": run_id, "payload": json.dumps({"job_state": state})},
    )


def _persist_candidates(conn: Any, row: Any, snap: Snapshot, outcome: solver.Outcome) -> None:
    schedule_id = uuid.UUID(row.config["schedule_id"])
    conn.execute(text("SELECT id FROM schedules WHERE id = :s FOR UPDATE"), {"s": schedule_id})
    number = conn.execute(
        text("SELECT coalesce(max(version_number), 0) FROM schedule_versions WHERE schedule_id = :s"),
        {"s": schedule_id},
    ).scalar_one()
    base_id = row.base_version_ids[0] if row.base_version_ids else None
    base_keys: set[tuple[Any, ...]] = set()
    if base_id:
        base_keys = {
            tuple(r)
            for r in conn.execute(
                text(
                    "SELECT logical_shift_id, employee_id, skill_id, start_at, end_at FROM version_shifts WHERE version_id = :v"
                ),
                {"v": base_id},
            )
        }
    for rank, cand in enumerate(outcome.candidates, start=1):
        number += 1
        version_id = uuid.uuid7()
        conn.execute(
            text("""INSERT INTO schedule_versions (id, org_id, schedule_id, version_number, status, source,
                                 reason, base_version_id, optimization_run_id, input_hash)
                             VALUES (:id, :org, :s, :n, 'draft', 'generate', :reason, :base, :run, :hash)"""),
            {
                "id": version_id,
                "org": row.org_id,
                "s": schedule_id,
                "n": number,
                "base": base_id,
                "reason": f"Generated ({cand.strategy.replace('_', ' ')})",
                "run": row.id,
                "hash": row.input_hash,
            },
        )
        new_logical = [sh for sh in cand.roster if sh.logical_id not in snap.base_locked]
        if new_logical:
            conn.execute(
                text("""INSERT INTO logical_shifts (id, org_id, schedule_id, created_in_version_id)
                                 VALUES (:id, :org, :s, :v)"""),
                [
                    {"id": sh.logical_id, "org": row.org_id, "s": schedule_id, "v": version_id}
                    for sh in new_logical
                ],
            )
        conn.execute(
            text("""INSERT INTO version_shifts (id, org_id, schedule_id, version_id, logical_shift_id, outlet_id,
                                 employee_id, skill_id, start_at, end_at, break_start_at, break_minutes, locked, lock_reason)
                             VALUES (:id, :org, :s, :v, :l, :o, :e, :k, :a, :b, :bs, :bm, :locked, :reason)"""),
            [
                {
                    "id": uuid.uuid7(),
                    "org": row.org_id,
                    "s": schedule_id,
                    "v": version_id,
                    "l": sh.logical_id,
                    "o": sh.outlet_id,
                    "e": sh.employee_id,
                    "k": sh.skill_id,
                    "a": sh.start_at,
                    "b": sh.end_at,
                    "bs": sh.break_start_at,
                    "bm": sh.break_minutes,
                    "locked": sh.locked,
                    "reason": "Locked by manager" if sh.locked else None,
                }
                for sh in cand.roster
            ],
        )
        result = validator.validate(snap, cand.roster)
        changed = sum(
            1
            for sh in cand.roster
            if (sh.logical_id, sh.employee_id, sh.skill_id, sh.start_at, sh.end_at) not in base_keys
        )
        key = sorted((str(sh.employee_id), sh.start_at.isoformat(), str(sh.skill_id)) for sh in cand.roster)
        conn.execute(
            text("""INSERT INTO optimization_candidates (id, org_id, run_id, rank, strategy, solver_status,
                                 proven_optimal, objective_components, metrics, diff, draft_version_id, validation,
                                 explanation_facts, dedup_hash)
                             VALUES (:id, :org, :run, :rank, :strategy, :status, :optimal, CAST(:components AS jsonb),
                                     CAST(:metrics AS jsonb), CAST(:diff AS jsonb), :v, CAST(:validation AS jsonb),
                                     '{}'::jsonb, :hash)
                             ON CONFLICT (run_id, dedup_hash) DO NOTHING"""),
            {
                "id": uuid.uuid7(),
                "org": row.org_id,
                "run": row.id,
                "rank": rank,
                "strategy": cand.strategy,
                "status": cand.status,
                "optimal": cand.proven_optimal,
                "components": json.dumps(cand.components),
                "metrics": json.dumps(metrics.as_contract(metrics.compute(snap, cand.roster))),
                "diff": json.dumps({"changed_shifts": changed}),
                "v": version_id,
                "validation": json.dumps(validator.as_contract(result)),
                "hash": hashlib.sha256(json.dumps(key).encode()).hexdigest(),
            },
        )


def process(engine: Engine, row: Any, me: str) -> str:
    """Solve one claimed run and write its result if this worker still holds the lease."""
    error: dict[str, Any] | None = None
    outcome: solver.Outcome | None = None
    snap: Snapshot | None = None
    with Lease(engine, row.id, me, row.attempts):
        try:
            snap = snapshot_json.load(row.input_snapshot)
            outcome = solver.generate(
                snap,
                row.strategy,
                time_limit=float(row.config["time_limit_seconds"]),
                seed=int(row.config.get("seed", 7)),
                workers=int(row.config.get("workers", 4)),
            )
        except Exception:  # the job failed; the error is recorded, not raised into the loop
            log.exception("run %s failed", row.id)
            error = {
                "code": "internal",
                "message": "The optimizer stopped unexpectedly. Try again.",
                "retryable": True,
                "details": {},
            }
    with engine.begin() as conn:
        if outcome is None or snap is None or outcome.status == "MODEL_INVALID":
            state, status, stats = "failed", outcome.status if outcome else None, {}
            error = error or {
                "code": "internal",
                "message": "The optimizer could not build a model for this input.",
                "retryable": False,
                "details": {},
            }
        else:
            state, status = "succeeded", outcome.status
            stats = dict(outcome.stats)
            if outcome.status == "INFEASIBLE":
                stats["infeasibility"] = {
                    "summary": outcome.summary or "No roster satisfies every rule.",
                    "shortages": [
                        {
                            "outlet_id": str(snap.outlet_id),
                            "skill_id": str(sh.skill_id),
                            "interval_start": sh.interval_start.isoformat(),
                            "interval_end": sh.interval_end.isoformat(),
                            "minimum_required": sh.minimum_required,
                            "max_assignable": sh.max_assignable,
                        }
                        for sh in outcome.shortages
                    ],
                }
        best = outcome.candidates[0] if outcome and outcome.candidates else None
        won = conn.execute(
            FENCE,
            {
                "state": state,
                "status": status,
                "wall": outcome.wall_ms if outcome else None,
                "objective": best.objective if best else None,
                "bound": best.bound if best else None,
                "stats": json.dumps(stats),
                "error": json.dumps(error) if error else None,
                "id": row.id,
                "me": me,
                "attempt": row.attempts,
            },
        ).first()
        if won is None:
            conn.rollback()
            log.warning("run %s: lease lost; discarding this attempt's output", row.id)
            return "lost_lease"
        if state == "succeeded" and outcome and snap and outcome.candidates:
            _persist_candidates(conn, row, snap, outcome)
        _release(conn, row.id, row.org_id, state)
    return state


def run_once(
    engine: Engine | None = None, me: str | None = None, lanes: tuple[str, ...] = LANES
) -> uuid.UUID | None:
    engine = engine or admin_engine()
    me = me or worker_id()
    sweep(engine)
    for lane in lanes:
        with engine.begin() as conn:
            row = conn.execute(
                CLAIM, {"me": me, "lease": LEASE_SECONDS, "lane": lane, "max_attempts": MAX_ATTEMPTS}
            ).first()
        if row is not None:
            process(engine, row, me)
            claimed: uuid.UUID = row.id
            return claimed
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--lanes", default=",".join(LANES), help="claim order, e.g. interactive or interactive,batch"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    lanes = tuple(x for x in args.lanes.split(",") if x)
    me = worker_id()
    if args.once:
        run_once(me=me, lanes=lanes)
        return 0
    log.info("worker %s serving lanes %s", me, lanes)
    while True:
        if run_once(me=me, lanes=lanes) is None:
            time.sleep(1.0)  # NOTIFY is only a wake-up hint; polling bounds the delay to ~1 s


if __name__ == "__main__":
    raise SystemExit(main())
