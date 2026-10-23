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

CONTRACT_VERSION = "3.20.0-p4"


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
    sandbox_id: UUID | None = Field(
        default=None,
        description="Switch persona inside an existing sandbox; omit to start a fresh one (B6.2).",
    )


class DemoSession(Model):
    """Synthetic public demo only; private deployments never expose this endpoint."""

    access_token: str = Field(description="Send as `Authorization: Bearer <token>`.")
    token_type: Literal["bearer"] = "bearer"
    expires_at: AwareDatetime
    me: Me
    sandbox_id: UUID | None = Field(
        default=None,
        description="This visitor's private copy of the synthetic organization; send it back to switch "
        "persona. Changes are visible to nobody else and disappear at sandbox_expires_at.",
    )
    sandbox_expires_at: AwareDatetime | None = None


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


RuleType = Literal["max_shift_end_time", "max_days_per_week"]
ScopeLevel = Literal["organization", "outlet", "tag", "employee"]


class RuleDefinition(Model):
    """A scheduling rule (architecture v3 section 21). Precedence is by scope, never by number: a more
    specific rule replaces another only when it names it in overrides_rule_id.

    parameters by rule_type: max_shift_end_time {latest_end_minute (0-1440, half-hour), weekdays
    [0=Monday..6]}; max_days_per_week {days (1-7)}."""

    rule_type: RuleType
    scope_level: ScopeLevel
    scope: dict[str, str] = Field(
        description="{} for organization; {outlet_id}; {tag} (e.g. student); {employee_id}."
    )
    parameters: dict[str, Any]
    hard: bool = Field(default=True, description="Only hard rules are supported in the MVP.")
    overrides_rule_id: UUID | None = Field(default=None, description="The rule this one is an exception to.")
    source_text: str | None = Field(default=None, max_length=500, description="How a person phrased it.")


class RuleEmployee(Model):
    employee_id: UUID
    name: str


class RuleConflict(Model):
    rule_id: UUID
    rule_name: str
    employees: list[str] = Field(description="Names of the people both rules apply to.")
    message: str = Field(description='E.g. This conflicts with "Students must finish by 9 PM". ...')
    suggested_exception: RuleDefinition | None = Field(
        description="When one person is in both: the same rule scoped to them, overriding the existing "
        "rule. Offer it as 'Create an exception for <name>'; otherwise keep the existing rule."
    )


class RuleImpact(Model):
    employee_id: UUID
    name: str
    logical_shift_id: UUID
    start_at: AwareDatetime
    end_at: AwareDatetime
    message: str


class RulePreview(Model):
    """What saving the rule would mean. Writes nothing."""

    rule: RuleDefinition
    summary: str = Field(description="Deterministic description, e.g. No shift ends after 21:00 on weekdays.")
    valid: bool = Field(description="false when it conflicts with an active rule; saving would be 409.")
    affected: list[RuleEmployee]
    conflicts: list[RuleConflict]
    impact: list[RuleImpact] = Field(
        description="Upcoming published shifts this rule would break (at most 50). They stay published; "
        "the next generation or repair respects the rule."
    )


class SchedulingRule(RuleDefinition):
    id: UUID
    summary: str
    status: Literal["draft", "active", "archived"]
    created_at: AwareDatetime


class RuleList(Model):
    items: list[SchedulingRule]


LanguageStatus = Literal["ready", "needs_clarification", "unsupported", "unavailable"]


class CommandRequest(Model):
    text: str = Field(min_length=1, max_length=500, description='E.g. "Give Ravi Saturday off".')
    outlet_id: UUID | None = Field(default=None, description="Defaults to the manager's outlet.")
    employee_id: UUID | None = Field(
        default=None, description='The answer to "Which Ravi?", sent with the same text.'
    )


class CommandOption(Model):
    employee_id: UUID
    name: str


class ProposedCall(Model):
    """The existing API call that carries out the command, made by the UI after the person confirms."""

    operation_id: str
    method: Literal["POST"]
    path: str
    body: dict[str, Any]


class CommandPreview(Model):
    """A language command as a preview (architecture v3 section 33). Never a write: confirming means
    making `action` (with an Idempotency-Key). ready: show summary and confirm. needs_clarification:
    ask question, offering options. unsupported or unavailable: point to the form."""

    status: LanguageStatus
    intent: Literal["give_time_off", "report_sick", "generate_week"] | None = None
    summary: str
    question: str | None = None
    options: list[CommandOption] = Field(default_factory=list)
    action: ProposedCall | None = None
    affected_shift_count: int | None = None


