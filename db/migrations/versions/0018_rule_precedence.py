"""Rule precedence by scope (architecture v3 section 21, tasks A3.12 and B5.2).

There is no numeric priority: priority is dropped. A rule has a scope_level (organization, outlet,
tag, employee) and overrides another only by naming it in overrides_rule_id.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scheduling_rules",
        sa.Column("scope_level", sa.String(length=20), server_default="organization", nullable=False),
    )
    op.add_column("scheduling_rules", sa.Column("overrides_rule_id", sa.UUID(), nullable=True))
    op.create_unique_constraint("scheduling_rules_org_id_id_key", "scheduling_rules", ["org_id", "id"])
    op.create_foreign_key(
        "scheduling_rules_overrides_fkey",
        "scheduling_rules",
        "scheduling_rules",
        ["org_id", "overrides_rule_id"],
        ["org_id", "id"],
    )
    op.create_check_constraint(
        "rule_scope_level", "scheduling_rules", "scope_level IN ('organization', 'outlet', 'tag', 'employee')"
    )
    op.drop_column("scheduling_rules", "priority")


def downgrade() -> None:
    op.add_column(
        "scheduling_rules", sa.Column("priority", sa.SmallInteger(), server_default="0", nullable=False)
    )
    op.drop_constraint("rule_scope_level", "scheduling_rules", type_="check")
    op.drop_constraint("scheduling_rules_overrides_fkey", "scheduling_rules", type_="foreignkey")
    op.drop_constraint("scheduling_rules_org_id_id_key", "scheduling_rules", type_="unique")
    op.drop_column("scheduling_rules", "overrides_rule_id")
    op.drop_column("scheduling_rules", "scope_level")
