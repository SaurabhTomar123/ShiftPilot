"""Proposals and the publication transaction (architecture v3 sections 23 and 31, task A3.4).

    candidate --select--> draft --edit (optional)--> proposal --approve--> published version

A proposal records what the manager agreed to: the draft revision and its metrics at proposal time.
Approval runs v3 section 31 in one transaction and answers with one of four outcomes:

    published  roster unchanged, plan valid, metrics unchanged or acknowledged
    stale      someone published first (or the draft was edited after it was proposed)
    invalid    a current fact breaks the plan; the violations say which
    changed    still valid, but cost or coverage moved materially; approve again with acknowledge_changes

Each outcome is a normal business result (200), stored under the request's Idempotency-Key.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.drafts import _live_check, _outbox, _publish_locked, _require_draft, _tz, _version
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, idempotent
from core.auth import Caller, Role, assert_outlet
from db.models_v2 import OptimizationCandidate, Schedule, ScheduleProposal, ScheduleVersion
from db.session import tenant_session
from scheduling import metrics

PROPOSAL_TTL = timedelta(hours=24)
STALE_PUBLISHED = "The schedule changed while you were reviewing. Recalculating against the latest version."
STALE_EDITED = "The draft was edited after it was proposed. Review it and propose it again."


class _Approval(BaseModel):
    """What an Idempotency-Key is bound to for approveProposal."""

    proposal_id: uuid.UUID
    acknowledge_changes: bool


def _view(session: Session, proposal: ScheduleProposal) -> s.Proposal:
    draft = session.get(ScheduleVersion, proposal.draft_version_ids[0])
    assert draft is not None
    schedule = session.get(Schedule, draft.schedule_id)
    assert schedule is not None
    tz = _tz(session, schedule)
    return s.Proposal(
        id=proposal.id,
        schedule_id=schedule.id,
        draft_version_id=draft.id,
        draft_revision=proposal.draft_revisions[0],
        base_version_id=proposal.base_version_ids[0] if proposal.base_version_ids else None,
        candidate_id=proposal.candidate_id,
        status=proposal.status,  # type: ignore[arg-type]
        metrics_at_proposal=s.Metrics.model_validate(proposal.metrics_at_proposal),
        requested_by_user_id=proposal.requested_by_user_id,
        decided_by_user_id=proposal.decided_by_user_id,
        created_at=proposal.created_at.astimezone(tz),
        decided_at=proposal.decided_at.astimezone(tz) if proposal.decided_at else None,
        expires_at=proposal.expires_at.astimezone(tz),
    )


def _load(
    session: Session, caller: Caller, proposal_id: uuid.UUID, *, for_update: bool = False
) -> tuple[ScheduleProposal, ScheduleVersion, Schedule]:
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "You do not have permission to do this.")
    query = select(ScheduleProposal).where(ScheduleProposal.id == proposal_id)
    proposal = session.scalars(query.with_for_update() if for_update else query).first()
    if proposal is None:
        raise not_found("Proposal")
    draft = session.get(ScheduleVersion, proposal.draft_version_ids[0])
    assert draft is not None
    schedule = session.get(Schedule, draft.schedule_id)
    assert schedule is not None
    assert_outlet(caller, str(schedule.outlet_id))
    return proposal, draft, schedule


def _require_pending(proposal: ScheduleProposal) -> None:
    if proposal.status != "pending":
        raise ApiError("conflict", f"This proposal is already {proposal.status}.", status=proposal.status)
    if proposal.expires_at <= datetime.now(UTC):
        raise ApiError("conflict", "This proposal expired. Propose the draft again.", status="expired")


def _decide(
    session: Session, caller: Caller, proposal: ScheduleProposal, status: str, result: dict[str, Any]
) -> None:
    proposal.status = status
    proposal.decided_by_user_id = uuid.UUID(caller.user_id)
    proposal.decided_at = datetime.now(UTC)
    proposal.result = json.loads(json.dumps(result, default=str))
    session.flush()
    session.refresh(proposal)


def create(caller: Caller, key: str, body: s.CreateProposalRequest) -> s.Proposal:
    require(caller, "publish")
    with tenant_session(caller) as session:

        def produce() -> s.Proposal:
            draft, schedule = _version(session, caller, body.draft_version_id, for_update=True)
            _require_draft(draft)
            if body.expected_revision != draft.revision:
                raise ApiError(
                    "stale_version",
                    "This draft was changed by someone else. Reload and try again.",
                    current_revision=draft.revision,
                )
            hard, measured = _live_check(session, schedule, draft)
            if hard:
                raise ApiError(
                    "validation_failed",
                    "This draft breaks scheduling rules. Fix them before proposing it.",
                    violations=hard,
                )
            candidate_id = session.scalar(
                select(OptimizationCandidate.id).where(
                    OptimizationCandidate.materialized_version_id == draft.id
                )
            )
            proposal = ScheduleProposal(
                id=uuid.uuid7(),
                org_id=schedule.org_id,
                candidate_id=candidate_id,
                draft_version_ids=[draft.id],
                draft_revisions=[draft.revision],
                base_version_ids=[draft.base_version_id] if draft.base_version_id else [],
                metrics_at_proposal=measured,
                input_hash=draft.input_hash,
                status="pending",
                required_role="manager",
                requested_by_user_id=uuid.UUID(caller.user_id),
                expires_at=datetime.now(UTC) + PROPOSAL_TTL,
                idempotency_key=key,
                request_hash="sha256:"
                + hashlib.sha256(
                    json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
                ).hexdigest(),
            )
            session.add(proposal)
            session.flush()
            session.refresh(proposal)
            _audit(session, caller, "PROPOSAL_CREATED", "schedule_proposal", proposal.id, None, None)
            _outbox(
                session,
                schedule.org_id,
                "proposal.ready",
                "schedule_proposal",
                proposal.id,
                {"schedule_id": schedule.id, "draft_version_id": draft.id},
            )
            return _view(session, proposal)

        return s.Proposal.model_validate(idempotent(session, caller, key, "createProposal", body, produce))


def get(caller: Caller, proposal_id: uuid.UUID) -> s.Proposal:
    with tenant_session(caller) as session:
        proposal, _, _ = _load(session, caller, proposal_id)
        return _view(session, proposal)


def reject(caller: Caller, proposal_id: uuid.UUID) -> s.Proposal:
    require(caller, "publish")
    with tenant_session(caller) as session:
        proposal, _, _ = _load(session, caller, proposal_id, for_update=True)
        if proposal.status == "rejected":
            return _view(session, proposal)
        _require_pending(proposal)
        _decide(session, caller, proposal, "rejected", {"outcome": "rejected"})
        _audit(session, caller, "PROPOSAL_REJECTED", "schedule_proposal", proposal.id, None, None)
        return _view(session, proposal)


def approve(
    caller: Caller, proposal_id: uuid.UUID, key: str, body: s.ApproveProposalRequest
) -> s.ProposalDecision:
    require(caller, "publish")  # 1. authorize before any idempotent replay
    with tenant_session(caller) as session:

        def produce() -> s.ProposalDecision:
            proposal, draft, schedule = _load(session, caller, proposal_id, for_update=True)
            _require_pending(proposal)
            # 3. lock the schedule row, then the draft
            session.execute(select(Schedule).where(Schedule.id == schedule.id).with_for_update())
            session.refresh(schedule)
            session.execute(select(ScheduleVersion).where(ScheduleVersion.id == draft.id).with_for_update())
            session.refresh(draft)
            base = proposal.base_version_ids[0] if proposal.base_version_ids else None
            # 4. base versions still current, and the draft is what was proposed?
            if (
                schedule.current_version_id != base
                or draft.status != "draft"
                or draft.revision != proposal.draft_revisions[0]
            ):
                message = STALE_PUBLISHED if schedule.current_version_id != base else STALE_EDITED
                _decide(
                    session,
                    caller,
                    proposal,
                    "stale",
                    {"outcome": "stale", "current_version_id": schedule.current_version_id},
                )
                _outbox(
                    session,
                    schedule.org_id,
                    "proposal.stale",
                    "schedule_proposal",
                    proposal.id,
                    {"schedule_id": schedule.id, "current_version_id": schedule.current_version_id},
                )
                return s.ProposalDecision(
                    outcome="stale",
                    message=message,
                    proposal=_view(session, proposal),
                    current_version_id=schedule.current_version_id,
                )
            # 5. the independent validator against CURRENT facts
            hard, measured = _live_check(session, schedule, draft)
            if hard:
                _decide(session, caller, proposal, "failed", {"outcome": "invalid", "violations": hard})
                return s.ProposalDecision(
                    outcome="invalid",
                    message=f"This recommendation is no longer valid: {hard[0]['message']}",
                    proposal=_view(session, proposal),
                    violations=[s.Violation.model_validate(v) for v in hard],
                )
            # 6. metrics against current rates and demand, versus what the manager agreed to
            deltas = metrics.material_changes(proposal.metrics_at_proposal, measured)
            if deltas and not body.acknowledge_changes:
                return s.ProposalDecision(
                    outcome="changed",
                    message=" ".join(d["message"] for d in deltas) + " Approve again to accept.",
                    proposal=_view(session, proposal),
                    deltas=[s.MetricDelta.model_validate(d) for d in deltas],
                )
            # 7-8. supersede and publish, mark approved, audit and outbox
            summary, previous = _publish_locked(session, caller, schedule, draft)
            _decide(
                session,
                caller,
                proposal,
                "approved",
                {"outcome": "published", "version_id": draft.id, "acknowledged_deltas": deltas},
            )
            _audit(session, caller, "PROPOSAL_APPROVED", "schedule_proposal", proposal.id, None, None)
            return s.ProposalDecision(
                outcome="published",
                message="Published.",
                proposal=_view(session, proposal),
                published=summary,
                superseded_version_id=previous,
            )

        request = _Approval(proposal_id=proposal_id, acknowledge_changes=body.acknowledge_changes)
        return s.ProposalDecision.model_validate(
            idempotent(session, caller, key, "approveProposal", request, produce)
        )
