"""Staffing templates and the outlet-week demand revision (architecture v3 section 18).

staffing_templates is the default demand for a normal week: weekday x block x skill -> minimum and
preferred staff. StaffingRequirementService.expand(outlet, week) turns it (and optional demand bands)
into date-specific 30-minute staffing_requirements with source template or band. Re-expanding replaces
template and band rows but never manual overrides.

Replacing an outlet's template set deactivates the old rows rather than deleting them, so the set's
revision stays monotonic. demand_weeks holds the outlet-week demand_revision, which every change to
that week's requirements bumps; previously it was derived from the rows and could go back to 1 when a
week's rows were rebuilt.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
GRANTS = {"staffing_templates": "SELECT, INSERT, UPDATE", "demand_weeks": "SELECT, INSERT, UPDATE"}


def upgrade() -> None:
    op.create_table(
        "staffing_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_minute", sa.SmallInteger(), nullable=False),
        sa.Column("end_minute", sa.SmallInteger(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("minimum_required", sa.SmallInteger(), nullable=False),
        sa.Column("preferred_required", sa.SmallInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="staffing_template_weekday"),
        sa.CheckConstraint(
            "start_minute >= 0 AND end_minute <= 1440 AND end_minute > start_minute "
            "AND start_minute % 30 = 0 AND end_minute % 30 = 0",
            name="staffing_template_block",
        ),
        sa.CheckConstraint(
            "minimum_required >= 0 AND preferred_required >= minimum_required", name="staffing_template_staff"
        ),
        sa.CheckConstraint("revision >= 1", name="staffing_template_revision"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "outlet_id"], ["outlets.org_id", "outlets.id"]),
        sa.ForeignKeyConstraint(["org_id", "skill_id"], ["skills.org_id", "skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_staffing_templates_org_id"), "staffing_templates", ["org_id"], unique=False)
    op.create_index(
        "ix_staffing_templates_active",
        "staffing_templates",
        ["outlet_id", "weekday"],
        unique=False,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "demand_weeks",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("demand_revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("demand_revision >= 1", name="demand_week_revision"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "outlet_id"], ["outlets.org_id", "outlets.id"]),
        sa.PrimaryKeyConstraint("outlet_id", "week_start"),
    )
    op.create_index(op.f("ix_demand_weeks_org_id"), "demand_weeks", ["org_id"], unique=False)
    op.drop_constraint("requirement_source", "staffing_requirements", type_="check")
    op.create_check_constraint(
        "requirement_source",
        "staffing_requirements",
        "source IN ('template', 'band', 'manual', 'scenario', 'forecast')",
    )
    # Carry today's derived revisions over, per outlet-local Monday.
    op.execute(
        """
        INSERT INTO demand_weeks (org_id, outlet_id, week_start, demand_revision)
        SELECT r.org_id, r.outlet_id,
               date_trunc('week', r.interval_start AT TIME ZONE o.timezone)::date,
               max(r.demand_revision)
          FROM staffing_requirements r JOIN outlets o ON o.id = r.outlet_id
         GROUP BY 1, 2, 3
        """
    )
    for table, privileges in GRANTS.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
        )
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DELETE FROM staffing_requirements WHERE source IN ('template', 'forecast')")
    op.drop_constraint("requirement_source", "staffing_requirements", type_="check")
    op.create_check_constraint(
        "requirement_source", "staffing_requirements", "source IN ('band', 'manual', 'scenario')"
    )
    op.drop_index(op.f("ix_demand_weeks_org_id"), table_name="demand_weeks")
    op.drop_table("demand_weeks")
    op.drop_index("ix_staffing_templates_active", table_name="staffing_templates")
    op.drop_index(op.f("ix_staffing_templates_org_id"), table_name="staffing_templates")
    op.drop_table("staffing_templates")
