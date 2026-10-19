"""Lightweight candidates (architecture v3 section 23).

A candidate is a diff against its base version (added, changed and removed logical shifts) with metrics,
validation and explanation facts. Nothing is written to schedule_versions until a manager selects one:
POST /v2/optimization-candidates/{id}/select materializes a draft and records materialized_version_id.

Existing candidates were materialized by the worker when they were created, so their draft becomes the
materialized version.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("optimization_candidates", sa.Column("materialized_version_id", sa.UUID(), nullable=True))
    op.execute("UPDATE optimization_candidates SET materialized_version_id = draft_version_id")
    op.drop_constraint(
        "optimization_candidates_org_id_draft_version_id_fkey", "optimization_candidates", type_="foreignkey"
    )
    op.drop_column("optimization_candidates", "draft_version_id")
    op.create_foreign_key(
        "optimization_candidates_org_id_materialized_version_id_fkey",
        "optimization_candidates",
        "schedule_versions",
        ["org_id", "materialized_version_id"],
        ["org_id", "id"],
    )


def downgrade() -> None:
    # Unselected candidates have no version to point at; they cannot survive a downgrade.
    op.execute("DELETE FROM optimization_candidates WHERE materialized_version_id IS NULL")
    op.add_column("optimization_candidates", sa.Column("draft_version_id", sa.UUID(), nullable=True))
    op.execute("UPDATE optimization_candidates SET draft_version_id = materialized_version_id")
    op.alter_column("optimization_candidates", "draft_version_id", nullable=False)
    op.drop_constraint(
        "optimization_candidates_org_id_materialized_version_id_fkey",
        "optimization_candidates",
        type_="foreignkey",
    )
    op.drop_column("optimization_candidates", "materialized_version_id")
    op.create_foreign_key(
        "optimization_candidates_org_id_draft_version_id_fkey",
        "optimization_candidates",
        "schedule_versions",
        ["org_id", "draft_version_id"],
        ["org_id", "id"],
    )
