"""Scheduling v2 tables (docs/runbooks/v2-schema-plan.md §3).

Every table carries org_id and references tenant-owned parents through composite
(org_id, parent_id) foreign keys, so a row can never point at another tenant's data even though
RLS hides those rows from reads. Instants are timestamptz; recurring times are minutes from
outlet-local midnight; durations are minutes; money is integer paise.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base


def pk() -> Mapped[uuid.UUID]:
    # UUIDv7: time-ordered, so inserts append to the right edge of B-tree indexes (architecture §17).
    # Never use its embedded time as business ordering.
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid7)


def org() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)


def ref(column: str, parent: str, *, name: str | None = None) -> ForeignKeyConstraint:
    """Composite tenant FK: (org_id, column) -> parent(org_id, id)."""
    return ForeignKeyConstraint(["org_id", column], [f"{parent}.org_id", f"{parent}.id"], name=name)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def one_of(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)


# ---------------------------------------------------------------- people


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("org_id", "name"), UniqueConstraint("org_id", "id"))
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    name: Mapped[str] = mapped_column(String(80))


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    __table_args__ = (
        ref("employee_id", "employees"),
        ref("skill_id", "skills"),
        CheckConstraint("level BETWEEN 1 AND 3", name="employee_skills_level"),
    )
    org_id: Mapped[uuid.UUID] = org()
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    level: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")


AVAILABILITY_KINDS = ("available", "preferred", "unavailable")


class EmployeeAvailability(Base):
    __tablename__ = "employee_availability"
    __table_args__ = (
        ref("employee_id", "employees"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="availability_weekday"),
        CheckConstraint(
            "start_minute >= 0 AND end_minute <= 2880 AND end_minute > start_minute",
            name="availability_window",
        ),
        one_of("kind", AVAILABILITY_KINDS, "availability_kind"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="availability_validity"),
        Index("ix_employee_availability_lookup", "org_id", "employee_id", "weekday"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_minute: Mapped[int] = mapped_column(SmallInteger)
    end_minute: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class Absence(Base):
    __tablename__ = "absences"
    __table_args__ = (
        ref("employee_id", "employees"),
        ref("reported_by_user_id", "users"),
        CheckConstraint("end_at > start_at", name="absence_interval"),
        one_of("kind", ("leave", "sick", "other"), "absence_kind"),
        one_of("status", ("requested", "confirmed", "rejected", "cancelled"), "absence_status"),
        one_of("source", ("manager", "employee", "import"), "absence_source"),
        Index("ix_absences_lookup", "org_id", "employee_id", "start_at"),
        UniqueConstraint("org_id", "id"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    reported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at()


class EmployeePreference(Base):
    __tablename__ = "employee_preferences"
    __table_args__ = (ref("employee_id", "employees"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    preference_type: Mapped[str] = mapped_column(String(40))
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    weight: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")


class TravelTime(Base):
    __tablename__ = "travel_times"
    __table_args__ = (
        ref("from_outlet_id", "outlets"),
        ref("to_outlet_id", "outlets"),
        CheckConstraint("minutes >= 0", name="travel_minutes"),
        CheckConstraint("from_outlet_id <> to_outlet_id", name="travel_distinct"),
    )
    org_id: Mapped[uuid.UUID] = org()
    from_outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    to_outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    minutes: Mapped[int] = mapped_column(SmallInteger)


# ---------------------------------------------------------------- policy, templates, demand


class SchedulingPolicy(Base):
    __tablename__ = "scheduling_policies"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        UniqueConstraint("org_id", "outlet_id", "revision", postgresql_nulls_not_distinct=True),
        CheckConstraint("grid_minutes IN (15, 30, 60)", name="policy_grid"),
        CheckConstraint("min_rest_minutes >= 0", name="policy_rest"),
        CheckConstraint("default_max_weekly_minutes >= default_regular_weekly_minutes", name="policy_caps"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer)
    min_rest_minutes: Mapped[int] = mapped_column(Integer, default=600, server_default="600")
    grid_minutes: Mapped[int] = mapped_column(SmallInteger, default=30, server_default="30")
    default_regular_weekly_minutes: Mapped[int] = mapped_column(Integer, default=2880, server_default="2880")
    default_max_weekly_minutes: Mapped[int] = mapped_column(Integer, default=2880, server_default="2880")
    daily_ot_threshold_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ot_multiplier_bp: Mapped[int] = mapped_column(Integer, default=20000, server_default="20000")
    break_rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    effective_from: Mapped[date] = mapped_column(Date)


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        ref("skill_id", "skills"),
        UniqueConstraint("org_id", "id"),
        CheckConstraint("start_minute BETWEEN 0 AND 1439", name="template_start"),
        CheckConstraint("duration_minutes > 0 AND duration_minutes <= 960", name="template_duration"),
        CheckConstraint("break_minutes >= 0 AND break_minutes < duration_minutes", name="template_break"),
        CheckConstraint(
            "break_offset_minutes IS NULL OR (break_offset_minutes >= 0 "
            "AND break_offset_minutes + break_minutes <= duration_minutes)",
            name="template_break_offset",
        ),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    skill_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(80))
    start_minute: Mapped[int] = mapped_column(SmallInteger)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger)
    break_minutes: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    # Minutes from shift start to break start; null = no fixed position (placed at the midpoint).
    break_offset_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class DemandBand(Base):
    __tablename__ = "demand_bands"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        ref("skill_id", "skills"),
        CheckConstraint(
            "min_orders >= 0 AND (max_orders IS NULL OR max_orders >= min_orders)", name="band_orders"
        ),
        CheckConstraint("staff_minimum >= 0 AND staff_preferred >= staff_minimum", name="band_staff"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    min_orders: Mapped[int] = mapped_column(Integer)
    max_orders: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staff_minimum: Mapped[int] = mapped_column(SmallInteger)
    staff_preferred: Mapped[int] = mapped_column(SmallInteger)


class DemandInput(Base):
    __tablename__ = "demand_inputs"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        one_of("source", ("history", "scenario", "manual"), "demand_input_source"),
        CheckConstraint("orders >= 0", name="demand_input_orders"),
    )
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(20), primary_key=True)
    orders: Mapped[int] = mapped_column(Integer)


REQUIREMENT_SOURCES = ("template", "band", "manual", "scenario", "forecast")


class StaffingTemplate(Base):
    """Default demand for a normal week (architecture v3 section 18): weekday x block x skill.
    Replacing a set deactivates the old rows, so revision (shared by the active set) stays monotonic."""

    __tablename__ = "staffing_templates"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        ref("skill_id", "skills"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="staffing_template_weekday"),
        CheckConstraint(
            "start_minute >= 0 AND end_minute <= 1440 AND end_minute > start_minute "
            "AND start_minute % 30 = 0 AND end_minute % 30 = 0",
            name="staffing_template_block",
        ),
        CheckConstraint(
            "minimum_required >= 0 AND preferred_required >= minimum_required", name="staffing_template_staff"
        ),
        CheckConstraint("revision >= 1", name="staffing_template_revision"),
        Index("ix_staffing_templates_active", "outlet_id", "weekday", postgresql_where=text("active")),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_minute: Mapped[int] = mapped_column(SmallInteger)
    end_minute: Mapped[int] = mapped_column(SmallInteger)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    minimum_required: Mapped[int] = mapped_column(SmallInteger)
    preferred_required: Mapped[int] = mapped_column(SmallInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    revision: Mapped[int] = mapped_column(Integer)


class DemandWeek(Base):
    """The outlet-week demand_revision; every change to that week's staffing requirements bumps it."""

    __tablename__ = "demand_weeks"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        CheckConstraint("demand_revision >= 1", name="demand_week_revision"),
    )
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    demand_revision: Mapped[int] = mapped_column(Integer)


