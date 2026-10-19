"""Draft revision on schedule_versions (contract 2.3: optimistic concurrency for draft edits).

The transitions trigger from 0003 already freezes every column of a published version, so the
revision can only move while the version is a draft.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedule_versions", sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
    op.create_check_constraint("version_revision", "schedule_versions", "revision >= 1")


def downgrade() -> None:
    op.drop_constraint("version_revision", "schedule_versions", type_="check")
    op.drop_column("schedule_versions", "revision")
