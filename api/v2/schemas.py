"""Scheduling v2 request/response models: the provider side of contracts/v2.

Exported to contracts/v2/openapi.json by `python -m api.v2.contract_build`. Changing a model is a
contract change: bump CONTRACT_VERSION, rebuild, and hand off to the web consumer.

Conventions (docs/runbooks/v2-schema-plan.md section 6): instants are RFC 3339 with offset, recurring
times are minutes from outlet-local midnight, durations are integer minutes, money is integer
paise. Weekday 0 is Monday.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "3.1.0-p4"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Weekday = Annotated[int, Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday")]
MinuteOfDay = Annotated[
    int,
    Field(
        ge=0,
        le=2880,
        description="Minutes from outlet-local midnight; values above 1440 continue past midnight",
    ),
]
Minutes = Annotated[int, Field(ge=0)]
Ratio = Annotated[float, Field(ge=0, le=1)]
Role = Literal["owner", "manager", "staff"]


# ---------------------------------------------------------------- errors

ErrorCode = Literal[
    "unauthenticated",
    "permission_denied",
    "not_found",
    "validation_failed",
    "stale_version",
    "conflict",
    "idempotency_conflict",
    "run_in_progress",
    "rate_limited",
    "not_implemented",
    "internal",
]


class ErrorBody(Model):
    code: ErrorCode
    message: str = Field(description="Safe to show to the user.")
    retryable: bool
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Code-specific structured facts, "
        "e.g. field errors or the current revision for stale_version.",
    )
    trace_id: str | None = Field(default=None, description="Quote this when reporting a problem.")


class ErrorResponse(Model):
    error: ErrorBody


class Money(Model):
    amount_paise: int
    currency: Literal["INR"] = "INR"


# ---------------------------------------------------------------- identity and org


Capability = Literal[
    "view_all_outlets",
    "manage_employees",
    "edit_demand",
    "generate",
    "publish",
    "view_costs",
    "approve_cross_outlet",
    "view_own_schedule",
    "report_own_absence",
]


class Me(Model):
    user_id: UUID
    org_id: UUID
    org_name: str
    display_name: str
    role: Role
    outlet_id: UUID | None = Field(description="Set for managers and staff; null for owners.")
    employee_id: UUID | None = Field(description="Set for staff.")
    timezone: str = Field(description="Organization default IANA timezone.")
    capabilities: list[Capability] = Field(
        description="What this caller may do. Use it to show or hide controls; the server still "
        "enforces every action."
    )


class DemoSessionRequest(Model):
    persona: Literal["owner", "manager", "staff"]


class DemoSession(Model):
    """Synthetic public demo only; private deployments never expose this endpoint."""

    access_token: str = Field(description="Send as `Authorization: Bearer <token>`.")
    token_type: Literal["bearer"] = "bearer"
    expires_at: AwareDatetime
    me: Me


class OperatingWindow(Model):
    weekday: Weekday
    open_minute: MinuteOfDay
    close_minute: MinuteOfDay

    @model_validator(mode="after")
    def _ordered(self) -> OperatingWindow:
        if self.close_minute <= self.open_minute:
            raise ValueError("close_minute must be after open_minute")
        return self


class Outlet(Model):
    id: UUID
    name: str
    slug: str
    timezone: str
    operating_hours: list[OperatingWindow]


class OutletList(Model):
    items: list[Outlet]


class Skill(Model):
    id: UUID
    name: str


class SkillList(Model):
    items: list[Skill]


# ---------------------------------------------------------------- employees


class EmployeeSkill(Model):
    skill_id: UUID
    level: int = Field(ge=1, le=3)


class EmployeeFields(Model):
    name: str = Field(min_length=1, max_length=120)
    home_outlet_id: UUID
    status: Literal["active", "inactive"]
    hourly_rate: Money
    skills: list[EmployeeSkill]
    tags: list[str]
    regular_weekly_minutes: Minutes = Field(description="Overtime threshold.")
    max_weekly_minutes: Minutes = Field(description="Absolute cap; overtime permission never lifts it.")
    preferred_weekly_minutes: Minutes | None
    overtime_allowed: bool
    cross_outlet_eligible: bool


class Employee(EmployeeFields):
    id: UUID
    revision: int = Field(ge=1, description="Send as base_revision when updating.")


class EmployeeList(Model):
    items: list[Employee]
    next_cursor: str | None


class EmployeeCreate(EmployeeFields):
    pass


class EmployeeUpdate(Model):
    """Partial update. Omit a field to leave it unchanged. Sending null for a field that cannot be
    null is rejected (422 validation_failed); only preferred_weekly_minutes accepts null, which
    clears it."""

    base_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    home_outlet_id: UUID | None = None
    status: Literal["active", "inactive"] | None = None
    hourly_rate: Money | None = None
    skills: list[EmployeeSkill] | None = None
    tags: list[str] | None = None
    regular_weekly_minutes: Minutes | None = None
    max_weekly_minutes: Minutes | None = None
    preferred_weekly_minutes: Minutes | None = None
    overtime_allowed: bool | None = None
    cross_outlet_eligible: bool | None = None

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> EmployeeUpdate:
        nulls = sorted(
            f for f in self.model_fields_set if getattr(self, f) is None and f != "preferred_weekly_minutes"
        )
        if nulls:
            raise ValueError(
                f"null is not allowed for {', '.join(nulls)}; omit a field to leave it unchanged"
            )
        return self


class AvailabilityWindow(Model):
    weekday: Weekday
    start_minute: MinuteOfDay
    end_minute: MinuteOfDay
    kind: Literal["available", "preferred", "unavailable"]

    @model_validator(mode="after")
    def _ordered(self) -> AvailabilityWindow:
        if self.end_minute <= self.start_minute:
            raise ValueError("end_minute must be after start_minute")
        return self


class Availability(Model):
    employee_id: UUID
    windows: list[AvailabilityWindow]
    revision: int = Field(ge=1)


class AvailabilityUpdate(Model):
    base_revision: int = Field(ge=1)
    windows: list[AvailabilityWindow]


# ---------------------------------------------------------------- demand


class StaffingInterval(Model):
    skill_id: UUID
    interval_start: AwareDatetime
    interval_end: AwareDatetime
    minimum_required: int = Field(ge=0, description="Hard: a roster below this is infeasible.")
    preferred_required: int = Field(ge=0, description="Soft: shortfall is penalized.")
    source: Literal["band", "manual", "scenario"]

    @model_validator(mode="after")
    def _consistent(self) -> StaffingInterval:
        if self.interval_end <= self.interval_start:
            raise ValueError("interval_end must be after interval_start")
        if self.preferred_required < self.minimum_required:
            raise ValueError("preferred_required must be >= minimum_required")
        return self


class StaffingRequirements(Model):
    outlet_id: UUID
    week_start: date
    interval_minutes: int = Field(description="Grid size, 30 by default.")
    demand_revision: int = Field(ge=1)
    intervals: list[StaffingInterval]


class StaffingRequirementsUpdate(Model):
    base_demand_revision: int = Field(ge=1)
    intervals: list[StaffingInterval]


# ---------------------------------------------------------------- schedules


class Shift(Model):
    id: UUID = Field(description="This version's row. Changes between versions.")
    logical_shift_id: UUID = Field(description="Stable identity across versions; key diffs on it.")
    outlet_id: UUID
    employee_id: UUID | None = Field(description="null = open (unfilled) shift.")
    skill_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    break_start_at: AwareDatetime | None
    break_minutes: Minutes
    locked: bool
    lock_reason: str | None


ViolationCode = Literal[
    "unavailable",
    "absent",
    "missing_skill",
    "overlap",
    "insufficient_rest",
    "travel_time",
    "weekly_cap",
    "overtime",
    "minimum_coverage",
    "preferred_coverage",
    "locked_changed",
    "outside_grid",
    "outside_operating_hours",
    "inactive_employee",
]


class Violation(Model):
    code: ViolationCode
    severity: Literal["hard", "soft"]
    message: str = Field(description="Deterministic text built from facts; safe to show.")
    employee_id: UUID | None
    logical_shift_ids: list[UUID]
    facts: dict[str, Any] = Field(
        description="Structured evidence, e.g. rest_minutes and required_rest_minutes."
    )


class ValidationResult(Model):
    hard_violations: int = Field(ge=0)
    soft_violations: int = Field(ge=0)
    violations: list[Violation]


class Metrics(Model):
    coverage_ratio: Ratio | None = Field(
        description="sum(min(assigned, preferred) x minutes) / "
        "sum(preferred x minutes). null when there is no demand. "
        "Overstaffing never raises it."
    )
    minimum_deficit_minutes: Minutes = Field(description="Staff-minutes below the hard minimum.")
    preferred_deficit_minutes: Minutes
    labour_cost: Money = Field(description="Estimated roster cost, not payroll.")
    overtime_cost: Money
    overtime_minutes: Minutes
    preference_match_ratio: Ratio | None
    open_shifts: int = Field(ge=0)
    assigned_minutes: Minutes


class CoverageCell(Model):
    skill_id: UUID
    interval_start: AwareDatetime
    minimum_required: int
    preferred_required: int
    scheduled: int = Field(description="Staff productively on shift (breaks excluded).")


VersionStatus = Literal["draft", "published", "superseded", "discarded"]
VersionSource = Literal["seed", "manual", "generate", "optimize", "repair", "restore", "import"]


class ScheduleVersionSummary(Model):
    id: UUID
    schedule_id: UUID
    version_number: int = Field(ge=1)
    status: VersionStatus
    source: VersionSource
    reason: str
    base_version_id: UUID | None
    optimization_run_id: UUID | None
    created_by_user_id: UUID | None = Field(description="null = created by ShiftPilot.")
    approved_by_user_id: UUID | None
    created_at: AwareDatetime
    published_at: AwareDatetime | None
    revision: int = Field(
        ge=1,
        description="Bumped by every applied edit while the version is a draft; send it as "
        "expected_revision. Fixed once published.",
    )
    recorded_metrics: Metrics | None = Field(
        default=None,
        description="Stored when the draft was last saved and recomputed at publication, then frozen: "
        "what the version cost and covered when it went live. Cheap to list in history. null for "
        "versions saved before contract 3.1. ScheduleVersion.metrics is evaluated against current facts.",
    )


class ScheduleVersion(ScheduleVersionSummary):
    input_hash: str
    shifts: list[Shift]
    metrics: Metrics
    coverage: list[CoverageCell]
    validation: ValidationResult


class ScheduleWeek(Model):
    outlet_id: UUID
    week_start: date = Field(description="Monday, outlet-local.")
    timezone: str
    schedule_id: UUID | None = Field(description="null when nothing exists for this week yet.")
    current_version: ScheduleVersion | None = Field(description="Live published version, if any.")
    drafts: list[ScheduleVersionSummary]
    employees: list[RosterEmployee] = Field(
        description="Rows for the roster: active home-outlet employees plus anyone with a shift in "
        "current_version. An employee with no shift on a day is off that day."
    )
    absences: list[AbsenceMark] = Field(description="Absences overlapping this week for listed employees.")


class RosterEmployee(Model):
    id: UUID
    name: str
    home_outlet_id: UUID
    skill_ids: list[UUID]
    status: Literal["active", "inactive"]
    scheduled_minutes: Minutes = Field(
        description="Paid minutes this week across all outlets' published versions."
    )
    regular_weekly_minutes: Minutes
    max_weekly_minutes: Minutes


class AbsenceMark(Model):
    id: UUID
    employee_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    kind: Literal["leave", "sick", "other"]
    status: Literal["requested", "confirmed", "rejected", "cancelled"] = Field(
        description="Only confirmed absences make an overlapping shift invalid. Rosters list only "
        "requested and confirmed absences; rejected and cancelled appear in absence management (2.4)."
    )


class OutletRef(Model):
    id: UUID
    name: str
    timezone: str


class MyWeek(Model):
    """An employee's own published shifts across all outlets for one week."""

    employee_id: UUID
    week_start: date
    shifts: list[Shift] = Field(description="Only shifts from current published versions.")
    outlets: list[OutletRef] = Field(description="Outlets referenced by the shifts.")
    skills: list[Skill] = Field(description="Skills referenced by the shifts, for role labels.")