class RuleParseRequest(Model):
    text: str = Field(
        min_length=1, max_length=500, description='E.g. "Students cannot work after 9 PM on weekdays".'
    )


class RuleParse(Model):
    """A rule in words, run through the rule validation service. ready: preview is what createRule
    would save (send preview.rule). Unsupported rules are refused, never approximated."""

    status: LanguageStatus
    message: str
    preview: RulePreview | None = None
    options: list[CommandOption] = Field(default_factory=list)


class Notification(Model):
    """An in-app notification (architecture v3 section 40)."""

    id: UUID
    topic: str = Field(
        description="schedule.published (your week), run.finished (options or a repair are ready), "
        "absence.reported, proposal.ready or proposal.stale."
    )
    title: str = Field(description="Deterministic text; safe to show.")
    payload: dict[str, Any] = Field(description="Ids to link to, e.g. schedule_id, version_id, run_id.")
    delivered_at: AwareDatetime
    read_at: AwareDatetime | None


class NotificationList(Model):
    items: list[Notification] = Field(description="Newest first, at most 100.")


class ImportTemplate(Model):
    """The fixed employee CSV template (architecture v3 section 19). No column mapping in the MVP."""

    columns: list[str]
    example: str = Field(description="One valid data row.")
    notes: list[str]


class StageImportRequest(Model):
    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=1_000_000, description="The CSV text (UTF-8), header row first.")


class ImportRowError(Model):
    column: str = Field(description="Template column, or * for the whole row.")
    message: str


class ImportRow(Model):
    row_number: int = Field(ge=2, description="Line in the file; the header is line 1.")
    name: str
    outlet_id: UUID | None
    errors: list[ImportRowError]
    employee_id: UUID | None = Field(description="Set once the import is committed.")


class ImportJob(Model):
    id: UUID
    kind: Literal["employees"]
    status: Literal["staged", "invalid", "committed", "expired"] = Field(
        description="staged: every row is valid; commit it. invalid: fix the listed errors and upload "
        "again (nothing was written). committed: the employees exist. expired: staged over 24 hours ago."
    )
    filename: str
    row_count: int = Field(ge=0)
    error_count: int = Field(ge=0, description="Rows with at least one error.")
    file_errors: list[str] = Field(description="Problems with the file itself, e.g. its header.")
    created_at: AwareDatetime
    expires_at: AwareDatetime
    committed_at: AwareDatetime | None
    rows: list[ImportRow]


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
    source: Literal["template", "band", "manual", "scenario", "forecast"] = Field(
        description="template/band rows are regenerated by expandStaffingRequirements; manual rows are "
        "overrides that survive re-expansion."
    )

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


class StaffingTemplateBlock(Model):
    """Default demand for one weekday, block and skill (e.g. Monday 12:00-15:00: 2 Grill, 3 preferred)."""

    weekday: int = Field(ge=0, le=6, description="Monday = 0.")
    start_minute: int = Field(
        ge=0, le=1410, multiple_of=30, description="Outlet-local minutes from midnight."
    )
    end_minute: int = Field(ge=30, le=1440, multiple_of=30)
    skill_id: UUID
    minimum_required: int = Field(ge=0)
    preferred_required: int = Field(ge=0)

    @model_validator(mode="after")
    def _consistent(self) -> StaffingTemplateBlock:
        if self.end_minute <= self.start_minute:
            raise ValueError("end_minute must be after start_minute")
        if self.preferred_required < self.minimum_required:
            raise ValueError("preferred_required must be >= minimum_required")
        return self


class StaffingTemplateSet(Model):
    outlet_id: UUID
    revision: int = Field(ge=0, description="0 before any template was saved. Send it as base_revision.")
    items: list[StaffingTemplateBlock] = Field(description="By weekday, skill and start.")


class StaffingTemplateUpdate(Model):
    base_revision: int = Field(ge=0)
    items: list[StaffingTemplateBlock] = Field(
        max_length=2000, description="The whole set; blocks of one weekday and skill must not overlap."
    )


class ExpandStaffingRequest(Model):
    base_demand_revision: int = Field(ge=1)
    use_demand_bands: bool = Field(
        default=False,
        description="Let demand bands (orders/hour -> staff) override the template where the week has "
        "order counts.",
    )


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
    "rule",
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


