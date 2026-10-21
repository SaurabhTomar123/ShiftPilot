"""Staffing templates and week expansion (architecture v3 section 18, task A3.9).

Managers keep a weekly template per outlet; expandStaffingRequirements turns it into a week's 30-minute
requirements. Re-expanding replaces template and band rows but never manual overrides, and bumps the
outlet-week demand_revision like every other change to that week's requirements.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError
from api.v2.service import (
    _audit,
    _check_skills,
    _outlet,
    _staffing_view,
    bump_demand,
    demand_revision,
    idempotent,
    week_bounds,
)
from core.auth import Caller, Role
from db.models import Outlet
from db.models_v2 import DemandBand, DemandInput, StaffingRequirement, StaffingTemplate
from db.session import tenant_session
from scheduling import demand

INPUT_RANK = {"manual": 0, "scenario": 1, "history": 2}  # the most deliberate order count wins


def _active(session: Session, outlet_id: uuid.UUID) -> list[StaffingTemplate]:
    return list(
        session.scalars(
            select(StaffingTemplate)
            .where(StaffingTemplate.outlet_id == outlet_id, StaffingTemplate.active)
            .order_by(StaffingTemplate.weekday, StaffingTemplate.skill_id, StaffingTemplate.start_minute)
        )
    )


def _template_revision(session: Session, outlet_id: uuid.UUID) -> int:
    revision = session.scalar(
        select(func.max(StaffingTemplate.revision)).where(StaffingTemplate.outlet_id == outlet_id)
    )
    return int(revision or 0)


def _set_view(session: Session, outlet: Outlet) -> s.StaffingTemplateSet:
    return s.StaffingTemplateSet(
        outlet_id=outlet.id,
        revision=_template_revision(session, outlet.id),
        items=[
            s.StaffingTemplateBlock(
                weekday=t.weekday,
                start_minute=t.start_minute,
                end_minute=t.end_minute,
                skill_id=t.skill_id,
                minimum_required=t.minimum_required,
                preferred_required=t.preferred_required,
            )
            for t in _active(session, outlet.id)
        ],
    )


def list_templates(caller: Caller, outlet_id: uuid.UUID) -> s.StaffingTemplateSet:
    if caller.role is Role.STAFF:
        raise ApiError("permission_denied", "Staff cannot view staffing requirements.")
    with tenant_session(caller) as session:
        return _set_view(session, _outlet(session, caller, outlet_id))


def put_templates(
    caller: Caller, outlet_id: uuid.UUID, body: s.StaffingTemplateUpdate
) -> s.StaffingTemplateSet:
    """Replace the outlet's whole template set. Old rows are deactivated, not deleted."""
    require(caller, "edit_demand")
    with tenant_session(caller) as session:
        outlet = _outlet(session, caller, outlet_id)
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"staffing-templates:{outlet.id}"},
        )
        current = _template_revision(session, outlet.id)
        if body.base_revision != current:
            raise ApiError(
                "stale_version",
                "The staffing template was changed by someone else. Reload and try again.",
                current_revision=current,
            )
        _check_skills(
            session, [s.EmployeeSkill(skill_id=k, level=1) for k in {b.skill_id for b in body.items}]
        )
        blocks = [
            demand.Block(
                b.weekday, b.start_minute, b.end_minute, b.skill_id, b.minimum_required, b.preferred_required
            )
            for b in body.items
        ]
        clashes = demand.overlapping(blocks)
        if clashes:
            index = {id(b): n for n, b in enumerate(blocks)}
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                fields=[
                    {
                        "path": ["items", index[id(later)]],
                        "message": "Overlaps another block for this weekday and role.",
                    }
                    for _, later in clashes
                ],
            )
        session.execute(
            update(StaffingTemplate)
            .where(StaffingTemplate.outlet_id == outlet.id, StaffingTemplate.active)
            .values(active=False)
        )
        session.add_all(
            [
                StaffingTemplate(
                    id=uuid.uuid7(),
                    org_id=outlet.org_id,
                    outlet_id=outlet.id,
                    weekday=b.weekday,
                    start_minute=b.start_minute,
                    end_minute=b.end_minute,
                    skill_id=b.skill_id,
                    minimum_required=b.minimum_required,
                    preferred_required=b.preferred_required,
                    active=True,
                    revision=current + 1,
                )
                for b in body.items
            ]
        )
        session.flush()
        _audit(session, caller, "STAFFING_TEMPLATE_REPLACED", "outlet", outlet.id, None, None)
        return _set_view(session, outlet)


