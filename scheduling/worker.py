"""Optimization worker (B2.3; architecture v3 sections 27-30).

    python -m scheduling.worker                  # process pool of 2; slot 0 only takes repairs
    python -m scheduling.worker --processes 3
    python -m scheduling.worker --once           # process at most one run, then exit (tests, cron)

Claims by priority (repairs first) and kind. With N processes at most N-1 take batch work, so one slot is
always free for an absence repair; physically separate pools are a scaling option, not an MVP need.

Claims runs with SKIP LOCKED leases (database clock only), renews the lease while solving, and writes
results in one transaction fenced by (lease_owner, attempts, job_state='running'): a worker that lost its
lease discards its output and writes nothing. Exhausted retries are failed by the sweeper.

Connects as the least-privilege shiftpilot_worker role (WORKER_DATABASE_URL, migration 0015): it bypasses
row-level security to work across tenants but can only touch runs, base shifts, candidates and the outbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import multiprocessing
import os
import socket
import threading
import time
import uuid
from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy import Engine, text

from db.session import worker_engine
from scheduling import metrics, repair, snapshot_json, solver, trace, validator
from scheduling.model import Shift, Snapshot

log = logging.getLogger("shiftpilot.worker")
LEASE_SECONDS = 30
RENEW_SECONDS = 10
MAX_ATTEMPTS = 3
ALL_KINDS = ("repair", "generate", "optimize", "scenario")  # one process stays REPAIR_ONLY
REPAIR_ONLY = ("repair",)

CLAIM = text("""
    UPDATE optimization_runs r
       SET job_state = 'running', lease_owner = :me, lease_until = now() + make_interval(secs => :lease),
           attempts = r.attempts + 1, started_at = coalesce(r.started_at, now())
     WHERE r.id = (
             SELECT id FROM optimization_runs
              WHERE kind = ANY(:kinds)
                AND (job_state = 'queued' OR (job_state = 'running' AND lease_until < now()))
                AND attempts < :max_attempts
              ORDER BY priority, queued_at
              FOR UPDATE SKIP LOCKED
              LIMIT 1)
 RETURNING r.id, r.org_id, r.kind, r.attempts, r.input_snapshot, r.config, r.strategy, r.base_version_ids, r.input_hash
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
    conn.execute(
        text("""INSERT INTO outbox_events (id, org_id, topic, aggregate_type, aggregate_id, payload)
                         VALUES (:id, :org, 'run.finished', 'optimization_run', :run, CAST(:payload AS jsonb))"""),
        {"id": uuid.uuid7(), "org": org_id, "run": run_id, "payload": json.dumps({"job_state": state})},
    )


