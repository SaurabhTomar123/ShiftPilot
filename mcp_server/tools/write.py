"""Write tools only PROPOSE. They validate, then create a pending_action that a human must approve
through the API (mcp_server.actions.decide). The LLM has no tool that executes anything."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.auth import (
    Caller,
    PermissionDenied,
    approver_role_for_deduction,
    assert_can_view_employee,
)
from core.jsonable import jsonable
from core.money import fmt_inr, inr
from db.models import Deduction, PendingAction
from mcp_server.queries import get_employee, period_for
from mcp_server.tools.read import envelope

ACTION_TTL = timedelta(minutes=30)
DEDUCTION_TYPES = {"advance", "meal", "uniform", "damage", "pf", "esi", "tds"}


def idempotency_key(caller: Caller, tool: str, args: dict[str, Any]) -> str:
    """Same caller + same tool + same args = same proposal (no duplicates on retries)."""
    raw = json.dumps({"u": caller.user_id, "t": tool, "a": jsonable(args)}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def _create_pending(s: Session, caller: Caller, tool: str, args: dict[str, Any], outlet_id: str,
                    summary: str, approver_role: str, warnings: list[str]) -> dict[str, Any]:
    key = idempotency_key(caller, tool, args)
    existing = s.scalars(select(PendingAction).where(PendingAction.idempotency_key == key)).first()
    now = datetime.now(UTC)
    if existing and existing.status == "pending" and existing.expires_at > now:
        action = existing
    else:
        if existing:  # stale/decided proposal with same args: re-key the old one
            existing.idempotency_key = f"{key}:{existing.id}"[:80]
        action = PendingAction(
            id=uuid.uuid4(), org_id=uuid.UUID(caller.org_id), outlet_id=uuid.UUID(outlet_id),
            requested_by=uuid.UUID(caller.user_id), tool=tool, args=jsonable(args),
            summary_text=summary, status="pending", required_approver_role=approver_role,
            idempotency_key=key, expires_at=now + ACTION_TTL)
        s.add(action)
        s.flush()
    return envelope({"pending_action_id": action.id, "status": action.status,
                     "summary": summary, "requires_approval_from": approver_role,
                     "expires_at": action.expires_at},
                    warnings + ["Nothing has changed yet. Ask the user to approve or reject."],
                    [str(action.id)])


# 11 --------------------------------------------------------------------------------------------
def propose_deduction(s: Session, caller: Caller, employee_id: str, type: str, amount: str,
                      note: str, period_date: date | None = None) -> dict[str, Any]:
    if type not in DEDUCTION_TYPES:
        raise ValueError(f"type must be one of {sorted(DEDUCTION_TYPES)}")
    try:
        value = inr(Decimal(amount))
    except InvalidOperation as exc:
        raise ValueError("amount must be a number in rupees") from exc
    if value <= 0:
        raise ValueError("amount must be positive")
    emp = get_employee(s, employee_id)
    assert_can_view_employee(caller, str(emp.id), str(emp.outlet_id))
    approver = approver_role_for_deduction(caller, value)
    period = period_for(s, str(emp.outlet_id), period_date)
    if period.status != "open":
        raise PermissionDenied(f"Pay period starting {period.start_date} is {period.status}.")

    warnings = []
    dupes = s.scalars(select(Deduction).where(
        Deduction.employee_id == emp.id, Deduction.pay_period_id == period.id,
        Deduction.type == type, Deduction.amount == value)).all()
    if dupes:
        warnings.append(f"{emp.name} already has a {type} deduction of {fmt_inr(value)} in this "
                        "pay period. Confirm this is not a duplicate.")
    summary = (f"Add {type} deduction of {fmt_inr(value)} for {emp.name} "
               f"(pay period {period.start_date}–{period.end_date}). Note: {note}")
    args = {"employee_id": str(emp.id), "type": type, "amount": str(value), "note": note,
            "pay_period_id": str(period.id)}
    return _create_pending(s, caller, "propose_deduction", args, str(emp.outlet_id), summary,
                           approver.value, warnings)


# 9, 10, 12 -------------------------------------------------------------------------------------
# TODO(M2): implement with the same pattern as propose_deduction:
#   propose_shift_swap(shift_a_id, shift_b_id): both shifts in caller's outlet; same job_role;
#     no overlap for either person; >= 10 h rest before/after (handbook §1.4); store versions in
#     args so execution can do optimistic locking. Staff may propose only for their own shift.
#   propose_shift_reassign(shift_id, to_employee_id): same checks, for covering absences.
#   propose_checklist_update(item_id, note): manager or staff on shift that day.
# Then add an executor for each in mcp_server/actions.py::EXECUTORS and register in server.py.