class StaffingRequirement(Base):
    __tablename__ = "staffing_requirements"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        ref("skill_id", "skills"),
        UniqueConstraint("outlet_id", "skill_id", "interval_start"),
        Index("ix_staffing_requirements_week", "outlet_id", "interval_start"),
        CheckConstraint("interval_end > interval_start", name="requirement_interval"),
        CheckConstraint(
            "minimum_required >= 0 AND preferred_required >= minimum_required", name="requirement_staff"
        ),
        one_of("source", REQUIREMENT_SOURCES, "requirement_source"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    interval_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    minimum_required: Mapped[int] = mapped_column(SmallInteger)
    preferred_required: Mapped[int] = mapped_column(SmallInteger)
    source: Mapped[str] = mapped_column(String(20))
    demand_revision: Mapped[int] = mapped_column(Integer)


class SchedulingRule(Base):
    __tablename__ = "scheduling_rules"
    __table_args__ = (
        ref("created_by_user_id", "users"),
        one_of("status", ("draft", "active", "archived"), "rule_status"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rule_type: Mapped[str] = mapped_column(String(60))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    hard: Mapped[bool] = mapped_column(Boolean)
    priority: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = created_at()


# ---------------------------------------------------------------- schedules and immutable versions

VERSION_STATUSES = ("draft", "published", "superseded", "discarded")
VERSION_SOURCES = ("seed", "manual", "generate", "optimize", "repair", "restore", "import")


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        UniqueConstraint("org_id", "outlet_id", "week_start"),
        UniqueConstraint("org_id", "id"),
        CheckConstraint("extract(isodow FROM week_start) = 1", name="schedule_week_monday"),
        # The live version must belong to this schedule (not just this tenant).
        ForeignKeyConstraint(
            ["current_version_id", "id"],
            ["schedule_versions.id", "schedule_versions.schedule_id"],
            name="schedules_current_version_fkey",
            use_alter=True,
        ),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    week_start: Mapped[date] = mapped_column(Date)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = created_at()


class ScheduleVersion(Base):
    __tablename__ = "schedule_versions"
    __table_args__ = (
        ref("schedule_id", "schedules"),
        ref("created_by_user_id", "users"),
        ref("approved_by_user_id", "users"),
        ForeignKeyConstraint(
            ["base_version_id", "schedule_id"],
            ["schedule_versions.id", "schedule_versions.schedule_id"],
            name="schedule_versions_base_fkey",
        ),
        ref("optimization_run_id", "optimization_runs", name="schedule_versions_run_fkey"),
        UniqueConstraint("schedule_id", "version_number"),
        UniqueConstraint("org_id", "id"),
        UniqueConstraint("id", "schedule_id"),
        one_of("status", VERSION_STATUSES, "version_status"),
        one_of("source", VERSION_SOURCES, "version_source"),
        CheckConstraint(
            "(status IN ('published', 'superseded')) = (published_at IS NOT NULL)",
            name="version_published_at",
        ),
        CheckConstraint("revision >= 1", name="version_revision"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    base_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    optimization_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = created_at()
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Contract Metrics, stored while a draft is validated and at publication (v3 section 22).
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class LogicalShift(Base):
    __tablename__ = "logical_shifts"
    __table_args__ = (
        ref("schedule_id", "schedules"),
        UniqueConstraint("org_id", "id"),
        UniqueConstraint("id", "schedule_id"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    created_in_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class VersionShift(Base):
    __tablename__ = "version_shifts"
    __table_args__ = (
        ref("outlet_id", "outlets"),
        ref("employee_id", "employees"),
        ref("skill_id", "skills"),
        ref("template_id", "shift_templates"),
        # Version and logical shift must both belong to the same schedule as this row.
        ForeignKeyConstraint(
            ["version_id", "schedule_id"],
            ["schedule_versions.id", "schedule_versions.schedule_id"],
            name="version_shifts_version_fkey",
        ),
        ForeignKeyConstraint(
            ["logical_shift_id", "schedule_id"],
            ["logical_shifts.id", "logical_shifts.schedule_id"],
            name="version_shifts_logical_fkey",
        ),
        ref("schedule_id", "schedules", name="version_shifts_schedule_fkey"),
        UniqueConstraint("version_id", "logical_shift_id"),
        CheckConstraint(
            "end_at > start_at AND end_at - start_at <= interval '16 hours'", name="shift_interval"
        ),
        CheckConstraint("break_minutes >= 0", name="shift_break_minutes"),
        CheckConstraint(
            "break_start_at IS NULL OR (break_start_at >= start_at AND "
            "break_start_at + make_interval(mins => break_minutes) <= end_at)",
            name="shift_break_inside",
        ),
        CheckConstraint("locked OR lock_reason IS NULL", name="shift_lock_reason"),
        Index("ix_version_shifts_roster", "version_id", "employee_id", "start_at"),
        Index("ix_version_shifts_employee_time", "employee_id", "start_at"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    logical_shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    break_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    break_minutes: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


# ---------------------------------------------------------------- runs, candidates, proposals

JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled")
SOLVER_STATUSES = ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "MODEL_INVALID", "UNKNOWN")


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    __table_args__ = (
        ref("requested_by_user_id", "users"),
        UniqueConstraint("org_id", "id"),
        UniqueConstraint("org_id", "idempotency_key"),
        one_of("kind", ("generate", "optimize", "repair"), "run_kind"),
        one_of("job_state", JOB_STATES, "run_job_state"),
        CheckConstraint(
            f"solver_status IS NULL OR solver_status IN {SOLVER_STATUSES}", name="run_solver_status"
        ),
        CheckConstraint("attempts >= 0", name="run_attempts"),
        ref("schedule_id", "schedules", name="optimization_runs_schedule_fkey"),
        ref("trigger_absence_id", "absences", name="optimization_runs_absence_fkey"),
        Index(
            "ix_optimization_runs_claim",
            "priority",
            "queued_at",
            postgresql_where=text("job_state = 'queued'"),
        ),
        Index(
            "ux_optimization_runs_active_batch",
            "org_id",
            "schedule_id",
            unique=True,
            postgresql_where=text("kind IN ('generate', 'optimize') AND job_state IN ('queued', 'running')"),
        ),
        Index(
            "ux_optimization_runs_active_repair",
            "org_id",
            "trigger_absence_id",
            unique=True,
            postgresql_where=text("job_state IN ('queued', 'running')"),
        ),
        Index("ix_optimization_runs_lease", "lease_until", postgresql_where=text("job_state = 'running'")),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    kind: Mapped[str] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(SmallInteger, default=100, server_default="100")
    strategy: Mapped[str] = mapped_column(String(20))
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    trigger_absence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    outlet_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    base_version_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(80))
    job_state: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    solver_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(80))
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    lease_owner: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    solver_wall_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    objective: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    best_bound: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    traceparent: Mapped[str | None] = mapped_column(String(80), nullable=True)


class OptimizationCandidate(Base):
    __tablename__ = "optimization_candidates"
    __table_args__ = (
        ref("run_id", "optimization_runs"),
        ref("materialized_version_id", "schedule_versions"),
        UniqueConstraint("run_id", "dedup_hash"),
        UniqueConstraint("run_id", "rank"),
        UniqueConstraint("org_id", "id"),
        one_of("solver_status", ("OPTIMAL", "FEASIBLE"), "candidate_solver_status"),
        CheckConstraint("rank >= 1", name="candidate_rank"),
        CheckConstraint("NOT proven_optimal OR solver_status = 'OPTIMAL'", name="candidate_optimality"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    rank: Mapped[int] = mapped_column(SmallInteger)
    strategy: Mapped[str] = mapped_column(String(20))
    solver_status: Mapped[str] = mapped_column(String(20))
    proven_optimal: Mapped[bool] = mapped_column(Boolean)
    objective_components: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    diff: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Null until a manager selects the candidate (architecture v3 section 23).
    materialized_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    validation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    explanation_facts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    dedup_hash: Mapped[str] = mapped_column(String(80))


class ScheduleProposal(Base):
    __tablename__ = "schedule_proposals"
    __table_args__ = (
        ref("candidate_id", "optimization_candidates"),
        ref("requested_by_user_id", "users"),
        ref("decided_by_user_id", "users"),
        UniqueConstraint("org_id", "idempotency_key"),
        one_of(
            "status", ("pending", "approved", "rejected", "expired", "stale", "failed"), "proposal_status"
        ),
        one_of("required_role", ("owner", "manager"), "proposal_required_role"),
        CheckConstraint("(status = 'pending') = (decided_at IS NULL)", name="proposal_decided_at"),
        CheckConstraint(
            "cardinality(draft_revisions) = cardinality(draft_version_ids)", name="proposal_draft_revisions"
        ),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    draft_version_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    base_version_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    # What the manager agreed to (architecture v3 section 31): the draft revisions and their metrics.
    draft_revisions: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default=text("'{}'::integer[]"))
    metrics_at_proposal: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    input_hash: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    required_role: Mapped[str] = mapped_column(String(20))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(80))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = created_at()


OUTBOX_TOPICS = (
    "schedule.published",
    "proposal.ready",
    "proposal.stale",
    "run.finished",
    "absence.reported",
    "rule.changed",
    "version.metrics.requested",
)


class OutboxEvent(Base):
    """Transactional outbox (architecture §19): written in the same transaction as the change,
    delivered at least once by jobs.outbox_relay."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("org_id", "id"),
        one_of("topic", OUTBOX_TOPICS, "outbox_topic"),
        CheckConstraint("attempts >= 0", name="outbox_attempts"),
        Index("ix_outbox_events_pending", "next_attempt_at", postgresql_where=text("published_at IS NULL")),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    topic: Mapped[str] = mapped_column(String(60))
    aggregate_type: Mapped[str] = mapped_column(String(40))
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    traceparent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = created_at()
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationDelivery(Base):
    """Idempotent consumer record: one delivery per event, recipient and channel. No FK to
    outbox_events, whose published rows are deleted after 7 days."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        ref("recipient_user_id", "users"),
        UniqueConstraint("event_id", "recipient_user_id", "channel"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    channel: Mapped[str] = mapped_column(String(20))
    delivered_at: Mapped[datetime] = created_at()


class IdempotencyKey(Base):
    """Stored result of a mutating request, replayed when the same key is sent again. A different
    request body under the same key is a 409 idempotency_conflict."""

    __tablename__ = "idempotency_keys"
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    operation: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(80))
    status_code: Mapped[int] = mapped_column(SmallInteger)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()


V2_TENANT_TABLES = [
    "skills",
    "employee_skills",
    "employee_availability",
    "absences",
    "employee_preferences",
    "travel_times",
    "scheduling_policies",
    "shift_templates",
    "demand_bands",
    "demand_inputs",
    "staffing_requirements",
    "scheduling_rules",
    "schedules",
    "schedule_versions",
    "logical_shifts",
    "version_shifts",
    "optimization_runs",
    "optimization_candidates",
    "schedule_proposals",
    "outbox_events",
    "notification_deliveries",
    "idempotency_keys",
]


class ImportJob(Base):
    """One uploaded onboarding file (architecture v3 section 19). Committed all at once or not at all."""

    __tablename__ = "import_jobs"
    __table_args__ = (
        ref("created_by_user_id", "users"),
        UniqueConstraint("org_id", "id"),
        one_of("kind", ("employees",), "import_kind"),
        one_of("status", ("staged", "invalid", "committed", "expired"), "import_status"),
        CheckConstraint("(status = 'committed') = (committed_at IS NOT NULL)", name="import_committed_at"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(200))
    row_count: Mapped[int] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer)
    file_errors: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = created_at()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "job_id"], ["import_jobs.org_id", "import_jobs.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("job_id", "row_number"),
    )
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org()
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    row_number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    errors: Mapped[list[dict[str, str]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