# ---------------------------------------------------------------- drafts, edits, publication, history (P3)

ChangeKind = Literal[
    "added", "removed", "reassigned", "moved", "resized", "role_changed", "lock_changed", "break_changed"
]


class AddShift(Model):
    op: Literal["add"]
    employee_id: UUID | None = Field(description="null adds an open (unfilled) shift.")
    skill_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    break_start_at: AwareDatetime | None = None
    break_minutes: Minutes = 0
    locked: bool = False


class UpdateShift(Model):
    """Move, resize, reassign or change role. Omitted fields keep their value; employee_id may be
    null to unassign."""

    op: Literal["update"]
    logical_shift_id: UUID
    employee_id: UUID | None = None
    skill_id: UUID | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    break_start_at: AwareDatetime | None = None
    break_minutes: Minutes | None = None


class RemoveShift(Model):
    op: Literal["remove"]
    logical_shift_id: UUID


class SetLock(Model):
    op: Literal["lock", "unlock"]
    logical_shift_id: UUID
    reason: str | None = Field(default=None, max_length=200)


ShiftEdit = Annotated[AddShift | UpdateShift | RemoveShift | SetLock, Field(discriminator="op")]


class EditRequest(Model):
    expected_revision: int = Field(ge=1, description="The draft revision the edits were made against.")
    edits: list[ShiftEdit] = Field(min_length=1, max_length=200)


