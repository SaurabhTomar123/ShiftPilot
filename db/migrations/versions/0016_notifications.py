"""In-app notifications and the outbox relay role (architecture v3 section 40, B6.3).

notification_deliveries becomes the in-app inbox: one row per event, recipient and channel, carrying its
own topic, title and payload (published outbox rows are deleted after 7 days) and a read_at the
recipient sets. The relay runs as shiftpilot_relay: it reads pending outbox events and just enough to
find recipients, marks events published and records deliveries. Its only employee access is the
id -> outlet mapping.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from core.config import settings

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
RELAY_ROLE = "shiftpilot_relay"
RELAY_GRANTS = {
    "outbox_events": "SELECT, UPDATE",
    "notification_deliveries": "SELECT, INSERT",
    "users": "SELECT",
    "schedules": "SELECT",
    "schedule_versions": "SELECT",
    "version_shifts": "SELECT",
    "optimization_runs": "SELECT",
    "absences": "SELECT",
    "schedule_proposals": "SELECT",
    "employees": "SELECT (id, outlet_id)",
}


def upgrade() -> None:
    op.add_column(
        "notification_deliveries", sa.Column("topic", sa.String(length=60), server_default="", nullable=False)
    )
    op.add_column("notification_deliveries", sa.Column("title", sa.Text(), server_default="", nullable=False))
    op.add_column(
        "notification_deliveries",
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("notification_deliveries", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_notification_deliveries_inbox",
        "notification_deliveries",
        ["recipient_user_id", "delivered_at"],
        unique=False,
    )
    op.execute(f"GRANT UPDATE (read_at) ON notification_deliveries TO {APP_ROLE}")

    password = settings().relay_db_password.replace("'", "''")
    op.execute(
        f"""DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{RELAY_ROLE}') THEN
                CREATE ROLE {RELAY_ROLE} LOGIN PASSWORD '{password}' NOSUPERUSER BYPASSRLS;
              END IF;
            END $$"""
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {RELAY_ROLE}")
    for table, privileges in RELAY_GRANTS.items():
        if "(" in privileges:
            verb, columns = privileges.split(" ", 1)
            op.execute(f"GRANT {verb} {columns} ON {table} TO {RELAY_ROLE}")
        else:
            op.execute(f"GRANT {privileges} ON {table} TO {RELAY_ROLE}")


def downgrade() -> None:
    for table, privileges in RELAY_GRANTS.items():
        verb = privileges.split(" ", 1)[0] if "(" in privileges else privileges
        op.execute(f"REVOKE {verb} ON {table} FROM {RELAY_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {RELAY_ROLE}")
    op.drop_index("ix_notification_deliveries_inbox", table_name="notification_deliveries")
    for column in ("read_at", "payload", "title", "topic"):
        op.drop_column("notification_deliveries", column)
