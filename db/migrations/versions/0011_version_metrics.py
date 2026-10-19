"""Stored version metrics (architecture v3 section 22).

Metrics are a column, not a read model: the validator's coverage, cost and overtime figures are stored
when a draft is created, selected, restored or edited, and recomputed against current facts at
publication. The immutability trigger freezes them with the rest of the row once the version leaves
draft. Versions from before this revision keep null.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedule_versions", sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("schedule_versions", "metrics")