class FairnessComponents(Model):
    """Burden points by component (architecture v4 section 12). Last-minute and transfer burden are not
    part of policy 1."""

    policy_version: int
    closing: int = Field(ge=0, description="3 per shift ending at 22:00 or later.")
    weekend: int = Field(ge=0, description="2 per Saturday or Sunday shift.")
    split: int = Field(ge=0, description="2 per extra shift on the same day.")
    overtime: int = Field(ge=0, description="1 per full hour beyond the regular week.")


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
    hours_preference_deviation_minutes: Minutes | None = Field(
        default=None,
        description="Hours-preference alignment: sum over employees with a preferred weekly total of "
        "|worked - preferred| minutes. Lower is better. Not a fairness measure. null when nobody states a "
        "preference, and in metrics stored before contract 3.4.",
    )
    fairness_burden_deviation: float | None = Field(
        default=None,
        description="Fairness burden (v4 section 12): mean absolute deviation, across the outlet's staff, "
        "of burden points per 40 h over the last 8 published weeks plus this one. Points: closing "
        "shift 3, weekend 2, second shift in a day 2, overtime hour 1. Lower is fairer; null in "
        "metrics stored before 3.16.",
    )
    fairness_components: FairnessComponents | None = Field(
        default=None,
        description="This roster's burden points this week by component (history excluded), with the "
        "policy version. Compare two plans component by component.",
    )


class CoverageCell(Model):
    skill_id: UUID
    interval_start: AwareDatetime
    minimum_required: int
    preferred_required: int
    scheduled: int = Field(description="Staff productively on shift (breaks excluded).")


VersionStatus = Literal["draft", "published", "superseded", "discarded"]
VersionSource = Literal["seed", "manual", "generate", "optimize", "repair", "restore", "import", "scenario"]


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
    absences: list[AbsenceMark] = Field(
        default_factory=list,
        description="The employee's own absences overlapping the week, any status (v3 section 20).",
    )


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


class AddFromTemplate(Model):
    """Add a shift shaped by one of the outlet's shift templates (listShiftTemplates). Start, end and
    break come from the template, so no client chooses a break policy."""

    op: Literal["add_from_template"]
    template_id: UUID
    day: date = Field(description="Outlet-local date the shift starts on; must be in the draft's week.")
    employee_id: UUID | None = Field(default=None, description="null adds an open (unfilled) shift.")
    skill_id: UUID | None = Field(
        default=None, description="Required when the template allows any skill; must match it otherwise."
    )
    locked: bool = False


ShiftEdit = Annotated[
    AddShift | AddFromTemplate | UpdateShift | RemoveShift | SetLock, Field(discriminator="op")
]


class ShiftTemplate(Model):
    id: UUID
    name: str
    skill_id: UUID | None = Field(description="null: usable for any skill.")
    start_minute: int = Field(ge=0, le=1439, description="Outlet-local minutes from midnight.")
    duration_minutes: Minutes
    break_minutes: Minutes
    break_start_minute: int | None = Field(
        description="Where the break starts, in minutes from shift start (the server's placement); null "
        "when the template has no break."
    )


class ShiftTemplateList(Model):
    outlet_id: UUID
    items: list[ShiftTemplate] = Field(description="Active templates, by start time.")


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


class ProposalList(Model):
    items: list[Proposal] = Field(description="Newest first, at most 100.")


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
    allow_cross_outlet: bool = Field(
        default=False,
        description="Owner only: let the repair borrow staff from other outlets (widening stage "
        "other_outlets). Managers get 403.",
    )
    freeze: FreezeSpec | None = Field(
        default=None,
        description="Shifts no stage may change (v4 section 13). 409 when the absence or another current "
        "fact breaks one of them.",
    )
    time_limit_seconds: int = Field(default=3, ge=1, le=10)


# ---------------------------------------------------------------- optimization

Strategy = Literal["balanced", "lowest_cost", "staff_friendly", "max_coverage", "stability", "fairness"]
# Repair profiles (2.4): candidates of a repair run use these names.
RepairProfile = Literal["least_disruption", "lowest_cost", "best_coverage"]
JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
SolverStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN"]


class FreezeSpec(Model):
    """Protect commitments for one run (architecture v4 section 13): these published shifts are held
    exactly as they are. Nothing is stored as a lock; the next run starts unfrozen."""

    shift_ids: list[UUID] = Field(default_factory=list, description="Logical shift ids to pin.")
    employee_ids: list[UUID] = Field(default_factory=list, description="Hold all of these people's shifts.")
    days: list[date] = Field(default_factory=list, description="Hold every shift on these outlet-local days.")