class ShiftChange(Model):
    logical_shift_id: UUID
    kinds: list[ChangeKind]
    before: Shift | None
    after: Shift | None


class EditPreview(Model):
    """What the draft would look like after the edits. Nothing is written; the server is the only
    authority on validity, cost and coverage."""

    version_id: UUID
    expected_revision: int
    shifts: list[Shift]
    changes: list[ShiftChange]
    metrics: Metrics
    validation: ValidationResult


class CreateDraftRequest(Model):
    base_version_id: UUID | None = Field(
        description="The currently published version (null for an empty week). Stale -> 409."
    )
    copy_from_version_id: UUID | None = Field(
        default=None,
        description="Version whose shifts start the draft; "
        "defaults to base_version_id (empty when both are null).",
    )


class PublishRequest(Model):
    expected_base_version_id: UUID | None = Field(description="The published version this draft replaces.")
    expected_revision: int = Field(ge=1)


class PublishResult(Model):
    schedule_id: UUID
    published: ScheduleVersionSummary
    superseded_version_id: UUID | None


ProposalStatus = Literal["pending", "approved", "rejected", "expired", "stale", "failed"]
PublicationOutcome = Literal["published", "stale", "invalid", "changed"]


class CreateProposalRequest(Model):
    draft_version_id: UUID
    expected_revision: int = Field(ge=1, description="The draft revision the manager reviewed.")


