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
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, _outlet, week_bounds
from core.auth import Caller, Role, assert_outlet
from db.models import Outlet
from db.models_v2 import Absence as AbsenceRow
from db.models_v2 import OptimizationCandidate, OptimizationRun, Schedule, VersionShift
from db.session import tenant_session
from scheduling import repair, snapshot_db, snapshot_json
from scheduling.model import Absence, Shift

ACTIVE = ("queued", "running")
BATCH_PRIORITY, REPAIR_PRIORITY = 5, 1  # lower is claimed first (v3 section 28)
ORG_ACTIVE_CAP = 10  # architecture v3 section 28 (lower for demo organizations later)
RETRY_AFTER_SECONDS = 3
SOLVER_WORKERS = 8  # 4 workers lack the bound-improving strategies; see docs/runbooks/solver-benchmark.md


def _request_hash(outlet_id: uuid.UUID, week_start: date, body: BaseModel) -> str:
    raw = json.dumps(
        {"outlet": str(outlet_id), "week": week_start.isoformat(), **body.model_dump(mode="json")},
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def candidate_fields(c: OptimizationCandidate) -> dict[str, Any]:
    """The contract Candidate (summary) fields; the full diff is served by getOptimizationCandidate."""
    return {
        "id": c.id,
        "rank": c.rank,
        "strategy": c.strategy,
        "solver_status": c.solver_status,
        "proven_optimal": c.proven_optimal,
        "materialized_version_id": c.materialized_version_id,
        "metrics": c.metrics,
        "changed_shifts": c.diff.get("changed_shifts", 0),
        "validation": c.validation,
        "disruption": c.diff.get("disruption"),
        "explanations": (c.explanation_facts or {}).get("explanations", []),
    }


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
            "absence_id": (run.config or {}).get("absence_id"),
            "job_state": run.job_state,
            "solver_status": run.solver_status,
            "input_hash": run.input_hash,
            "queued_at": run.queued_at.astimezone(tz),
            "started_at": run.started_at.astimezone(tz) if run.started_at else None,
            "finished_at": run.finished_at.astimezone(tz) if run.finished_at else None,
            "solver_wall_ms": run.solver_wall_ms,
            "poll_after_ms": (300 if run.kind == "repair" else 500) if run.job_state in ACTIVE else None,
            "candidates": [candidate_fields(c) for c in candidates],
            "infeasibility": infeasibility,
            "error": run.error,
            "repair_stages": (run.stats or {}).get("widening", []) if run.kind == "repair" else [],
        }
    )


def _admit(
    session: Session,
    caller: Caller,
    outlet_id: uuid.UUID,
    week_start: date,
    key: str,
    request_hash: str,
    base_version_id: uuid.UUID | None,
    kind: str = "generate",
) -> tuple[OptimizationRun | None, Schedule]:
    """Idempotency, org cap, schedule and base check (architecture v3 section 28).

    Runs are read-only, so only duplicated work is refused: a second active generate/optimize run on
    the same schedule (409 run_in_progress). Repairs are never blocked by batch work."""
    org = uuid.UUID(caller.org_id)
    outlet = _outlet(session, caller, outlet_id)
    week_bounds(outlet, week_start)
    existing = session.scalars(select(OptimizationRun).where(OptimizationRun.idempotency_key == key)).first()
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ApiError(
                "idempotency_conflict",
                "This request key was already used with different input.",
                run_id=str(existing.id),
            )
        return existing, session.get(Schedule, uuid.UUID(existing.config["schedule_id"]))  # type: ignore[return-value]
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
    if base_version_id != schedule.current_version_id:
        raise ApiError(
            "stale_version",
            "The schedule changed since you opened it. Reload and try again.",
            current_version_id=str(schedule.current_version_id) if schedule.current_version_id else None,
        )
    if kind in ("generate", "optimize"):
        running_batch = session.scalars(
            select(OptimizationRun).where(
                OptimizationRun.schedule_id == schedule.id,
                OptimizationRun.kind.in_(("generate", "optimize")),
                OptimizationRun.job_state.in_(ACTIVE),
            )
        ).first()
        if running_batch is not None:
            raise ApiError(
                "run_in_progress",
                "An optimization is already running for this week. Showing its progress.",
                run_id=str(running_batch.id),
            )
    return None, schedule