def _bands(session: Session, outlet: Outlet) -> list[demand.Band]:
    rows = list(
        session.scalars(
            select(DemandBand).where((DemandBand.outlet_id == outlet.id) | DemandBand.outlet_id.is_(None))
        )
    )
    own = {b.skill_id for b in rows if b.outlet_id == outlet.id}  # outlet bands replace org defaults
    return [
        demand.Band(b.skill_id, b.min_orders, b.max_orders, b.staff_minimum, b.staff_preferred)
        for b in rows
        if b.outlet_id == outlet.id or b.skill_id not in own
    ]


def _orders(session: Session, outlet: Outlet, start: datetime, end: datetime) -> dict[datetime, int]:
    chosen: dict[datetime, tuple[int, int]] = {}
    for i in session.scalars(
        select(DemandInput).where(
            DemandInput.outlet_id == outlet.id,
            DemandInput.interval_start >= start,
            DemandInput.interval_start < end,
        )
    ):
        rank = INPUT_RANK[i.source]
        if i.interval_start not in chosen or rank < chosen[i.interval_start][0]:
            chosen[i.interval_start] = (rank, i.orders)
    return {k: v[1] for k, v in chosen.items()}


def expand(
    caller: Caller, outlet_id: uuid.UUID, week_start: date, key: str, body: s.ExpandStaffingRequest
) -> s.StaffingRequirements:
    require(caller, "edit_demand")
    with tenant_session(caller) as session:
        outlet = _outlet(session, caller, outlet_id)
        start, end = week_bounds(outlet, week_start)

        def produce() -> s.StaffingRequirements:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                {"k": f"staffing:{outlet.id}:{week_start}"},
            )
            rows = list(
                session.scalars(
                    select(StaffingRequirement).where(
                        StaffingRequirement.outlet_id == outlet.id,
                        StaffingRequirement.interval_start >= start,
                        StaffingRequirement.interval_start < end,
                    )
                )
            )
            current = demand_revision(session, outlet, week_start, rows)
            if body.base_demand_revision != current:
                raise ApiError(
                    "stale_version",
                    "Staffing needs were changed by someone else. Reload and try again.",
                    current_demand_revision=current,
                )
            templates = _active(session, outlet.id)
            if not templates:
                raise ApiError(
                    "validation_failed",
                    "Some fields need attention.",
                    fields=[
                        {"path": ["outlet_id"], "message": "Save a staffing template for this outlet first."}
                    ],
                )
            generated = demand.expand(
                week_start,
                ZoneInfo(outlet.timezone),
                [
                    demand.Block(
                        t.weekday,
                        t.start_minute,
                        t.end_minute,
                        t.skill_id,
                        t.minimum_required,
                        t.preferred_required,
                    )
                    for t in templates
                ],
                bands=_bands(session, outlet) if body.use_demand_bands else (),
                orders=_orders(session, outlet, start, end) if body.use_demand_bands else None,
                manual={(r.skill_id, r.interval_start) for r in rows if r.source == "manual"},
            )
            session.execute(
                delete(StaffingRequirement).where(
                    StaffingRequirement.outlet_id == outlet.id,
                    StaffingRequirement.interval_start >= start,
                    StaffingRequirement.interval_start < end,
                    StaffingRequirement.source.in_(("template", "band")),
                )
            )
            session.flush()
            # Rows from other producers (scenario, later forecast) keep their slot: one row per interval.
            kept = {
                (r.skill_id, r.interval_start) for r in rows if r.source not in ("template", "band", "manual")
            }
            revision = bump_demand(session, outlet, week_start, current)
            session.add_all(
                [
                    StaffingRequirement(
                        id=uuid.uuid7(),
                        org_id=outlet.org_id,
                        outlet_id=outlet.id,
                        skill_id=g.skill_id,
                        interval_start=g.interval_start,
                        interval_end=g.interval_end,
                        minimum_required=g.minimum,
                        preferred_required=g.preferred,
                        source=g.source,
                        demand_revision=revision,
                    )
                    for g in generated
                    if (g.skill_id, g.interval_start) not in kept
                ]
            )
            session.flush()
            _audit(session, caller, "STAFFING_EXPANDED", "outlet", outlet.id, None, None)
            return _staffing_view(session, outlet, week_start)

        return s.StaffingRequirements.model_validate(
            idempotent(session, caller, key, f"expandStaffing:{outlet_id}:{week_start}", body, produce)
        )
