"""Shared DB lookups for tools. Every function takes a tenant-scoped session, so RLS already
limits rows to the caller's org; role/outlet checks happen in the tools."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.clock import IST
from core.payroll import DeductionLine, OtRule, Payslip, WorkDay, compute_payslip, worked_hours
from db.models import (
    Attendance,
    Deduction,
    Employee,
    OtRuleRow,
    Outlet,
    PayPeriod,
    RateHistory,
    Shift,
    Tip,
    TipAllocation,
)


class NotFound(Exception):
    pass


def as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except ValueError as exc:
        raise NotFound(f"Invalid id: {value}") from exc


def get_employee(s: Session, employee_id: str) -> Employee:
    emp = s.get(Employee, as_uuid(employee_id))
    if emp is None:
        raise NotFound("Employee not found.")
    return emp


def get_outlet(s: Session, outlet_id: str) -> Outlet:
    outlet = s.get(Outlet, as_uuid(outlet_id))
    if outlet is None:
        raise NotFound("Outlet not found.")
    return outlet


def org_outlet_ids(s: Session) -> list[str]:
    return [str(i) for i in s.scalars(select(Outlet.id).order_by(Outlet.name))]


def period_for(s: Session, outlet_id: str, on: date | None) -> PayPeriod:
    """Pay period containing `on`, or the latest one for the outlet."""
    q = select(PayPeriod).where(PayPeriod.outlet_id == as_uuid(outlet_id))
    q = (q.where(PayPeriod.start_date <= on, PayPeriod.end_date >= on) if on
         else q.order_by(PayPeriod.start_date.desc()))
    period = s.scalars(q.limit(1)).first()
    if period is None:
        raise NotFound(f"No pay period for {on or 'latest'}.")
    return period


def previous_period(s: Session, period: PayPeriod) -> PayPeriod | None:
    return s.scalars(
        select(PayPeriod)
        .where(PayPeriod.outlet_id == period.outlet_id,
               PayPeriod.end_date < period.start_date)
        .order_by(PayPeriod.start_date.desc())
        .limit(1)
    ).first()


def ot_rule_for(s: Session, outlet: Outlet) -> OtRule:
    row = s.get(OtRuleRow, outlet.ot_rule_id)
    if row is None:
        return OtRule()
    return OtRule(row.daily_threshold_hrs, row.weekly_threshold_hrs, row.multiplier)


def compute_period_payslip(s: Session, emp: Employee, period: PayPeriod) -> Payslip:
    """Recompute a payslip from source records (used after approved writes and imports)."""
    rates = s.execute(
        select(RateHistory.effective_from, RateHistory.hourly_rate)
        .where(RateHistory.employee_id == emp.id).order_by(RateHistory.effective_from)
    ).all()

    def rate_on(day: date) -> Decimal:
        applicable = [r for eff, r in rates if eff <= day]
        return applicable[-1] if applicable else emp.hourly_rate

    rows = s.execute(
        select(Attendance, Shift)
        .join(Shift, Shift.id == Attendance.shift_id)
        .where(Attendance.employee_id == emp.id,
               Shift.day >= period.start_date, Shift.day <= period.end_date,
               Shift.status != "cancelled")
    ).all()
    work_days = []
    for att, shift in rows:
        end = datetime.combine(shift.day, shift.end_time, IST)
        if shift.end_time <= shift.start_time:
            end += timedelta(days=1)
        hours, _ = worked_hours(att.clock_in, att.clock_out, end)
        work_days.append(WorkDay(shift.day, hours, rate_on(shift.day)))

    tips = list(s.scalars(
        select(TipAllocation.amount)
        .join(Tip, Tip.id == TipAllocation.tip_id)
        .where(TipAllocation.employee_id == emp.id,
               Tip.day >= period.start_date, Tip.day <= period.end_date)
    ))
    deds = [DeductionLine(d.type, d.amount, d.note) for d in s.scalars(
        select(Deduction).where(Deduction.employee_id == emp.id,
                                Deduction.pay_period_id == period.id))]
    outlet = get_outlet(s, str(emp.outlet_id))
    return compute_payslip(work_days, tips, deds, ot_rule_for(s, outlet))
