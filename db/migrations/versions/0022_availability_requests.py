"""Availability-change requests (architecture v4 section 29, task A4.8).

An employee proposes a new recurring availability; the manager sees which published shifts it would
break and accepts or rejects it. Only acceptance replaces employee_availability (with the same revision
check as a manager edit).

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "availability_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("windows", JSONB, nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("affected", JSONB, nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')", name="availability_request_status"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "employee_id"], ["employees.org_id", "employees.id"]),
        sa.ForeignKeyConstraint(["org_id", "decided_by_user_id"], ["users.org_id", "users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
    )
    op.create_index(
        op.f("ix_availability_requests_org_id"), "availability_requests", ["org_id"], unique=False
    )
    op.create_index(
        "ux_availability_requests_pending",
        "availability_requests",
        ["org_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.execute("ALTER TABLE availability_requests ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON availability_requests "
        "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
        "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON availability_requests TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_index("ux_availability_requests_pending", table_name="availability_requests")
    op.drop_index(op.f("ix_availability_requests_org_id"), table_name="availability_requests")
    op.drop_table("availability_requests")