class GenerateRequest(Model):
    strategy: Strategy = "balanced"
    base_version_id: UUID | None = Field(
        default=None,
        description="Current published version the draft replaces; null for an empty week. Stale -> 409.",
    )
    time_limit_seconds: int = Field(default=10, ge=1, le=30)
    freeze: FreezeSpec | None = Field(
        default=None,
        description="Regenerating over a published week: shifts to keep exactly. 409 conflict when "
        "current facts break a frozen shift (details.frozen_logical_shift_ids).",
    )


class ExplanationFact(Model):
    code: Literal[
        "skill",
        "available",
        "no_conflict",
        "weekly_hours",
        "travel",
        "rules",
        "incremental_cost",
        "fairness_burden",
        "disruption",
    ] = Field(
        description="incremental_cost, fairness_burden and disruption appear for the chosen person only. "
        "Unknown codes may be added; show their message."
    )
    ok: bool
    message: str = Field(description="Deterministic text built from facts; safe to show.")
    facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Blocking reasons carry provenance: rule_ids and/or absence_ids (v4 section 18).",
    )


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


ScenarioEventType = Literal["demand_change", "absence", "outlet_closure", "labour_cap", "rule"]


class ScenarioEventIn(Model):
    """One hypothetical event (architecture v4 section 23). Payloads by type:

    - demand_change: {percent: -100..300, skill_id?, weekdays?: [0..6], start_minute?, end_minute?}
    - absence: {employee_id, start_at, end_at}
    - outlet_closure: {day: YYYY-MM-DD}
    - labour_cap: {max_cost_paise}
    - rule: {rule_type, parameters, employee_ids: [...]} (same rule types as createRule)

    Other types are refused (422), never turned into free-form solver input."""

    type: ScenarioEventType
    payload: dict[str, Any]


class ScenarioEvent(ScenarioEventIn):
    id: UUID
    sequence: int = Field(ge=1, description="Events apply in this order.")


class CreateScenarioRequest(Model):
    title: str = Field(min_length=1, max_length=120)
    events: list[ScenarioEventIn] = Field(default_factory=list, max_length=20)


class ScenarioRunRequest(Model):
    strategy: Strategy = "balanced"
    time_limit_seconds: int = Field(default=10, ge=1, le=30)


class ConvertScenarioRequest(Model):
    candidate_id: UUID = Field(description="A candidate of this scenario's latest successful run.")


class ScenarioBaseline(Model):
    """The current plan as it would stand if the events happened: the "before" of the comparison."""

    run_id: UUID
    metrics: Metrics
    hard_violations: int = Field(ge=0, description="Shifts the events would break (e.g. an absence).")
    violation_codes: list[str]


class Scenario(Model):
    """A what-if that never changes real facts. Run it, compare each candidate's trace (deltas against
    the base version, measured under the scenario) with `baseline`, then convert one candidate: it is
    re-checked against current facts and becomes a normal draft."""

    id: UUID
    outlet_id: UUID
    week_start: date
    schedule_id: UUID
    title: str
    base_version_id: UUID | None = Field(description="The published version the scenario starts from.")
    status: Literal["open", "converted", "discarded", "expired"]
    created_by_user_id: UUID
    created_at: AwareDatetime
    expires_at: AwareDatetime
    converted_version_id: UUID | None
    events: list[ScenarioEvent]
    latest_run_id: UUID | None
    baseline: ScenarioBaseline | None = Field(description="From the latest run; null before the first.")


class ScenarioList(Model):
    items: list[Scenario]


class ReplacementRequest(Model):
    version_id: UUID = Field(description="The version the shift is in: published or a draft.")
    logical_shift_id: UUID
    profile: Strategy = Field(
        default="balanced",
        description="Ranks eligible people the way the profile weighs cost, fairness and preferences.",
    )
    include_other_outlets: bool = Field(default=False, description="Owner only; managers get 403.")
    limit: int = Field(default=5, ge=1, le=10)


class Recommendation(Model):
    rank: int = Field(ge=1)
    employee_id: UUID
    name: str
    home_outlet_id: UUID
    disruption_class: Literal["direct", "overtime", "cross_outlet"] = Field(
        description="Ranked in this order first: direct, then pushing into overtime, then another outlet."
    )
    incremental_cost: Money = Field(
        description="Labour plus overtime premium, against leaving the shift open."
    )
    overtime_minutes_added: Minutes
    fairness_delta: float | None = Field(
        description="Change in fairness burden deviation; negative = fairer."
    )
    weekly_minutes_after: Minutes
    within_preferred_window: bool | None = Field(description="null: the person states no preferred windows.")
    reasons: list[ExplanationFact] = Field(
        description="Every eligibility check passed, plus cost, burden and disruption."
    )
    edit: UpdateShift = Field(description="Apply to a draft with applyEdits to choose this person.")


