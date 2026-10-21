"""B4.1: absences as operational facts (decision 5).

An absence never edits a published version. Reporting one returns the live shifts it touches (all
outlets) and which of them are locked, so the manager can authorize changes explicitly before repair.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import CAPABILITIES
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, idempotent
from core.auth import Caller, PermissionDenied, Role, assert_outlet
from db.models import Employee
from db.models import Outlet as OutletRow
from db.models_v2 import Absence, OutboxEvent, Schedule
from db.session import tenant_session
from scheduling import snapshot_db


def _mark(a: Absence, tz: ZoneInfo) -> s.AbsenceMark:
    return s.AbsenceMark.model_validate(
        {
            "id": a.id,
            "employee_id": a.employee_id,
            "start_at": a.start_at.astimezone(tz),
            "end_at": a.end_at.astimezone(tz),
            "kind": a.kind,
            "status": a.status,
        }
    )


def _tz(session: Session, employee: Employee) -> ZoneInfo:
    outlet = session.get(OutletRow, employee.outlet_id)
    return ZoneInfo(outlet.timezone if outlet else "UTC")


def affected(session: Session, absence: Absence, tz: ZoneInfo) -> list[s.AffectedShift]:
    rows = snapshot_db.live_shifts(
        session, absence.start_at, absence.end_at, employee_ids=[absence.employee_id]
    )
    schedules = {
        sc.id: sc
        for sc in session.scalars(select(Schedule).where(Schedule.id.in_({r.schedule_id for r in rows})))
    }
    return [
        s.AffectedShift(
            schedule_id=r.schedule_id,
            version_id=schedules[r.schedule_id].current_version_id or r.version_id,
            logical_shift_id=r.logical_shift_id,
            outlet_id=r.outlet_id,
            skill_id=r.skill_id,
            start_at=r.start_at.astimezone(tz),
            end_at=r.end_at.astimezone(tz),
            locked=r.locked,
        )
        for r in sorted(rows, key=lambda r: r.start_at)
    ]


def _report_view(session: Session, absence: Absence, tz: ZoneInfo) -> s.AbsenceReport:
    hits = affected(session, absence, tz) if absence.status in ("requested", "confirmed") else []
    return s.AbsenceReport(
        absence=_mark(absence, tz),
        affected=hits,
        lock_conflicts=[h.logical_shift_id for h in hits if h.locked],
        repair_suggested=absence.status == "confirmed" and bool(hits),
    )


def _outbox(session: Session, absence: Absence) -> None:
    session.add(
        OutboxEvent(
            id=uuid.uuid7(),
            org_id=absence.org_id,
            topic="absence.reported",
            aggregate_type="absence",
            aggregate_id=absence.id,
            payload={"employee_id": str(absence.employee_id), "status": absence.status},
        )
    )


def _auto_repair(caller: Caller, absence_id: uuid.UUID) -> list[uuid.UUID]:
    """Transaction 2 (v3 section 20): enqueue a repair per affected schedule. The absence is already
    committed, so it stands whether or not a repair can be enqueued. Schedules whose affected shifts
    are locked are skipped; the report lists those shifts for explicit authorization."""
    if "generate" not in CAPABILITIES[caller.role]:
        return []
    from api.v2 import generation  # local import: generation imports this module's neighbours

    runs: list[uuid.UUID] = []
    with tenant_session(caller, "REPEATABLE READ") as session:
        absence = session.get(Absence, absence_id)
        if absence is None or absence.status != "confirmed":
            return []
        rows = snapshot_db.live_shifts(
            session, absence.start_at, absence.end_at, employee_ids=[absence.employee_id]
        )
        for schedule_id in sorted({r.schedule_id for r in rows}, key=str):
            schedule = session.get(Schedule, schedule_id)
            if schedule is None:
                continue
            try:
                assert_outlet(caller, str(schedule.outlet_id))
                with session.begin_nested():
                    run = generation.repair_in_session(
                        session,
                        caller,
                        absence,
                        schedule,
                        key=f"absence-repair:{uuid.uuid7()}",
                        request_hash="sha256:"
                        + hashlib.sha256(f"absence:{absence.id}:{schedule.id}".encode()).hexdigest(),
                        unlocked=set(),
                        time_limit_seconds=3,
                    )
                runs.append(run.id)
            except ApiError, PermissionDenied:
                continue  # lock conflict or another outlet: flagged in the report, never silently changed
    return runs


def report(caller: Caller, key: str, body: s.ReportAbsenceRequest) -> s.AbsenceReport:
    result = _report(caller, key, body)
    if result.absence.status == "confirmed" and result.affected and not result.repair_run_ids:
        result = result.model_copy(update={"repair_run_ids": _auto_repair(caller, result.absence.id)})
    return result


def _report(caller: Caller, key: str, body: s.ReportAbsenceRequest) -> s.AbsenceReport:
    with tenant_session(caller) as session:

        def produce() -> s.AbsenceReport:
            employee = session.get(Employee, body.employee_id)
            if employee is None:
                raise not_found("Employee")
            if caller.role is Role.STAFF:
                if caller.employee_id != str(body.employee_id):
                    raise ApiError("permission_denied", "You can only report your own absence.")
                if body.status != "requested":
                    raise ApiError(
                        "permission_denied", "Your manager confirms absences; send a request instead."
                    )
            else:
                assert_outlet(caller, str(employee.outlet_id))
            absence = Absence(
                id=uuid.uuid7(),
                org_id=employee.org_id,
                employee_id=employee.id,
                start_at=body.start_at,
                end_at=body.end_at,
                kind=body.kind,
                status=body.status,
                reported_by_user_id=uuid.UUID(caller.user_id),
                source="employee" if caller.role is Role.STAFF else "manager",
                reason=body.reason,
            )
            session.add(absence)
            session.flush()
            _audit(session, caller, "ABSENCE_REPORTED", "absence", absence.id, None, None)
            _outbox(session, absence)
            return _report_view(session, absence, _tz(session, employee))

        return s.AbsenceReport.model_validate(
            idempotent(session, caller, key, "reportAbsence", body, produce)
        )


def list_absences(
    caller: Caller, outlet_id: uuid.UUID | None, start: datetime | None, end: datetime | None
) -> s.AbsenceList:
    with tenant_session(caller) as session:
        query = (
            select(Absence, Employee)
            .join(Employee, Employee.id == Absence.employee_id)
            .order_by(Absence.start_at)
        )
        if caller.role is Role.STAFF:
            query = query.where(Absence.employee_id == uuid.UUID(caller.employee_id or str(uuid.UUID(int=0))))
        else:
            outlet_id = outlet_id or (uuid.UUID(caller.outlet_id) if caller.outlet_id else None)
            if outlet_id is not None:
                assert_outlet(caller, str(outlet_id))
                query = query.where(Employee.outlet_id == outlet_id)
        if start is not None:
            query = query.where(Absence.end_at > start)
        if end is not None:
            query = query.where(Absence.start_at < end)
        return s.AbsenceList(items=[_mark(a, _tz(session, e)) for a, e in session.execute(query)])


def my_absences(caller: Caller, start: datetime | None, end: datetime | None) -> s.AbsenceList:
    if caller.role is not Role.STAFF or not caller.employee_id:
        raise ApiError("permission_denied", "This view is for employees.")
    return list_absences(caller, None, start, end)


def update(caller: Caller, absence_id: uuid.UUID, body: s.UpdateAbsenceRequest) -> s.AbsenceReport:
    """Managers confirm, reject or cancel. An employee may only withdraw (cancel) their own request
    while it is still requested (v3 section 20: employee self-report)."""
    staff = caller.role is Role.STAFF
    if staff and body.status != "cancelled":
        raise ApiError("permission_denied", "Only managers can confirm or reject absences.")
    with tenant_session(caller) as session:
        absence = session.scalars(select(Absence).where(Absence.id == absence_id).with_for_update()).first()
        if absence is None or (staff and str(absence.employee_id) != caller.employee_id):
            raise not_found("Absence")
        if staff and absence.status != "requested":
            raise ApiError(
                "conflict", "Only a request that is still waiting can be withdrawn. Ask your manager."
            )
        employee = session.get(Employee, absence.employee_id)
        assert employee is not None
        if not staff:
            assert_outlet(caller, str(employee.outlet_id))
        if absence.status in ("rejected", "cancelled"):
            raise ApiError("conflict", f"This absence was already {absence.status}.")
        absence.status = body.status
        session.flush()
        _audit(session, caller, f"ABSENCE_{body.status.upper()}", "absence", absence.id, None, None)
        if body.status == "confirmed":
            _outbox(session, absence)
        view = _report_view(session, absence, _tz(session, employee))
    if view.absence.status == "confirmed" and view.affected:
        view = view.model_copy(update={"repair_run_ids": _auto_repair(caller, absence_id)})
    return view
