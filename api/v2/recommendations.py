"""Replacement recommendations (architecture v4 sections 11, 38, 46): synchronous, read-only, short.

Nothing is written. Choosing a person means applying the returned `edit` to a draft (applyEdits), which
then follows the normal proposal and approval path."""

from __future__ import annotations

from sqlalchemy import select

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.drafts import _contract_shift, _rows, _tz, _version
from api.v2.errors import ApiError
from core.auth import Caller, Role
from db.models import Outlet
from db.session import tenant_session
from scheduling import recommend, repair, snapshot_db


def replacements(caller: Caller, body: s.ReplacementRequest) -> s.ReplacementRecommendations:
    require(caller, "publish")
    if body.include_other_outlets and caller.role is not Role.OWNER:
        raise ApiError("permission_denied", "Only an owner can borrow staff from other outlets.")
    with tenant_session(caller) as session:
        version, schedule = _version(session, caller, body.version_id)
        rows = _rows(session, version.id)
        roster = [snapshot_db.to_shift(r) for r in rows]
        others = (
            list(session.scalars(select(Outlet.id).where(Outlet.id != schedule.outlet_id)))
            if body.include_other_outlets
            else []
        )
        snap = snapshot_db.load(session, schedule.outlet_id, schedule.week_start, roster, schedule.id, others)
        try:
            result = recommend.recommend(
                snap,
                roster,
                body.logical_shift_id,
                body.profile,
                limit=body.limit,
                cross_outlet=body.include_other_outlets,
            )
        except recommend.UnknownShift:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[{"path": ["logical_shift_id"], "message": "That shift is not in this version."}],
            ) from None
        tz = _tz(session, schedule)
        row = next(r for r in rows if r.logical_shift_id == body.logical_shift_id)
        return s.ReplacementRecommendations(
            version_id=version.id,
            version_status=version.status,  # type: ignore[arg-type]
            shift=_contract_shift(result.target, tz, row.id, row.lock_reason),
            vacating_employee_id=result.target.employee_id,
            profile=body.profile,
            policy_version=recommend.POLICY_VERSION,
            considered=result.considered,
            eligible=result.eligible,
            recommendations=[
                s.Recommendation(
                    rank=i,
                    employee_id=o.employee_id,
                    name=o.name,
                    home_outlet_id=o.home_outlet_id,
                    disruption_class=o.disruption_class,  # type: ignore[arg-type]
                    incremental_cost=s.Money(amount_paise=o.incremental_cost_paise, currency="INR"),
                    overtime_minutes_added=max(0, o.overtime_minutes_added),
                    fairness_delta=o.fairness_delta,
                    weekly_minutes_after=o.weekly_minutes_after,
                    within_preferred_window=o.within_preferred_window,
                    reasons=[s.ExplanationFact.model_validate(_reason(r)) for r in o.reasons],
                    edit=s.UpdateShift(
                        op="update", logical_shift_id=body.logical_shift_id, employee_id=o.employee_id
                    ),
                )
                for i, o in enumerate(result.options, start=1)
            ],
            rejected=[
                s.AlternativeFact.model_validate(
                    {
                        "employee_id": a.employee_id,
                        "name": a.name,
                        "status": a.status,
                        "reasons": [_reason(r) for r in a.reasons],
                    }
                )
                for a in result.rejected
            ],
        )


def _reason(r: repair.Reason) -> dict[str, object]:
    return {"code": r.code, "ok": r.ok, "message": r.message, "facts": r.facts}
