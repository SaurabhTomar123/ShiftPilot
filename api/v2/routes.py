"""Scheduling v2 route declarations (contract surface for P1-P2).

Handlers are stubs that answer 501 `not_implemented` until B1.2/B2.3 implement them; the
signatures, status codes and error responses here are what contracts/v2/openapi.json exports.
Not mounted on api.main yet.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, Path, Query, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime

from api.v2 import absences, candidates, drafts, generation, imports, proposals, rosters, service, staffing
from api.v2 import auth as v2auth
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
OptionalIdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=80,
        description="Recommended: with it a repeat returns the stored result, so a lost response can be "
        "retried safely; without it only revision fencing applies.",
    ),
]
WeekStart = Annotated[date, Query(description="Monday of the week, outlet-local.")]


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: {"model": s.ErrorResponse} for code in (401, 501, *codes)}


def _header(description: str) -> dict[str, Any]:
    return {"description": description, "schema": {"type": "string"}}


ETAG = _header("Opaque validator. Send it back as If-None-Match to get 304 when nothing changed.")
IMMUTABLE = _header(
    "Always `private, no-cache`: shift content never changes, but status does (published later becomes "
    "superseded), so clients revalidate with If-None-Match and get 304 when nothing changed."
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
def get_my_week(caller: v2auth.CallerDep, week_start: WeekStart) -> s.MyWeek:
    """Staff only: the caller's own published shifts."""
    return rosters.my_week(caller, week_start)


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


ImportPath = Annotated[UUID, Path(description="An onboarding import.")]


@router.get(
    "/imports/employees/template",
    operation_id="getEmployeeImportTemplate",
    response_model=s.ImportTemplate,
    responses=_errors(403),
)
def get_employee_import_template(caller: v2auth.CallerDep) -> s.ImportTemplate:
    """The fixed CSV columns, one valid example row and the rules (architecture v3 section 19)."""
    v2auth.require(caller, "manage_employees")
    return imports.template()


@router.post(
    "/imports/employees",
    operation_id="stageEmployeeImport",
    response_model=s.ImportJob,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 409, 422),
)
def stage_employee_import(
    caller: v2auth.CallerDep, idempotency_key: IdempotencyKey, body: s.StageImportRequest
) -> s.ImportJob:
    """Parse and validate every row; writes no employees. status staged (all valid) or invalid (fix
    the row errors and upload again)."""
    return imports.stage(caller, idempotency_key, body)


@router.get(
    "/imports/{import_id}",
    operation_id="getImport",
    response_model=s.ImportJob,
    responses=_errors(403, 404, 422),
)
def get_import(caller: v2auth.CallerDep, import_id: ImportPath) -> s.ImportJob:
    return imports.get(caller, import_id)


@router.post(
    "/imports/{import_id}/commit",
    operation_id="commitImport",
    response_model=s.ImportJob,
    responses=_errors(403, 404, 409, 422),
)
def commit_import(
    caller: v2auth.CallerDep, import_id: ImportPath, idempotency_key: IdempotencyKey
) -> s.ImportJob:
    """Create every employee in one transaction. 409 conflict when the import is invalid, expired or
    already committed, or when a row no longer fits (details.rows)."""
    return imports.commit(caller, import_id, idempotency_key)


@router.get(
    "/outlets/{outlet_id}/shift-templates",
    operation_id="listShiftTemplates",
    response_model=s.ShiftTemplateList,
    responses=_errors(403, 404, 422),
)
def list_shift_templates(caller: v2auth.CallerDep, outlet_id: UUID) -> s.ShiftTemplateList:
    """The outlet's active shift shapes, for add_from_template edits. Read-only here."""
    return drafts.list_shift_templates(caller, outlet_id)


@router.get(
    "/outlets/{outlet_id}/staffing-templates",
    operation_id="listStaffingTemplates",
    response_model=s.StaffingTemplateSet,
    responses=_errors(403, 404, 422),
)
def list_staffing_templates(caller: v2auth.CallerDep, outlet_id: UUID) -> s.StaffingTemplateSet:
    """The outlet's weekly staffing template: weekday x block x role -> minimum and preferred staff."""
    return staffing.list_templates(caller, outlet_id)


