"""Who is calling and what they may touch. Enforced in the tool layer (and by Postgres RLS),
never by the prompt."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

MANAGER_DEDUCTION_LIMIT = Decimal("2000")


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"


class PermissionDenied(Exception):
    """Raised by tools; the agent turns it into a polite refusal."""


@dataclass(frozen=True)
class Caller:
    user_id: str
    org_id: str
    role: Role
    outlet_id: str | None = None  # managers and staff are bound to one outlet
    employee_id: str | None = None  # staff only

    def require_role(self, *roles: Role) -> None:
        if self.role not in roles:
            raise PermissionDenied(f"{self.role} cannot do this")


def can_view_outlet(caller: Caller, outlet_id: str) -> bool:
    return caller.role is Role.OWNER or caller.outlet_id == outlet_id


def assert_outlet(caller: Caller, outlet_id: str) -> None:
    if not can_view_outlet(caller, outlet_id):
        raise PermissionDenied("You can only access your own outlet.")


def assert_can_view_employee(caller: Caller, employee_id: str, employee_outlet_id: str) -> None:
    """Shift/attendance/pay data for one employee."""
    if caller.role is Role.STAFF:
        if caller.employee_id != employee_id:
            raise PermissionDenied("Staff can only see their own records.")
        return
    assert_outlet(caller, employee_outlet_id)


def scope_outlets(caller: Caller, requested: str | None, org_outlets: list[str]) -> list[str]:
    """Outlets a query may cover. Owners default to all; others are pinned to their outlet."""
    if requested is not None:
        assert_outlet(caller, requested)
        return [requested]
    if caller.role is Role.OWNER:
        return org_outlets
    return [caller.outlet_id] if caller.outlet_id else []


def approver_role_for_deduction(caller: Caller, amount: Decimal) -> Role:
    """Who must approve a proposed deduction. Staff cannot propose deductions at all."""
    if caller.role is Role.STAFF:
        raise PermissionDenied("Staff cannot add deductions.")
    if amount > MANAGER_DEDUCTION_LIMIT:
        return Role.OWNER
    return Role.MANAGER


def can_approve(approver: Caller, required: Role, action_outlet_id: str) -> bool:
    """A requester with enough authority confirms their own action explicitly (the human in the
    loop). Anything beyond their authority needs someone who has it; staff never approve."""
    if required is Role.OWNER:
        return approver.role is Role.OWNER
    return approver.role is Role.OWNER or (
        approver.role is Role.MANAGER and approver.outlet_id == action_outlet_id
    )
