"""Demo sandboxes (B6.2): one isolated copy of the synthetic org per public demo session.

The registry is admin-only (the app role has no grants on it); the sandbox org itself is an ordinary
tenant with plan 'sandbox', isolated by row-level security like any other.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_sandboxes",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("template_org_id", sa.UUID(), nullable=False),
        sa.Column("salt", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("org_id"),
    )
    op.create_index("ix_demo_sandboxes_expires_at", "demo_sandboxes", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_demo_sandboxes_expires_at", table_name="demo_sandboxes")
    op.drop_table("demo_sandboxes")
