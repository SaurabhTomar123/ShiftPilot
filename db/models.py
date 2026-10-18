"""SQLAlchemy models. Every table carries org_id so Postgres row-level security can isolate
tenants (see db/rls.sql). IDs are UUIDs; seed data derives them deterministically."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1536
Money = Numeric(12, 2)
Hours = Numeric(6, 2)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB()}


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(40), default="demo")


class OtRuleRow(Base):
    __tablename__ = "ot_rules"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    daily_threshold_hrs: Mapped[Decimal] = mapped_column(Hours, default=Decimal("9"))
    weekly_threshold_hrs: Mapped[Decimal] = mapped_column(Hours, default=Decimal("48"))
    multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("2.0"))


class Outlet(Base):
    __tablename__ = "outlets"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    city: Mapped[str] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    ot_rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ot_rules.id"))


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    job_role: Mapped[str] = mapped_column(String(40))
    pay_type: Mapped[str] = mapped_column(String(20), default="hourly")
    hourly_rate: Mapped[Decimal] = mapped_column(Money)
    monthly_base: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    phone: Mapped[str] = mapped_column(String(20))
    joined_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")


class RateHistory(Base):
    __tablename__ = "rate_history"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    hourly_rate: Mapped[Decimal] = mapped_column(Money)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    outlet_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("outlets.id"), nullable=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    role: Mapped[str] = mapped_column(String(20))  # owner | manager | staff
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    job_role: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(20))  # opening | mid | closing
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    version: Mapped[int] = mapped_column(Integer, default=1)


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    shift_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shifts.id"), unique=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    clock_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    clock_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="app")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Tip(Base):
    __tablename__ = "tips"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    total_amount: Mapped[Decimal] = mapped_column(Money)
    method: Mapped[str] = mapped_column(String(20))


class TipAllocation(Base):
    __tablename__ = "tip_allocations"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    tip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tips.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Money)


class PayPeriod(Base):
    __tablename__ = "pay_periods"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")


class Deduction(Base):
    __tablename__ = "deductions"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    pay_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pay_periods.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Money)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class PayslipRow(Base):
    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("employee_id", "pay_period_id"),)
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    pay_period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pay_periods.id"), index=True)
    shifts_worked: Mapped[int] = mapped_column(Integer)
    regular_hours: Mapped[Decimal] = mapped_column(Hours)
    ot_hours: Mapped[Decimal] = mapped_column(Hours)
    base_pay: Mapped[Decimal] = mapped_column(Money)
    ot_pay: Mapped[Decimal] = mapped_column(Money)
    tips_total: Mapped[Decimal] = mapped_column(Money)
    deductions_total: Mapped[Decimal] = mapped_column(Money)
    net_pay: Mapped[Decimal] = mapped_column(Money)
    detail: Mapped[dict[str, Any]] = mapped_column()  # full core.payroll.Payslip.to_json()
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Checklist(Base):
    __tablename__ = "checklists"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(20))  # opening | closing


class ChecklistItem(Base):
    __tablename__ = "checklist_items"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    checklist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checklists.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    done_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PolicyDoc(Base):
    __tablename__ = "policy_docs"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(200))


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policy_docs.id"), index=True)
    section: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class PendingAction(Base):
    __tablename__ = "pending_actions"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    tool: Mapped[str] = mapped_column(String(60))
    args: Mapped[dict[str, Any]] = mapped_column()
    summary_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    required_approver_role: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(20))
    tool: Mapped[str] = mapped_column(String(60))
    args_redacted: Mapped[dict[str, Any]] = mapped_column()
    outcome: Mapped[str] = mapped_column(String(20))  # ok | denied | error
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = pk()
    org_id: Mapped[uuid.UUID] = org_fk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_inr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


TENANT_TABLES = [t.name for t in Base.metadata.sorted_tables if "org_id" in t.columns]
