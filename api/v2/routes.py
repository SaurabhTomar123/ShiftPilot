"""Scheduling v2 route declarations (contract surface for P1–P2).

Handlers are stubs that answer 501 `not_implemented` until B1.2/B2.3 implement them; the
signatures, status codes and error responses here are what contracts/v2/openapi.json exports.
Not mounted on api.main yet.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, Query, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.v2 import schemas as s

bearer = HTTPBearer(auto_error=False)
Auth = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=80,
        description="Unique per logical request; replays return the "
        "original result, a different body with the same key is 409.",
    ),
]
WeekStart = Annotated[date, Query(description="Monday of the week, outlet-local.")]


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: {"model": s.ErrorResponse} for code in (401, 501, *codes)}


class NotImplementedYet(Exception):
    pass


def _stub() -> NoReturn:
    raise NotImplementedYet


def not_implemented_response() -> JSONResponse:
    body = s.ErrorResponse(
        error=s.ErrorBody(
            code="not_implemented",
            retryable=False,
            message="This endpoint is declared but not implemented yet.",
        )
    )
    return JSONResponse(status_code=501, content=body.model_dump(mode="json"))


router = APIRouter(prefix="/v2")


def install(app: FastAPI) -> None:
    app.include_router(router)
    app.add_exception_handler(NotImplementedYet, lambda _req, _exc: not_implemented_response())


@router.get("/me", operation_id="getMe", response_model=s.Me, responses=_errors())
def get_me(auth: Auth) -> s.Me:
    _stub()


@router.get("/me/shifts", operation_id="getMyWeek", response_model=s.MyWeek, responses=_errors(403, 422))
def get_my_week(auth: Auth, week_start: WeekStart) -> s.MyWeek:
    """Staff only: the caller's own published shifts."""
    _stub()


@router.get("/outlets", operation_id="listOutlets", response_model=s.OutletList, responses=_errors())
def list_outlets(auth: Auth) -> s.OutletList:
    """Owners see every outlet; managers and staff see their own."""
    _stub()


@router.get("/skills", operation_id="listSkills", response_model=s.SkillList, responses=_errors())
def list_skills(auth: Auth) -> s.SkillList:
    _stub()


@router.get(
    "/employees", operation_id="listEmployees", response_model=s.EmployeeList, responses=_errors(403, 422)
)
def list_employees(
    auth: Auth,
    outlet_id: Annotated[
        UUID | None, Query(description="Home outlet filter; required for managers' own outlet only.")
    ] = None,
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(active|inactive)$")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> s.EmployeeList:
    _stub()


@router.post(
    "/employees",
    operation_id="createEmployee",
    response_model=s.Employee,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 409, 422),
)
def create_employee(auth: Auth, idempotency_key: IdempotencyKey, body: s.EmployeeCreate) -> s.Employee:
    _stub()


@router.get(
    "/employees/{employee_id}",
    operation_id="getEmployee",
    response_model=s.Employee,
    responses=_errors(403, 404, 422),
)
def get_employee(auth: Auth, employee_id: UUID) -> s.Employee:
    _stub()


@router.patch(
    "/employees/{employee_id}",
    operation_id="updateEmployee",
    response_model=s.Employee,
    responses=_errors(403, 404, 409, 422),
)
def update_employee(auth: Auth, employee_id: UUID, body: s.EmployeeUpdate) -> s.Employee:
    """409 stale_version when base_revision is not current; details.current_revision is set."""
    _stub()


@router.get(
    "/employees/{employee_id}/availability",
    operation_id="getAvailability",
    response_model=s.Availability,
    responses=_errors(403, 404, 422),
)
def get_availability(auth: Auth, employee_id: UUID) -> s.Availability:
    _stub()


@router.put(
    "/employees/{employee_id}/availability",
    operation_id="putAvailability",
    response_model=s.Availability,
    responses=_errors(403, 404, 409, 422),
)
def put_availability(auth: Auth, employee_id: UUID, body: s.AvailabilityUpdate) -> s.Availability:
    _stub()


@router.get(
    "/outlets/{outlet_id}/staffing-requirements",
    operation_id="getStaffingRequirements",
    response_model=s.StaffingRequirements,
    responses=_errors(403, 404, 422),
)
def get_staffing_requirements(auth: Auth, outlet_id: UUID, week_start: WeekStart) -> s.StaffingRequirements:
    _stub()


@router.put(
    "/outlets/{outlet_id}/staffing-requirements",
    operation_id="putStaffingRequirements",
    response_model=s.StaffingRequirements,
    responses=_errors(403, 404, 409, 422),
)
def put_staffing_requirements(
    auth: Auth, outlet_id: UUID, week_start: WeekStart, body: s.StaffingRequirementsUpdate
) -> s.StaffingRequirements:
    _stub()


@router.get(
    "/outlets/{outlet_id}/schedules/{week_start}",
    operation_id="getScheduleWeek",
    response_model=s.ScheduleWeek,
    responses=_errors(403, 404, 422),
)
def get_schedule_week(auth: Auth, outlet_id: UUID, week_start: date) -> s.ScheduleWeek:
    """200 with schedule_id null when the week has no schedule yet; 404 only for unknown outlets."""
    _stub()


@router.get(
    "/schedule-versions/{version_id}",
    operation_id="getScheduleVersion",
    response_model=s.ScheduleVersion,
    responses=_errors(403, 404, 422),
)
def get_schedule_version(auth: Auth, version_id: UUID) -> s.ScheduleVersion:
    _stub()


@router.post(
    "/outlets/{outlet_id}/schedules/{week_start}/generate",
    operation_id="generateSchedule",
    response_model=s.OptimizationRun,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_errors(403, 404, 409, 422, 429),
)
def generate_schedule(
    auth: Auth, outlet_id: UUID, week_start: date, idempotency_key: IdempotencyKey, body: s.GenerateRequest
) -> s.OptimizationRun:
    """Queues a run and returns it (job_state queued). Poll getOptimizationRun. 409 stale_version
    when base_version_id is no longer the published version."""
    _stub()


@router.get(
    "/optimization-runs/{run_id}",
    operation_id="getOptimizationRun",
    response_model=s.OptimizationRun,
    responses=_errors(403, 404, 422),
)
def get_optimization_run(auth: Auth, run_id: UUID) -> s.OptimizationRun:
    _stub()