class Proposal(Model):
    id: UUID
    schedule_id: UUID
    draft_version_id: UUID
    draft_revision: int = Field(ge=1)
    base_version_id: UUID | None = Field(description="The published version this plan replaces.")
    candidate_id: UUID | None = Field(description="Set when the draft came from an optimization candidate.")
    status: ProposalStatus
    metrics_at_proposal: Metrics = Field(
        description="What the manager agreed to; Changed is judged against it."
    )
    requested_by_user_id: UUID
    decided_by_user_id: UUID | None
    created_at: AwareDatetime
    decided_at: AwareDatetime | None
    expires_at: AwareDatetime


class ApproveProposalRequest(Model):
    acknowledge_changes: bool = Field(
        default=False,
        description="Set after a `changed` outcome to accept the moved metrics and publish.",
    )


class MetricDelta(Model):
    metric: Literal["labour_cost", "coverage_ratio", "minimum_deficit_minutes", "open_shifts"]
    before: float | None = Field(description="labour_cost in paise.")
    after: float | None
    message: str = Field(description="Deterministic text built from the numbers; safe to show.")


class ProposalDecision(Model):
    """The publication transaction's answer (architecture v3 section 31). Always 200: each outcome is a
    normal business result, not an error."""

    outcome: PublicationOutcome = Field(
        description="published: the new version is live. stale: someone published first or the draft "
        "changed; re-run against current_version_id. invalid: a current fact breaks the plan "
        "(violations); offer a repair. changed: still valid but metrics moved materially (deltas); "
        "approve again with acknowledge_changes to accept."
    )
    message: str
    proposal: Proposal
    published: ScheduleVersionSummary | None = None
    superseded_version_id: UUID | None = None
    current_version_id: UUID | None = Field(default=None, description="Set when stale.")
    violations: list[Violation] = Field(default_factory=list, description="Set when invalid.")
    deltas: list[MetricDelta] = Field(default_factory=list, description="Set when changed.")

    @model_validator(mode="after")
    def _consistent(self) -> ProposalDecision:
        expected = {"published": "approved", "stale": "stale", "invalid": "failed", "changed": "pending"}
        if self.proposal.status != expected[self.outcome]:
            raise ValueError(f"outcome {self.outcome} requires proposal status {expected[self.outcome]}")
        if (self.outcome == "published") != (self.published is not None):
            raise ValueError("published is set exactly when the outcome is published")
        if self.outcome == "invalid" and not self.violations:
            raise ValueError("an invalid outcome lists the violations")
        if self.outcome == "changed" and not self.deltas:
            raise ValueError("a changed outcome lists the deltas")
        return self


