"""CSV onboarding staging (architecture v3 section 19, task B5.4).

import_jobs holds one uploaded file; import_rows its parsed rows with their errors. Committing creates
every employee in one transaction (status committed); an invalid file writes no business rows. Staged
rows expire after 24 hours (the retention job deletes them and marks the job expired).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
GRANTS = {"import_jobs": "SELECT, INSERT, UPDATE", "import_rows": "SELECT, INSERT, UPDATE"}


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column(
            "file_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('employees')", name="import_kind"),
        sa.CheckConstraint("status IN ('staged', 'invalid', 'committed', 'expired')", name="import_status"),
        sa.CheckConstraint("(status = 'committed') = (committed_at IS NOT NULL)", name="import_committed_at"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "created_by_user_id"], ["users.org_id", "users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
    )
    op.create_index(op.f("ix_import_jobs_org_id"), "import_jobs", ["org_id"], unique=False)
    op.create_table(
        "import_rows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("employee_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "job_id"], ["import_jobs.org_id", "import_jobs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "row_number"),
    )
    op.create_index(op.f("ix_import_rows_org_id"), "import_rows", ["org_id"], unique=False)
    for table, privileges in GRANTS.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
        )
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")


def downgrade() -> None:
    op.drop_index(op.f("ix_import_rows_org_id"), table_name="import_rows")
    op.drop_table("import_rows")
    op.drop_index(op.f("ix_import_jobs_org_id"), table_name="import_jobs")
    op.drop_table("import_jobs")
