"""B2.3: generation requests and run status (architecture sections 7-11).

The run row is the job. Enqueue validates the request, captures the input snapshot in one REPEATABLE READ
transaction, inserts the run and its admission slot, and NOTIFYs workers, all atomically: there is no
second write to a broker that could fail after commit.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from importlib.metadata import version as package_version
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, _outlet, week_bounds
from core.auth import Caller, assert_outlet
from db.models import Outlet
from db.models_v2 import OptimizationCandidate, OptimizationRun, Schedule, ScheduleRunSlot, VersionShift
from db.session import tenant_session
from scheduling import snapshot_db, snapshot_json

ACTIVE = ("queued", "running")
ORG_ACTIVE_CAP = 5
RETRY_AFTER_SECONDS = 3
SOLVER_WORKERS = 4


def _request_hash(outlet_id: uuid.UUID, week_start: date, body: s.GenerateRequest) -> str:
    raw = json.dumps(
        {"outlet": str(outlet_id), "week": week_start.isoformat(), **body.model_dump(mode="json")},
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def run_view(session: Session, run: OptimizationRun) -> s.OptimizationRun:
    outlet = session.get(Outlet, run.outlet_ids[0])
    tz = ZoneInfo(outlet.timezone if outlet else "UTC")
    candidates = list(
        session.scalars(
            select(OptimizationCandidate)
            .where(OptimizationCandidate.run_id == run.id)
            .order_by(OptimizationCandidate.rank)
        )
    )
    infeasibility = (run.stats or {}).get("infeasibility") if run.solver_status == "INFEASIBLE" else None
    return s.OptimizationRun.model_validate(
        {
            "id": run.id,
            "kind": run.kind,
            "outlet_ids": run.outlet_ids,
            "base_version_ids": run.base_version_ids,
            "strategy": run.strategy,
            "job_state": run.job_state,
            "solver_status": run.solver_status,
            "input_hash": run.input_hash,
            "queued_at": run.queued_at.astimezone(tz),
            "started_at": run.started_at.astimezone(tz) if run.started_at else None,
            "finished_at": run.finished_at.astimezone(tz) if run.finished_at else None,
            "solver_wall_ms": run.solver_wall_ms,
            "poll_after_ms": (300 if run.lane == "interactive" else 500) if run.job_state in ACTIVE else None,
            "candidates": [
                {
                    "id": c.id,
                    "rank": c.rank,
                    "strategy": c.strategy,
                    "solver_status": c.solver_status,
                    "proven_optimal": c.proven_optimal,
                    "draft_version_id": c.draft_version_id,
                    "metrics": c.metrics,
                    "changed_shifts": c.diff.get("changed_shifts", 0),
                    "validation": c.validation,
                }
                for c in candidates
            ],
            "infeasibility": infeasibility,
            "error": run.error,
        }
    )


def enqueue(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, key: str, body: s.GenerateRequest
) -> s.OptimizationRun:
    require(caller, "generate")
    request_hash = _request_hash(outlet_id, week_start, body)
    org = uuid.UUID(caller.org_id)
    with tenant_session(caller, "REPEATABLE READ") as session:
        outlet = _outlet(session, caller, outlet_id)
        week_bounds(outlet, week_start)
        existing = session.scalars(
            select(OptimizationRun).where(OptimizationRun.idempotency_key == key)
        ).first()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ApiError(
                    "idempotency_conflict",
                    "This request key was already used with different input.",
                    run_id=str(existing.id),
                )
            return run_view(session, existing)

        session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"runs:{org}"})
        active = (
            session.scalar(
                select(func.count()).select_from(OptimizationRun).where(OptimizationRun.job_state.in_(ACTIVE))
            )
            or 0
        )
        if active >= ORG_ACTIVE_CAP:
            raise ApiError(
                "rate_limited",
                "Too many optimizations are running. Try again shortly.",
                retryable=True,
                headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
                retry_after_ms=RETRY_AFTER_SECONDS * 1000,
            )

        session.execute(
            pg_insert(Schedule)
            .values(id=uuid.uuid7(), org_id=org, outlet_id=outlet_id, week_start=week_start)
            .on_conflict_do_nothing(index_elements=["org_id", "outlet_id", "week_start"])
        )
        schedule = session.scalars(
            select(Schedule).where(Schedule.outlet_id == outlet_id, Schedule.week_start == week_start)
        ).first()
        if schedule is None:  # created concurrently after this transaction's snapshot
            raise ApiError(
                "conflict", "The schedule was just created by another request. Try again.", retryable=True
            )
        if body.base_version_id != schedule.current_version_id:
            raise ApiError(
                "stale_version",
                "The schedule changed since you opened it. Reload and try again.",
                current_version_id=str(schedule.current_version_id) if schedule.current_version_id else None,
            )
        slot = session.get(ScheduleRunSlot, (org, schedule.id))
        if slot is not None:
            raise ApiError(
                "run_in_progress",
                "An optimization is already running for this week. Showing its progress.",
                run_id=str(slot.run_id),
            )

        locked = []
        if schedule.current_version_id:
            locked = [
                snapshot_db.to_shift(r)
                for r in session.scalars(
                    select(VersionShift).where(
                        VersionShift.version_id == schedule.current_version_id, VersionShift.locked
                    )
                )
            ]
        snap = snapshot_db.load(session, outlet_id, week_start, locked, schedule.id)
        snap = snapshot_db.with_base_locks(snap, locked)
        doc = snapshot_json.dump(snap)
        run = OptimizationRun(
            id=uuid.uuid7(),
            org_id=org,
            kind="generate",
            lane="batch",
            priority=100,
            strategy=body.strategy,
            outlet_ids=[outlet_id],
            base_version_ids=[schedule.current_version_id] if schedule.current_version_id else [],
            requested_by_user_id=uuid.UUID(caller.user_id),
            idempotency_key=key,
            request_hash=request_hash,
            job_state="queued",
            input_hash=snapshot_json.digest(doc),
            input_snapshot=doc,
            config={
                "strategy": body.strategy,
                "time_limit_seconds": body.time_limit_seconds,
                "seed": 7,
                "workers": SOLVER_WORKERS,
                "ortools_version": package_version("ortools"),
                "snapshot_schema_version": snapshot_json.SCHEMA_VERSION,
                "schedule_id": str(schedule.id),
            },
        )
        session.add(run)
        session.flush()
        session.add(ScheduleRunSlot(org_id=org, schedule_id=schedule.id, run_id=run.id))
        try:
            session.flush()
        except IntegrityError as exc:  # a concurrent request won the slot after our snapshot was taken
            raise ApiError(
                "run_in_progress", "An optimization is already running for this week. Showing its progress."
            ) from exc
        _audit(session, caller, "OPTIMIZATION_REQUESTED", "optimization_run", run.id, None, None)
        session.execute(text("NOTIFY optimization_runs"))
        session.flush()
        session.refresh(run)
        return run_view(session, run)


def get_run(caller: Caller, run_id: uuid.UUID) -> s.OptimizationRun:
    with tenant_session(caller) as session:
        run = session.get(OptimizationRun, run_id)
        if run is None:
            raise not_found("Optimization run")
        for outlet_id in run.outlet_ids:
            assert_outlet(caller, str(outlet_id))
        return run_view(session, run)