def _insert(
    session: Session,
    caller: Caller,
    schedule: Schedule,
    *,
    kind: str,
    priority: int,
    trigger_absence_id: uuid.UUID | None = None,
    strategy: str,
    doc: dict[str, Any],
    config: dict[str, Any],
    key: str,
    request_hash: str,
) -> OptimizationRun:
    run = OptimizationRun(
        id=uuid.uuid7(),
        org_id=schedule.org_id,
        kind=kind,
        priority=priority,
        schedule_id=schedule.id,
        trigger_absence_id=trigger_absence_id,
        strategy=strategy,
        outlet_ids=[schedule.outlet_id],
        base_version_ids=[schedule.current_version_id] if schedule.current_version_id else [],
        requested_by_user_id=uuid.UUID(caller.user_id),
        idempotency_key=key,
        request_hash=request_hash,
        job_state="queued",
        input_hash=snapshot_json.digest(doc),
        input_snapshot=doc,
        config={
            "seed": 7,
            "workers": SOLVER_WORKERS,
            "ortools_version": package_version("ortools"),
            "snapshot_schema_version": snapshot_json.SCHEMA_VERSION,
            "schedule_id": str(schedule.id),
            **config,
        },
    )
    session.add(run)
    try:
        session.flush()  # the partial unique indexes enforce one active batch run / one repair per absence
    except IntegrityError as exc:  # a concurrent request won after this transaction's snapshot
        raise ApiError(
            "run_in_progress",
            "An optimization is already running for this work. Showing its progress.",
            retryable=True,
        ) from exc
    _audit(session, caller, "OPTIMIZATION_REQUESTED", "optimization_run", run.id, None, None)
    session.execute(text("NOTIFY optimization_runs"))
    session.flush()
    session.refresh(run)
    return run


def _current_shifts(session: Session, schedule: Schedule, *, locked_only: bool = False) -> list[Shift]:
    if not schedule.current_version_id:
        return []
    query = select(VersionShift).where(VersionShift.version_id == schedule.current_version_id)
    if locked_only:
        query = query.where(VersionShift.locked)
    return [snapshot_db.to_shift(r) for r in session.scalars(query)]


def enqueue(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, key: str, body: s.GenerateRequest
) -> s.OptimizationRun:
    require(caller, "generate")
    request_hash = _request_hash(outlet_id, week_start, body)
    with tenant_session(caller, "REPEATABLE READ") as session:
        existing, schedule = _admit(
            session, caller, outlet_id, week_start, key, request_hash, body.base_version_id
        )
        if existing is not None:
            return run_view(session, existing)
        base = _current_shifts(session, schedule)
        locked = [x for x in base if x.locked]
        snap = snapshot_db.with_base_locks(
            snapshot_db.load(session, outlet_id, week_start, base, schedule.id), locked, base
        )
        run = _insert(
            session,
            caller,
            schedule,
            kind="generate",
            priority=BATCH_PRIORITY,
            strategy=body.strategy,
            doc=snapshot_json.dump(snap),
            key=key,
            request_hash=request_hash,
            config={"strategy": body.strategy, "time_limit_seconds": body.time_limit_seconds},
        )
        return run_view(session, run)


