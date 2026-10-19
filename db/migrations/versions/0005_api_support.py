"""API support for B1.2: stored idempotent results and the availability revision.

- idempotency_keys: one row per (org, key) holding the first response, so a replayed request
  returns it and a different body under the same key is rejected. Tenant-scoped under RLS.
- employees.availability_revision: optimistic concurrency for PUT availability (base_revision).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=80), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("org_id", "key"),
    )
    op.add_column(
        "employees", sa.Column("availability_revision", sa.Integer(), server_default="1", nullable=False)
    )
    op.execute("ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON idempotency_keys "
        "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
        "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
    )
    op.execute(f"GRANT SELECT, INSERT ON idempotency_keys TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_column("employees", "availability_revision")
    op.drop_table("idempotency_keys")
