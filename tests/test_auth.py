from decimal import Decimal as D

import pytest

from core.auth import (
    Caller,
    PermissionDenied,
    Role,
    approver_role_for_deduction,
    assert_can_view_employee,
    can_approve,
    scope_outlets,
)
from core.redact import redact

OWNER = Caller("u-owner", "org", Role.OWNER)
MGR_A = Caller("u-mgr-a", "org", Role.MANAGER, outlet_id="A")
MGR_B = Caller("u-mgr-b", "org", Role.MANAGER, outlet_id="B")
STAFF = Caller("u-staff", "org", Role.STAFF, outlet_id="A", employee_id="e1")


def test_scope_outlets() -> None:
    assert scope_outlets(OWNER, None, ["A", "B"]) == ["A", "B"]
    assert scope_outlets(MGR_A, None, ["A", "B"]) == ["A"]
    with pytest.raises(PermissionDenied):
        scope_outlets(MGR_A, "B", ["A", "B"])


def test_staff_sees_only_self() -> None:
    assert_can_view_employee(STAFF, "e1", "A")
    with pytest.raises(PermissionDenied):
        assert_can_view_employee(STAFF, "e2", "A")


def test_manager_cannot_cross_outlets() -> None:
    assert_can_view_employee(MGR_A, "e9", "A")
    with pytest.raises(PermissionDenied):
        assert_can_view_employee(MGR_A, "e9", "B")


def test_deduction_approval_tiers() -> None:
    assert approver_role_for_deduction(MGR_A, D("2000")) is Role.MANAGER
    assert approver_role_for_deduction(MGR_A, D("2000.01")) is Role.OWNER
    with pytest.raises(PermissionDenied):
        approver_role_for_deduction(STAFF, D("10"))


def test_can_approve() -> None:
    assert can_approve(MGR_A, Role.MANAGER, "A")
    assert not can_approve(MGR_B, Role.MANAGER, "A")
    assert not can_approve(MGR_A, Role.OWNER, "A")
    assert can_approve(OWNER, Role.OWNER, "A")
    assert not can_approve(STAFF, Role.MANAGER, "A")


def test_redaction() -> None:
    out = redact({"phone": "+919812345678", "msg": "call me on 9812345678",
                  "acct": "account 123456789012"})
    assert out["phone"] == "[redacted]"
    assert "9812345678" not in out["msg"]
    assert "123456789012" not in out["acct"]
