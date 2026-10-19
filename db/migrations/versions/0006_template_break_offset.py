"""Break position on shift templates (decision 3: templates carry length and break rules).

Breaks reduce productive coverage, so where a template's break falls matters to the solver and the
validator. Null keeps the old behaviour of an unspecified position (placed at the midpoint).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("shift_templates", sa.Column("break_offset_minutes", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "template_break_offset",
        "shift_templates",
        "break_offset_minutes IS NULL OR (break_offset_minutes >= 0 "
        "AND break_offset_minutes + break_minutes <= duration_minutes)",
    )


def downgrade() -> None:
    op.drop_constraint("template_break_offset", "shift_templates", type_="check")
    op.drop_column("shift_templates", "break_offset_minutes")