@router.put(
    "/outlets/{outlet_id}/staffing-templates",
    operation_id="putStaffingTemplates",
    response_model=s.StaffingTemplateSet,
    responses=_errors(403, 404, 409, 422),
)
def put_staffing_templates(
    caller: v2auth.CallerDep, outlet_id: UUID, body: s.StaffingTemplateUpdate
) -> s.StaffingTemplateSet:
    """Replace the whole template set. 409 stale_version when base_revision is not current; 422 when
    blocks of one weekday and role overlap. Weeks change only when expanded."""
    return staffing.put_templates(caller, outlet_id, body)


@router.post(
    "/outlets/{outlet_id}/staffing-requirements/expand",
    operation_id="expandStaffingRequirements",
    response_model=s.StaffingRequirements,
    responses=_errors(403, 404, 409, 422),
)
def expand_staffing_requirements(
    caller: v2auth.CallerDep,
    outlet_id: UUID,
    week_start: WeekStart,
    idempotency_key: IdempotencyKey,
    body: s.ExpandStaffingRequest,
) -> s.StaffingRequirements:
    """Regenerate the week's template (and, if asked, band) rows from the template. Manual overrides
    survive; the outlet-week demand_revision is bumped. 409 stale_version on a stale base."""
    return staffing.expand(caller, outlet_id, week_start, idempotency_key, body)


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
    caller: v2auth.CallerDep, outlet_id: UUID, week_start: date, if_none_match: IfNoneMatch = None
) -> Response:
    """200 with schedule_id null when the week has no schedule yet; 404 only for unknown outlets."""
    etag, body = rosters.schedule_week(caller, outlet_id, week_start, if_none_match)
    if body is None:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(body.model_dump(mode="json"), headers={"ETag": etag})


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
    caller: v2auth.CallerDep, version_id: UUID, if_none_match: IfNoneMatch = None
) -> Response:
    etag, cache, body = rosters.schedule_version(caller, version_id, if_none_match)
    if body is None:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cache})
    return JSONResponse(body.model_dump(mode="json"), headers={"ETag": etag, "Cache-Control": cache})


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
    caller: v2auth.CallerDep,
    outlet_id: UUID,
    week_start: date,
    idempotency_key: IdempotencyKey,
    body: s.GenerateRequest,
) -> s.OptimizationRun:
    """Queues a run and returns it (job_state queued). Poll getOptimizationRun. 409 stale_version
    when base_version_id is no longer the published version."""
    return generation.enqueue(caller, outlet_id, week_start, idempotency_key, body)


@router.get(
    "/optimization-runs/{run_id}",
    operation_id="getOptimizationRun",
    response_model=s.OptimizationRun,
    responses=_errors(403, 404, 422),
)
def get_optimization_run(caller: v2auth.CallerDep, run_id: UUID) -> s.OptimizationRun:
    return generation.get_run(caller, run_id)


@router.get(
    "/optimization-candidates/{candidate_id}",
    operation_id="getOptimizationCandidate",
    response_model=s.CandidateDetail,
    responses=_errors(403, 404, 422),
)
def get_optimization_candidate(caller: v2auth.CallerDep, candidate_id: UUID) -> s.CandidateDetail:
    """The candidate's diff against its base version. Candidates are not versions until selected."""
    return candidates.get_candidate(caller, candidate_id)


@router.post(
    "/optimization-candidates/{candidate_id}/select",
    operation_id="selectOptimizationCandidate",
    response_model=s.ScheduleVersion,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 404, 409, 422),
)
def select_optimization_candidate(
    caller: v2auth.CallerDep, candidate_id: UUID, idempotency_key: IdempotencyKey
) -> s.ScheduleVersion:
    """Materializes the candidate into a draft (its base_version_id is the run's base, so publishing it
    after someone else published returns stale_version). Selecting again returns the same draft while it
    is still a draft."""
    return candidates.select_candidate(caller, candidate_id, idempotency_key)


# ---------------------------------------------------------------- P3: drafts, edits, publication, history
# Declared in contract 2.3; implemented in B3.1-B3.3. Authentication runs before the 501.

VersionPath = Annotated[UUID, Path(description="A schedule version (draft, published or superseded).")]


@router.post(
    "/outlets/{outlet_id}/schedules/{week_start}/drafts",
    operation_id="createDraft",
    response_model=s.ScheduleVersion,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 404, 409, 422),
)
def create_draft(
    caller: v2auth.CallerDep,
    outlet_id: UUID,
    week_start: date,
    idempotency_key: IdempotencyKey,
    body: s.CreateDraftRequest,
) -> s.ScheduleVersion:
    """A new draft copied from the published version (or another version of the same week). 409
    stale_version when base_version_id is no longer the published version."""
    return drafts.create_draft(caller, outlet_id, week_start, idempotency_key, body)


