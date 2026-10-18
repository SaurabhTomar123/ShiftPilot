"""Durable work (architecture revision 2, roadmap decision 16).

- optimization_runs: lane (interactive|batch), priority and traceparent; partial indexes for the
  worker claim query and lease reclaim replace the single queue index.
- schedule_run_slots: one active run per schedule, enforced by its primary key (admission guard).
- outbox_events and notification_deliveries: transactional outbox and idempotent consumer record.
- Hot-path indexes from architecture §18; narrower indexes they make redundant are dropped.

The outbox relay needs its own cross-tenant role; that role is created with the relay task, not
here. Until then the app role may only insert and read its own tenant's outbox rows.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
GRANTS = {
    "schedule_run_slots": "SELECT, INSERT, DELETE",
    "outbox_events": "SELECT, INSERT",
    "notification_deliveries": "SELECT, INSERT",
}


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("topic", sa.String(length=60), nullable=False),
        sa.Column("aggregate_type", sa.String(length=40), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("traceparent", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "topic IN ('schedule.published', 'proposal.ready', 'proposal.stale', 'run.finished', 'absence.reported', 'rule.changed', 'version.metrics.requested')",
            name="outbox_topic",
        ),
        sa.CheckConstraint("attempts >= 0", name="outbox_attempts"),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
    )
    op.create_index(op.f("ix_outbox_events_org_id"), "outbox_events", ["org_id"], unique=False)
    op.create_index(
        "ix_outbox_events_pending",
        "outbox_events",
        ["next_attempt_at"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("recipient_user_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column(
            "delivered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "recipient_user_id"],
            ["users.org_id", "users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "recipient_user_id", "channel"),
    )
    op.create_index(
        op.f("ix_notification_deliveries_org_id"), "notification_deliveries", ["org_id"], unique=False
    )
    op.create_table(
        "schedule_run_slots",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id", "run_id"],
            ["optimization_runs.org_id", "optimization_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "schedule_id"],
            ["schedules.org_id", "schedules.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("org_id", "schedule_id"),
    )
    op.create_index(op.f("ix_schedule_run_slots_run_id"), "schedule_run_slots", ["run_id"], unique=False)
    op.drop_index(op.f("ix_absences_employee_time"), table_name="absences")
    op.create_index("ix_absences_lookup", "absences", ["org_id", "employee_id", "start_at"], unique=False)
    op.create_index(
        "ix_audit_log_target", "audit_log", ["org_id", "target_type", "target_id", "ts"], unique=False
    )
    op.drop_index(op.f("ix_employee_availability_employee_id"), table_name="employee_availability")
    op.create_index(
        "ix_employee_availability_lookup",
        "employee_availability",
        ["org_id", "employee_id", "weekday"],
        unique=False,
    )
    op.create_index(
        "ix_employees_org_outlet_status", "employees", ["org_id", "outlet_id", "status"], unique=False
    )
    op.create_index("ix_employees_tags", "employees", ["tags"], unique=False, postgresql_using="gin")
    op.add_column(
        "optimization_runs", sa.Column("lane", sa.String(length=20), server_default="batch", nullable=False)
    )
    op.add_column(
        "optimization_runs", sa.Column("priority", sa.SmallInteger(), server_default="100", nullable=False)
    )
    op.add_column("optimization_runs", sa.Column("traceparent", sa.String(length=80), nullable=True))
    op.drop_index(
        op.f("ix_optimization_runs_queue"),
        table_name="optimization_runs",
        postgresql_where="((job_state)::text = ANY ((ARRAY['queued'::character varying, 'running'::character varying])::text[]))",
    )
    op.create_index(
        "ix_optimization_runs_claim",
        "optimization_runs",
        ["lane", "priority", "queued_at"],
        unique=False,
        postgresql_where=sa.text("job_state = 'queued'"),
    )
    op.create_index(
        "ix_optimization_runs_lease",
        "optimization_runs",
        ["lease_until"],
        unique=False,
        postgresql_where=sa.text("job_state = 'running'"),
    )
    op.create_index(
        "ix_staffing_requirements_week",
        "staffing_requirements",
        ["outlet_id", "interval_start"],
        unique=False,
    )
    op.drop_index(op.f("ix_version_shifts_version_id"), table_name="version_shifts")
    op.create_index(
        "ix_version_shifts_roster", "version_shifts", ["version_id", "employee_id", "start_at"], unique=False
    )
    op.create_check_constraint("run_lane", "optimization_runs", "lane IN ('interactive', 'batch')")
    op.execute("UPDATE optimization_runs SET lane = 'interactive' WHERE kind = 'repair'")

    for table, privileges in GRANTS.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
        )
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_constraint("run_lane", "optimization_runs", type_="check")
    op.drop_index("ix_version_shifts_roster", table_name="version_shifts")
    op.create_index(op.f("ix_version_shifts_version_id"), "version_shifts", ["version_id"], unique=False)
    op.drop_index("ix_staffing_requirements_week", table_name="staffing_requirements")
    op.drop_index(
        "ix_optimization_runs_lease",
        table_name="optimization_runs",
        postgresql_where=sa.text("job_state = 'running'"),
    )
    op.drop_index(
        "ix_optimization_runs_claim",
        table_name="optimization_runs",
        postgresql_where=sa.text("job_state = 'queued'"),
    )
    op.create_index(
        op.f("ix_optimization_runs_queue"),
        "optimization_runs",
        ["queued_at"],
        unique=False,
        postgresql_where="((job_state)::text = ANY ((ARRAY['queued'::character varying, 'running'::character varying])::text[]))",
    )
    op.drop_column("optimization_runs", "traceparent")
    op.drop_column("optimization_runs", "priority")
    op.drop_column("optimization_runs", "lane")
    op.drop_index("ix_employees_tags", table_name="employees", postgresql_using="gin")
    op.drop_index("ix_employees_org_outlet_status", table_name="employees")
    op.drop_index("ix_employee_availability_lookup", table_name="employee_availability")
    op.create_index(
        op.f("ix_employee_availability_employee_id"), "employee_availability", ["employee_id"], unique=False
    )
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_index("ix_absences_lookup", table_name="absences")
    op.create_index(op.f("ix_absences_employee_time"), "absences", ["employee_id", "start_at"], unique=False)
    op.drop_index(op.f("ix_schedule_run_slots_run_id"), table_name="schedule_run_slots")
    op.drop_table("schedule_run_slots")
    op.drop_index(op.f("ix_notification_deliveries_org_id"), table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index(
        "ix_outbox_events_pending",
        table_name="outbox_events",
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.drop_index(op.f("ix_outbox_events_org_id"), table_name="outbox_events")
    op.drop_table("outbox_events")