def _persist_candidates(
    conn: Any,
    row: Any,
    snap: Snapshot,
    outcome: solver.Outcome,
    extras: dict[int, dict[str, Any]] | None = None,
) -> None:
    """Store candidates as diffs against the base version (architecture v3 section 23).

    Nothing is written to schedule_versions or logical_shifts here: selecting a candidate materializes
    it into a draft. extras: per-rank repair data ({'disruption': ..., 'explanations': [...]})."""
    base_id = row.base_version_ids[0] if row.base_version_ids else None
    base: list[Shift] = []
    if base_id:
        base = [
            Shift(
                r.logical_shift_id,
                r.outlet_id,
                r.employee_id,
                r.skill_id,
                r.start_at,
                r.end_at,
                r.break_minutes,
                r.break_start_at,
                r.locked,
            )
            for r in conn.execute(
                text("""SELECT logical_shift_id, outlet_id, employee_id, skill_id, start_at, end_at,
                               break_minutes, break_start_at, locked
                          FROM version_shifts WHERE version_id = :v"""),
                {"v": base_id},
            )
        ]
    for rank, cand in enumerate(outcome.candidates, start=1):
        doc = snapshot_json.candidate_diff(base, cand.roster)
        changed = len(doc["added"]) + len(doc["changed"]) + len(doc["removed"])
        if extras and "disruption" in extras.get(rank, {}):
            doc["disruption"] = extras[rank]["disruption"]
        key = sorted((str(sh.employee_id), sh.start_at.isoformat(), str(sh.skill_id)) for sh in cand.roster)
        conn.execute(
            text("""INSERT INTO optimization_candidates (id, org_id, run_id, rank, strategy, solver_status,
                                 proven_optimal, objective_components, metrics, diff, validation,
                                 explanation_facts, dedup_hash)
                             VALUES (:id, :org, :run, :rank, :strategy, :status, :optimal, CAST(:components AS jsonb),
                                     CAST(:metrics AS jsonb), CAST(:diff AS jsonb), CAST(:validation AS jsonb),
                                     CAST(:facts AS jsonb), :hash)
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
                "diff": json.dumps({"changed_shifts": changed, **doc}),
                "facts": json.dumps(
                    {k: v for k, v in (extras or {}).get(rank, {}).items() if k in ("explanations", "trace")}
                ),
                "validation": json.dumps(validator.as_contract(validator.validate(snap, cand.roster))),
                "hash": hashlib.sha256(json.dumps(key).encode()).hexdigest(),
            },
        )


def _explanations_json(plan: repair.Plan) -> list[dict[str, Any]]:
    return [repair.explanation_json(e) for e in plan.explanations]


def _traces(
    snap: Snapshot,
    outcome: solver.Outcome,
    base: list[Shift],
    extras: dict[int, dict[str, Any]],
    *,
    explain: bool,
    exclude: frozenset[uuid.UUID] = frozenset(),
) -> dict[int, dict[str, Any]]:
    """Decision trace per candidate (v4 section 18), computed before the result transaction opens."""
    requested = list(outcome.candidates[0].roster) if outcome.candidates else None
    for rank, cand in enumerate(outcome.candidates, start=1):
        trace_doc, rows, explanations = trace.build(
            snap,
            cand.strategy,
            base,
            list(cand.roster),
            None if rank == 1 else requested,
            explain=explain,
            exclude=exclude,
        )
        entry = extras.setdefault(rank, {})
        entry["trace"] = {**trace_doc, "changes": rows}
        if explain and "explanations" not in entry:
            entry["explanations"] = explanations
    return extras


def _run_repair(snap: Snapshot, row: Any) -> tuple[solver.Outcome, dict[int, dict[str, Any]]]:
    """Run absence repair and present it as an Outcome, so persistence and the run view are shared.

    A plan that cannot keep minimum staffing is not offered as a candidate: the run is INFEASIBLE and
    reports the remaining shortages (decision 1: partial rosters must visibly report their gaps)."""
    doc = row.input_snapshot["repair"]
    base = [snapshot_json.shift_from_doc(d) for d in doc["base"]]
    absence = snapshot_json.absence_from_doc(doc["absence"])
    result = repair.repair(
        snap,
        base,
        absence,
        unlocked={uuid.UUID(u) for u in doc["unlocked"]},
        time_limit=float(row.config["time_limit_seconds"]),
        workers=int(row.config.get("workers", 8)),
        allow_cross_outlet=bool(doc.get("allow_cross_outlet", False)),
    )
    outcome = solver.Outcome(
        status=result.status, stats={"repair": result.stats, "widening": result.widening}
    )
    if result.status == "LOCK_CONFLICT":
        outcome.stats["lock_conflict"] = {
            "locked_logical_shift_ids": [str(s.logical_id) for s in result.locked_conflicts]
        }
        return outcome, {}
    with_absence = replace(snap, absences=(*snap.absences, absence))
    extras: dict[int, dict[str, Any]] = {}
    for plan in result.plans:
        if metrics.compute(with_absence, list(plan.roster)).minimum_deficit_minutes:
            continue
        outcome.candidates.append(
            solver.Candidate(
                plan.profile,
                plan.status,
                plan.roster,
                0,
                0,
                {k: v.get("value") or 0 for k, v in plan.stages.items()},
            )
        )
        extras[len(outcome.candidates)] = {
            "disruption": plan.disruption,
            "explanations": _explanations_json(plan),
        }
    if result.plans and not outcome.candidates:
        best = metrics.compute(with_absence, list(result.plans[0].roster))
        merged: list[solver.Shortage] = []
        for c in (c for c in best.cells if c.scheduled < c.minimum_required):
            end = c.interval_start + timedelta(minutes=30)
            last = merged[-1] if merged else None
            if last and last.skill_id == c.skill_id and last.interval_end == c.interval_start:
                merged[-1] = replace(last, interval_end=end)
            else:
                merged.append(
                    solver.Shortage(c.skill_id, c.interval_start, end, c.minimum_required, c.scheduled)
                )
        outcome.status = "INFEASIBLE"
        outcome.shortages = merged
        outcome.summary = (
            solver.describe(snap, outcome.shortages[0]).replace("qualified employee", "available employee")
            if outcome.shortages
            else "No replacement keeps minimum staffing."
        )
    elif outcome.candidates:
        outcome.status = outcome.candidates[0].status
    if outcome.candidates:
        # Repair explanations already exist per changed shift; the trace adds taxonomy and summary.
        _traces(with_absence, outcome, base, extras, explain=False)
        for entry in extras.values():
            entry["trace"]["explained_shifts"] = len(entry.get("explanations", []))
    return outcome, extras


def process(engine: Engine, row: Any, me: str) -> str:
    """Solve one claimed run and write its result if this worker still holds the lease."""
    error: dict[str, Any] | None = None
    outcome: solver.Outcome | None = None
    snap: Snapshot | None = None
    extras: dict[int, dict[str, Any]] | None = None
    with Lease(engine, row.id, me, row.attempts):
        try:
            snap = snapshot_json.load(row.input_snapshot)
            if row.kind == "repair":
                outcome, extras = _run_repair(snap, row)
            else:
                extras = None
                outcome = solver.generate(
                    snap,
                    row.strategy,
                    time_limit=float(row.config["time_limit_seconds"]),
                    seed=int(row.config.get("seed", 7)),
                    workers=int(row.config.get("workers", 4)),
                    # Evaluation mode: reproducible from (input_hash, config); production leaves it unset.
                    deterministic_time=row.config.get("deterministic_time"),
                )
                base = [*snap.base, *snap.base_locked.values()]
                extras = _traces(snap, outcome, base, {}, explain=True)
        except Exception:  # the job failed; the error is recorded, not raised into the loop
            log.exception("run %s failed", row.id)
            error = {
                "code": "internal",
                "message": "The optimizer stopped unexpectedly. Try again.",
                "retryable": True,
                "details": {},
            }
    with engine.begin() as conn:
        if outcome is not None and outcome.status == "LOCK_CONFLICT":
            state, status, stats = "failed", None, dict(outcome.stats)
            error = {
                "code": "conflict",
                "retryable": False,
                "details": stats.get("lock_conflict", {}),
                "message": "A locked shift is affected. Authorize changing it and repair again.",
            }
        elif outcome is None or snap is None or outcome.status == "MODEL_INVALID":
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
                    "conflict_set": stats.pop("conflict_set", []),
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
                    "options": [
                        {
                            "kind": r.kind,
                            "summary": r.summary,
                            "employees": [
                                {"employee_id": str(e), "name": n, "home_outlet_id": str(o), "minutes": m}
                                for e, n, o, m in r.employees
                            ],
                            "shortages": [
                                {
                                    "outlet_id": str(snap.outlet_id),
                                    "skill_id": str(g.skill_id),
                                    "interval_start": g.interval_start.isoformat(),
                                    "interval_end": g.interval_end.isoformat(),
                                    "minimum_required": g.minimum_required,
                                    "max_assignable": g.max_assignable,
                                }
                                for g in r.shortages
                            ],
                        }
                        for r in outcome.relaxations
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
            _persist_candidates(conn, row, snap, outcome, extras)
        _release(conn, row.id, row.org_id, state)
    return state


def run_once(
    engine: Engine | None = None, me: str | None = None, kinds: tuple[str, ...] = ALL_KINDS
) -> uuid.UUID | None:
    engine = engine or worker_engine()
    me = me or worker_id()
    sweep(engine)
    with engine.begin() as conn:
        row = conn.execute(
            CLAIM, {"me": me, "lease": LEASE_SECONDS, "kinds": list(kinds), "max_attempts": MAX_ATTEMPTS}
        ).first()
    if row is None:
        return None
    process(engine, row, me)
    claimed: uuid.UUID = row.id
    return claimed


def serve(kinds: tuple[str, ...]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    me = worker_id()
    log.info("worker %s claiming %s", me, ",".join(kinds))
    while True:
        if run_once(me=me, kinds=kinds) is None:
            time.sleep(1.0)  # NOTIFY is only a wake-up hint; polling bounds the delay to ~1 s


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--processes", type=int, default=2, help="pool size; at least 2 in deployments")
    args = parser.parse_args()
    if args.once:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        run_once()
        return 0
    if args.processes < 2:
        serve(ALL_KINDS)
        return 0
    procs = [
        multiprocessing.Process(target=serve, args=(REPAIR_ONLY if i == 0 else ALL_KINDS,), daemon=True)
        for i in range(args.processes)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
