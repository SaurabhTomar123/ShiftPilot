"""Employee shift requests: open-shift claims, giveaways and swaps (architecture v4 section 28, A4.8).

Every request ends in a manager decision that goes through the normal publication gate: the change is
applied to a new draft copied from the current published version, re-validated against current facts
and published (schedule_versions.source 'request'). Nothing an employee does publishes by itself.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
SOURCES = "'seed', 'manual', 'generate', 'optimize', 'repair', 'restore', 'import', 'scenario'"
STATUSES = "'open', 'pending_manager', 'approved', 'rejected', 'cancelled', 'expired', 'stale', 'invalid'"


def upgrade() -> None:
    op.create_table(
        "shift_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("logical_shift_id", sa.UUID(), nullable=False),
        sa.Column("base_version_id", sa.UUID(), nullable=False),
        sa.Column("requester_employee_id", sa.UUID(), nullable=False),
        sa.Column("target_employee_id", sa.UUID(), nullable=True),
        sa.Column("target_logical_shift_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_version_id", sa.UUID(), nullable=True),
        sa.Column("outcome", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint("type IN ('open_shift_claim', 'giveaway', 'swap')", name="shift_request_type"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="shift_request_status"),
        sa.CheckConstraint(
            "(type = 'swap') = (target_logical_shift_id IS NOT NULL)", name="shift_request_swap_target"
        ),
        sa.CheckConstraint(
            "type <> 'swap' OR target_employee_id IS NOT NULL", name="shift_request_swap_employee"
        ),
        sa.CheckConstraint(
            "(status = 'approved') = (published_version_id IS NOT NULL)", name="shift_request_published"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "schedule_id"], ["schedules.org_id", "schedules.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "base_version_id"], ["schedule_versions.org_id", "schedule_versions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "published_version_id"], ["schedule_versions.org_id", "schedule_versions.id"]
        ),
        sa.ForeignKeyConstraint(["org_id", "requester_employee_id"], ["employees.org_id", "employees.id"]),
        sa.ForeignKeyConstraint(["org_id", "target_employee_id"], ["employees.org_id", "employees.id"]),
        sa.ForeignKeyConstraint(["org_id", "decided_by_user_id"], ["users.org_id", "users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
    )
    op.create_index(op.f("ix_shift_requests_org_id"), "shift_requests", ["org_id"], unique=False)
    op.create_index("ix_shift_requests_schedule", "shift_requests", ["schedule_id", "status"], unique=False)
    op.create_index(
        "ux_shift_requests_active_shift",
        "shift_requests",
        ["org_id", "logical_shift_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'pending_manager')"),
    )
    op.execute("ALTER TABLE shift_requests ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON shift_requests "
        "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
        "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON shift_requests TO {APP_ROLE}")
    op.drop_constraint("version_source", "schedule_versions", type_="check")
    op.create_check_constraint("version_source", "schedule_versions", f"source IN ({SOURCES}, 'request')")


def downgrade() -> None:
    op.execute("DELETE FROM schedule_versions WHERE source = 'request' AND status = 'draft'")
    op.drop_constraint("version_source", "schedule_versions", type_="check")
    op.create_check_constraint("version_source", "schedule_versions", f"source IN ({SOURCES})")
    op.drop_index("ux_shift_requests_active_shift", table_name="shift_requests")
    op.drop_index("ix_shift_requests_schedule", table_name="shift_requests")
    op.drop_index(op.f("ix_shift_requests_org_id"), table_name="shift_requests")
    op.drop_table("shift_requests")