class ReplacementRecommendations(Model):
    """Who can cover this shift (architecture v4 sections 11, 46). Read-only; nothing is written.

    basis is a direct assignment: each person is checked as if they took the shift and nothing else
    changed. Someone blocked only by another of their shifts could become free if that shift moved; that
    is a repair run, never presented as a recommendation."""

    version_id: UUID
    version_status: VersionStatus
    shift: Shift
    vacating_employee_id: UUID | None = Field(description="Who holds the shift now; null = open.")
    profile: Strategy
    basis: Literal["direct_assignment"] = "direct_assignment"
    policy_version: int
    considered: int = Field(ge=0, description="Qualified people checked.")
    eligible: int = Field(
        ge=0, description="Of those, people no rule blocks (recommendations is the top `limit`)."
    )
    recommendations: list[Recommendation]
    rejected: list[AlternativeFact] = Field(description="Blocked people with the concrete rule (at most 10).")


ChangeClass = Literal["KEPT", "MOVED_TIME", "REASSIGNED", "CREATED", "REMOVED", "UNFILLED"]


class TraceChange(Model):
    logical_shift_id: UUID
    change: ChangeClass = Field(description="Never KEPT: kept shifts are only counted.")
    kinds: list[str] = Field(description="Finer diff kinds: added, removed, reassigned, moved, resized, ...")
    before_employee_id: UUID | None
    after_employee_id: UUID | None


class PlanDelta(Model):
    compared_to: Literal["base_version", "requested_plan"] | None = Field(
        description="base_version when regenerating or repairing; on an empty week, other plans compare "
        "with the requested plan (rank 1), whose deltas are null."
    )
    cost_delta_paise: int | None = Field(description="Labour plus overtime premium; negative = cheaper.")
    preferred_gap_delta_minutes: int | None = Field(description="Negative = better preferred coverage.")
    fairness_delta: float | None = Field(description="Fairness burden deviation; negative = fairer.")
    overtime_minutes: Minutes
    cross_outlet_moves: Minutes = Field(description="Shifts worked away from the person's home outlet.")
    changed_commitments: Minutes = Field(description="MOVED_TIME + REASSIGNED + REMOVED + UNFILLED.")


class DecisionTrace(Model):
    """What changed, what stayed, and the trade-off that produced the plan (architecture v4 section 18)."""

    strategy: Strategy | RepairProfile
    summary: PlanDelta
    counts: dict[ChangeClass, int] = Field(description="Every class, KEPT included.")
    explained_shifts: int = Field(ge=0, description="Changed shifts with why/why-not facts.")
    explanations_truncated: bool = Field(description="More changed shifts than were explained (limit 30).")


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
        default_factory=list,
        description="One per reassigned, created or unfilled shift against a base version (repairs, "
        "regeneration). Empty on an empty week, where every shift is new.",
    )
    trace: DecisionTrace | None = Field(default=None, description="null for candidates stored before 3.18.")

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
    trace_changes: list[TraceChange] = Field(
        default_factory=list, description="The change class of every non-kept shift, in time order."
    )


class Shortage(Model):
    outlet_id: UUID
    skill_id: UUID
    interval_start: AwareDatetime
    interval_end: AwareDatetime
    minimum_required: int
    max_assignable: int = Field(description="Upper bound of eligible staff for this interval.")


class RelaxationEmployee(Model):
    employee_id: UUID
    name: str
    home_outlet_id: UUID
    minutes: Minutes = Field(
        description="overtime: minutes beyond the regular week; cross_outlet: minutes worked."
    )


class RelaxationOption(Model):
    """A business option instead of a bare INFEASIBLE (architecture v3 section 13). It is a diagnosis
    found by re-solving with that one relaxation, not a schedule: apply it, then generate again."""

    kind: Literal["overtime", "cross_outlet", "reduced_minimum"] = Field(
        description="overtime: let the named people work overtime (update their overtime permission). "
        "cross_outlet: borrow the named people from their outlets (owner). reduced_minimum: operate the "
        "listed intervals with fewer staff (lower the week's minimum_required)."
    )
    summary: str = Field(description="Deterministic text built from the facts; safe to show.")
    employees: list[RelaxationEmployee] = Field(default_factory=list)
    shortages: list[Shortage] = Field(default_factory=list, description="reduced_minimum only.")


