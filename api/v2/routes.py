"""Scheduling v2 route declarations (contract surface for P1-P2).

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

from api.v2 import auth as v2auth
from api.v2 import schemas as s
from api.v2 import service

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


def _header(description: str) -> dict[str, Any]:
    return {"description": description, "schema": {"type": "string"}}


ETAG = _header("Opaque validator. Send it back as If-None-Match to get 304 when nothing changed.")
IMMUTABLE = _header(
    "`private, max-age=31536000, immutable` for published and superseded versions (they never "
    "change); `private, no-cache` for drafts."
)
NOT_MODIFIED: dict[int | str, dict[str, Any]] = {
    304: {
        "description": "Not modified: the If-None-Match value is still current. No body.",
        "headers": {"ETag": ETAG},
    }
}
IfNoneMatch = Annotated[
    str | None, Header(alias="If-None-Match", description="ETag from a previous response.")
]


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
    from api.v2 import errors

    app.include_router(router)
    app.add_exception_handler(NotImplementedYet, lambda _req, _exc: not_implemented_response())
    errors.install(app)


@router.post(
    "/session/demo",
    operation_id="createDemoSession",
    response_model=s.DemoSession,
    status_code=status.HTTP_201_CREATED,
    responses={code: {"model": s.ErrorResponse} for code in (403, 422, 429, 501)},
)
def create_demo_session(body: s.DemoSessionRequest) -> s.DemoSession:
    """Public synthetic demo only: issues a short-lived token for an isolated demo org (B6.2).
    403 permission_denied when the deployment is private."""
    return v2auth.demo_session(body.persona)


@router.get("/me", operation_id="getMe", response_model=s.Me, responses=_errors())
def get_me(caller: v2auth.CallerDep) -> s.Me:
    return v2auth.me(caller)


@router.get("/me/shifts", operation_id="getMyWeek", response_model=s.MyWeek, responses=_errors(403, 422))
def get_my_week(auth: Auth, week_start: WeekStart) -> s.MyWeek:
    """Staff only: the caller's own published shifts."""
    _stub()


@router.get("/outlets", operation_id="listOutlets", response_model=s.OutletList, responses=_errors())
def list_outlets(caller: v2auth.CallerDep) -> s.OutletList:
    """Owners see every outlet; managers and staff see their own."""
    return service.list_outlets(caller)


@router.get("/skills", operation_id="listSkills", response_model=s.SkillList, responses=_errors())
def list_skills(caller: v2auth.CallerDep) -> s.SkillList:
    return service.list_skills(caller)


@router.get(
    "/employees", operation_id="listEmployees", response_model=s.EmployeeList, responses=_errors(403, 422)
)
def list_employees(
    caller: v2auth.CallerDep,
    outlet_id: Annotated[
        UUID | None, Query(description="Home outlet filter; required for managers' own outlet only.")
    ] = None,
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(active|inactive)$")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> s.EmployeeList:
    return service.list_employees(caller, outlet_id, status_filter, cursor, limit)


@router.post(
    "/employees",
    operation_id="createEmployee",
    response_model=s.Employee,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 409, 422),
)
def create_employee(
    caller: v2auth.CallerDep, idempotency_key: IdempotencyKey, body: s.EmployeeCreate
) -> s.Employee:
    return service.create_employee(caller, idempotency_key, body)


@router.get(
    "/employees/{employee_id}",
    operation_id="getEmployee",
    response_model=s.Employee,
    responses=_errors(403, 404, 422),
)
def get_employee(caller: v2auth.CallerDep, employee_id: UUID) -> s.Employee:
    return service.get_employee(caller, employee_id)


@router.patch(
    "/employees/{employee_id}",
    operation_id="updateEmployee",
    response_model=s.Employee,
    responses=_errors(403, 404, 409, 422),
)
def update_employee(caller: v2auth.CallerDep, employee_id: UUID, body: s.EmployeeUpdate) -> s.Employee:
    """409 stale_version when base_revision is not current; details.current_revision is set."""
    return service.update_employee(caller, employee_id, body)


@router.get(
    "/employees/{employee_id}/availability",
    operation_id="getAvailability",
    response_model=s.Availability,
    responses=_errors(403, 404, 422),
)
def get_availability(caller: v2auth.CallerDep, employee_id: UUID) -> s.Availability:
    return service.get_availability(caller, employee_id)


@router.put(
    "/employees/{employee_id}/availability",
    operation_id="putAvailability",
    response_model=s.Availability,
    responses=_errors(403, 404, 409, 422),
)
def put_availability(
    caller: v2auth.CallerDep, employee_id: UUID, body: s.AvailabilityUpdate
) -> s.Availability:
    return service.put_availability(caller, employee_id, body)


@router.get(
    "/outlets/{outlet_id}/staffing-requirements",
    operation_id="getStaffingRequirements",
    response_model=s.StaffingRequirements,
    responses=_errors(403, 404, 422),
)
def get_staffing_requirements(
    caller: v2auth.CallerDep, outlet_id: UUID, week_start: WeekStart
) -> s.StaffingRequirements:
    return service.get_staffing(caller, outlet_id, week_start)


@router.put(
    "/outlets/{outlet_id}/staffing-requirements",
    operation_id="putStaffingRequirements",
    response_model=s.StaffingRequirements,
    responses=_errors(403, 404, 409, 422),
)
def put_staffing_requirements(
    caller: v2auth.CallerDep, outlet_id: UUID, week_start: WeekStart, body: s.StaffingRequirementsUpdate
) -> s.StaffingRequirements:
    return service.put_staffing(caller, outlet_id, week_start, body)


@router.get(
    "/outlets/{outlet_id}/schedules/{week_start}",
    operation_id="getScheduleWeek",
    response_model=s.ScheduleWeek,
    responses={
        **_errors(403, 404, 422),
        **NOT_MODIFIED,
        200: {"headers": {"ETag": _header("Derived from current_version_id; changes on every publication.")}},
    },
)
def get_schedule_week(
    auth: Auth, outlet_id: UUID, week_start: date, if_none_match: IfNoneMatch = None
) -> s.ScheduleWeek:
    """200 with schedule_id null when the week has no schedule yet; 404 only for unknown outlets."""
    _stub()


@router.get(
    "/schedule-versions/{version_id}",
    operation_id="getScheduleVersion",
    response_model=s.ScheduleVersion,
    responses={
        **_errors(403, 404, 422),
        **NOT_MODIFIED,
        200: {"headers": {"ETag": ETAG, "Cache-Control": IMMUTABLE}},
    },
)
def get_schedule_version(
    auth: Auth, version_id: UUID, if_none_match: IfNoneMatch = None
) -> s.ScheduleVersion:
    _stub()


@router.post(
    "/outlets/{outlet_id}/schedules/{week_start}/generate",
    operation_id="generateSchedule",
    response_model=s.OptimizationRun,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **_errors(403, 404, 409, 422),
        409: {
            "model": s.ErrorResponse,
            "description": "stale_version (base changed), idempotency_conflict (key reused with other input) "
            "or run_in_progress (another run is active for this schedule; details.run_id is that run: "
            "attach to it and poll instead of showing an error).",
        },
        429: {
            "model": s.ErrorResponse,
            "description": "rate_limited: the organization's run cap is reached.",
            "headers": {"Retry-After": _header("Seconds to wait before retrying.")},
        },
    },
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
