"""Read tools. Each returns {"data", "warnings", "source_ids"}; all numbers come from the DB or
core.payroll, so the agent can quote them without doing maths."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from core import anomalies as an
from core.auth import Caller, PermissionDenied, Role, assert_can_view_employee, scope_outlets
from core.clock import IST
from core.jsonable import jsonable
from core.money import fmt_inr
from core.payroll import diff_payslips, payslip_from_json, worked_hours
from db.models import (
    Attendance,
    Checklist,
    ChecklistItem,
    Deduction,
    Employee,
    PayPeriod,
    PayslipRow,
    PolicyChunk,
    PolicyDoc,
    RateHistory,
    Shift,
    Tip,
    TipAllocation,
)
from mcp_server.queries import (
    as_uuid,
    get_employee,
    get_outlet,
    org_outlet_ids,
    period_for,
    previous_period,
)

MAX_RANGE_DAYS = 31
LATE_GRACE = timedelta(minutes=10)
EARLY_LEAVE = timedelta(minutes=15)


def envelope(data: Any, warnings: list[str] | None = None,
             source_ids: list[str] | None = None) -> dict[str, Any]:
    return {"data": jsonable(data), "warnings": warnings or [], "source_ids": source_ids or []}


def _check_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise ValueError("date_to is before date_from.")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise ValueError(f"Date range is limited to {MAX_RANGE_DAYS} days.")


def _staff_self_only(caller: Caller, employee_id: str | None) -> str | None:
    if caller.role is Role.STAFF:
        if employee_id and employee_id != caller.employee_id:
            raise PermissionDenied("Staff can only see their own records.")
        return caller.employee_id
    return employee_id


# 1 ---------------------------------------------------------------------------------------------
def find_employee(s: Session, caller: Caller, query: str,
                  outlet_id: str | None = None) -> dict[str, Any]:
    """Resolve a name to employees. Exact name/alias match scores 1.0; more than one strong match
    means the agent must ask which person was meant."""
    outlets = scope_outlets(caller, outlet_id, org_outlet_ids(s))
    q = select(Employee).where(Employee.outlet_id.in_([as_uuid(o) for o in outlets]))
    if caller.role is Role.STAFF:
        q = q.where(Employee.id == as_uuid(caller.employee_id or ""))
    needle = query.strip().lower()
    scored = []
    for emp in s.scalars(q):
        names = [emp.name, *emp.aliases]
        exact = any(needle == n.lower() for n in names)
        score = 1.0 if exact else max(fuzz.WRatio(needle, n.lower()) for n in names) / 100 * 0.95
        if score >= 0.5:
            scored.append((score, emp))
    scored.sort(key=lambda x: (-x[0], x[1].name))
    candidates: list[dict[str, Any]] = [{"employee_id": e.id, "name": e.name, "job_role": e.job_role,
                   "outlet_id": e.outlet_id, "score": round(sc, 2)} for sc, e in scored[:5]]
    exact_matches = [c for c in candidates if c["score"] == 1.0]
    strong = [c for c in candidates if c["score"] >= 0.7]
    if len(exact_matches) == 1 and exact_matches[0]["name"].lower() == needle:
        needs = False
    elif exact_matches:
        needs = len(exact_matches) > 1
    else:
        needs = len(strong) > 1 and strong[0]["score"] - strong[1]["score"] < 0.05
    warnings = ["Multiple people match; ask the user which one."] if needs else []
    if not candidates:
        warnings.append("No matching employee.")
    return envelope({"candidates": candidates, "needs_disambiguation": needs}, warnings,
                    [str(c["employee_id"]) for c in candidates])


# 2 ---------------------------------------------------------------------------------------------
def get_shifts(s: Session, caller: Caller, date_from: date, date_to: date,
               outlet_id: str | None = None, employee_id: str | None = None,
               label: str | None = None, job_role: str | None = None) -> dict[str, Any]:
    _check_range(date_from, date_to)
    employee_id = _staff_self_only(caller, employee_id)
    outlets = scope_outlets(caller, outlet_id, org_outlet_ids(s))
    q = (select(Shift, Employee.name).join(Employee, Employee.id == Shift.employee_id)
         .where(Shift.outlet_id.in_([as_uuid(o) for o in outlets]),
                Shift.day >= date_from, Shift.day <= date_to, Shift.status != "cancelled")
         .order_by(Shift.day, Shift.start_time, Employee.name))
    if employee_id:
        q = q.where(Shift.employee_id == as_uuid(employee_id))
    if label:
        q = q.where(Shift.label == label)
    if job_role:
        q = q.where(Shift.job_role == job_role)
    rows = s.execute(q.limit(500)).all()
    shifts = [{"shift_id": sh.id, "day": sh.day, "weekday": sh.day.strftime("%A"),
               "employee": name, "employee_id": sh.employee_id, "label": sh.label,
               "start": sh.start_time, "end": sh.end_time, "job_role": sh.job_role,
               "outlet_id": sh.outlet_id} for sh, name in rows]
    return envelope({"count": len(shifts), "shifts": shifts},
                    ["Truncated at 500 rows."] if len(rows) == 500 else [],
                    [str(r["shift_id"]) for r in shifts])


# 3 ---------------------------------------------------------------------------------------------
def get_attendance(s: Session, caller: Caller, date_from: date, date_to: date,
                   outlet_id: str | None = None, employee_id: str | None = None,
                   only_issues: bool = False) -> dict[str, Any]:
    _check_range(date_from, date_to)
    employee_id = _staff_self_only(caller, employee_id)
    outlets = scope_outlets(caller, outlet_id, org_outlet_ids(s))
    q = (select(Attendance, Shift, Employee.name)
         .join(Shift, Shift.id == Attendance.shift_id)
         .join(Employee, Employee.id == Attendance.employee_id)
         .where(Shift.outlet_id.in_([as_uuid(o) for o in outlets]),
                Shift.day >= date_from, Shift.day <= date_to)
         .order_by(Shift.day, Employee.name))
    if employee_id:
        q = q.where(Attendance.employee_id == as_uuid(employee_id))
    records = []
    for att, sh, name in s.execute(q):
        start = datetime.combine(sh.day, sh.start_time, IST)
        end = datetime.combine(sh.day, sh.end_time, IST)
        hours, missing = worked_hours(att.clock_in, att.clock_out, end)
        flags = []
        if att.clock_in > start + LATE_GRACE:
            flags.append("late")
        if missing:
            flags.append("missing_clock_out")
        elif att.clock_out and att.clock_out < end - EARLY_LEAVE:
            flags.append("early_leave")
        if hours > an.OT_SPIKE_HOURS:
            flags.append("over_12_hours")
        if only_issues and not flags:
            continue
        records.append({"attendance_id": att.id, "day": sh.day, "employee": name,
                        "employee_id": att.employee_id, "scheduled": f"{sh.start_time}-{sh.end_time}",
                        "clock_in": att.clock_in.astimezone(IST).time(),
                        "clock_out": att.clock_out.astimezone(IST).time() if att.clock_out else None,
                        "hours": hours, "flags": flags})
    return envelope({"count": len(records), "records": records[:500]}, [],
                    [str(r["attendance_id"]) for r in records[:500]])


# 4 ---------------------------------------------------------------------------------------------
def explain_payslip(s: Session, caller: Caller, employee_id: str,
                    period_date: date | None = None,
                    compare_to_previous: bool = True) -> dict[str, Any]:
    """Payslip for the period containing period_date (default: latest), with a line-by-line
    explanation of the change from the previous period. All amounts are pre-computed."""
    emp = get_employee(s, employee_id)
    assert_can_view_employee(caller, str(emp.id), str(emp.outlet_id))
    period = period_for(s, str(emp.outlet_id), period_date)

    def slip_for(p: PayPeriod) -> PayslipRow | None:
        return s.scalars(select(PayslipRow).where(PayslipRow.employee_id == emp.id,
                                                  PayslipRow.pay_period_id == p.id)).first()

    row = slip_for(period)
    if row is None:
        return envelope(None, [f"No payslip for {emp.name} in {period.start_date}."])
    current = payslip_from_json(row.detail)
    data: dict[str, Any] = {
        "employee": emp.name, "period": {"start": period.start_date, "end": period.end_date,
                                         "status": period.status},
        "net_pay": fmt_inr(current.net_pay),
        "line_items": [{**li, "amount": fmt_inr(Decimal(str(li["amount"])))}
                       for li in current.line_items],
        "regular_hours": current.regular_hours, "ot_hours": current.ot_hours,
        "shifts_worked": current.shifts_worked,
    }
    sources = [str(row.id)]
    prev = previous_period(s, period) if compare_to_previous else None
    prev_row = slip_for(prev) if prev else None
    if prev and prev_row:
        total, changes = diff_payslips(payslip_from_json(prev_row.detail), current)
        data["comparison"] = {
            "previous_period_start": prev.start_date,
            "previous_net_pay": fmt_inr(payslip_from_json(prev_row.detail).net_pay),
            "net_change": fmt_inr(total),
            "changes": [{"component": c.component, "amount": fmt_inr(c.delta), "reason": c.reason}
                        for c in changes],
        }
        sources.append(str(prev_row.id))
    return envelope(data, [], sources)


# 5 ---------------------------------------------------------------------------------------------
def get_payroll_summary(s: Session, caller: Caller, outlet_id: str | None = None,
                        period_date: date | None = None) -> dict[str, Any]:
    caller.require_role(Role.OWNER, Role.MANAGER)
    outlets = scope_outlets(caller, outlet_id, org_outlet_ids(s))
    summaries = []
    for oid in outlets:
        period = period_for(s, oid, period_date)
        q = (select(func.count(), func.sum(PayslipRow.net_pay), func.sum(PayslipRow.ot_hours),
                    func.sum(PayslipRow.ot_pay), func.sum(PayslipRow.tips_total),
                    func.sum(PayslipRow.deductions_total))
             .where(PayslipRow.pay_period_id == period.id))
        n, net, ot_h, ot_pay, tips, deds = s.execute(q).one()
        summaries.append({"outlet": get_outlet(s, oid).name, "outlet_id": oid,
                          "period_start": period.start_date, "period_end": period.end_date,
                          "status": period.status, "employees_paid": n,
                          "total_net_pay": fmt_inr(Decimal(net or 0)), "total_ot_hours": ot_h or 0,
                          "total_ot_pay": fmt_inr(Decimal(ot_pay or 0)),
                          "total_tips": fmt_inr(Decimal(tips or 0)),
                          "total_deductions": fmt_inr(Decimal(deds or 0))})
    return envelope({"outlets": summaries})


# 6 ---------------------------------------------------------------------------------------------
def list_anomalies(s: Session, caller: Caller, outlet_id: str | None = None,
                   period_date: date | None = None,
                   types: list[str] | None = None) -> dict[str, Any]:
    caller.require_role(Role.OWNER, Role.MANAGER)
    found: list[an.Anomaly] = []
    names: dict[str, str] = {}
    for oid in scope_outlets(caller, outlet_id, org_outlet_ids(s)):
        period = period_for(s, oid, period_date)
        emps = {str(e.id): e for e in s.scalars(select(Employee).where(
            Employee.outlet_id == as_uuid(oid)))}
        names |= {k: v.name for k, v in emps.items()}
        att_rows = []
        for att, sh in s.execute(
                select(Attendance, Shift).join(Shift, Shift.id == Attendance.shift_id)
                .where(Shift.outlet_id == as_uuid(oid), Shift.day >= period.start_date,
                       Shift.day <= period.end_date)):
            hours, missing = worked_hours(att.clock_in, att.clock_out,
                                          datetime.combine(sh.day, sh.end_time, IST))
            att_rows.append(an.AttendanceRec(str(att.id), str(att.employee_id), sh.day, hours,
                                             missing))
        found += an.missing_clock_outs(att_rows) + an.ot_spikes(att_rows)
        found += an.duplicate_deductions([
            an.DeductionRec(str(d.id), str(d.employee_id), str(d.pay_period_id), d.type, d.amount)
            for d in s.scalars(select(Deduction).where(Deduction.pay_period_id == period.id))])
        tip_rows = s.execute(
            select(Tip.id, Tip.day, Tip.total_amount,
                   func.coalesce(func.sum(TipAllocation.amount), 0))
            .outerjoin(TipAllocation, TipAllocation.tip_id == Tip.id)
            .where(Tip.outlet_id == as_uuid(oid), Tip.day >= period.start_date,
                   Tip.day <= period.end_date)
            .group_by(Tip.id)).all()
        found += an.tip_mismatches([an.TipRec(str(i), d, tot, alloc)
                                    for i, d, tot, alloc in tip_rows])
        changes = []
        for emp_id in emps:
            hist = s.execute(select(RateHistory.id, RateHistory.effective_from,
                                    RateHistory.hourly_rate)
                             .where(RateHistory.employee_id == as_uuid(emp_id))
                             .order_by(RateHistory.effective_from)).all()
            for (_, _, old), (rid, eff, new) in zip(hist, hist[1:], strict=False):
                changes.append(an.RateChangeRec(str(rid), emp_id, eff, old, new))
        found += an.mid_period_rate_changes(changes, period.start_date, period.end_date)
    if types:
        found = [a for a in found if a.type in types]
    items = [{**a.to_json(), "employee": names.get(a.employee_id or "")} for a in found]
    items.sort(key=lambda a: ({"high": 0, "medium": 1, "low": 2}[a["severity"]], a["day"] or ""))
    return envelope({"count": len(items), "anomalies": items}, [],
                    [sid for a in found for sid in a.source_ids])


# 7 ---------------------------------------------------------------------------------------------
def get_checklist(s: Session, caller: Caller, day: date, type: str,
                  outlet_id: str | None = None) -> dict[str, Any]:
    if type not in {"opening", "closing"}:
        raise ValueError("type must be 'opening' or 'closing'.")
    out = []
    for oid in scope_outlets(caller, outlet_id, org_outlet_ids(s)):
        cl = s.scalars(select(Checklist).where(Checklist.outlet_id == as_uuid(oid),
                                               Checklist.day == day, Checklist.type == type)).first()
        if cl is None:
            continue
        items = s.execute(select(ChecklistItem, Employee.name)
                          .outerjoin(Employee, Employee.id == ChecklistItem.done_by)
                          .where(ChecklistItem.checklist_id == cl.id)
                          .order_by(ChecklistItem.position)).all()
        out.append({"outlet": get_outlet(s, oid).name, "checklist_id": cl.id, "day": day,
                    "type": type,
                    "done": sum(1 for i, _ in items if i.done_at), "total": len(items),
                    "items": [{"item_id": i.id, "title": i.title, "required": i.required,
                               "done": i.done_at is not None, "done_by": who,
                               "done_at": i.done_at.astimezone(IST).time() if i.done_at else None}
                              for i, who in items]})
    return envelope({"checklists": out}, [] if out else [f"No {type} checklist for {day}."])


# 8 ---------------------------------------------------------------------------------------------
def search_policy(s: Session, caller: Caller, query: str, k: int = 5) -> dict[str, Any]:
    """Full-text search over policy chunks.
    TODO(M3): hybrid retrieval = pgvector cosine + this FTS, merged with reciprocal rank fusion,
    once `python -m rag.ingest --embed` has filled embeddings."""
    k = max(1, min(k, 10))
    tsv = func.to_tsvector(text("'english'"), PolicyChunk.section + " " + PolicyChunk.text)
    tsq = func.websearch_to_tsquery(text("'english'"), query)
    rank = func.ts_rank(tsv, tsq)
    rows = s.execute(select(PolicyChunk, PolicyDoc.title, rank.label("rank"))
                     .join(PolicyDoc, PolicyDoc.id == PolicyChunk.doc_id)
                     .where(tsv.op("@@")(tsq)).order_by(rank.desc()).limit(k)).all()
    if not rows:  # fall back to OR-matching any keyword
        or_q = " or ".join(w for w in query.split() if len(w) > 2)
        tsq = func.websearch_to_tsquery(text("'english'"), or_q)
        rank = func.ts_rank(tsv, tsq)
        rows = s.execute(select(PolicyChunk, PolicyDoc.title, rank.label("rank"))
                         .join(PolicyDoc, PolicyDoc.id == PolicyChunk.doc_id)
                         .where(tsv.op("@@")(tsq)).order_by(rank.desc()).limit(k)).all()
    hits = [{"chunk_id": c.id, "document": title, "section": c.section, "text": c.text,
             "score": round(float(r), 4), "citation": f"[{title} › {c.section}]"}
            for c, title, r in rows]
    return envelope({"hits": hits}, [] if hits else ["Nothing relevant found in policies."],
                    [str(h["chunk_id"]) for h in hits])
