"""v1 baseline: the schema `python -m db.init` produced before migrations existed.

Tables, indexes, the vector extension, the RLS-bound app role, grants and tenant policies,
frozen as they were at baseline 392fc5a. Never edit this revision; an existing database that
matches it is adopted with `python -m db.migrate adopt`.

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from core.config import settings

APP_ROLE = "shiftpilot_app"
V1_TENANT_TABLES = [
    "audit_log",
    "ot_rules",
    "policy_docs",
    "outlets",
    "policy_chunks",
    "checklists",
    "employees",
    "pay_periods",
    "tips",
    "checklist_items",
    "payslips",
    "rate_history",
    "shifts",
    "tip_allocations",
    "users",
    "attendance",
    "conversations",
    "deductions",
    "pending_actions",
    "messages",
]

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("plan", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("tool", sa.String(length=60), nullable=False),
        sa.Column("args_redacted", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_org_id"), "audit_log", ["org_id"], unique=False)
    op.create_table(
        "ot_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("daily_threshold_hrs", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("weekly_threshold_hrs", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("multiplier", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ot_rules_org_id"), "ot_rules", ["org_id"], unique=False)
    op.create_table(
        "policy_docs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_policy_docs_org_id"), "policy_docs", ["org_id"], unique=False)
    op.create_table(
        "outlets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("ot_rule_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["ot_rule_id"],
            ["ot_rules.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_outlets_org_id"), "outlets", ["org_id"], unique=False)
    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("doc_id", sa.UUID(), nullable=False),
        sa.Column("section", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True),
        sa.ForeignKeyConstraint(
            ["doc_id"],
            ["policy_docs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_policy_chunks_doc_id"), "policy_chunks", ["doc_id"], unique=False)
    op.create_index(op.f("ix_policy_chunks_org_id"), "policy_chunks", ["org_id"], unique=False)
    op.create_table(
        "checklists",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checklists_org_id"), "checklists", ["org_id"], unique=False)
    op.create_index(op.f("ix_checklists_outlet_id"), "checklists", ["outlet_id"], unique=False)
    op.create_table(
        "employees",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("job_role", sa.String(length=40), nullable=False),
        sa.Column("pay_type", sa.String(length=20), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("monthly_base", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_employees_org_id"), "employees", ["org_id"], unique=False)
    op.create_index(op.f("ix_employees_outlet_id"), "employees", ["outlet_id"], unique=False)
    op.create_table(
        "pay_periods",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pay_periods_org_id"), "pay_periods", ["org_id"], unique=False)
    op.create_index(op.f("ix_pay_periods_outlet_id"), "pay_periods", ["outlet_id"], unique=False)
    op.create_table(
        "tips",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tips_org_id"), "tips", ["org_id"], unique=False)
    op.create_index(op.f("ix_tips_outlet_id"), "tips", ["outlet_id"], unique=False)
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("checklist_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("done_by", sa.UUID(), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["checklist_id"],
            ["checklists.id"],
        ),
        sa.ForeignKeyConstraint(
            ["done_by"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_checklist_items_checklist_id"), "checklist_items", ["checklist_id"], unique=False
    )
    op.create_index(op.f("ix_checklist_items_org_id"), "checklist_items", ["org_id"], unique=False)
    op.create_table(
        "payslips",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("pay_period_id", sa.UUID(), nullable=False),
        sa.Column("shifts_worked", sa.Integer(), nullable=False),
        sa.Column("regular_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("ot_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("base_pay", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("ot_pay", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tips_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("deductions_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("net_pay", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["pay_period_id"],
            ["pay_periods.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "pay_period_id"),
    )
    op.create_index(op.f("ix_payslips_employee_id"), "payslips", ["employee_id"], unique=False)
    op.create_index(op.f("ix_payslips_org_id"), "payslips", ["org_id"], unique=False)
    op.create_index(op.f("ix_payslips_pay_period_id"), "payslips", ["pay_period_id"], unique=False)
    op.create_table(
        "rate_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rate_history_employee_id"), "rate_history", ["employee_id"], unique=False)
    op.create_index(op.f("ix_rate_history_org_id"), "rate_history", ["org_id"], unique=False)
    op.create_table(
        "shifts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("job_role", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shifts_day"), "shifts", ["day"], unique=False)
    op.create_index(op.f("ix_shifts_employee_id"), "shifts", ["employee_id"], unique=False)
    op.create_index(op.f("ix_shifts_org_id"), "shifts", ["org_id"], unique=False)
    op.create_index(op.f("ix_shifts_outlet_id"), "shifts", ["outlet_id"], unique=False)
    op.create_table(
        "tip_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("tip_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tip_id"],
            ["tips.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tip_allocations_employee_id"), "tip_allocations", ["employee_id"], unique=False)
    op.create_index(op.f("ix_tip_allocations_org_id"), "tip_allocations", ["org_id"], unique=False)
    op.create_index(op.f("ix_tip_allocations_tip_id"), "tip_allocations", ["tip_id"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=True),
        sa.Column("employee_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )
    op.create_index(op.f("ix_users_org_id"), "users", ["org_id"], unique=False)
    op.create_table(
        "attendance",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("shift_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("clock_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["shifts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shift_id"),
    )
    op.create_index(op.f("ix_attendance_employee_id"), "attendance", ["employee_id"], unique=False)
    op.create_index(op.f("ix_attendance_org_id"), "attendance", ["org_id"], unique=False)
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_org_id"), "conversations", ["org_id"], unique=False)
    op.create_table(
        "deductions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("pay_period_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["pay_period_id"],
            ["pay_periods.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deductions_employee_id"), "deductions", ["employee_id"], unique=False)
    op.create_index(op.f("ix_deductions_org_id"), "deductions", ["org_id"], unique=False)
    op.create_index(op.f("ix_deductions_pay_period_id"), "deductions", ["pay_period_id"], unique=False)
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("outlet_id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("tool", sa.String(length=60), nullable=False),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("required_approver_role", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["outlet_id"],
            ["outlets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_pending_actions_org_id"), "pending_actions", ["org_id"], unique=False)
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("cost_inr", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_messages_org_id"), "messages", ["org_id"], unique=False)
    for stmt in rls_statements(settings().app_db_password):
        op.execute(stmt)


def rls_statements(password: str) -> list[str]:
    """Frozen copy of db.init.rls_statements at baseline."""
    stmts = [
        f"""DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS;
              END IF;
            END $$""",
        f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
        f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}",
        f"REVOKE UPDATE ON audit_log FROM {APP_ROLE}",
        "ALTER TABLE organizations ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation ON organizations",
        "CREATE POLICY tenant_isolation ON organizations "
        "USING (id = nullif(current_setting('app.org_id', true), '')::uuid)",
    ]
    for table in V1_TENANT_TABLES:
        stmts += [
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
            f"DROP POLICY IF EXISTS tenant_isolation ON {table}",
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)",
        ]
    return stmts


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_org_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_pending_actions_org_id"), table_name="pending_actions")
    op.drop_table("pending_actions")
    op.drop_index(op.f("ix_deductions_pay_period_id"), table_name="deductions")
    op.drop_index(op.f("ix_deductions_org_id"), table_name="deductions")
    op.drop_index(op.f("ix_deductions_employee_id"), table_name="deductions")
    op.drop_table("deductions")
    op.drop_index(op.f("ix_conversations_org_id"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_attendance_org_id"), table_name="attendance")
    op.drop_index(op.f("ix_attendance_employee_id"), table_name="attendance")
    op.drop_table("attendance")
    op.drop_index(op.f("ix_users_org_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_tip_allocations_tip_id"), table_name="tip_allocations")
    op.drop_index(op.f("ix_tip_allocations_org_id"), table_name="tip_allocations")
    op.drop_index(op.f("ix_tip_allocations_employee_id"), table_name="tip_allocations")
    op.drop_table("tip_allocations")
    op.drop_index(op.f("ix_shifts_outlet_id"), table_name="shifts")
    op.drop_index(op.f("ix_shifts_org_id"), table_name="shifts")
    op.drop_index(op.f("ix_shifts_employee_id"), table_name="shifts")
    op.drop_index(op.f("ix_shifts_day"), table_name="shifts")
    op.drop_table("shifts")
    op.drop_index(op.f("ix_rate_history_org_id"), table_name="rate_history")
    op.drop_index(op.f("ix_rate_history_employee_id"), table_name="rate_history")
    op.drop_table("rate_history")
    op.drop_index(op.f("ix_payslips_pay_period_id"), table_name="payslips")
    op.drop_index(op.f("ix_payslips_org_id"), table_name="payslips")
    op.drop_index(op.f("ix_payslips_employee_id"), table_name="payslips")
    op.drop_table("payslips")
    op.drop_index(op.f("ix_checklist_items_org_id"), table_name="checklist_items")
    op.drop_index(op.f("ix_checklist_items_checklist_id"), table_name="checklist_items")
    op.drop_table("checklist_items")
    op.drop_index(op.f("ix_tips_outlet_id"), table_name="tips")
    op.drop_index(op.f("ix_tips_org_id"), table_name="tips")
    op.drop_table("tips")
    op.drop_index(op.f("ix_pay_periods_outlet_id"), table_name="pay_periods")
    op.drop_index(op.f("ix_pay_periods_org_id"), table_name="pay_periods")
    op.drop_table("pay_periods")
    op.drop_index(op.f("ix_employees_outlet_id"), table_name="employees")
    op.drop_index(op.f("ix_employees_org_id"), table_name="employees")
    op.drop_table("employees")
    op.drop_index(op.f("ix_checklists_outlet_id"), table_name="checklists")
    op.drop_index(op.f("ix_checklists_org_id"), table_name="checklists")
    op.drop_table("checklists")
    op.drop_index(op.f("ix_policy_chunks_org_id"), table_name="policy_chunks")
    op.drop_index(op.f("ix_policy_chunks_doc_id"), table_name="policy_chunks")
    op.drop_table("policy_chunks")
    op.drop_index(op.f("ix_outlets_org_id"), table_name="outlets")
    op.drop_table("outlets")
    op.drop_index(op.f("ix_policy_docs_org_id"), table_name="policy_docs")
    op.drop_table("policy_docs")
    op.drop_index(op.f("ix_ot_rules_org_id"), table_name="ot_rules")
    op.drop_table("ot_rules")
    op.drop_index(op.f("ix_audit_log_org_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("organizations")