@router.post(
    "/schedule-versions/{version_id}/edits/preview",
    operation_id="previewEdits",
    response_model=s.EditPreview,
    responses=_errors(403, 404, 409, 422),
)
def preview_edits(caller: v2auth.CallerDep, version_id: VersionPath, body: s.EditRequest) -> s.EditPreview:
    """Validate edits against the draft without writing anything (drag/resize/keyboard previews)."""
    return drafts.preview_edits(caller, version_id, body)


@router.post(
    "/schedule-versions/{version_id}/edits",
    operation_id="applyEdits",
    response_model=s.ScheduleVersion,
    responses=_errors(403, 404, 409, 422),
)
def apply_edits(
    caller: v2auth.CallerDep,
    version_id: VersionPath,
    body: s.EditRequest,
    idempotency_key: OptionalIdempotencyKey = None,
) -> s.ScheduleVersion:
    """Apply edits to a draft. 409 stale_version when expected_revision is not current
    (details.current_revision); 409 conflict when the version is not a draft. Edits that break rules
    are applied and reported in validation; publishing is what refuses hard violations."""
    return drafts.apply_edits(caller, version_id, body, idempotency_key)


@router.post(
    "/schedule-versions/{version_id}/publish",
    operation_id="publishVersion",
    response_model=s.PublishResult,
    responses=_errors(403, 404, 409, 422),
)
def publish_version(
    caller: v2auth.CallerDep, version_id: VersionPath, idempotency_key: IdempotencyKey, body: s.PublishRequest
) -> s.PublishResult:
    """Atomically publish a draft and supersede the current version. 409 stale_version when the published
    version or the draft revision moved; 422 validation_failed with details.violations when the draft has
    hard violations against current facts."""
    return drafts.publish(caller, version_id, idempotency_key, body)


ProposalPath = Annotated[UUID, Path(description="A schedule proposal.")]


@router.post(
    "/proposals",
    operation_id="createProposal",
    response_model=s.Proposal,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 404, 409, 422),
)
def create_proposal(
    caller: v2auth.CallerDep, idempotency_key: IdempotencyKey, body: s.CreateProposalRequest
) -> s.Proposal:
    """Propose a draft for publication, recording its revision and its metrics against current facts
    (what the manager agrees to). 409 stale_version when the draft revision moved; 422 validation_failed
    when it has hard violations."""
    return proposals.create(caller, idempotency_key, body)


@router.get(
    "/proposals",
    operation_id="listProposals",
    response_model=s.ProposalList,
    responses=_errors(403, 404, 422),
)
def list_proposals(
    caller: v2auth.CallerDep,
    schedule_id: Annotated[UUID, Query(description="The week (schedule) whose proposals to list.")],
    statuses: Annotated[
        list[s.ProposalStatus] | None,
        Query(
            alias="status",
            description="Repeat to filter, e.g. status=pending. A pending proposal past expiry is expired.",
        ),
    ] = None,
) -> s.ProposalList:
    """Find a week's proposals, e.g. the pending one after a reload. Newest first."""
    return proposals.list_for_schedule(caller, schedule_id, statuses)


@router.get(
    "/proposals/{proposal_id}",
    operation_id="getProposal",
    response_model=s.Proposal,
    responses=_errors(403, 404, 422),
)
def get_proposal(caller: v2auth.CallerDep, proposal_id: ProposalPath) -> s.Proposal:
    return proposals.get(caller, proposal_id)


@router.post(
    "/proposals/{proposal_id}/approve",
    operation_id="approveProposal",
    response_model=s.ProposalDecision,
    responses=_errors(403, 404, 409, 422),
)
def approve_proposal(
    caller: v2auth.CallerDep,
    proposal_id: ProposalPath,
    idempotency_key: IdempotencyKey,
    body: s.ApproveProposalRequest,
) -> s.ProposalDecision:
    """The publication transaction (architecture v3 section 31). Always 200 with an `outcome`: published,
    stale, invalid or changed. 409 conflict only when the proposal is no longer pending or expired."""
    return proposals.approve(caller, proposal_id, idempotency_key, body)


@router.post(
    "/proposals/{proposal_id}/reject",
    operation_id="rejectProposal",
    response_model=s.Proposal,
    responses=_errors(403, 404, 409, 422),
)
def reject_proposal(caller: v2auth.CallerDep, proposal_id: ProposalPath) -> s.Proposal:
    return proposals.reject(caller, proposal_id)


