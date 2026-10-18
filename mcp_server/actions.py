"""Approval + execution of pending actions. Called by the API (web buttons, WhatsApp buttons,
spoken "yes"), never exposed as an LLM tool."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.auth import Caller, PermissionDenied, Role, can_approve
from core.jsonable import jsonable
from db.models import Deduction, PayPeriod, PayslipRow, PendingAction
from mcp_server.queries import as_uuid, compute_period_payslip, get_employee

Executor = Callable[[Session, Caller, PendingAction], dict[str, Any]]


def _exec_deduction(s: Session, caller: Caller, action: PendingAction) -> dict[str, Any]:
    a = action.args
    emp = get_employee(s, a["employee_id"])
    period = s.get(PayPeriod, as_uuid(a["pay_period_id"]))
    if period is None or period.status != "open":
        raise PermissionDenied("Pay period is no longer open.")
    ded = Deduction(id=uuid.uuid4(), org_id=action.org_id, employee_id=emp.id,
                    pay_period_id=period.id, type=a["type"], amount=Decimal(a["amount"]),
                    note=a["note"], created_by=uuid.UUID(caller.user_id))
    s.add(ded)
    s.flush()
    slip = compute_period_payslip(s, emp, period)
    row = s.scalars(select(PayslipRow).where(PayslipRow.employee_id == emp.id,
                                             PayslipRow.pay_period_id == period.id)).first()
    if row:
        row.deductions_total, row.net_pay = slip.deductions_total, slip.net_pay
        row.detail = slip.to_json()
    return {"deduction_id": str(ded.id), "new_net_pay": str(slip.net_pay)}


EXECUTORS: dict[str, Executor] = {"propose_deduction": _exec_deduction}


def decide(s: Session, approver: Caller, action_id: str, approve: bool) -> dict[str, Any]:
    """Approve (and execute) or reject. Idempotent: deciding an already-decided action returns
    its stored result instead of executing twice."""
    action = s.scalars(select(PendingAction).where(PendingAction.id == as_uuid(action_id))
                       .with_for_update()).first()
    if action is None:
        raise PermissionDenied("Action not found.")
    if action.status in {"executed", "rejected", "failed", "expired"}:
        done: dict[str, Any] = jsonable({"status": action.status, "result": action.result,
                                         "idempotent": True})
        return done
    if action.expires_at <= datetime.now(UTC):
        action.status = "expired"
        return {"status": "expired"}
    if not can_approve(approver, Role(action.required_approver_role), str(action.outlet_id)):
        raise PermissionDenied(f"Needs approval from {action.required_approver_role}.")

    action.decided_by = uuid.UUID(approver.user_id)
    action.decided_at = datetime.now(UTC)
    if not approve:
        action.status = "rejected"
        return {"status": "rejected"}
    try:
        with s.begin_nested():
            action.result = EXECUTORS[action.tool](s, approver, action)
        action.status = "executed"
    except Exception as exc:  # report, never half-apply (savepoint rolled back)
        action.status, action.result = "failed", {"error": str(exc)}
    out: dict[str, Any] = jsonable({"status": action.status, "result": action.result})
    return out
