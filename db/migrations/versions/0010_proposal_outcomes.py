"""Proposals and the four publication outcomes (architecture v3 sections 23 and 31).

A proposal records what the manager agreed to: the draft revisions and the metrics at proposal time.
Approval publishes only if the base versions are still current (else stale), the draft is still valid
against current facts (else invalid) and its metrics have not moved materially, unless the manager
acknowledged the change (else changed).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedule_proposals",
        sa.Column(
            "metrics_at_proposal",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "schedule_proposals",
        sa.Column(
            "draft_revisions",
            postgresql.ARRAY(sa.Integer()),
            server_default=sa.text("'{}'::integer[]"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE schedule_proposals SET draft_revisions = "
        "array_fill(1, ARRAY[cardinality(draft_version_ids)]) WHERE cardinality(draft_version_ids) > 0"
    )
    op.create_check_constraint(
        "proposal_draft_revisions",
        "schedule_proposals",
        "cardinality(draft_revisions) = cardinality(draft_version_ids)",
    )


def downgrade() -> None:
    op.drop_constraint("proposal_draft_revisions", "schedule_proposals", type_="check")
    op.drop_column("schedule_proposals", "draft_revisions")
    op.drop_column("schedule_proposals", "metrics_at_proposal")
