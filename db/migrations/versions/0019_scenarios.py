"""Scenario Lab (architecture v4 sections 23, 42, task A4.6).

planning_scenarios holds a hypothetical what-if for one outlet week; scenario_events its overlay events in
sequence. Events are applied only while building the solver input: no scenario ever writes absences,
availability, rules or staffing requirements. Scenario runs are optimization_runs with kind 'scenario'
and a scenario_id; a converted scenario becomes a normal draft (schedule_versions.source 'scenario').

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
GRANTS = {"planning_scenarios": "SELECT, INSERT, UPDATE", "scenario_events": "SELECT, INSERT"}
OLD_SOURCES = "'seed', 'manual', 'generate', 'optimize', 'repair', 'restore', 'import'"


def upgrade() -> None:
    op.create_table(
        "planning_scenarios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("base_version_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("converted_version_id", sa.UUID(), nullable=True),
        sa.CheckConstraint("status IN ('open', 'converted', 'discarded', 'expired')", name="scenario_status"),
        sa.CheckConstraint(
            "(status = 'converted') = (converted_version_id IS NOT NULL)", name="scenario_converted_version"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "schedule_id"], ["schedules.org_id", "schedules.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "base_version_id"], ["schedule_versions.org_id", "schedule_versions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "converted_version_id"], ["schedule_versions.org_id", "schedule_versions.id"]
        ),
        sa.ForeignKeyConstraint(["org_id", "created_by_user_id"], ["users.org_id", "users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
    )
    op.create_index(op.f("ix_planning_scenarios_org_id"), "planning_scenarios", ["org_id"], unique=False)
    op.create_index("ix_planning_scenarios_schedule", "planning_scenarios", ["schedule_id"], unique=False)
    op.create_table(
        "scenario_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("scenario_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "type IN ('demand_change', 'absence', 'outlet_closure', 'labour_cap', 'rule')",
            name="scenario_event_type",
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "scenario_id"],
            ["planning_scenarios.org_id", "planning_scenarios.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_id", "sequence"),
    )
    op.create_index(op.f("ix_scenario_events_org_id"), "scenario_events", ["org_id"], unique=False)
    for table, privileges in GRANTS.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
        )
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")

    op.add_column("optimization_runs", sa.Column("scenario_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "optimization_runs_scenario_fkey",
        "optimization_runs",
        "planning_scenarios",
        ["org_id", "scenario_id"],
        ["org_id", "id"],
    )
    op.drop_constraint("run_kind", "optimization_runs", type_="check")
    op.create_check_constraint(
        "run_kind", "optimization_runs", "kind IN ('generate', 'optimize', 'repair', 'scenario')"
    )
    op.create_check_constraint(
        "run_scenario", "optimization_runs", "(kind = 'scenario') = (scenario_id IS NOT NULL)"
    )
    op.create_index(
        "ux_optimization_runs_active_scenario",
        "optimization_runs",
        ["org_id", "scenario_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'scenario' AND job_state IN ('queued', 'running')"),
    )
    op.drop_constraint("version_source", "schedule_versions", type_="check")
    op.create_check_constraint(
        "version_source", "schedule_versions", f"source IN ({OLD_SOURCES}, 'scenario')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM optimization_runs WHERE kind = 'scenario'")
    op.drop_constraint("version_source", "schedule_versions", type_="check")
    op.create_check_constraint("version_source", "schedule_versions", f"source IN ({OLD_SOURCES})")
    op.drop_index("ux_optimization_runs_active_scenario", table_name="optimization_runs")
    op.drop_constraint("run_scenario", "optimization_runs", type_="check")
    op.drop_constraint("run_kind", "optimization_runs", type_="check")
    op.create_check_constraint("run_kind", "optimization_runs", "kind IN ('generate', 'optimize', 'repair')")
    op.drop_constraint("optimization_runs_scenario_fkey", "optimization_runs", type_="foreignkey")
    op.drop_column("optimization_runs", "scenario_id")
    op.drop_index(op.f("ix_scenario_events_org_id"), table_name="scenario_events")
    op.drop_table("scenario_events")
    op.drop_index("ix_planning_scenarios_schedule", table_name="planning_scenarios")
    op.drop_index(op.f("ix_planning_scenarios_org_id"), table_name="planning_scenarios")
    op.drop_table("planning_scenarios")
