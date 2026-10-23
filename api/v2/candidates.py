"""Lightweight candidates and selection (architecture v3 section 23, task A3.3).

A candidate is a diff against its run's base version. Nothing is written to schedule_versions until a
manager selects one; selection materializes a draft whose base is the run's base version, so a candidate
computed against an older published version is caught as stale at publication (section 31).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.drafts import DEFAULT_LOCK_REASON, _rows, _tz
from api.v2.errors import ApiError, not_found
from api.v2.generation import candidate_fields
from api.v2.rosters import version_view
from api.v2.service import _audit, idempotent
from core.auth import Caller, Role, assert_outlet
from db.models_v2 import (
    LogicalShift,
    OptimizationCandidate,
    OptimizationRun,
    Schedule,
    ScheduleVersion,
    VersionShift,
)
from db.session import tenant_session
from scheduling import snapshot_db, snapshot_json


class _Selection(BaseModel):
    """What an Idempotency-Key is bound to for selectOptimizationCandidate (the request has no body)."""

    candidate_id: uuid.UUID


def _load(
    session: Session, caller: Caller, candidate_id: uuid.UUID, *, for_update: bool = False
) -> tuple[OptimizationCandidate, OptimizationRun, Schedule]:
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "You do not have permission to do this.")
    query = select(OptimizationCandidate).where(OptimizationCandidate.id == candidate_id)
    candidate = session.scalars(query.with_for_update() if for_update else query).first()
    if candidate is None:
        raise not_found("Optimization candidate")
    run = session.get(OptimizationRun, candidate.run_id)
    assert run is not None and run.schedule_id is not None
    for outlet_id in run.outlet_ids:
        assert_outlet(caller, str(outlet_id))
    schedule = session.get(Schedule, run.schedule_id)
    assert schedule is not None
    return candidate, run, schedule


def _base_id(run: OptimizationRun) -> uuid.UUID | None:
    return run.base_version_ids[0] if run.base_version_ids else None


def get_candidate(caller: Caller, candidate_id: uuid.UUID) -> s.CandidateDetail:
    with tenant_session(caller) as session:
        candidate, run, schedule = _load(session, caller, candidate_id)
        tz = _tz(session, schedule)

        def shift(d: dict[str, Any]) -> dict[str, Any]:
            sh = snapshot_json.shift_from_doc(d)
            return {
                "logical_shift_id": sh.logical_id,
                "outlet_id": sh.outlet_id,
                "employee_id": sh.employee_id,
                "skill_id": sh.skill_id,
                "start_at": sh.start_at.astimezone(tz),
                "end_at": sh.end_at.astimezone(tz),
                "break_start_at": sh.break_start_at.astimezone(tz) if sh.break_start_at else None,
                "break_minutes": sh.break_minutes,
                "locked": sh.locked,
            }

        diff = candidate.diff
        return s.CandidateDetail.model_validate(
            candidate_fields(candidate)
            | {
                "run_id": run.id,
                "base_version_id": _base_id(run),
                "diff": {
                    "added": [shift(d) for d in diff.get("added", [])],
                    "changed": [shift(d) for d in diff.get("changed", [])],
                    "removed": diff.get("removed", []),
                },
                "trace_changes": ((candidate.explanation_facts or {}).get("trace") or {}).get("changes", []),
            }
        )


def _materialize(
    session: Session,
    caller: Caller,
    candidate: OptimizationCandidate,
    run: OptimizationRun,
    schedule: Schedule,
) -> ScheduleVersion:
    base_id = _base_id(run)
    base_rows = _rows(session, base_id) if base_id else []
    by_logical = {r.logical_shift_id: r for r in base_rows}
    roster = snapshot_json.apply_candidate_diff([snapshot_db.to_shift(r) for r in base_rows], candidate.diff)
    number = session.scalar(
        select(func.coalesce(func.max(ScheduleVersion.version_number), 0)).where(
            ScheduleVersion.schedule_id == schedule.id
        )
    )
    draft = ScheduleVersion(
        id=uuid.uuid7(),
        org_id=schedule.org_id,
        schedule_id=schedule.id,
        version_number=(number or 0) + 1,
        status="draft",
        base_version_id=base_id,  # the run's base, so publication detects a newer published version
        source=run.kind,
        reason=f"Selected option {candidate.rank} ({candidate.strategy.replace('_', ' ')})",
        optimization_run_id=run.id,
        created_by_user_id=uuid.UUID(caller.user_id),
        input_hash=run.input_hash,
        revision=1,
    )
    session.add(draft)
    session.flush()
    new_ids = [sh.logical_id for sh in roster if sh.logical_id not in by_logical]
    if new_ids:
        session.execute(
            pg_insert(LogicalShift)
            .values(
                [
                    {
                        "id": lid,
                        "org_id": schedule.org_id,
                        "schedule_id": schedule.id,
                        "created_in_version_id": draft.id,
                    }
                    for lid in new_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
    session.add_all(
        [
            VersionShift(
                id=uuid.uuid7(),
                org_id=schedule.org_id,
                schedule_id=schedule.id,
                version_id=draft.id,
                logical_shift_id=sh.logical_id,
                outlet_id=sh.outlet_id,
                employee_id=sh.employee_id,
                skill_id=sh.skill_id,
                start_at=sh.start_at,
                end_at=sh.end_at,
                break_start_at=sh.break_start_at,
                break_minutes=sh.break_minutes,
                locked=sh.locked,
                lock_reason=(
                    (by_logical[sh.logical_id].lock_reason if sh.logical_id in by_logical else None)
                    or DEFAULT_LOCK_REASON
                )
                if sh.locked
                else None,
                template_id=by_logical[sh.logical_id].template_id if sh.logical_id in by_logical else None,
            )
            for sh in roster
        ]
    )
    candidate.materialized_version_id = draft.id
    session.flush()
    return draft


def select_candidate(caller: Caller, candidate_id: uuid.UUID, key: str) -> s.ScheduleVersion:
    """Materialize a candidate into a draft. Selecting it again returns the same draft while it is still a
    draft; once that draft was discarded or published, a new draft is materialized."""
    require(caller, "publish")
    with tenant_session(caller) as session:

        def produce() -> s.ScheduleVersion:
            candidate, run, schedule = _load(session, caller, candidate_id, for_update=True)
            if run.kind == "scenario":
                raise ApiError(
                    "conflict",
                    "This plan is a what-if. Turn it into a plan from its scenario instead.",
                    scenario_id=str(run.scenario_id),
                )
            session.execute(select(Schedule.id).where(Schedule.id == schedule.id).with_for_update())
            if candidate.materialized_version_id is not None:
                existing = session.get(ScheduleVersion, candidate.materialized_version_id)
                if existing is not None and existing.status == "draft":
                    return version_view(session, existing)
            draft = _materialize(session, caller, candidate, run, schedule)
            _audit(session, caller, "CANDIDATE_SELECTED", "schedule_version", draft.id, None, None)
            return version_view(session, draft, record=True)

        return s.ScheduleVersion.model_validate(
            idempotent(
                session,
                caller,
                key,
                "selectOptimizationCandidate",
                _Selection(candidate_id=candidate_id),
                produce,
            )
        )
