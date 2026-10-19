"""B1.2 (part 1) acceptance: the real v2 API against a seeded scratch database.

Where seeded data and a contract fixture describe the same thing, the live response must equal
the fixture body, so the UI's fixture-driven work carries over unchanged.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api.v2 import schemas
from core import config
from core.auth import Caller, Role
from core.tokens import issue
from db import migrate, session
from seed import v2
from seed.world import uid

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "v2" / "fixtures"
WEEK = "2026-10-19"
IND, KOR = str(uid("outlet", "indiranagar")), str(uid("outlet", "koramangala"))
RAVI = str(uid("employee", "ravi"))


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())["response"]["body"]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    base = config.settings()
    with migrate.scratch_database(base.database_url) as url:
        migrate.upgrade(url)
        with create_engine(url).begin() as conn:
            v2.load_org(conn, v2.SPICE)
            v2.load_org(conn, v2.NORTHWIND)
        app_url = url.replace(base.database_url.split("@")[0], base.app_database_url.split("@")[0], 1)
        mp = pytest.MonkeyPatch()
        mp.setenv("DATABASE_URL", url)
        mp.setenv("APP_DATABASE_URL", app_url)
        mp.setenv("DEMO_SESSIONS_ENABLED", "true")
        for cached in (config.settings, session.admin_engine, session.app_engine):
            cached.cache_clear()
        from api.v2.app import create_app

        try:
            yield TestClient(create_app())
        finally:
            session.admin_engine().dispose()
            session.app_engine().dispose()
            mp.undo()
            for cached in (config.settings, session.admin_engine, session.app_engine):
                cached.cache_clear()


def token(
    key: str, role: Role, outlet: str | None = None, employee: str | None = None, org: str = v2.SPICE
) -> dict[str, str]:
    caller = Caller(
        user_id=str(uid("user", key)),
        org_id=str(uid("org", org)),
        role=role,
        outlet_id=outlet,
        employee_id=employee,
    )
    return {"Authorization": f"Bearer {issue(caller)}"}


OWNER = token("owner", Role.OWNER)
MANAGER = token("manager_indiranagar", Role.MANAGER, IND)
STAFF = token("staff_ravi", Role.STAFF, IND, RAVI)
NW_OWNER = token(f"{v2.NORTHWIND}:owner", Role.OWNER, org=v2.NORTHWIND)


def error_code(response: Any) -> str:
    return schemas.ErrorResponse.model_validate(response.json()).error.code


# ---------------------------------------------------------------- identity


def test_requests_without_a_token_get_the_error_envelope(client: TestClient) -> None:
    r = client.get("/v2/me")
    assert r.status_code == 401 and error_code(r) == "unauthenticated"


def test_demo_session_issues_a_working_token(client: TestClient) -> None:
    r = client.post("/v2/session/demo", json={"persona": "manager"})
    assert r.status_code == 201, r.text
    session_body = schemas.DemoSession.model_validate(r.json())
    me = client.get("/v2/me", headers={"Authorization": f"Bearer {session_body.access_token}"}).json()
    assert me == fixture("me.manager")


def test_me_matches_the_fixture_for_each_persona(client: TestClient) -> None:
    assert client.get("/v2/me", headers=OWNER).json() == fixture("me.owner")
    assert client.get("/v2/me", headers=STAFF).json() == fixture("me.staff")


# ---------------------------------------------------------------- outlets and skills


def test_outlets_are_scoped_by_role(client: TestClient) -> None:
    owner = client.get("/v2/outlets", headers=OWNER).json()["items"]
    assert {o["name"] for o in owner} == {"Indiranagar", "Koramangala", "HSR Layout"}
    assert client.get("/v2/outlets", headers=MANAGER).json() == fixture("outlets.manager")


def test_skills_are_tenant_isolated(client: TestClient) -> None:
    assert {k["name"] for k in client.get("/v2/skills", headers=OWNER).json()["items"]} == {
        "Grill",
        "Prep",
        "Server",
        "Cashier",
        "Barista",
    }
    assert {k["name"] for k in client.get("/v2/skills", headers=NW_OWNER).json()["items"]} == {
        "Grill",
        "Server",
    }


# ---------------------------------------------------------------- employees


def test_employee_read_matches_the_fixture(client: TestClient) -> None:
    assert client.get(f"/v2/employees/{RAVI}", headers=MANAGER).json() == fixture("employees.get")


def test_manager_lists_own_outlet_and_is_denied_others(client: TestClient) -> None:
    items = client.get("/v2/employees", headers=MANAGER, params={"status": "active"}).json()["items"]
    assert len(items) == 20 and {e["home_outlet_id"] for e in items} == {IND}
    fixture_ids = {e["id"] for e in fixture("employees.list")["items"]}
    assert fixture_ids <= {e["id"] for e in items}
    r = client.get("/v2/employees", headers=MANAGER, params={"outlet_id": KOR})
    assert r.status_code == 403 and error_code(r) == "permission_denied"
    assert client.get("/v2/employees", headers=STAFF).status_code == 403


def test_employee_pagination_walks_every_row_once(client: TestClient) -> None:
    seen, cursor = [], None
    while True:
        params: dict[str, Any] = {"limit": 7, **({"cursor": cursor} if cursor else {})}
        page = client.get("/v2/employees", headers=OWNER, params=params).json()
        seen += [e["id"] for e in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 60


def test_other_tenants_employees_do_not_exist(client: TestClient) -> None:
    r = client.get(f"/v2/employees/{RAVI}", headers=NW_OWNER)
    assert r.status_code == 404 and error_code(r) == "not_found"


def new_employee(**overrides: Any) -> dict[str, Any]:
    body = {
        "name": "Tara Singh",
        "home_outlet_id": IND,
        "status": "active",
        "hourly_rate": {"amount_paise": 15900, "currency": "INR"},
        "skills": [{"skill_id": str(uid("skill", "Barista")), "level": 2}],
        "tags": [],
        "regular_weekly_minutes": 2400,
        "max_weekly_minutes": 2880,
        "preferred_weekly_minutes": None,
        "overtime_allowed": False,
        "cross_outlet_eligible": False,
    }
    return body | overrides


def test_create_employee_is_idempotent(client: TestClient) -> None:
    key = {"Idempotency-Key": f"emp-{uuid.uuid4().hex[:12]}"}
    first = client.post("/v2/employees", headers=MANAGER | key, json=new_employee())
    assert first.status_code == 201, first.text
    again = client.post("/v2/employees", headers=MANAGER | key, json=new_employee())
    assert again.status_code == 201 and again.json() == first.json()
    clash = client.post("/v2/employees", headers=MANAGER | key, json=new_employee(name="Someone Else"))
    assert clash.status_code == 409 and error_code(clash) == "idempotency_conflict"


def test_create_employee_validates_scope_and_input(client: TestClient) -> None:
    key = lambda: {"Idempotency-Key": f"emp-{uuid.uuid4().hex[:12]}"}  # noqa: E731
    other = client.post("/v2/employees", headers=MANAGER | key(), json=new_employee(home_outlet_id=KOR))
    assert other.status_code == 403
    caps = client.post("/v2/employees", headers=MANAGER | key(), json=new_employee(max_weekly_minutes=60))
    assert caps.status_code == 422 and caps.json()["error"]["details"]["fields"][0]["path"] == [
        "max_weekly_minutes"
    ]
    unknown = client.post(
        "/v2/employees",
        headers=MANAGER | key(),
        json=new_employee(skills=[{"skill_id": str(uuid.uuid4()), "level": 1}]),
    )
    assert unknown.status_code == 422
    assert client.post("/v2/employees", headers=STAFF | key(), json=new_employee()).status_code == 403


def test_update_employee_uses_revisions_and_is_audited(client: TestClient) -> None:
    target = str(uid("employee", "karan"))
    current = client.get(f"/v2/employees/{target}", headers=MANAGER).json()
    ok = client.patch(
        f"/v2/employees/{target}",
        headers=MANAGER,
        json={"base_revision": current["revision"], "tags": ["senior"]},
    )
    assert ok.status_code == 200 and ok.json()["revision"] == current["revision"] + 1
    assert ok.json()["tags"] == ["senior"]
    stale = client.patch(
        f"/v2/employees/{target}", headers=MANAGER, json={"base_revision": current["revision"], "tags": []}
    )
    assert (
        stale.status_code == 409
        and stale.json()["error"]["details"]["current_revision"] == current["revision"] + 1
    )
    null = client.patch(f"/v2/employees/{target}", headers=MANAGER, json={"base_revision": 99, "name": None})
    assert null.status_code == 422 and error_code(null) == "validation_failed"
    with create_engine(config.settings().database_url).connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_log WHERE action = 'EMPLOYEE_UPDATED' AND target_id = :t"),
                {"t": target},
            ).scalar()
            == 1
        )


# ---------------------------------------------------------------- availability and staffing


def test_availability_matches_the_fixture_and_replaces_with_revision(client: TestClient) -> None:
    assert client.get(f"/v2/employees/{RAVI}/availability", headers=MANAGER).json() == fixture(
        "availability.get"
    )
    target = str(uid("employee", "farhan"))
    current = client.get(f"/v2/employees/{target}/availability", headers=MANAGER).json()
    windows = [{"weekday": 0, "start_minute": 600, "end_minute": 1080, "kind": "available"}]
    ok = client.put(
        f"/v2/employees/{target}/availability",
        headers=MANAGER,
        json={"base_revision": current["revision"], "windows": windows},
    )
    assert (
        ok.status_code == 200
        and ok.json()["windows"] == windows
        and ok.json()["revision"] == current["revision"] + 1
    )
    stale = client.put(
        f"/v2/employees/{target}/availability",
        headers=MANAGER,
        json={"base_revision": current["revision"], "windows": windows},
    )
    assert stale.status_code == 409


def test_staffing_matches_the_fixture(client: TestClient) -> None:
    live = client.get(
        f"/v2/outlets/{IND}/staffing-requirements", headers=MANAGER, params={"week_start": WEEK}
    ).json()
    expected = fixture("staffing.get")
    key = lambda i: (i["interval_start"], i["skill_id"])  # noqa: E731
    assert {k: v for k, v in live.items() if k != "intervals"} == {
        k: v for k, v in expected.items() if k != "intervals"
    }
    assert sorted(live["intervals"], key=key) == sorted(expected["intervals"], key=key)


def test_staffing_replace_checks_revision_week_and_role(client: TestClient) -> None:
    url = f"/v2/outlets/{KOR}/staffing-requirements"
    current = client.get(url, headers=OWNER, params={"week_start": WEEK}).json()
    body = {"base_demand_revision": current["demand_revision"], "intervals": current["intervals"][:10]}
    ok = client.put(url, headers=OWNER, params={"week_start": WEEK}, json=body)
    assert ok.status_code == 200 and ok.json()["demand_revision"] == current["demand_revision"] + 1
    assert len(ok.json()["intervals"]) == 10
    assert client.put(url, headers=OWNER, params={"week_start": WEEK}, json=body).status_code == 409
    assert client.get(url, headers=OWNER, params={"week_start": "2026-10-20"}).status_code == 422
    assert client.get(url, headers=STAFF, params={"week_start": WEEK}).status_code == 403
    assert client.get(url, headers=MANAGER, params={"week_start": WEEK}).status_code == 403


def test_schedule_reads_stay_declared_but_unimplemented(client: TestClient) -> None:
    r = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER)
    assert r.status_code == 501 and error_code(r) == "not_implemented"
