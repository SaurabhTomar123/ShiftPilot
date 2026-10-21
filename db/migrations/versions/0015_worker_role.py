"""Least-privilege worker role (B6.3).

The optimization worker claims runs across tenants, so it bypasses row-level security; everything else it
may touch is exactly what it does: claim, lease, fence and finish runs, read the base version's shifts,
insert candidates and the run.finished outbox event. It cannot read employees, rates or absences (it
solves from the run's stored snapshot), and it cannot delete anything.

The retention job keeps the admin connection: it is a maintenance job that deletes across many tables.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

from core.config import settings

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKER_ROLE = "shiftpilot_worker"
GRANTS = {
    "optimization_runs": "SELECT, UPDATE",
    "version_shifts": "SELECT",
    "optimization_candidates": "SELECT, INSERT",
    "outbox_events": "INSERT",
}


def upgrade() -> None:
    password = settings().worker_db_password.replace("'", "''")
    op.execute(
        f"""DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{WORKER_ROLE}') THEN
                CREATE ROLE {WORKER_ROLE} LOGIN PASSWORD '{password}' NOSUPERUSER BYPASSRLS;
              END IF;
            END $$"""
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {WORKER_ROLE}")
    for table, privileges in GRANTS.items():
        op.execute(f"GRANT {privileges} ON {table} TO {WORKER_ROLE}")


def downgrade() -> None:
    for table, privileges in GRANTS.items():
        op.execute(f"REVOKE {privileges} ON {table} FROM {WORKER_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {WORKER_ROLE}")
