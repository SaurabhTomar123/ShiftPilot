"""B6.2 acceptance: every public demo session gets an isolated, expiring sandbox."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v2 import auth as v2auth
from api.v2 import generation
from db.session import admin_engine
from jobs import retention
from seed import v2
from seed.world import uid
from tests.integration.test_api_v2 import WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
TEMPLATE = uid("org", v2.SPICE)


def start(c: TestClient, persona: str = "manager", sandbox_id: str | None = None) -> Any:
    body = {"persona": persona} | ({"sandbox_id": sandbox_id} if sandbox_id else {})
    return c.post("/v2/session/demo", json=body)


def auth(session: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


def count(statement: str, **params: Any) -> int:
    with admin_engine().begin() as conn:
        return int(conn.execute(text(statement), params).scalar_one())


def week(c: TestClient, session: dict[str, Any]) -> dict[str, Any]:
    outlet = session["me"]["outlet_id"]
    return dict(c.get(f"/v2/outlets/{outlet}/schedules/{WEEK}", headers=auth(session)).json())


def test_each_visitor_gets_a_private_copy(client: TestClient) -> None:
    template_versions = count("SELECT count(*) FROM schedule_versions WHERE org_id = :o", o=TEMPLATE)
    a, b = start(client).json(), start(client).json()
    assert a["sandbox_id"] != b["sandbox_id"] and a["me"]["org_id"] == a["sandbox_id"]
    assert datetime.fromisoformat(a["expires_at"]) <= datetime.fromisoformat(a["sandbox_expires_at"])
    wa, wb = week(client, a), week(client, b)
    assert len(wa["current_version"]["shifts"]) == len(wb["current_version"]["shifts"]) > 0
    assert wa["current_version"]["id"] != wb["current_version"]["id"]

    draft = client.post(
        f"/v2/outlets/{wa['outlet_id']}/schedules/{WEEK}/drafts",
        headers=auth(a) | {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"},
        json={"base_version_id": wa["current_version"]["id"], "copy_from_version_id": None},
    )
    assert draft.status_code == 201, draft.text
    assert client.get(f"/v2/schedule-versions/{draft.json()['id']}", headers=auth(b)).status_code == 404
    assert week(client, b)["drafts"] == []
    assert count("SELECT count(*) FROM schedule_versions WHERE org_id = :o", o=TEMPLATE) == template_versions

    staff = start(client, "staff", a["sandbox_id"]).json()  # switch persona inside the same sandbox
    assert staff["sandbox_id"] == a["sandbox_id"] and staff["me"]["role"] == "staff"
    gone = start(client, "owner", str(uuid.uuid4()))
    assert gone.status_code == 404


def test_sandboxes_have_tighter_limits(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = start(client, "owner").json()
    outlets = [o["id"] for o in client.get("/v2/outlets", headers=auth(owner)).json()["items"]]
    codes = [
        client.post(
            f"/v2/outlets/{o}/schedules/2026-11-16/generate",
            headers=auth(owner) | {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"},
            json={"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 3},
        ).status_code
        for o in outlets[:3]
    ]
    assert codes == [202, 202, 429] and generation.SANDBOX_ACTIVE_CAP == 2
    monkeypatch.setattr(v2auth, "MAX_SANDBOXES", 0)
    busy = start(client)
    assert busy.status_code == 429 and error_code(busy) == "rate_limited"


def test_expired_sandboxes_are_purged_completely(client: TestClient) -> None:
    session = start(client).json()
    org = session["sandbox_id"]
    assert count("SELECT count(*) FROM employees WHERE org_id = :o", o=org) > 0
    report = retention.run(now=datetime.now(UTC) + timedelta(hours=3))
    assert report["sandboxes_purged"] >= 1
    for table in ("employees", "schedule_versions", "version_shifts", "users", "optimization_runs"):
        assert count(f"SELECT count(*) FROM {table} WHERE org_id = :o", o=org) == 0, table
    assert count("SELECT count(*) FROM organizations WHERE id = :o", o=org) == 0
    assert client.get("/v2/me", headers=auth(session)).status_code == 401
    assert count("SELECT count(*) FROM employees WHERE org_id = :o", o=TEMPLATE) > 0  # template intact
