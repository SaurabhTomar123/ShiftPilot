"""Scheduling v2 request/response models: the provider side of contracts/v2.

Exported to contracts/v2/openapi.json by `python -m api.v2.contract_build`. Changing a model is a
contract change: bump CONTRACT_VERSION, rebuild, and hand off to the web consumer.

Conventions (docs/runbooks/v2-schema-plan.md §6): instants are RFC 3339 with offset, recurring
times are minutes from outlet-local midnight, durations are integer minutes, money is integer
paise. Weekday 0 is Monday.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "2.1.0-p1p2"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Weekday = Annotated[int, Field(ge=0, le=6, description="0 = Monday … 6 = Sunday")]
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
        description="sum(min(assigned, preferred) × minutes) / "
        "sum(preferred × minutes). null when there is no demand. "
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
    status: Literal["requested", "confirmed"] = Field(
        description="Only confirmed absences make an overlapping shift invalid."
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


# ---------------------------------------------------------------- optimization

Strategy = Literal["balanced", "lowest_cost", "staff_friendly", "max_coverage"]
JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
SolverStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN"]


class GenerateRequest(Model):
    strategy: Strategy = "balanced"
    base_version_id: UUID | None = Field(
        default=None,
        description="Current published version the draft replaces; null for an empty week. Stale → 409.",
    )
    time_limit_seconds: int = Field(default=10, ge=1, le=30)


class Candidate(Model):
    id: UUID
    rank: int = Field(ge=1)
    strategy: Strategy
    solver_status: Literal["OPTIMAL", "FEASIBLE"]
    proven_optimal: bool = Field(
        description="False when the time limit ended the search with a valid but unproven schedule."
    )
    draft_version_id: UUID = Field(description="Fetch with GET /v2/schedule-versions/{id}.")
    metrics: Metrics
    changed_shifts: int = Field(ge=0, description="Logical shifts differing from the base version.")
    validation: ValidationResult = Field(
        description="Independent validator result. A candidate with hard violations is never returned."
    )

    @model_validator(mode="after")
    def _honest(self) -> Candidate:
        if self.validation.hard_violations:
            raise ValueError("a candidate with hard violations must not be returned")
        if self.proven_optimal and self.solver_status != "OPTIMAL":
            raise ValueError("proven_optimal requires solver_status OPTIMAL")
        return self


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
    strategy: Strategy
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
