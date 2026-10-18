"""Tenant hardening on v1 tables (v2-schema-plan §1, §3.1, §3.5).

- UNIQUE (org_id, id) on outlets, employees and users so v2 tables can use composite tenant FKs.
- outlets.slug and pending_actions.idempotency_key become unique per org instead of globally.
- organizations.timezone, outlets.operating_hours and the employee scheduling fields.
- audit_log gains action/target/before/after and is append-only (no UPDATE, no DELETE).

Constraint names are the ones Postgres would generate, so models and database agree.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"


def upgrade() -> None:
    op.add_column(
        "organizations", sa.Column("timezone", sa.String(64), server_default="Asia/Kolkata", nullable=False)
    )

    op.add_column("outlets", sa.Column("operating_hours", postgresql.JSONB(), nullable=True))
    op.drop_constraint("outlets_slug_key", "outlets", type_="unique")
    op.create_unique_constraint("outlets_org_id_slug_key", "outlets", ["org_id", "slug"])
    op.create_unique_constraint("outlets_org_id_id_key", "outlets", ["org_id", "id"])

    op.add_column(
        "employees", sa.Column("regular_weekly_minutes", sa.Integer(), server_default="2880", nullable=False)
    )
    op.add_column(
        "employees", sa.Column("max_weekly_minutes", sa.Integer(), server_default="2880", nullable=False)
    )
    op.add_column("employees", sa.Column("preferred_weekly_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "employees", sa.Column("tags", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False)
    )
    op.add_column(
        "employees", sa.Column("overtime_allowed", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column(
        "employees", sa.Column("cross_outlet_eligible", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("employees", sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
    op.create_unique_constraint("employees_org_id_id_key", "employees", ["org_id", "id"])
    op.create_check_constraint(
        "employee_weekly_caps", "employees", "max_weekly_minutes >= regular_weekly_minutes"
    )

    op.create_unique_constraint("users_org_id_id_key", "users", ["org_id", "id"])

    op.drop_constraint("pending_actions_idempotency_key_key", "pending_actions", type_="unique")
    op.create_unique_constraint(
        "pending_actions_org_id_idempotency_key_key", "pending_actions", ["org_id", "idempotency_key"]
    )

    op.add_column("audit_log", sa.Column("action", sa.String(60), nullable=True))
    op.add_column("audit_log", sa.Column("target_type", sa.String(40), nullable=True))
    op.add_column("audit_log", sa.Column("target_id", sa.UUID(), nullable=True))
    op.add_column("audit_log", sa.Column("before", postgresql.JSONB(), nullable=True))
    op.add_column("audit_log", sa.Column("after", postgresql.JSONB(), nullable=True))
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM {APP_ROLE}")


def downgrade() -> None:
    op.drop_column("audit_log", "after")
    op.drop_column("audit_log", "before")
    op.drop_column("audit_log", "target_id")
    op.drop_column("audit_log", "target_type")
    op.drop_column("audit_log", "action")

    op.drop_constraint("pending_actions_org_id_idempotency_key_key", "pending_actions", type_="unique")
    op.create_unique_constraint("pending_actions_idempotency_key_key", "pending_actions", ["idempotency_key"])

    op.drop_constraint("users_org_id_id_key", "users", type_="unique")

    op.drop_constraint("employee_weekly_caps", "employees", type_="check")
    op.drop_constraint("employees_org_id_id_key", "employees", type_="unique")
    for column in (
        "revision",
        "cross_outlet_eligible",
        "overtime_allowed",
        "tags",
        "preferred_weekly_minutes",
        "max_weekly_minutes",
        "regular_weekly_minutes",
    ):
        op.drop_column("employees", column)

    op.drop_constraint("outlets_org_id_id_key", "outlets", type_="unique")
    op.drop_constraint("outlets_org_id_slug_key", "outlets", type_="unique")
    op.create_unique_constraint("outlets_slug_key", "outlets", ["slug"])
    op.drop_column("outlets", "operating_hours")

    op.drop_column("organizations", "timezone")
