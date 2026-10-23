"""Scenario Lab (architecture v4 sections 23, 42).

A scenario is a hypothetical overlay on one outlet week. Its events live only in scenario_events and
take effect only inside scheduling.scenario.apply while a run's solver input is built: no function here
writes absences, availability, rules or staffing requirements.

Runs go through the normal queue (kind 'scenario'). Their candidates cannot be selected; "Turn this into
a plan" (convert) re-checks the chosen candidate against CURRENT facts, refuses when the real schedule
moved or when the plan only works under the scenario's assumptions, and otherwise creates a normal
draft that follows the usual proposal and publication path.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.candidates import _materialize
from api.v2.errors import ApiError, not_found
from api.v2.generation import (
    SCENARIO_PRIORITY,
    _admit,
    _current_shifts,
    _insert,
    _request_hash,
    run_view,
)
from api.v2.rosters import version_view
from api.v2.service import _audit, _outlet, idempotent, week_bounds
from core.auth import Caller, assert_outlet
from db.models import Outlet
from db.models_v2 import (
    OptimizationCandidate,
    OptimizationRun,
    PlanningScenario,
    ScenarioEvent,
    Schedule,
    VersionShift,
)
from db.session import tenant_session
from scheduling import metrics, snapshot_db, snapshot_json, validator
from scheduling import scenario as overlay

LIFETIME = timedelta(days=7)  # scenario overlays expire quickly (v4 section 34)


class _Convert(BaseModel):
    scenario_id: uuid.UUID
    candidate_id: uuid.UUID


def _event_error(exc: overlay.EventError, index: int | None = None) -> ApiError:
    path: list[str | int] = ["events", index, *exc.path] if index is not None else list(exc.path)
    return ApiError(
        "validation_failed", "Some fields need attention.", fields=[{"path": path, "message": str(exc)}]
    )


def _schedule(session: Session, caller: Caller, outlet_id: uuid.UUID, week_start: date) -> Schedule:
    outlet = _outlet(session, caller, outlet_id)
    week_bounds(outlet, week_start)
    session.execute(
        pg_insert(Schedule)
        .values(id=uuid.uuid7(), org_id=uuid.UUID(caller.org_id), outlet_id=outlet_id, week_start=week_start)
        .on_conflict_do_nothing(index_elements=["org_id", "outlet_id", "week_start"])
    )
    schedule = session.scalars(
        select(Schedule).where(Schedule.outlet_id == outlet_id, Schedule.week_start == week_start)
    ).first()
    assert schedule is not None
    return schedule


def _snapshot(session: Session, schedule: Schedule) -> tuple[Any, list[Any]]:
    """Current real facts for the week, exactly as a generate run would see them."""
    base = _current_shifts(session, schedule)
    others = list(session.scalars(select(Outlet.id).where(Outlet.id != schedule.outlet_id)))
    snap = snapshot_db.with_base_locks(
        snapshot_db.load(session, schedule.outlet_id, schedule.week_start, base, schedule.id, others),
        [x for x in base if x.locked],
        base,
    )
    return snap, base


def _events(session: Session, scenario_id: uuid.UUID) -> list[ScenarioEvent]:
    return list(
        session.scalars(
            select(ScenarioEvent)
            .where(ScenarioEvent.scenario_id == scenario_id)
            .order_by(ScenarioEvent.sequence)
        )
    )


def _check(snap: Any, events: list[s.ScenarioEventIn]) -> None:
    """Every event must apply cleanly, in order, on top of the ones before it."""
    current = snap
    for i, e in enumerate(events):
        try:
            current = overlay.apply(current, [overlay.Event(e.type, e.payload)])
        except overlay.EventError as exc:
            raise _event_error(exc, i) from None


def _load(
    session: Session, caller: Caller, scenario_id: uuid.UUID, *, for_update: bool = False
) -> PlanningScenario:
    query = select(PlanningScenario).where(PlanningScenario.id == scenario_id)
    sc = session.scalars(query.with_for_update() if for_update else query).first()
    if sc is None:
        raise not_found("Scenario")
    schedule = session.get(Schedule, sc.schedule_id)
    assert schedule is not None
    assert_outlet(caller, str(schedule.outlet_id))
    if sc.status == "open" and sc.expires_at <= datetime.now(UTC):
        sc.status = "expired"
        session.flush()
    return sc


def _view(session: Session, sc: PlanningScenario) -> s.Scenario:
    schedule = session.get(Schedule, sc.schedule_id)
    assert schedule is not None
    latest = session.scalars(
        select(OptimizationRun)
        .where(OptimizationRun.scenario_id == sc.id)
        .order_by(OptimizationRun.queued_at.desc(), OptimizationRun.id.desc())
        .limit(1)
    ).first()
    stored = ((latest.config or {}).get("scenario") or {}).get("baseline") if latest else None
    return s.Scenario(
        id=sc.id,
        outlet_id=schedule.outlet_id,
        week_start=schedule.week_start,
        schedule_id=schedule.id,
        title=sc.title,
        base_version_id=sc.base_version_id,
        status=sc.status,  # type: ignore[arg-type]
        created_by_user_id=sc.created_by_user_id,
        created_at=sc.created_at,
        expires_at=sc.expires_at,
        converted_version_id=sc.converted_version_id,
        events=[
            s.ScenarioEvent(id=e.id, sequence=e.sequence, type=e.type, payload=e.payload)  # type: ignore[arg-type]
            for e in _events(session, sc.id)
        ],
        latest_run_id=latest.id if latest else None,
        baseline=s.ScenarioBaseline.model_validate({"run_id": latest.id, **stored})
        if latest and stored
        else None,
    )


def _require_open(sc: PlanningScenario) -> None:
    if sc.status != "open":
        raise ApiError(
            "conflict", f"This scenario is {sc.status}; it can no longer change.", status=sc.status
        )


def create(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, body: s.CreateScenarioRequest
) -> s.Scenario:
    require(caller, "generate")
    with tenant_session(caller) as session:
        schedule = _schedule(session, caller, outlet_id, week_start)
        snap, _ = _snapshot(session, schedule)
        _check(snap, body.events)
        sc = PlanningScenario(
            id=uuid.uuid7(),
            org_id=schedule.org_id,
            schedule_id=schedule.id,
            title=body.title,
            base_version_id=schedule.current_version_id,
            status="open",
            created_by_user_id=uuid.UUID(caller.user_id),
            expires_at=datetime.now(UTC) + LIFETIME,
        )
        session.add(sc)
        session.flush()
        session.add_all(
            [
                ScenarioEvent(
                    id=uuid.uuid7(),
                    org_id=sc.org_id,
                    scenario_id=sc.id,
                    sequence=i,
                    type=e.type,
                    payload=e.payload,
                )
                for i, e in enumerate(body.events, start=1)
            ]
        )
        session.flush()
        _audit(session, caller, "SCENARIO_CREATED", "planning_scenario", sc.id, None, None)
        return _view(session, sc)


def get(caller: Caller, scenario_id: uuid.UUID) -> s.Scenario:
    require(caller, "generate")
    with tenant_session(caller) as session:
        return _view(session, _load(session, caller, scenario_id))


def list_for(caller: Caller, outlet_id: uuid.UUID, week_start: date | None) -> s.ScenarioList:
    require(caller, "generate")
    with tenant_session(caller) as session:
        _outlet(session, caller, outlet_id)
        query = (
            select(PlanningScenario)
            .join(Schedule, Schedule.id == PlanningScenario.schedule_id)
            .where(Schedule.outlet_id == outlet_id)
            .order_by(PlanningScenario.created_at.desc(), PlanningScenario.id.desc())
            .limit(50)
        )
        if week_start is not None:
            query = query.where(Schedule.week_start == week_start)
        return s.ScenarioList(items=[_view(session, sc) for sc in session.scalars(query)])


def add_event(caller: Caller, scenario_id: uuid.UUID, body: s.ScenarioEventIn) -> s.Scenario:
    require(caller, "generate")
    with tenant_session(caller) as session:
        sc = _load(session, caller, scenario_id, for_update=True)
        _require_open(sc)
        schedule = session.get(Schedule, sc.schedule_id)
        assert schedule is not None
        snap, _ = _snapshot(session, schedule)
        existing = _events(session, sc.id)
        current = overlay.apply(snap, [overlay.Event(e.type, e.payload) for e in existing])
        try:
            overlay.check(current, overlay.Event(body.type, body.payload))
        except overlay.EventError as exc:
            raise _event_error(exc) from None
        number = (
            session.scalar(select(func.max(ScenarioEvent.sequence)).where(ScenarioEvent.scenario_id == sc.id))
            or 0
        ) + 1
        session.add(
            ScenarioEvent(
                id=uuid.uuid7(),
                org_id=sc.org_id,
                scenario_id=sc.id,
                sequence=number,
                type=body.type,
                payload=body.payload,
            )
        )
        session.flush()
        _audit(session, caller, "SCENARIO_EVENT_ADDED", "planning_scenario", sc.id, None, None)
        return _view(session, sc)


def discard(caller: Caller, scenario_id: uuid.UUID) -> s.Scenario:
    require(caller, "generate")
    with tenant_session(caller) as session:
        sc = _load(session, caller, scenario_id, for_update=True)
        _require_open(sc)
        sc.status = "discarded"
        session.flush()
        _audit(session, caller, "SCENARIO_DISCARDED", "planning_scenario", sc.id, None, None)
        return _view(session, sc)


def run(caller: Caller, scenario_id: uuid.UUID, key: str, body: s.ScenarioRunRequest) -> s.OptimizationRun:
    """Solve the week as if the events happened. The baseline (the current plan under the same events)
    is computed here and stored on the run, so the comparison is reproducible."""
    require(caller, "generate")
    with tenant_session(caller, "REPEATABLE READ") as session:
        sc = _load(session, caller, scenario_id)
        _require_open(sc)
        schedule = session.get(Schedule, sc.schedule_id)
        assert schedule is not None
        request_hash = _request_hash(
            schedule.outlet_id, schedule.week_start, _RunKey(scenario_id=sc.id, **body.model_dump())
        )
        # The base must still be current: a scenario never pretends a moved schedule is unchanged.
        existing, schedule = _admit(
            session,
            caller,
            schedule.outlet_id,
            schedule.week_start,
            key,
            request_hash,
            sc.base_version_id,
            kind="scenario",
        )
        if existing is not None:
            return run_view(session, existing)
        snap, base = _snapshot(session, schedule)
        events = _events(session, sc.id)
        try:
            what_if = overlay.apply(snap, [overlay.Event(e.type, e.payload) for e in events])
        except overlay.EventError as exc:  # a fact changed since the event was added (e.g. a person left)
            raise _event_error(exc) from None
        before = overlay.baseline(what_if, base)
        check = validator.validate(what_if, before)
        hard = [v for v in check.violations if v.severity == "hard"]
        row = _insert(
            session,
            caller,
            schedule,
            kind="scenario",
            priority=SCENARIO_PRIORITY,
            scenario_id=sc.id,
            strategy=body.strategy,
            doc=snapshot_json.dump(what_if),
            key=key,
            request_hash=request_hash,
            config={
                "strategy": body.strategy,
                "time_limit_seconds": body.time_limit_seconds,
                "scenario": {
                    "scenario_id": str(sc.id),
                    "event_ids": [str(e.id) for e in events],
                    "baseline": {
                        "metrics": metrics.as_contract(metrics.compute(what_if, before)),
                        "hard_violations": len(hard),
                        "violation_codes": sorted({v.code for v in hard}),
                    },
                },
            },
        )
        return run_view(session, row)


class _RunKey(BaseModel):
    scenario_id: uuid.UUID
    strategy: str
    time_limit_seconds: int


def convert(
    caller: Caller, scenario_id: uuid.UUID, key: str, body: s.ConvertScenarioRequest
) -> s.ScheduleVersion:
    """Turn a scenario candidate into a real draft (v4 sections 23, 42): resolve the current base and
    facts again, refuse if either moved under the plan, then materialize a normal draft."""
    require(caller, "publish")
    with tenant_session(caller) as session:

        def produce() -> s.ScheduleVersion:
            sc = _load(session, caller, scenario_id, for_update=True)
            _require_open(sc)
            candidate = session.get(OptimizationCandidate, body.candidate_id)
            run_row = session.get(OptimizationRun, candidate.run_id) if candidate else None
            if candidate is None or run_row is None or run_row.scenario_id != sc.id:
                raise not_found("Scenario candidate")
            schedule = session.scalars(
                select(Schedule).where(Schedule.id == sc.schedule_id).with_for_update()
            ).first()
            assert schedule is not None
            run_base = run_row.base_version_ids[0] if run_row.base_version_ids else None
            if schedule.current_version_id != sc.base_version_id or run_base != sc.base_version_id:
                raise ApiError(
                    "stale_version",
                    "The real schedule changed since this scenario ran. Run the scenario again.",
                    current_version_id=str(schedule.current_version_id)
                    if schedule.current_version_id
                    else None,
                )
            rows = (
                list(session.scalars(select(VersionShift).where(VersionShift.version_id == run_base)))
                if run_base
                else []
            )
            roster = snapshot_json.apply_candidate_diff(
                [snapshot_db.to_shift(r) for r in rows], candidate.diff
            )
            real = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, roster, schedule.id)
            hard = [v for v in validator.validate(real, roster).violations if v.severity == "hard"]
            if hard:
                raise ApiError(
                    "conflict",
                    "This plan only works under the scenario's assumptions; current facts break it. "
                    "Generate against the real week instead.",
                    hard_violations=len(hard),
                    violation_codes=sorted({v.code for v in hard}),
                )
            draft = _materialize(session, caller, candidate, run_row, schedule)
            sc.status = "converted"
            sc.converted_version_id = draft.id
            session.flush()
            _audit(session, caller, "SCENARIO_CONVERTED", "schedule_version", draft.id, None, None)
            return version_view(session, draft, record=True)

        return s.ScheduleVersion.model_validate(
            idempotent(
                session,
                caller,
                key,
                "convertScenario",
                _Convert(scenario_id=scenario_id, candidate_id=body.candidate_id),
                produce,
            )
        )