def repair_in_session(
    session: Session,
    caller: Caller,
    absence: AbsenceRow,
    schedule: Schedule,
    *,
    key: str,
    request_hash: str,
    unlocked: set[uuid.UUID],
    time_limit_seconds: int,
    allow_cross_outlet: bool = False,
) -> OptimizationRun:
    """Enqueue (or return) the repair run for one confirmed absence on one schedule (v3 section 20).

    One active repair per absence: an existing active run is returned. A locked affected shift without
    explicit authorization is a 409 conflict listing those shifts (decision 5)."""
    active = session.scalars(
        select(OptimizationRun).where(
            OptimizationRun.trigger_absence_id == absence.id, OptimizationRun.job_state.in_(ACTIVE)
        )
    ).first()
    if active is not None:
        return active
    base = _current_shifts(session, schedule)
    model_absence = Absence(absence.employee_id, absence.start_at, absence.end_at, "confirmed")
    conflicts = [
        x.logical_id
        for x in repair.affected_shifts(base, model_absence)
        if x.locked and x.logical_id not in unlocked
    ]
    if conflicts:
        raise ApiError(
            "conflict",
            "The absence hits a locked shift. Authorize changing it to repair.",
            locked_logical_shift_ids=[str(c) for c in conflicts],
        )
    # Cross-outlet repair needs the other outlets' staff in the snapshot: the worker reads nothing else.
    others = (
        list(session.scalars(select(Outlet.id).where(Outlet.id != schedule.outlet_id)))
        if allow_cross_outlet
        else []
    )
    snap = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, base, schedule.id, others)
    doc = snapshot_json.dump(snap)
    doc["repair"] = {
        "base": [snapshot_json.shift_doc(x) for x in base],
        "absence": snapshot_json.absence_doc(model_absence),
        "unlocked": sorted(str(u) for u in unlocked),
        "allow_cross_outlet": allow_cross_outlet,
    }
    return _insert(
        session,
        caller,
        schedule,
        kind="repair",
        priority=REPAIR_PRIORITY,
        trigger_absence_id=absence.id,
        strategy="least_disruption",
        doc=doc,
        key=key,
        request_hash=request_hash,
        config={
            "strategy": "least_disruption",
            "time_limit_seconds": time_limit_seconds,
            "absence_id": str(absence.id),
        },
    )


def enqueue_repair(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, key: str, body: s.RepairRequest
) -> s.OptimizationRun:
    """Repairs are claimed before batch work and never blocked by it (v3 section 28)."""
    require(caller, "generate")
    if body.allow_cross_outlet and caller.role is not Role.OWNER:
        raise ApiError("permission_denied", "Only an owner can let a repair borrow staff from other outlets.")
    request_hash = _request_hash(outlet_id, week_start, body)
    with tenant_session(caller, "REPEATABLE READ") as session:
        existing, schedule = _admit(
            session, caller, outlet_id, week_start, key, request_hash, body.base_version_id, kind="repair"
        )
        if existing is not None:
            return run_view(session, existing)
        absence = session.get(AbsenceRow, body.absence_id)
        if absence is None:
            raise not_found("Absence")
        if absence.status != "confirmed":
            raise ApiError("conflict", "Confirm the absence before repairing the schedule.")
        start, end = week_bounds(_outlet(session, caller, outlet_id), week_start)
        if not (absence.start_at < end and start < absence.end_at):
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[{"path": ["absence_id"], "message": "The absence is not in this week."}],
            )
        run = repair_in_session(
            session,
            caller,
            absence,
            schedule,
            key=key,
            request_hash=request_hash,
            unlocked=set(body.unlock_logical_shift_ids),
            time_limit_seconds=body.time_limit_seconds,
            allow_cross_outlet=body.allow_cross_outlet,
        )
        return run_view(session, run)


def get_run(caller: Caller, run_id: uuid.UUID) -> s.OptimizationRun:
    with tenant_session(caller) as session:
        run = session.get(OptimizationRun, run_id)
        if run is None:
            raise not_found("Optimization run")
        for outlet_id in run.outlet_ids:
            assert_outlet(caller, str(outlet_id))
        return run_view(session, run)