@router.post(
    "/schedule-versions/{version_id}/discard",
    operation_id="discardDraft",
    response_model=s.ScheduleVersionSummary,
    responses=_errors(403, 404, 409, 422),
)
def discard_draft(
    caller: v2auth.CallerDep, version_id: VersionPath, idempotency_key: OptionalIdempotencyKey = None
) -> s.ScheduleVersionSummary:
    return drafts.discard_draft(caller, version_id, idempotency_key)


@router.get(
    "/schedules/{schedule_id}/versions",
    operation_id="listVersions",
    response_model=s.VersionHistory,
    responses=_errors(403, 404, 422),
)
def list_versions(caller: v2auth.CallerDep, schedule_id: UUID) -> s.VersionHistory:
    return drafts.list_versions(caller, schedule_id)


@router.get(
    "/schedule-versions/{version_id}/compare",
    operation_id="compareVersions",
    response_model=s.VersionDiff,
    responses=_errors(403, 404, 422),
)
def compare_versions(
    caller: v2auth.CallerDep,
    version_id: VersionPath,
    with_version: Annotated[UUID, Query(alias="with", description="The version to compare against.")],
) -> s.VersionDiff:
    """Changes from `with` to this version, keyed on logical_shift_id."""
    return drafts.compare(caller, version_id, with_version)


@router.post(
    "/schedule-versions/{version_id}/restore",
    operation_id="restoreVersion",
    response_model=s.ScheduleVersion,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 404, 409, 422),
)
def restore_version(
    caller: v2auth.CallerDep, version_id: VersionPath, idempotency_key: IdempotencyKey, body: s.RestoreRequest
) -> s.ScheduleVersion:
    """A new draft with this version's shifts, validated against current facts (an absent employee's
    restored shift shows as a hard violation; it is never revived silently). History is never rewritten."""
    return drafts.restore(caller, version_id, idempotency_key, body)


# ---------------------------------------------------------------- P4: absences and repair (contract 2.4)


@router.post(
    "/absences",
    operation_id="reportAbsence",
    response_model=s.AbsenceReport,
    status_code=status.HTTP_201_CREATED,
    responses=_errors(403, 404, 409, 422),
)
def report_absence(
    caller: v2auth.CallerDep, idempotency_key: IdempotencyKey, body: s.ReportAbsenceRequest
) -> s.AbsenceReport:
    """Records the absence as a fact first (it stands whether or not a repair succeeds). A confirmed
    absence then enqueues a repair run per affected schedule (repair_run_ids); locked affected shifts are
    listed in lock_conflicts and need explicit authorization through repairSchedule."""
    return absences.report(caller, idempotency_key, body)


@router.get(
    "/absences", operation_id="listAbsences", response_model=s.AbsenceList, responses=_errors(403, 422)
)
def list_absences(
    caller: v2auth.CallerDep,
    outlet_id: UUID | None = None,
    start: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    end: Annotated[AwareDatetime | None, Query(alias="to")] = None,
) -> s.AbsenceList:
    return absences.list_absences(caller, outlet_id, start, end)


@router.patch(
    "/absences/{absence_id}",
    operation_id="updateAbsence",
    response_model=s.AbsenceReport,
    responses=_errors(403, 404, 409, 422),
)
def update_absence(
    caller: v2auth.CallerDep, absence_id: UUID, body: s.UpdateAbsenceRequest
) -> s.AbsenceReport:
    """Managers confirm, reject or cancel. Confirming enqueues repairs exactly as reportAbsence does."""
    return absences.update(caller, absence_id, body)


@router.post(
    "/outlets/{outlet_id}/schedules/{week_start}/repair",
    operation_id="repairSchedule",
    response_model=s.OptimizationRun,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **_errors(403, 404, 409, 422),
        429: {"model": s.ErrorResponse, "headers": {"Retry-After": _header("Seconds to wait.")}},
    },
)
def repair_schedule(
    caller: v2auth.CallerDep,
    outlet_id: UUID,
    week_start: date,
    idempotency_key: IdempotencyKey,
    body: s.RepairRequest,
) -> s.OptimizationRun:
    """Repair runs are claimed before batch work and never blocked by it. An active repair for the same
    absence is returned (idempotent). 409 conflict lists locked affected shifts without authorization."""
    return generation.enqueue_repair(caller, outlet_id, week_start, idempotency_key, body)