class RestoreRequest(Model):
    expected_base_version_id: UUID | None = Field(description="The currently published version.")


class VersionHistory(Model):
    schedule_id: UUID
    current_version_id: UUID | None
    items: list[ScheduleVersionSummary] = Field(description="Newest first; drafts included.")


class VersionDiff(Model):
    from_version_id: UUID
    to_version_id: UUID
    changes: list[ShiftChange]
    metrics_from: Metrics
    metrics_to: Metrics


# ---------------------------------------------------------------- absences and repair (P4)


class ReportAbsenceRequest(Model):
    employee_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    kind: Literal["leave", "sick", "other"]
    status: Literal["requested", "confirmed"] = Field(
        description="Managers may report confirmed absences; staff may only request for themselves."
    )
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _ordered(self) -> ReportAbsenceRequest:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class AffectedShift(Model):
    schedule_id: UUID
    version_id: UUID
    logical_shift_id: UUID
    outlet_id: UUID
    skill_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    locked: bool


class AbsenceReport(Model):
    absence: AbsenceMark
    affected: list[AffectedShift] = Field(
        description="Live published shifts the absence overlaps, all outlets."
    )
    lock_conflicts: list[UUID] = Field(
        description="Logical ids of affected shifts that are locked; repairing them "
        "needs explicit unlock authorization."
    )
    repair_suggested: bool
    repair_run_ids: list[UUID] = Field(
        default_factory=list,
        description="Repair runs enqueued automatically for this confirmed absence (one per affected "
        "schedule without unauthorized lock conflicts). Poll them like any run.",
    )


class AbsenceList(Model):
    items: list[AbsenceMark]


class UpdateAbsenceRequest(Model):
    status: Literal["confirmed", "rejected", "cancelled"]


class RepairRequest(Model):
    absence_id: UUID
    base_version_id: UUID = Field(description="The published version being repaired. Stale -> 409.")
    unlock_logical_shift_ids: list[UUID] = Field(
        default_factory=list,
        description="Locked affected shifts the manager authorizes to change (decision 5).",
    )
    time_limit_seconds: int = Field(default=3, ge=1, le=10)


# ---------------------------------------------------------------- optimization

Strategy = Literal["balanced", "lowest_cost", "staff_friendly", "max_coverage"]
# Repair profiles (2.4): candidates of a repair run use these names.
RepairProfile = Literal["least_disruption", "lowest_cost", "best_coverage"]
JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
SolverStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN"]


class GenerateRequest(Model):
    strategy: Strategy = "balanced"
    base_version_id: UUID | None = Field(
        default=None,
        description="Current published version the draft replaces; null for an empty week. Stale -> 409.",
    )
    time_limit_seconds: int = Field(default=10, ge=1, le=30)


class ExplanationFact(Model):
    code: Literal["skill", "available", "no_conflict", "weekly_hours", "travel"]
    ok: bool
    message: str = Field(description="Deterministic text built from facts; safe to show.")
    facts: dict[str, Any] = Field(default_factory=dict)


class AlternativeFact(Model):
    employee_id: UUID
    name: str
    status: Literal["rejected", "eligible_not_selected"] = Field(
        description="rejected: a concrete rule blocks this person (see reasons). eligible_not_selected: "
        "allowed, but this plan chose someone else; never presented as a rejection."
    )
    reasons: list[ExplanationFact]


class ShiftExplanation(Model):
    logical_shift_id: UUID
    chosen_employee_id: UUID | None = Field(description="null = the shift was left open.")
    reasons: list[ExplanationFact] = Field(description="Facts about the chosen employee.")
    alternatives: list[AlternativeFact] = Field(description="Other qualified people (bounded list).")


class Disruption(Model):
    changed_shifts: Minutes
    added_shifts: Minutes
    cross_outlet_moves: Minutes
    open_shifts: Minutes


