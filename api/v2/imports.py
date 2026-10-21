"""Employee CSV onboarding (architecture v3 section 19, task B5.4).

    upload -> parse against the fixed template -> validate every row -> row-level errors
           -> fix and re-upload -> commit all rows in one transaction

Staging writes only import_jobs/import_rows. Commit creates every employee, their roles and their weekly
availability in one transaction, re-checking outlet scope and duplicate names against current data;
an invalid or expired import writes no business rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.v2 import schemas as s
from api.v2.auth import require
from api.v2.errors import ApiError, not_found
from api.v2.service import _audit, idempotent
from core.auth import Caller, can_view_outlet
from db.models import Employee, Outlet
from db.models_v2 import EmployeeAvailability, EmployeeSkill, ImportJob, ImportRow, Skill
from db.session import tenant_session
from importer import employees_csv as csvi

STAGED_FOR = timedelta(hours=24)
OUT_OF_SCOPE = "You can only import staff for outlets you manage."
NOTES = [
    "One employee per row; the header row must match the template exactly.",
    "outlet: the outlet's name or slug. skills: role names separated by ';'.",
    "hourly_rate in rupees (up to 2 decimals). Hours on the half-hour; preferred_weekly_hours may be empty.",
    "Each day: start and end as HH:MM on the half-hour (end before start means overnight), or both empty.",
    "Imported staff work up to max_weekly_hours with no overtime; change that per employee afterwards.",
]


class _Commit(BaseModel):
    import_id: uuid.UUID


def template() -> s.ImportTemplate:
    return s.ImportTemplate(columns=list(csvi.COLUMNS), example=csvi.EXAMPLE, notes=NOTES)


def _in_scope(caller: Caller, outlet_id: uuid.UUID | None) -> bool:
    return outlet_id is None or can_view_outlet(caller, str(outlet_id))


def _view(session: Session, job: ImportJob, tz: ZoneInfo) -> s.ImportJob:
    rows = session.scalars(select(ImportRow).where(ImportRow.job_id == job.id).order_by(ImportRow.row_number))
    return s.ImportJob(
        id=job.id,
        kind="employees",
        status=job.status,  # type: ignore[arg-type]
        filename=job.filename,
        row_count=job.row_count,
        error_count=job.error_count,
        file_errors=list(job.file_errors),
        created_at=job.created_at.astimezone(tz),
        expires_at=job.expires_at.astimezone(tz),
        committed_at=job.committed_at.astimezone(tz) if job.committed_at else None,
        rows=[
            s.ImportRow(
                row_number=r.row_number,
                name=r.data.get("name", ""),
                outlet_id=r.data.get("outlet_id"),
                errors=[s.ImportRowError.model_validate(e) for e in r.errors],
                employee_id=r.employee_id,
            )
            for r in rows
        ],
    )


def _tz(session: Session, caller: Caller) -> ZoneInfo:
    outlet = session.scalars(select(Outlet).order_by(Outlet.name)).first()
    return ZoneInfo(outlet.timezone if outlet else "UTC")


def _lookups(
    session: Session,
) -> tuple[dict[str, uuid.UUID], dict[str, uuid.UUID], set[tuple[uuid.UUID, str]]]:
    outlets: dict[str, uuid.UUID] = {}
    for o in session.scalars(select(Outlet)):
        outlets[o.name.lower()] = o.id
        outlets[o.slug.lower()] = o.id
    skills = {k.name.lower(): k.id for k in session.scalars(select(Skill))}
    existing = {(e.outlet_id, e.name.lower()) for e in session.scalars(select(Employee))}
    return outlets, skills, existing


def stage(caller: Caller, key: str, body: s.StageImportRequest) -> s.ImportJob:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:

        def produce() -> s.ImportJob:
            outlets, skills, existing = _lookups(session)
            file_errors, rows = csvi.parse(body.content, outlets=outlets, skills=skills, existing=existing)
            for row in rows:
                if not _in_scope(caller, row.outlet_id):
                    row.errors.append(("outlet", OUT_OF_SCOPE))
            bad = sum(1 for r in rows if r.errors)
            now = datetime.now(UTC)
            job = ImportJob(
                id=uuid.uuid7(),
                org_id=uuid.UUID(caller.org_id),
                kind="employees",
                status="invalid" if file_errors or bad or not rows else "staged",
                filename=body.filename,
                row_count=len(rows),
                error_count=bad,
                file_errors=file_errors or ([] if rows else ["The file has no employee rows."]),
                created_by_user_id=uuid.UUID(caller.user_id),
                created_at=now,
                expires_at=now + STAGED_FOR,
            )
            session.add(job)
            session.flush()
            session.add_all(
                [
                    ImportRow(
                        id=uuid.uuid7(),
                        org_id=job.org_id,
                        job_id=job.id,
                        row_number=r.row_number,
                        data=_data(r),
                        errors=[{"column": c, "message": m} for c, m in r.errors],
                    )
                    for r in rows
                ]
            )
            session.flush()
            _audit(session, caller, "IMPORT_STAGED", "import_job", job.id, None, None)
            return _view(session, job, _tz(session, caller))

        return s.ImportJob.model_validate(
            idempotent(session, caller, key, "stageEmployeeImport", body, produce)
        )


def _data(r: csvi.Row) -> dict[str, Any]:
    return {
        "name": r.name,
        "outlet_id": str(r.outlet_id) if r.outlet_id else None,
        "skill_ids": [str(k) for k in r.skill_ids],
        "hourly_rate_paise": r.hourly_rate_paise,
        "max_weekly_minutes": r.max_weekly_minutes,
        "preferred_weekly_minutes": r.preferred_weekly_minutes,
        "windows": [list(w) for w in r.windows],
    }


def _load(session: Session, import_id: uuid.UUID, *, for_update: bool = False) -> ImportJob:
    query = select(ImportJob).where(ImportJob.id == import_id)
    job = session.scalars(query.with_for_update() if for_update else query).first()
    if job is None:
        raise not_found("Import")
    return job


def get(caller: Caller, import_id: uuid.UUID) -> s.ImportJob:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:
        return _view(session, _load(session, import_id), _tz(session, caller))


def commit(caller: Caller, import_id: uuid.UUID, key: str) -> s.ImportJob:
    require(caller, "manage_employees")
    with tenant_session(caller) as session:

        def produce() -> s.ImportJob:
            job = _load(session, import_id, for_update=True)
            now = datetime.now(UTC)
            if job.status != "staged" or job.expires_at <= now:
                state = "expired" if job.status == "staged" else job.status
                raise ApiError(
                    "conflict",
                    {
                        "invalid": "This import has errors. Fix them and upload the file again.",
                        "committed": "This import was already committed.",
                        "expired": "This import expired. Upload the file again.",
                    }[state],
                    status=state,
                )
            rows = list(
                session.scalars(
                    select(ImportRow).where(ImportRow.job_id == job.id).order_by(ImportRow.row_number)
                )
            )
            _, _, existing = _lookups(session)
            clashes = []
            for r in rows:
                outlet_id = uuid.UUID(r.data["outlet_id"])
                if not _in_scope(caller, outlet_id):
                    clashes.append({"row_number": r.row_number, "column": "outlet", "message": OUT_OF_SCOPE})
                elif (outlet_id, r.data["name"].lower()) in existing:
                    clashes.append(
                        {
                            "row_number": r.row_number,
                            "column": "name",
                            "message": "An employee with this name was added since the upload.",
                        }
                    )
            if clashes:
                raise ApiError("conflict", "Some rows no longer fit. Upload the file again.", rows=clashes)
            today = now.date()
            for r in rows:
                d = r.data
                employee = Employee(
                    id=uuid.uuid7(),
                    org_id=job.org_id,
                    outlet_id=uuid.UUID(d["outlet_id"]),
                    name=d["name"],
                    aliases=[],
                    job_role="staff",
                    pay_type="hourly",
                    hourly_rate=Decimal(d["hourly_rate_paise"]) / 100,
                    monthly_base=None,
                    phone="",
                    joined_on=today,
                    status="active",
                    regular_weekly_minutes=d["max_weekly_minutes"],
                    max_weekly_minutes=d["max_weekly_minutes"],
                    preferred_weekly_minutes=d["preferred_weekly_minutes"],
                    tags=["imported"],
                    overtime_allowed=False,
                    cross_outlet_eligible=False,
                    revision=1,
                )
                session.add(employee)
                session.flush()
                session.add_all(
                    [
                        EmployeeSkill(
                            org_id=job.org_id, employee_id=employee.id, skill_id=uuid.UUID(k), level=1
                        )
                        for k in d["skill_ids"]
                    ]
                    + [
                        EmployeeAvailability(
                            id=uuid.uuid7(),
                            org_id=job.org_id,
                            employee_id=employee.id,
                            weekday=w[0],
                            start_minute=w[1],
                            end_minute=w[2],
                            kind="available",
                            valid_from=today,
                        )
                        for w in d["windows"]
                    ]
                )
                r.employee_id = employee.id
            job.status = "committed"
            job.committed_at = now
            session.flush()
            _audit(session, caller, "IMPORT_COMMITTED", "import_job", job.id, None, None)
            return _view(session, job, _tz(session, caller))

        return s.ImportJob.model_validate(
            idempotent(session, caller, key, "commitImport", _Commit(import_id=import_id), produce)
        )