class Infeasibility(Model):
    summary: str
    shortages: list[Shortage]
    options: list[RelaxationOption] = Field(
        default_factory=list,
        description="In order: overtime, cross_outlet, reduced_minimum. Each was feasible on its own; none "
        "is claimed to be the smallest change. Overlap, availability, absences, mandatory skills, the "
        "absolute weekly cap and authorization boundaries are never relaxed.",
    )


RepairStageName = Literal["impact", "same_day", "adjacent_shifts", "other_outlets", "overtime"]


class RepairStage(Model):
    """One widening stage of a repair run (architecture v3 section 12), in the order tried."""

    stage: RepairStageName = Field(
        description="impact: only the shifts the absence breaks; everything else frozen (v4 section 15). "
        "same_day: the affected days from the absence onward, home staff, no overtime. "
        "adjacent_shifts: plus the day either side. other_outlets: plus other outlets' staff "
        "(owner-authorized). overtime: overtime where contracts allow it."
    )
    result: Literal["selected", "insufficient", "no_plan", "skipped"] = Field(
        description="selected: the candidates come from this stage. insufficient: minimum staffing "
        "could not be kept, so the repair widened. skipped: see reason."
    )
    reason: Literal["not_authorized", "same_scope"] | None = Field(
        default=None, description="Why a stage was skipped: not authorized, or no wider than the last."
    )
    free_shifts: int = Field(ge=0, description="Published shifts this stage was allowed to change.")
    pool: int = Field(ge=0, description="Employees who could take them.")
    minimum_shortfall_minutes: int | None = Field(
        default=None, ge=0, description="Best minimum-staffing shortfall found (staff-minutes)."
    )
    released: str | None = Field(default=None, description="What this stage was allowed to change.")
    widened_because: str | None = Field(default=None, description="Why the previous stage was not enough.")


class PortfolioDrop(Model):
    strategy: Strategy
    reason: Literal["duplicate", "guardrail", "dominated", "limit"] = Field(
        description="duplicate: same assignments as `detail[0]`. guardrail: broke the guardrails named "
        "in `detail` (cost, overtime, coverage, disruption, fairness), measured against the requested "
        "plan. dominated: `detail[0]` is no worse on every displayed metric and better on one. "
        "limit: valid and distinct, but beyond the three plans shown."
    )
    detail: list[str]


class PortfolioSummary(Model):
    """How the Candidate Portfolio chose what to show (architecture v4 section 16). The requested
    strategy's plan is always first; displayed metrics are total cost, preferred-coverage gap, overtime
    minutes, changed shifts (when there is a base) and fairness burden."""

    policy_version: int = Field(description="Guardrail policy revision.")
    considered: list[Strategy] = Field(description="Strategies solved, requested first.")
    dropped: list[PortfolioDrop]


class OptimizationRun(Model):
    id: UUID
    kind: Literal["generate", "optimize", "repair", "scenario"]
    outlet_ids: list[UUID]
    base_version_ids: list[UUID]
    strategy: Strategy | RepairProfile
    absence_id: UUID | None = Field(default=None, description="Repair runs: the absence being repaired.")
    scenario_id: UUID | None = Field(
        default=None, description="Scenario runs: hypothetical; their candidates cannot be selected."
    )
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
    repair_stages: list[RepairStage] = Field(
        default_factory=list,
        description="Repair runs, once finished: the widening stages tried and why it widened.",
    )
    frozen_logical_shift_ids: list[UUID] = Field(
        default_factory=list, description="The run's freeze set: shifts held exactly (v4 section 13)."
    )
    portfolio: PortfolioSummary | None = Field(
        default=None, description="Generate runs that finished with plans; null for repairs and before."
    )
    candidates_expired: bool = Field(
        default=False,
        description="Unselected candidates are removed 7 days after the run (retention); only selected "
        "ones remain, possibly none. Offer a new run instead of the old options.",
    )

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
            ok = (
                (has_candidates or self.candidates_expired)
                and self.infeasibility is None
                and self.error is None
            )
        elif self.solver_status == "INFEASIBLE":
            ok = not has_candidates and self.infeasibility is not None and self.error is None
        else:  # succeeded with UNKNOWN / MODEL_INVALID / missing status
            ok = self.solver_status is not None and not has_candidates and self.infeasibility is None
        if not ok:
            raise ValueError(
                f"inconsistent run: job_state={self.job_state} solver_status={self.solver_status}"
            )
        return self