class Candidate(Model):
    id: UUID
    rank: int = Field(ge=1)
    strategy: Strategy | RepairProfile
    solver_status: Literal["OPTIMAL", "FEASIBLE"]
    proven_optimal: bool = Field(
        description="False when the time limit ended the search with a valid but unproven schedule."
    )
    materialized_version_id: UUID | None = Field(
        default=None,
        description="null until a manager selects this candidate "
        "(POST /v2/optimization-candidates/{id}/select); then the draft it became.",
    )
    metrics: Metrics
    changed_shifts: int = Field(ge=0, description="Logical shifts differing from the base version.")
    validation: ValidationResult = Field(
        description="Independent validator result. A candidate with hard violations is never returned."
    )
    disruption: Disruption | None = Field(default=None, description="Repair runs only.")
    explanations: list[ShiftExplanation] = Field(
        default_factory=list, description="Repair runs: one per changed shift."
    )

    @model_validator(mode="after")
    def _honest(self) -> Candidate:
        if self.validation.hard_violations:
            raise ValueError("a candidate with hard violations must not be returned")
        if self.proven_optimal and self.solver_status != "OPTIMAL":
            raise ValueError("proven_optimal requires solver_status OPTIMAL")
        return self


class CandidateShift(Model):
    """A shift as a candidate proposes it. It has no row id until the candidate is selected."""

    logical_shift_id: UUID = Field(description="Existing ids keep their identity; new shifts get new ids.")
    outlet_id: UUID
    employee_id: UUID | None = Field(description="null = open (unfilled) shift.")
    skill_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    break_start_at: AwareDatetime | None
    break_minutes: Minutes
    locked: bool


class CandidateDiff(Model):
    """The candidate against its base version. For generation without a base, every shift is added."""

    added: list[CandidateShift]
    changed: list[CandidateShift] = Field(description="The new state of shifts that exist in the base.")
    removed: list[UUID] = Field(description="Logical shift ids of base shifts the candidate drops.")


class CandidateDetail(Candidate):
    run_id: UUID
    base_version_id: UUID | None = Field(description="The version this diff applies to; null = empty week.")
    diff: CandidateDiff


class Shortage(Model):
    outlet_id: UUID
    skill_id: UUID
    interval_start: AwareDatetime
    interval_end: AwareDatetime
    minimum_required: int
    max_assignable: int = Field(description="Upper bound of eligible staff for this interval.")


class Infeasibility(Model):
    summary: str
    shortages: list[Shortage]


class OptimizationRun(Model):
    id: UUID
    kind: Literal["generate", "optimize", "repair"]
    outlet_ids: list[UUID]
    base_version_ids: list[UUID]
    strategy: Strategy | RepairProfile
    absence_id: UUID | None = Field(default=None, description="Repair runs: the absence being repaired.")
    job_state: JobState
    solver_status: SolverStatus | None = Field(
        description="Set once solving ends. UNKNOWN means no "
        "solution within the time limit; it does not prove "
        "infeasibility."
    )
    input_hash: str
    queued_at: AwareDatetime
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    solver_wall_ms: int | None
    poll_after_ms: int | None = Field(
        description="Suggested polling delay while queued/running; null when terminal."
    )
    candidates: list[Candidate]
    infeasibility: Infeasibility | None
    error: ErrorBody | None = Field(description="Set when job_state is failed.")

    @model_validator(mode="after")
    def _consistent_state(self) -> OptimizationRun:
        """Job state, solver status and results must agree (roadmap decision 7)."""
        has_candidates = bool(self.candidates)
        if self.job_state in ("queued", "running"):
            ok = (
                self.solver_status is None
                and not has_candidates
                and self.infeasibility is None
                and self.error is None
                and self.finished_at is None
            )
        elif self.job_state == "failed":
            ok = self.error is not None and not has_candidates and self.infeasibility is None
        elif self.job_state == "cancelled":
            ok = not has_candidates and self.infeasibility is None
        elif self.solver_status in ("OPTIMAL", "FEASIBLE"):
            ok = has_candidates and self.infeasibility is None and self.error is None
        elif self.solver_status == "INFEASIBLE":
            ok = not has_candidates and self.infeasibility is not None and self.error is None
        else:  # succeeded with UNKNOWN / MODEL_INVALID / missing status
            ok = self.solver_status is not None and not has_candidates and self.infeasibility is None
        if not ok:
            raise ValueError(
                f"inconsistent run: job_state={self.job_state} solver_status={self.solver_status}"
            )
        return self
