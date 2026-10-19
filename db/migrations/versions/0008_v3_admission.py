"""Architecture v3 admission model (sections 24, 27, 28).

Optimization runs are read-only, so several may run on one schedule and an absence repair is never
blocked by batch work. Admission only prevents duplicated work:
- one active generate/optimize run per schedule (partial unique index -> 409 run_in_progress);
- one active repair per absence (partial unique index -> the existing run is returned).
The revision-2 lane column and schedule_run_slots table are removed; workers claim by priority and kind.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"


def upgrade() -> None:
    op.create_unique_constraint("absences_org_id_id_key", "absences", ["org_id", "id"])
    op.add_column("optimization_runs", sa.Column("schedule_id", sa.UUID(), nullable=True))
    op.add_column("optimization_runs", sa.Column("trigger_absence_id", sa.UUID(), nullable=True))
    op.execute(
        "UPDATE optimization_runs SET schedule_id = (config->>'schedule_id')::uuid "
        "WHERE config ? 'schedule_id'"
    )
    op.create_foreign_key(
        "optimization_runs_schedule_fkey",
        "optimization_runs",
        "schedules",
        ["org_id", "schedule_id"],
        ["org_id", "id"],
    )
    op.create_foreign_key(
        "optimization_runs_absence_fkey",
        "optimization_runs",
        "absences",
        ["org_id", "trigger_absence_id"],
        ["org_id", "id"],
    )

    op.drop_index("ix_optimization_runs_claim", table_name="optimization_runs")
    op.drop_constraint("run_lane", "optimization_runs", type_="check")
    op.drop_column("optimization_runs", "lane")
    op.create_index(
        "ix_optimization_runs_claim",
        "optimization_runs",
        ["priority", "queued_at"],
        postgresql_where=sa.text("job_state = 'queued'"),
    )
    op.create_index(
        "ux_optimization_runs_active_batch",
        "optimization_runs",
        ["org_id", "schedule_id"],
        unique=True,
        postgresql_where=sa.text("kind IN ('generate', 'optimize') AND job_state IN ('queued', 'running')"),
    )
    op.create_index(
        "ux_optimization_runs_active_repair",
        "optimization_runs",
        ["org_id", "trigger_absence_id"],
        unique=True,
        postgresql_where=sa.text("job_state IN ('queued', 'running')"),
    )
    op.drop_table("schedule_run_slots")


def downgrade() -> None:
    op.create_table(
        "schedule_run_slots",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id", "run_id"], ["optimization_runs.org_id", "optimization_runs.id"]),
        sa.ForeignKeyConstraint(["org_id", "schedule_id"], ["schedules.org_id", "schedules.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("org_id", "schedule_id"),
    )
    op.create_index("ix_schedule_run_slots_run_id", "schedule_run_slots", ["run_id"])
    op.execute("ALTER TABLE schedule_run_slots ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON schedule_run_slots "
        "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
        "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
    )
    op.execute(f"GRANT SELECT, INSERT, DELETE ON schedule_run_slots TO {APP_ROLE}")
    op.drop_index("ux_optimization_runs_active_repair", table_name="optimization_runs")
    op.drop_index("ux_optimization_runs_active_batch", table_name="optimization_runs")
    op.drop_index("ix_optimization_runs_claim", table_name="optimization_runs")
    op.add_column(
        "optimization_runs", sa.Column("lane", sa.String(20), server_default="batch", nullable=False)
    )
    op.create_check_constraint("run_lane", "optimization_runs", "lane IN ('interactive', 'batch')")
    op.create_index(
        "ix_optimization_runs_claim",
        "optimization_runs",
        ["lane", "priority", "queued_at"],
        postgresql_where=sa.text("job_state = 'queued'"),
    )
    op.drop_constraint("optimization_runs_absence_fkey", "optimization_runs", type_="foreignkey")
    op.drop_constraint("optimization_runs_schedule_fkey", "optimization_runs", type_="foreignkey")
    op.drop_column("optimization_runs", "trigger_absence_id")
    op.drop_column("optimization_runs", "schedule_id")
    op.drop_constraint("absences_org_id_id_key", "absences", type_="unique")
