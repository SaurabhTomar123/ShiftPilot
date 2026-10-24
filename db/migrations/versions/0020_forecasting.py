"""Demand forecasting and staffing proposals (architecture v4 sections 21, 22, 37; task A4.8).

forecast_runs is a durable job table of its own (forecasting fails and scales differently from solving)
with the same lease and attempt fencing. demand_forecasts holds a run's predicted orders per interval.
staffing_requirement_proposals holds what the labour model would set; a manager accepts or rejects it,
and only acceptance writes staffing_requirements (source 'forecast'). A forecast never overwrites
requirements by itself.

The worker role may claim and finish forecast runs and insert their output; it reads nothing else (the
run carries its own input).

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "shiftpilot_app"
WORKER_ROLE = "shiftpilot_worker"
APP_GRANTS = {
    "forecast_runs": "SELECT, INSERT",
    "demand_forecasts": "SELECT",
    "staffing_requirement_proposals": "SELECT, UPDATE",
}
WORKER_GRANTS = {
    "forecast_runs": "SELECT, UPDATE",
    "demand_forecasts": "INSERT",
    "staffing_requirement_proposals": "INSERT",
}
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column("job_state", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("lease_owner", sa.String(length=80), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=80), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("input_hash", sa.String(length=80), nullable=False),
        sa.Column("input", JSONB, nullable=False),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("quality", sa.String(length=20), nullable=True),
        sa.Column("error", JSONB, nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "job_state IN ('queued', 'running', 'succeeded', 'failed')", name="forecast_job_state"
        ),
        sa.CheckConstraint("quality IS NULL OR quality IN ('passed', 'failed')", name="forecast_quality"),
        sa.CheckConstraint("attempts >= 0", name="forecast_attempts"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "outlet_id"], ["outlets.org_id", "outlets.id"]),
        sa.ForeignKeyConstraint(["org_id", "requested_by_user_id"], ["users.org_id", "users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
        sa.UniqueConstraint("org_id", "idempotency_key"),
    )
    op.create_index(op.f("ix_forecast_runs_org_id"), "forecast_runs", ["org_id"], unique=False)
    op.create_index(
        "ix_forecast_runs_claim",
        "forecast_runs",
        ["queued_at"],
        postgresql_where=sa.text("job_state = 'queued'"),
    )
    op.create_index(
        "ux_forecast_runs_active",
        "forecast_runs",
        ["org_id", "outlet_id", "week_start"],
        unique=True,
        postgresql_where=sa.text("job_state IN ('queued', 'running')"),
    )
    op.create_table(
        "demand_forecasts",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted", sa.Integer(), nullable=False),
        sa.Column("lower", sa.Integer(), nullable=False),
        sa.Column("upper", sa.Integer(), nullable=False),
        sa.Column("samples", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "lower <= predicted AND predicted <= upper AND lower >= 0", name="forecast_interval"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["org_id", "run_id"], ["forecast_runs.org_id", "forecast_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", "interval_start"),
    )
    op.create_index(op.f("ix_demand_forecasts_org_id"), "demand_forecasts", ["org_id"], unique=False)
    op.create_table(
        "staffing_requirement_proposals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("forecast_run_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("base_demand_revision", sa.Integer(), nullable=False),
        sa.Column("rows", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'stale')", name="staffing_proposal_status"
        ),
        sa.CheckConstraint("(status = 'pending') = (decided_at IS NULL)", name="staffing_proposal_decided"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["org_id", "outlet_id"], ["outlets.org_id", "outlets.id"]),
        sa.ForeignKeyConstraint(["org_id", "forecast_run_id"], ["forecast_runs.org_id", "forecast_runs.id"]),
        sa.ForeignKeyConstraint(["org_id", "decided_by_user_id"], ["users.org_id", "users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "id"),
        sa.UniqueConstraint("forecast_run_id"),
    )
    op.create_index(
        op.f("ix_staffing_requirement_proposals_org_id"),
        "staffing_requirement_proposals",
        ["org_id"],
        unique=False,
    )
    for table, privileges in APP_GRANTS.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)"
        )
        op.execute(f"GRANT {privileges} ON {table} TO {APP_ROLE}")
    op.execute(
        f"""DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{WORKER_ROLE}') THEN
                {" ".join(f"GRANT {p} ON {t} TO {WORKER_ROLE};" for t, p in WORKER_GRANTS.items())}
              END IF;
            END $$"""
    )


def downgrade() -> None:
    op.execute(
        f"""DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{WORKER_ROLE}') THEN
                {" ".join(f"REVOKE ALL ON {t} FROM {WORKER_ROLE};" for t in WORKER_GRANTS)}
              END IF;
            END $$"""
    )
    op.drop_index(
        op.f("ix_staffing_requirement_proposals_org_id"), table_name="staffing_requirement_proposals"
    )
    op.drop_table("staffing_requirement_proposals")
    op.drop_index(op.f("ix_demand_forecasts_org_id"), table_name="demand_forecasts")
    op.drop_table("demand_forecasts")
    op.drop_index("ux_forecast_runs_active", table_name="forecast_runs")
    op.drop_index("ix_forecast_runs_claim", table_name="forecast_runs")
    op.drop_index(op.f("ix_forecast_runs_org_id"), table_name="forecast_runs")
    op.drop_table("forecast_runs")
