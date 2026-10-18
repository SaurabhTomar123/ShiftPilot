"""Tools against a real Postgres with RLS. Needs docker compose up + .env.

    python -m pytest -m integration
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from core.auth import Caller, PermissionDenied, Role
from db.models import Employee, PayslipRow, PendingAction
from db.session import tenant_session
from mcp_server.actions import decide
from mcp_server.context import caller_for_phone
from mcp_server.tools import read, write
from seed.generate import GROUND_TRUTH_PATH

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session", autouse=True)
def seeded() -> Iterator[dict]:
    subprocess.run([sys.executable, "-m", "db.init"], check=True)
    subprocess.run([sys.executable, "-m", "seed.load"], check=True)
    yield json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def gt(seeded: dict) -> dict:
    return seeded


def who(gt: dict, persona: str) -> Caller:
    return caller_for_phone(gt["users"][persona])


def find(caller: Caller, name: str) -> str:
    with tenant_session(caller) as s:
        res = read.find_employee(s, caller, name)
    return res["data"]["candidates"][0]["employee_id"]


def test_ambiguous_name_needs_disambiguation(gt: dict) -> None:
    mgr = who(gt, "cafe_manager")
    with tenant_session(mgr) as s:
        ravi = read.find_employee(s, mgr, "Ravi")["data"]
        exact = read.find_employee(s, mgr, "Ravi Kumar")["data"]
    assert ravi["needs_disambiguation"] is True
    assert exact["needs_disambiguation"] is False
    assert exact["candidates"][0]["name"] == "Ravi Kumar"


def test_explain_payslip_matches_ground_truth(gt: dict) -> None:
    mgr = who(gt, "cafe_manager")
    with tenant_session(mgr) as s:
        res = read.explain_payslip(s, mgr, find(mgr, "Ravi Kumar"))["data"]
    truth = gt["ravi_kumar_last_week_vs_previous"]
    assert res["comparison"]["net_change"] == truth["net_delta"]
    assert res["net_pay"] == truth["current_net"]


def test_staff_cannot_see_colleague_pay(gt: dict) -> None:
    mgr, staff = who(gt, "cafe_manager"), who(gt, "ravi_kumar_staff")
    ravi_k = find(mgr, "Ravi K")
    with pytest.raises(PermissionDenied), tenant_session(staff) as s:
        read.explain_payslip(s, staff, ravi_k)


def test_manager_cannot_cross_outlets(gt: dict) -> None:
    mgr, qsr = who(gt, "cafe_manager"), who(gt, "qsr_manager")
    with pytest.raises(PermissionDenied), tenant_session(mgr) as s:
        read.get_payroll_summary(s, mgr, outlet_id=qsr.outlet_id)


def test_rls_blocks_other_org(gt: dict) -> None:
    real = who(gt, "owner")
    intruder = Caller(real.user_id, str(uuid.uuid4()), Role.OWNER)
    with tenant_session(intruder) as s:
        assert s.scalar(select(func.count()).select_from(Employee)) == 0


def test_payroll_summary_matches_ground_truth(gt: dict) -> None:
    owner = who(gt, "owner")
    with tenant_session(owner) as s:
        res = read.get_payroll_summary(s, owner)["data"]["outlets"]
    by_name = {o["outlet"]: o["total_net_pay"] for o in res}
    assert by_name["Cloud Kitchen HSR"] == gt["outlet_net_payroll_last_week"]["kitchen_hsr"]


def test_anomalies_find_planted_missing_clock_outs(gt: dict) -> None:
    owner = who(gt, "owner")
    found = set()
    with tenant_session(owner) as s:
        for day in ("2026-09-21", "2026-09-28", "2026-10-05"):
            res = read.list_anomalies(s, owner, period_date=date.fromisoformat(day),
                                      types=["missing_clock_out"])
            found |= {(a["employee"], a["day"]) for a in res["data"]["anomalies"]}
    expected = {(r["employee"], r["day"]) for r in gt["missing_clock_outs"]}
    assert expected <= found


def test_policy_search_cites_overtime(gt: dict) -> None:
    staff = who(gt, "ravi_kumar_staff")
    with tenant_session(staff) as s:
        hits = read.search_policy(s, staff, "overtime rate")["data"]["hits"]
    assert hits and "Overtime" in hits[0]["section"]


def test_deduction_propose_approve_is_idempotent(gt: dict) -> None:
    mgr = who(gt, "cafe_manager")
    ravi_k = find(mgr, "Ravi K")
    with tenant_session(mgr) as s:
        proposal = write.propose_deduction(s, mgr, ravi_k, "meal", "150", "test meals")
        action_id = proposal["data"]["pending_action_id"]
        period_id = s.get(PendingAction, uuid.UUID(str(action_id))).args["pay_period_id"]
        before = s.scalar(select(PayslipRow.net_pay).where(
            PayslipRow.employee_id == uuid.UUID(ravi_k),
            PayslipRow.pay_period_id == uuid.UUID(period_id)))
    with tenant_session(mgr) as s:
        first = decide(s, mgr, str(action_id), approve=True)
    with tenant_session(mgr) as s:
        second = decide(s, mgr, str(action_id), approve=True)
    assert first["status"] == "executed", first
    assert second.get("idempotent") is True
    assert Decimal(first["result"]["new_net_pay"]) == before - Decimal("150")


def test_large_deduction_needs_owner(gt: dict) -> None:
    mgr = who(gt, "cafe_manager")
    with tenant_session(mgr) as s:
        prop = write.propose_deduction(s, mgr, find(mgr, "Ravi Kumar"), "damage", "2500", "grinder")
    assert prop["data"]["requires_approval_from"] == "owner"
    with pytest.raises(PermissionDenied), tenant_session(mgr) as s:
        decide(s, mgr, prop["data"]["pending_action_id"], approve=True)
