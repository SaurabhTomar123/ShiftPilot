"""Availability-change requests (architecture v4 section 29).

Recurring availability is not silently replaced: an employee proposes new windows, everyone sees which
published shifts the change would break, and a manager accepts or rejects it. Accepting goes through the
same write path and revision check as a manager's own edit; the affected shifts are frozen on the request
so the manager can find cover for each one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, _availability_view, _outlet, replace_availability
from core.auth import Caller, Role, assert_outlet
from db.models import Employee, Outlet
from db.models_v2 import AvailabilityRequest
from db.session import tenant_session
from scheduling import availability, snapshot_db
from scheduling.model import Window

HORIZON = timedelta(weeks=8)


def _me(caller: Caller) -> uuid.UUID:
    if caller.role is not Role.STAFF or not caller.employee_id:
        raise ApiError("permission_denied", "Availability requests are made by employees.")
    return uuid.UUID(caller.employee_id)


def _affected(
    session: Session, employee: Employee, windows: list[dict[str, int | str]]
) -> list[s.AffectedShift]:
    outlet = session.get(Outlet, employee.outlet_id)
    tz = ZoneInfo(outlet.timezone if outlet else "UTC")
    now = datetime.now(UTC)
    rows = [
        r
        for r in snapshot_db.live_shifts(session, now, now + HORIZON, employee_ids=[employee.id])
        if r.start_at > now
    ]
    by_id = {r.logical_shift_id: r for r in rows}
    hits = availability.impact(
        [
            Window(int(w["weekday"]), int(w["start_minute"]), int(w["end_minute"]), str(w["kind"]))
            for w in windows
        ],
        [snapshot_db.to_shift(r) for r in rows],
        tz,
    )
    return [
        s.AffectedShift(
            schedule_id=by_id[h.logical_id].schedule_id,
            version_id=by_id[h.logical_id].version_id,
            logical_shift_id=h.logical_id,
            outlet_id=h.outlet_id,
            skill_id=h.skill_id,
            start_at=h.start_at.astimezone(tz),
            end_at=h.end_at.astimezone(tz),
            locked=h.locked,
        )
        for h in hits
    ]


def _view(session: Session, r: AvailabilityRequest) -> s.AvailabilityRequestView:
    employee = session.get(Employee, r.employee_id)
    assert employee is not None
    affected = (
        _affected(session, employee, r.windows)
        if r.status == "pending"
        else [s.AffectedShift.model_validate(a) for a in (r.affected or [])]
    )
    return s.AvailabilityRequestView(
        id=r.id,
        employee_id=r.employee_id,
        status=r.status,  # type: ignore[arg-type]
        base_revision=r.base_revision,
        windows=[s.AvailabilityWindow.model_validate(w) for w in r.windows],
        current=_availability_view(session, employee).windows,
        note=r.note,
        created_at=r.created_at,
        decided_by_user_id=r.decided_by_user_id,
        decided_at=r.decided_at,
        affected=affected,
    )


def create(caller: Caller, body: s.CreateAvailabilityRequest) -> s.AvailabilityRequestView:
    me = _me(caller)
    with tenant_session(caller) as session:
        employee = session.get(Employee, me)
        if employee is None:
            raise not_found("Employee")
        if body.base_revision != employee.availability_revision:
            raise ApiError(
                "stale_version",
                "Your availability changed since you opened it. Reload and try again.",
                current_revision=employee.availability_revision,
            )
        r = AvailabilityRequest(
            id=uuid.uuid7(),
            org_id=employee.org_id,
            employee_id=me,
            windows=[w.model_dump() for w in body.windows],
            base_revision=body.base_revision,
            status="pending",
            note=body.note,
        )
        session.add(r)
        try:
            session.flush()
        except IntegrityError as exc:
            raise ApiError(
                "conflict", "You already have a pending availability request. Cancel it first."
            ) from exc
        _audit(session, caller, "AVAILABILITY_REQUESTED", "availability_request", r.id, None, None)
        return _view(session, r)


def mine(caller: Caller) -> s.AvailabilityRequestList:
    me = _me(caller)
    with tenant_session(caller) as session:
        rows = session.scalars(
            select(AvailabilityRequest)
            .where(AvailabilityRequest.employee_id == me)
            .order_by(AvailabilityRequest.created_at.desc())
            .limit(50)
        )
        return s.AvailabilityRequestList(items=[_view(session, r) for r in rows])


def _load(
    session: Session, caller: Caller, request_id: uuid.UUID, *, for_update: bool = False
) -> AvailabilityRequest:
    query = select(AvailabilityRequest).where(AvailabilityRequest.id == request_id)
    r = session.scalars(query.with_for_update() if for_update else query).first()
    if r is None:
        raise not_found("Availability request")
    if caller.role is Role.STAFF:
        if str(r.employee_id) != caller.employee_id:
            raise not_found("Availability request")
    else:
        employee = session.get(Employee, r.employee_id)
        assert employee is not None
        assert_outlet(caller, str(employee.outlet_id))
    return r


def get(caller: Caller, request_id: uuid.UUID) -> s.AvailabilityRequestView:
    with tenant_session(caller) as session:
        return _view(session, _load(session, caller, request_id))


def cancel(caller: Caller, request_id: uuid.UUID) -> s.AvailabilityRequestView:
    _me(caller)
    with tenant_session(caller) as session:
        r = _load(session, caller, request_id, for_update=True)
        if r.status != "pending":
            raise ApiError("conflict", f"This request was already {r.status}.", status=r.status)
        r.status = "cancelled"
        session.flush()
        _audit(session, caller, "AVAILABILITY_REQUEST_CANCELLED", "availability_request", r.id, None, None)
        return _view(session, r)


def for_outlet(caller: Caller, outlet_id: uuid.UUID, status: str | None) -> s.AvailabilityRequestList:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:
        _outlet(session, caller, outlet_id)
        query = (
            select(AvailabilityRequest)
            .join(Employee, Employee.id == AvailabilityRequest.employee_id)
            .where(Employee.outlet_id == outlet_id)
            .order_by(AvailabilityRequest.created_at.desc())
            .limit(100)
        )
        if status is not None:
            query = query.where(AvailabilityRequest.status == status)
        return s.AvailabilityRequestList(items=[_view(session, r) for r in session.scalars(query)])


def _decide(caller: Caller, request_id: uuid.UUID, accept: bool) -> s.AvailabilityRequestView:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:
        r = _load(session, caller, request_id, for_update=True)
        if r.status != "pending":
            raise ApiError("conflict", f"This request was already {r.status}.", status=r.status)
        employee = session.scalars(
            select(Employee).where(Employee.id == r.employee_id).with_for_update()
        ).one()
        affected = _affected(session, employee, r.windows)
        if accept:
            if employee.availability_revision != r.base_revision:
                raise ApiError(
                    "stale_version",
                    "This person's availability changed after the request. Ask them to send it again.",
                    current_revision=employee.availability_revision,
                )
            replace_availability(
                session, employee, [s.AvailabilityWindow.model_validate(w) for w in r.windows]
            )
        r.status = "accepted" if accept else "rejected"
        r.decided_by_user_id, r.decided_at = uuid.UUID(caller.user_id), datetime.now(UTC)
        r.affected = [a.model_dump(mode="json") for a in affected]
        session.flush()
        action = "AVAILABILITY_REQUEST_ACCEPTED" if accept else "AVAILABILITY_REQUEST_REJECTED"
        _audit(session, caller, action, "availability_request", r.id, None, None)
        return _view(session, r)


def accept(caller: Caller, request_id: uuid.UUID) -> s.AvailabilityRequestView:
    return _decide(caller, request_id, accept=True)


def reject(caller: Caller, request_id: uuid.UUID) -> s.AvailabilityRequestView:
    return _decide(caller, request_id, accept=False)
