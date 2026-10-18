"""Scheduling v2 core tables (v2-schema-plan §3.1-3.5).

Tables from db/models_v2.py, plus what autogenerate cannot express:
- backfill skills/employee_skills from employees.job_role;
- immutability triggers: a non-draft version's shifts never change, and a version only moves
  draft -> published|discarded or published -> superseded with nothing else changing;
- RLS (USING + WITH CHECK) and least-privilege grants for the app role.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
# Frozen copy of db.models_v2.V2_TENANT_TABLES at this revision.
TABLES = [
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
]
# Whole-set replacement (PUT) needs DELETE; version_shifts deletes are trigger-guarded to drafts.
DELETABLE = [
    "employee_skills",
    "employee_availability",
    "employee_preferences",
    "travel_times",
    "shift_templates",
    "demand_bands",
    "demand_inputs",
    "staffing_requirements",
    "version_shifts",
]
INSERT_ONLY = ["logical_shifts"]

VERSION_SHIFTS_GUARD = """
CREATE FUNCTION version_shifts_draft_only() RETURNS trigger LANGUAGE plpgsql AS $fn$
DECLARE st text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT status INTO st FROM schedule_versions WHERE id = OLD.version_id;
        IF st IS DISTINCT FROM 'draft' THEN
            RAISE EXCEPTION 'schedule version % is %; its shifts are immutable', OLD.version_id, st
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT status INTO st FROM schedule_versions WHERE id = NEW.version_id;
        IF st IS DISTINCT FROM 'draft' THEN
            RAISE EXCEPTION 'schedule version % is %; its shifts are immutable', NEW.version_id, st
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $fn$
"""

VERSION_TRANSITIONS_GUARD = """
CREATE FUNCTION schedule_versions_transitions() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.id <> OLD.id OR NEW.org_id <> OLD.org_id OR NEW.schedule_id <> OLD.schedule_id
       OR NEW.version_number <> OLD.version_number THEN
        RAISE EXCEPTION 'schedule version identity is immutable' USING ERRCODE = 'check_violation';
    END IF;
    IF OLD.status = 'draft' AND NEW.status IN ('draft', 'published', 'discarded') THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'published' AND NEW.status = 'superseded'
       AND (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'schedule version % cannot change from % to %', OLD.id, OLD.status, NEW.status
        USING ERRCODE = 'check_violation';
END $fn$
"""


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
        sa.UniqueConstraint("org_id", "name"),
    )
    op.create_index(op.f("ix_skills_org_id"), "skills", ["org_id"], unique=False)
    op.create_table(
        "demand_bands",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=True),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("min_orders", sa.Integer(), nullable=False),
        sa.Column("max_orders", sa.Integer(), nullable=True),
        sa.Column("staff_minimum", sa.SmallInteger(), nullable=False),
        sa.Column("staff_preferred", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "min_orders >= 0 AND (max_orders IS NULL OR max_orders >= min_orders)", name="band_orders"
        ),
        sa.CheckConstraint("staff_minimum >= 0 AND staff_preferred >= staff_minimum", name="band_staff"),
        sa.ForeignKeyConstraint(
            ["org_id", "outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "skill_id"],
            ["skills.org_id", "skills.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_demand_bands_org_id"), "demand_bands", ["org_id"], unique=False)
    op.create_table(
        "demand_inputs",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("orders", sa.Integer(), nullable=False),
        sa.CheckConstraint("source IN ('history', 'scenario', 'manual')", name="demand_input_source"),
        sa.CheckConstraint("orders >= 0", name="demand_input_orders"),
        sa.ForeignKeyConstraint(
            ["org_id", "outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("outlet_id", "interval_start", "source"),
    )
    op.create_index(op.f("ix_demand_inputs_org_id"), "demand_inputs", ["org_id"], unique=False)
    op.create_table(
        "schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("extract(isodow FROM week_start) = 1", name="schedule_week_monday"),
        sa.ForeignKeyConstraint(
            ["org_id", "outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
        sa.UniqueConstraint("org_id", "outlet_id", "week_start"),
    )
    op.create_index(op.f("ix_schedules_org_id"), "schedules", ["org_id"], unique=False)
    op.create_table(
        "scheduling_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("min_rest_minutes", sa.Integer(), server_default="600", nullable=False),
        sa.Column("grid_minutes", sa.SmallInteger(), server_default="30", nullable=False),
        sa.Column("default_regular_weekly_minutes", sa.Integer(), server_default="2880", nullable=False),
        sa.Column("default_max_weekly_minutes", sa.Integer(), server_default="2880", nullable=False),
        sa.Column("daily_ot_threshold_minutes", sa.Integer(), nullable=True),
        sa.Column("ot_multiplier_bp", sa.Integer(), server_default="20000", nullable=False),
        sa.Column(
            "break_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.CheckConstraint(
            "default_max_weekly_minutes >= default_regular_weekly_minutes", name="policy_caps"
        ),
        sa.CheckConstraint("grid_minutes IN (15, 30, 60)", name="policy_grid"),
        sa.CheckConstraint("min_rest_minutes >= 0", name="policy_rest"),
        sa.ForeignKeyConstraint(
            ["org_id", "outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "outlet_id", "revision", postgresql_nulls_not_distinct=True),
    )
    op.create_index(op.f("ix_scheduling_policies_org_id"), "scheduling_policies", ["org_id"], unique=False)
    op.create_table(
        "shift_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("start_minute", sa.SmallInteger(), nullable=False),
        sa.Column("duration_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("break_minutes", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint("break_minutes >= 0 AND break_minutes < duration_minutes", name="template_break"),
        sa.CheckConstraint("duration_minutes > 0 AND duration_minutes <= 960", name="template_duration"),
        sa.CheckConstraint("start_minute BETWEEN 0 AND 1439", name="template_start"),
        sa.ForeignKeyConstraint(
            ["org_id", "outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "skill_id"],
            ["skills.org_id", "skills.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
    )
    op.create_index(op.f("ix_shift_templates_org_id"), "shift_templates", ["org_id"], unique=False)
    op.create_index(op.f("ix_shift_templates_outlet_id"), "shift_templates", ["outlet_id"], unique=False)
    op.create_table(
        "staffing_requirements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minimum_required", sa.SmallInteger(), nullable=False),
        sa.Column("preferred_required", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("demand_revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("source IN ('band', 'manual', 'scenario')", name="requirement_source"),
        sa.CheckConstraint("interval_end > interval_start", name="requirement_interval"),
        sa.CheckConstraint(
            "minimum_required >= 0 AND preferred_required >= minimum_required", name="requirement_staff"
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "skill_id"],
            ["skills.org_id", "skills.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "skill_id", "interval_start"),
    )
    op.create_index(
        op.f("ix_staffing_requirements_org_id"), "staffing_requirements", ["org_id"], unique=False
    )
    op.create_table(
        "travel_times",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("from_outlet_id", sa.UUID(), nullable=False),
        sa.Column("to_outlet_id", sa.UUID(), nullable=False),
        sa.Column("minutes", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("from_outlet_id <> to_outlet_id", name="travel_distinct"),
        sa.CheckConstraint("minutes >= 0", name="travel_minutes"),
        sa.ForeignKeyConstraint(
            ["org_id", "from_outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "to_outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("from_outlet_id", "to_outlet_id"),
    )
    op.create_index(op.f("ix_travel_times_org_id"), "travel_times", ["org_id"], unique=False)
    op.create_table(
        "employee_availability",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_minute", sa.SmallInteger(), nullable=False),
        sa.Column("end_minute", sa.SmallInteger(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint("kind IN ('available', 'preferred', 'unavailable')", name="availability_kind"),
        sa.CheckConstraint(
            "start_minute >= 0 AND end_minute <= 2880 AND end_minute > start_minute",
            name="availability_window",
        ),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="availability_validity"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="availability_weekday"),
        sa.ForeignKeyConstraint(
            ["org_id", "employee_id"],
            ["employees.org_id", "employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_availability_employee_id"), "employee_availability", ["employee_id"], unique=False
    )
    op.create_index(
        op.f("ix_employee_availability_org_id"), "employee_availability", ["org_id"], unique=False
    )
    op.create_table(
        "employee_preferences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("preference_type", sa.String(length=40), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weight", sa.SmallInteger(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id", "employee_id"],
            ["employees.org_id", "employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_preferences_employee_id"), "employee_preferences", ["employee_id"], unique=False
    )
    op.create_index(op.f("ix_employee_preferences_org_id"), "employee_preferences", ["org_id"], unique=False)
    op.create_table(
        "employee_skills",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("level", sa.SmallInteger(), server_default="1", nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 3", name="employee_skills_level"),
        sa.ForeignKeyConstraint(
            ["org_id", "employee_id"],
            ["employees.org_id", "employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "skill_id"],
            ["skills.org_id", "skills.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("employee_id", "skill_id"),
    )
    op.create_index(op.f("ix_employee_skills_org_id"), "employee_skills", ["org_id"], unique=False)
    op.create_table(
        "logical_shifts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("created_in_version_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id", "schedule_id"],
            ["schedules.org_id", "schedules.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "schedule_id"),
        sa.UniqueConstraint("org_id", "id"),
    )
    op.create_index(op.f("ix_logical_shifts_org_id"), "logical_shifts", ["org_id"], unique=False)
    op.create_index(op.f("ix_logical_shifts_schedule_id"), "logical_shifts", ["schedule_id"], unique=False)
    op.create_table(
        "absences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reported_by_user_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('leave', 'sick', 'other')", name="absence_kind"),
        sa.CheckConstraint("source IN ('manager', 'employee', 'import')", name="absence_source"),
        sa.CheckConstraint(
            "status IN ('requested', 'confirmed', 'rejected', 'cancelled')", name="absence_status"
        ),
        sa.CheckConstraint("end_at > start_at", name="absence_interval"),
        sa.ForeignKeyConstraint(
            ["org_id", "employee_id"],
            ["employees.org_id", "employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "reported_by_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_absences_employee_time", "absences", ["employee_id", "start_at"], unique=False)
    op.create_index(op.f("ix_absences_org_id"), "absences", ["org_id"], unique=False)
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("strategy", sa.String(length=20), nullable=False),
        sa.Column("outlet_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("base_version_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=80), nullable=False),
        sa.Column("job_state", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("solver_status", sa.String(length=20), nullable=True),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("input_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("lease_owner", sa.String(length=80), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("solver_wall_ms", sa.Integer(), nullable=True),
        sa.Column("objective", sa.BigInteger(), nullable=True),
        sa.Column("best_bound", sa.BigInteger(), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "job_state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="run_job_state"
        ),
        sa.CheckConstraint("kind IN ('generate', 'optimize', 'repair')", name="run_kind"),
        sa.CheckConstraint(
            "solver_status IS NULL OR solver_status IN ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'MODEL_INVALID', 'UNKNOWN')",
            name="run_solver_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="run_attempts"),
        sa.ForeignKeyConstraint(
            ["org_id", "requested_by_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
        sa.UniqueConstraint("org_id", "idempotency_key"),
    )
    op.create_index(op.f("ix_optimization_runs_org_id"), "optimization_runs", ["org_id"], unique=False)
    op.create_index(
        "ix_optimization_runs_queue",
        "optimization_runs",
        ["queued_at"],
        unique=False,
        postgresql_where=sa.text("job_state IN ('queued', 'running')"),
    )
    op.create_table(
        "scheduling_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_type", sa.String(length=60), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hard", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="rule_status"),
        sa.ForeignKeyConstraint(
            ["org_id", "created_by_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scheduling_rules_org_id"), "scheduling_rules", ["org_id"], unique=False)
    op.create_table(
        "schedule_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("base_version_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("optimization_run_id", sa.UUID(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.CheckConstraint(
            "(status IN ('published', 'superseded')) = (published_at IS NOT NULL)",
            name="version_published_at",
        ),
        sa.CheckConstraint(
            "source IN ('seed', 'manual', 'generate', 'optimize', 'repair', 'restore', 'import')",
            name="version_source",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'superseded', 'discarded')", name="version_status"
        ),
        sa.ForeignKeyConstraint(
            ["base_version_id", "schedule_id"],
            ["schedule_versions.id", "schedule_versions.schedule_id"],
            name="schedule_versions_base_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "approved_by_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "created_by_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "optimization_run_id"],
            ["optimization_runs.org_id", "optimization_runs.id"],
            name="schedule_versions_run_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "schedule_id"],
            ["schedules.org_id", "schedules.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "schedule_id"),
        sa.UniqueConstraint("org_id", "id"),
        sa.UniqueConstraint("schedule_id", "version_number"),
    )
    op.create_index(op.f("ix_schedule_versions_org_id"), "schedule_versions", ["org_id"], unique=False)
    op.create_table(
        "optimization_candidates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("strategy", sa.String(length=20), nullable=False),
        sa.Column("solver_status", sa.String(length=20), nullable=False),
        sa.Column("proven_optimal", sa.Boolean(), nullable=False),
        sa.Column("objective_components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("draft_version_id", sa.UUID(), nullable=False),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "explanation_facts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("dedup_hash", sa.String(length=80), nullable=False),
        sa.CheckConstraint("NOT proven_optimal OR solver_status = 'OPTIMAL'", name="candidate_optimality"),
        sa.CheckConstraint("solver_status IN ('OPTIMAL', 'FEASIBLE')", name="candidate_solver_status"),
        sa.CheckConstraint("rank >= 1", name="candidate_rank"),
        sa.ForeignKeyConstraint(
            ["org_id", "draft_version_id"],
            ["schedule_versions.org_id", "schedule_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "run_id"],
            ["optimization_runs.org_id", "optimization_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
        sa.UniqueConstraint("run_id", "dedup_hash"),
        sa.UniqueConstraint("run_id", "rank"),
    )
    op.create_index(
        op.f("ix_optimization_candidates_org_id"), "optimization_candidates", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_optimization_candidates_run_id"), "optimization_candidates", ["run_id"], unique=False
    )
    op.create_table(
        "version_shifts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("logical_shift_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=True),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("break_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("break_minutes", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("lock_reason", sa.Text(), nullable=True),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "end_at > start_at AND end_at - start_at <= interval '16 hours'", name="shift_interval"
        ),
        sa.CheckConstraint("break_minutes >= 0", name="shift_break_minutes"),
        sa.CheckConstraint(
            "break_start_at IS NULL OR (break_start_at >= start_at AND break_start_at + make_interval(mins => break_minutes) <= end_at)",
            name="shift_break_inside",
        ),
        sa.CheckConstraint("locked OR lock_reason IS NULL", name="shift_lock_reason"),
        sa.ForeignKeyConstraint(
            ["logical_shift_id", "schedule_id"],
            ["logical_shifts.id", "logical_shifts.schedule_id"],
            name="version_shifts_logical_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "employee_id"],
            ["employees.org_id", "employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "outlet_id"],
            ["outlets.org_id", "outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "schedule_id"],
            ["schedules.org_id", "schedules.id"],
            name="version_shifts_schedule_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "skill_id"],
            ["skills.org_id", "skills.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "template_id"],
            ["shift_templates.org_id", "shift_templates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "schedule_id"],
            ["schedule_versions.id", "schedule_versions.schedule_id"],
            name="version_shifts_version_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "logical_shift_id"),
    )
    op.create_index(
        "ix_version_shifts_employee_time", "version_shifts", ["employee_id", "start_at"], unique=False
    )
    op.create_index(op.f("ix_version_shifts_org_id"), "version_shifts", ["org_id"], unique=False)
    op.create_index(op.f("ix_version_shifts_version_id"), "version_shifts", ["version_id"], unique=False)
    op.create_table(
        "schedule_proposals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=True),
        sa.Column("draft_version_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("base_version_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("required_role", sa.String(length=20), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=80), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("(status = 'pending') = (decided_at IS NULL)", name="proposal_decided_at"),
        sa.CheckConstraint("required_role IN ('owner', 'manager')", name="proposal_required_role"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'stale', 'failed')",
            name="proposal_status",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "candidate_id"],
            ["optimization_candidates.org_id", "optimization_candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "decided_by_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "requested_by_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "idempotency_key"),
    )
    op.create_index(op.f("ix_schedule_proposals_org_id"), "schedule_proposals", ["org_id"], unique=False)

    # Circular reference, added once both tables exist: the live version belongs to this schedule.
    op.create_foreign_key(
        "schedules_current_version_fkey",
        "schedules",
        "schedule_versions",
        ["current_version_id", "id"],
        ["id", "schedule_id"],
    )

    # Backfill: each distinct v1 job_role becomes a skill held by its employees.
    op.execute("""
        INSERT INTO skills (id, org_id, name)
        SELECT gen_random_uuid(), org_id, initcap(job_role)
        FROM (SELECT DISTINCT org_id, job_role FROM employees) roles
        ON CONFLICT (org_id, name) DO NOTHING
    """)
    op.execute("""
        INSERT INTO employee_skills (org_id, employee_id, skill_id, level)
        SELECT e.org_id, e.id, s.id, 2
        FROM employees e JOIN skills s ON s.org_id = e.org_id AND s.name = initcap(e.job_role)
        ON CONFLICT DO NOTHING
    """)

    op.execute(VERSION_SHIFTS_GUARD)
    op.execute(VERSION_TRANSITIONS_GUARD)
    op.execute(
        "CREATE TRIGGER version_shifts_draft_only BEFORE INSERT OR UPDATE OR DELETE ON version_shifts "
        "FOR EACH ROW EXECUTE FUNCTION version_shifts_draft_only()"
    )
    op.execute(
        "CREATE TRIGGER schedule_versions_transitions BEFORE UPDATE ON schedule_versions "
        "FOR EACH ROW EXECUTE FUNCTION schedule_versions_transitions()"
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
        )
        privileges = "SELECT, INSERT" if table in INSERT_ONLY else "SELECT, INSERT, UPDATE"
        if table in DELETABLE:
            privileges += ", DELETE"
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_constraint("schedules_current_version_fkey", "schedules", type_="foreignkey")
    op.drop_index(op.f("ix_schedule_proposals_org_id"), table_name="schedule_proposals")
    op.drop_table("schedule_proposals")
    op.drop_index(op.f("ix_version_shifts_version_id"), table_name="version_shifts")
    op.drop_index(op.f("ix_version_shifts_org_id"), table_name="version_shifts")
    op.drop_index("ix_version_shifts_employee_time", table_name="version_shifts")
    op.drop_table("version_shifts")
    op.drop_index(op.f("ix_optimization_candidates_run_id"), table_name="optimization_candidates")
    op.drop_index(op.f("ix_optimization_candidates_org_id"), table_name="optimization_candidates")
    op.drop_table("optimization_candidates")
    op.drop_index(op.f("ix_schedule_versions_org_id"), table_name="schedule_versions")
    op.drop_table("schedule_versions")
    op.drop_index(op.f("ix_scheduling_rules_org_id"), table_name="scheduling_rules")
    op.drop_table("scheduling_rules")
    op.drop_index(
        "ix_optimization_runs_queue",
        table_name="optimization_runs",
        postgresql_where=sa.text("job_state IN ('queued', 'running')"),
    )
    op.drop_index(op.f("ix_optimization_runs_org_id"), table_name="optimization_runs")
    op.drop_table("optimization_runs")
    op.drop_index(op.f("ix_absences_org_id"), table_name="absences")
    op.drop_index("ix_absences_employee_time", table_name="absences")
    op.drop_table("absences")
    op.drop_index(op.f("ix_logical_shifts_schedule_id"), table_name="logical_shifts")
    op.drop_index(op.f("ix_logical_shifts_org_id"), table_name="logical_shifts")
    op.drop_table("logical_shifts")
    op.drop_index(op.f("ix_employee_skills_org_id"), table_name="employee_skills")
    op.drop_table("employee_skills")
    op.drop_index(op.f("ix_employee_preferences_org_id"), table_name="employee_preferences")
    op.drop_index(op.f("ix_employee_preferences_employee_id"), table_name="employee_preferences")
    op.drop_table("employee_preferences")
    op.drop_index(op.f("ix_employee_availability_org_id"), table_name="employee_availability")
    op.drop_index(op.f("ix_employee_availability_employee_id"), table_name="employee_availability")
    op.drop_table("employee_availability")
    op.drop_index(op.f("ix_travel_times_org_id"), table_name="travel_times")
    op.drop_table("travel_times")
    op.drop_index(op.f("ix_staffing_requirements_org_id"), table_name="staffing_requirements")
    op.drop_table("staffing_requirements")
    op.drop_index(op.f("ix_shift_templates_outlet_id"), table_name="shift_templates")
    op.drop_index(op.f("ix_shift_templates_org_id"), table_name="shift_templates")
    op.drop_table("shift_templates")
    op.drop_index(op.f("ix_scheduling_policies_org_id"), table_name="scheduling_policies")
    op.drop_table("scheduling_policies")
    op.drop_index(op.f("ix_schedules_org_id"), table_name="schedules")
    op.drop_table("schedules")
    op.drop_index(op.f("ix_demand_inputs_org_id"), table_name="demand_inputs")
    op.drop_table("demand_inputs")
    op.drop_index(op.f("ix_demand_bands_org_id"), table_name="demand_bands")
    op.drop_table("demand_bands")
    op.drop_index(op.f("ix_skills_org_id"), table_name="skills")
    op.drop_table("skills")
    op.execute("DROP FUNCTION IF EXISTS version_shifts_draft_only()")
    op.execute("DROP FUNCTION IF EXISTS schedule_versions_transitions()")
