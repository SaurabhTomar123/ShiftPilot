"""Demand forecasts and staffing proposals (architecture v4 sections 21, 22, 37).

Requesting a forecast stores everything the worker needs (order history before the week, the staffing
template, the demand bands, the manual intervals and the demand revision) on a durable forecast run.
The worker writes the forecast and, if its backtest passes, a proposal. Only accepting a proposal writes
staffing_requirements, and only if the week's demand revision has not moved; manual overrides and other
producers' rows always survive.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from api.v2.service import (
    _audit,
    _outlet,
    _staffing_view,
    bump_demand,
    demand_revision,
    idempotent,
    week_bounds,
)
from api.v2.staffing import _active, _bands, _orders
from core.auth import Caller
from db.models import Outlet
from db.models_v2 import DemandForecast, ForecastRun, StaffingRequirement, StaffingRequirementProposal
from db.session import tenant_session
from scheduling import forecast

REPLACED = ("template", "band", "forecast")  # producers an accepted proposal supersedes; manual never


class _Accept(BaseModel):
    proposal_id: uuid.UUID


def _proposal_for(session: Session, run_id: uuid.UUID) -> StaffingRequirementProposal | None:
    return session.scalars(
        select(StaffingRequirementProposal).where(StaffingRequirementProposal.forecast_run_id == run_id)
    ).first()


def _run_view(session: Session, run: ForecastRun) -> s.ForecastRun:
    points = list(
        session.scalars(
            select(DemandForecast)
            .where(DemandForecast.run_id == run.id)
            .order_by(DemandForecast.interval_start)
        )
    )
    proposal = _proposal_for(session, run.id)
    return s.ForecastRun(
        id=run.id,
        outlet_id=run.outlet_id,
        week_start=run.week_start,
        model_version=run.model_version,
        job_state=run.job_state,  # type: ignore[arg-type]
        quality=run.quality,  # type: ignore[arg-type]
        metrics=s.ForecastMetrics.model_validate(run.metrics) if run.metrics else None,
        points=[
            s.ForecastPoint(
                interval_start=p.interval_start,
                predicted=p.predicted,
                lower=p.lower,
                upper=p.upper,
                samples=p.samples,
            )
            for p in points
        ],
        proposal_id=proposal.id if proposal else None,
        error=s.ErrorBody.model_validate(run.error) if run.error else None,
        queued_at=run.queued_at,
        finished_at=run.finished_at,
        poll_after_ms=1000 if run.job_state in ("queued", "running") else None,
    )


def request(caller: Caller, outlet_id: uuid.UUID, key: str, body: s.ForecastRequest) -> s.ForecastRun:
    require(caller, "edit_demand")
    request_hash = (
        "sha256:"
        + hashlib.sha256(
            json.dumps({"outlet": str(outlet_id), **body.model_dump(mode="json")}, sort_keys=True).encode()
        ).hexdigest()
    )
    with tenant_session(caller) as session:
        outlet = _outlet(session, caller, outlet_id)
        start, end = week_bounds(outlet, body.week_start)
        existing = session.scalars(select(ForecastRun).where(ForecastRun.idempotency_key == key)).first()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ApiError(
                    "idempotency_conflict", "This request key was already used with different input."
                )
            return _run_view(session, existing)
        templates = _active(session, outlet.id)
        if not templates:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {"path": ["outlet_id"], "message": "Save a staffing template for this outlet first."}
                ],
            )
        since = start - timedelta(weeks=forecast.WINDOW_WEEKS + forecast.BACKTEST_WEEKS)
        history = _orders(session, outlet, since, start)
        rows = list(
            session.scalars(
                select(StaffingRequirement).where(
                    StaffingRequirement.outlet_id == outlet.id,
                    StaffingRequirement.interval_start >= start,
                    StaffingRequirement.interval_start < end,
                )
            )
        )
        doc: dict[str, Any] = {
            "tz": outlet.timezone,
            "week_start": body.week_start.isoformat(),
            "history": sorted([t.isoformat(), v] for t, v in history.items()),
            "blocks": [
                [
                    t.weekday,
                    t.start_minute,
                    t.end_minute,
                    str(t.skill_id),
                    t.minimum_required,
                    t.preferred_required,
                ]
                for t in templates
            ],
            "bands": [
                [str(b.skill_id), b.min_orders, b.max_orders, b.minimum, b.preferred]
                for b in _bands(session, outlet)
            ],
            "manual": sorted(
                [str(r.skill_id), r.interval_start.isoformat()] for r in rows if r.source == "manual"
            ),
            "base_demand_revision": demand_revision(session, outlet, body.week_start, rows),
        }
        run = ForecastRun(
            id=uuid.uuid7(),
            org_id=outlet.org_id,
            outlet_id=outlet.id,
            week_start=body.week_start,
            model_version=forecast.MODEL_VERSION,
            job_state="queued",
            idempotency_key=key,
            request_hash=request_hash,
            requested_by_user_id=uuid.UUID(caller.user_id),
            input_hash="sha256:" + hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest(),
            input=doc,
        )
        session.add(run)
        try:
            session.flush()
        except IntegrityError as exc:
            raise ApiError(
                "run_in_progress", "A forecast for this week is already running.", retryable=True
            ) from exc
        _audit(session, caller, "FORECAST_REQUESTED", "forecast_run", run.id, None, None)
        session.execute(text("NOTIFY forecast_runs"))
        session.refresh(run)
        return _run_view(session, run)


def _load_outlet(session: Session, caller: Caller, outlet_id: uuid.UUID) -> Outlet:
    return _outlet(session, caller, outlet_id)


def get_run(caller: Caller, run_id: uuid.UUID) -> s.ForecastRun:
    require(caller, "edit_demand")
    with tenant_session(caller) as session:
        run = session.get(ForecastRun, run_id)
        if run is None:
            raise not_found("Forecast run")
        _load_outlet(session, caller, run.outlet_id)
        return _run_view(session, run)


def _week_rows(session: Session, outlet: Outlet, week_start: date) -> list[StaffingRequirement]:
    start, end = week_bounds(outlet, week_start)
    return list(
        session.scalars(
            select(StaffingRequirement).where(
                StaffingRequirement.outlet_id == outlet.id,
                StaffingRequirement.interval_start >= start,
                StaffingRequirement.interval_start < end,
            )
        )
    )


def _proposal_view(session: Session, p: StaffingRequirementProposal, outlet: Outlet) -> s.StaffingProposal:
    current = {(str(r.skill_id), r.interval_start): r for r in _week_rows(session, outlet, p.week_start)}
    proposed = {(r["skill_id"], datetime.fromisoformat(r["interval_start"])): r for r in p.rows}
    replaceable = {k for k, r in current.items() if r.source in REPLACED}
    added = changed = unchanged = 0
    for k, r in proposed.items():
        old = current.get(k)
        if old is None or k not in replaceable:
            added += old is None
            continue
        if (old.minimum_required, old.preferred_required) == (r["minimum"], r["preferred"]):
            unchanged += 1
        else:
            changed += 1
    return s.StaffingProposal(
        id=p.id,
        outlet_id=p.outlet_id,
        week_start=p.week_start,
        forecast_run_id=p.forecast_run_id,
        status=p.status,  # type: ignore[arg-type]
        base_demand_revision=p.base_demand_revision,
        created_at=p.created_at,
        decided_by_user_id=p.decided_by_user_id,
        decided_at=p.decided_at,
        changes=s.ProposalChanges(
            added=added,
            changed=changed,
            removed=len(replaceable - set(proposed)),
            unchanged=unchanged,
            manual_kept=sum(1 for r in current.values() if r.source == "manual"),
        ),
        rows=[s.ProposedRequirement.model_validate(r) for r in p.rows],
    )


def _load_proposal(
    session: Session, caller: Caller, proposal_id: uuid.UUID, *, for_update: bool = False
) -> tuple[StaffingRequirementProposal, Outlet]:
    query = select(StaffingRequirementProposal).where(StaffingRequirementProposal.id == proposal_id)
    p = session.scalars(query.with_for_update() if for_update else query).first()
    if p is None:
        raise not_found("Staffing proposal")
    return p, _load_outlet(session, caller, p.outlet_id)


def get_proposal(caller: Caller, proposal_id: uuid.UUID) -> s.StaffingProposal:
    require(caller, "edit_demand")
    with tenant_session(caller) as session:
        p, outlet = _load_proposal(session, caller, proposal_id)
        return _proposal_view(session, p, outlet)


def _pending(p: StaffingRequirementProposal) -> None:
    if p.status != "pending":
        raise ApiError("conflict", f"This proposal was already {p.status}.", status=p.status)


def reject(caller: Caller, proposal_id: uuid.UUID) -> s.StaffingProposal:
    require(caller, "edit_demand")
    with tenant_session(caller) as session:
        p, outlet = _load_proposal(session, caller, proposal_id, for_update=True)
        _pending(p)
        p.status, p.decided_by_user_id, p.decided_at = (
            "rejected",
            uuid.UUID(caller.user_id),
            datetime.now(UTC),
        )
        session.flush()
        _audit(session, caller, "STAFFING_PROPOSAL_REJECTED", "staffing_proposal", p.id, None, None)
        return _proposal_view(session, p, outlet)


def accept(caller: Caller, proposal_id: uuid.UUID, key: str) -> s.StaffingRequirements:
    """Write the proposal as the week's requirements: template/band/forecast rows are replaced; manual
    overrides and other producers' rows keep their intervals. 409 stale_version if demand moved."""
    require(caller, "edit_demand")
    with tenant_session(caller) as session:

        def produce() -> s.StaffingRequirements:
            p, outlet = _load_proposal(session, caller, proposal_id, for_update=True)
            _pending(p)
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                {"k": f"staffing:{outlet.id}:{p.week_start}"},
            )
            rows = _week_rows(session, outlet, p.week_start)
            current = demand_revision(session, outlet, p.week_start, rows)
            if current != p.base_demand_revision:
                raise ApiError(
                    "stale_version",
                    "Staffing needs changed after this forecast. Run the forecast again.",
                    current_demand_revision=current,
                )
            start, end = week_bounds(outlet, p.week_start)
            session.execute(
                delete(StaffingRequirement).where(
                    StaffingRequirement.outlet_id == outlet.id,
                    StaffingRequirement.interval_start >= start,
                    StaffingRequirement.interval_start < end,
                    StaffingRequirement.source.in_(REPLACED),
                )
            )
            session.flush()
            kept = {(r.skill_id, r.interval_start) for r in rows if r.source not in REPLACED}
            revision = bump_demand(session, outlet, p.week_start, current)
            session.add_all(
                [
                    StaffingRequirement(
                        id=uuid.uuid7(),
                        org_id=outlet.org_id,
                        outlet_id=outlet.id,
                        skill_id=uuid.UUID(r["skill_id"]),
                        interval_start=datetime.fromisoformat(r["interval_start"]),
                        interval_end=datetime.fromisoformat(r["interval_end"]),
                        minimum_required=r["minimum"],
                        preferred_required=r["preferred"],
                        source=r["source"],
                        demand_revision=revision,
                    )
                    for r in p.rows
                    if (uuid.UUID(r["skill_id"]), datetime.fromisoformat(r["interval_start"])) not in kept
                ]
            )
            p.status, p.decided_by_user_id, p.decided_at = (
                "accepted",
                uuid.UUID(caller.user_id),
                datetime.now(UTC),
            )
            session.flush()
            _audit(session, caller, "STAFFING_PROPOSAL_ACCEPTED", "staffing_proposal", p.id, None, None)
            return _staffing_view(session, outlet, p.week_start)

        return s.StaffingRequirements.model_validate(
            idempotent(
                session, caller, key, "acceptStaffingProposal", _Accept(proposal_id=proposal_id), produce
            )
        )
