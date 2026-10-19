"""Absences as facts and absence repair (B4.1/B4.2, architecture v3 sections 20, 28)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from db.session import admin_engine
from scheduling import worker
from seed.world import IST, uid
from tests.integration.test_api_v2 import IND, MANAGER, STAFF, WEEK, client, error_code

MONDAY = date.fromisoformat(WEEK)

pytestmark = pytest.mark.integration
__all__ = ["client"]
WEEK_URL = f"/v2/outlets/{IND}/schedules/{WEEK}"


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def current(c: TestClient) -> dict[str, Any]:
    return c.get(WEEK_URL, headers=MANAGER).json()["current_version"]


def shift_on(version: dict[str, Any], day: date, *, locked: bool = False) -> dict[str, Any]:
    return next(
        s
        for s in version["shifts"]
        if s["employee_id"]
        and s["locked"] == locked
        and datetime.fromisoformat(s["start_at"]).astimezone(IST).date() == day
    )


def report(
    c: TestClient, shift: dict[str, Any], status: str = "confirmed", as_: dict[str, str] = MANAGER
) -> Any:
    start = datetime.fromisoformat(shift["start_at"])
    return c.post(
        "/v2/absences",
        headers=as_ | key(),
        json={
            "employee_id": shift["employee_id"],
            "start_at": (start - timedelta(hours=1)).isoformat(),
            "end_at": shift["end_at"],
            "kind": "sick",
            "status": status,
            "reason": None,
        },
    )


def sql(statement: str, **params: Any) -> Any:
    with admin_engine().begin() as conn:
        result = conn.execute(text(statement), params)
        return result.all() if result.returns_rows else result.rowcount


def drain() -> None:
    while worker.run_once() is not None:
        pass


def test_confirmed_absence_is_a_fact_and_triggers_a_repair(client: TestClient) -> None:
    version = current(client)
    target = shift_on(version, MONDAY + timedelta(days=2))  # a Wednesday shift
    r = report(client, target)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["absence"]["status"] == "confirmed" and body["repair_suggested"]
    assert target["logical_shift_id"] in {a["logical_shift_id"] for a in body["affected"]}
    assert len(body["repair_run_ids"]) == 1
    run_id = body["repair_run_ids"][0]
    assert sql("SELECT count(*) FROM audit_log WHERE action = 'ABSENCE_REPORTED'")[0][0] >= 1

    drain()
    run = client.get(f"/v2/optimization-runs/{run_id}", headers=MANAGER).json()
    assert run["kind"] == "repair" and run["job_state"] == "succeeded", run
    assert run["absence_id"] == body["absence"]["id"] and run["candidates"]
    first = run["candidates"][0]
    assert first["strategy"] == "least_disruption" and first["disruption"]["changed_shifts"] >= 1
    explained = {e["logical_shift_id"]: e for e in first["explanations"]}
    assert target["logical_shift_id"] in explained
    chosen = explained[target["logical_shift_id"]]
    assert chosen["chosen_employee_id"] != target["employee_id"]
    for alt in chosen["alternatives"]:
        assert alt["status"] in ("rejected", "eligible_not_selected")
        if alt["status"] == "rejected":
            assert any(not reason["ok"] for reason in alt["reasons"])
    draft = client.get(f"/v2/schedule-versions/{first['draft_version_id']}", headers=MANAGER).json()
    assert draft["validation"]["hard_violations"] == 0
    assert current(client)["id"] == version["id"]  # the published roster is never edited by a repair


def test_repair_is_not_blocked_by_an_active_batch_run(client: TestClient) -> None:
    version = current(client)
    batch = client.post(
        f"{WEEK_URL}/generate",
        headers=MANAGER | key(),
        json={"strategy": "balanced", "base_version_id": version["id"], "time_limit_seconds": 3},
    )
    assert batch.status_code == 202, batch.text
    target = shift_on(version, MONDAY + timedelta(days=3))  # Thursday
    r = report(client, target)
    assert r.status_code == 201 and len(r.json()["repair_run_ids"]) == 1
    repair_id = r.json()["repair_run_ids"][0]
    assert str(worker.run_once()) == repair_id  # repairs are claimed first (priority 1 < 5)
    drain()
    assert (
        client.get(f"/v2/optimization-runs/{batch.json()['id']}", headers=MANAGER).json()["job_state"]
        == "succeeded"
    )


def test_staff_request_waits_for_manager_confirmation(client: TestClient) -> None:
    version = current(client)
    ravi = str(uid("employee", "ravi"))
    target = next(s for s in version["shifts"] if s["employee_id"] == ravi and not s["locked"])
    requested = report(client, target, status="requested", as_=STAFF)
    assert requested.status_code == 201 and requested.json()["repair_run_ids"] == []
    absence_id = requested.json()["absence"]["id"]
    assert (
        client.patch(f"/v2/absences/{absence_id}", headers=STAFF, json={"status": "confirmed"}).status_code
        == 403
    )
    confirmed = client.patch(f"/v2/absences/{absence_id}", headers=MANAGER, json={"status": "confirmed"})
    assert confirmed.status_code == 200 and len(confirmed.json()["repair_run_ids"]) == 1
    other = next(s for s in version["shifts"] if s["employee_id"] not in (ravi, None))
    assert report(client, other, status="requested", as_=STAFF).status_code == 403
    drain()


def test_locked_shift_needs_explicit_authorization(client: TestClient) -> None:
    version = current(client)
    locked = next(s for s in version["shifts"] if s["locked"])
    r = report(client, locked)
    assert r.status_code == 201
    body = r.json()
    assert body["lock_conflicts"] == [locked["logical_shift_id"]] and body["repair_run_ids"] == []
    week = datetime.fromisoformat(locked["start_at"]).astimezone(IST).date()
    week_start = week - timedelta(days=week.weekday())
    url = f"/v2/outlets/{IND}/schedules/{week_start}/repair"
    payload = {"absence_id": body["absence"]["id"], "base_version_id": version["id"], "time_limit_seconds": 3}
    refused = client.post(url, headers=MANAGER | key(), json=payload)
    assert refused.status_code == 409 and error_code(refused) == "conflict"
    assert refused.json()["error"]["details"]["locked_logical_shift_ids"] == [locked["logical_shift_id"]]
    allowed = client.post(
        url,
        headers=MANAGER | key(),
        json=payload | {"unlock_logical_shift_ids": [locked["logical_shift_id"]]},
    )
    assert allowed.status_code == 202, allowed.text
    again = client.post(
        url,
        headers=MANAGER | key(),
        json=payload | {"unlock_logical_shift_ids": [locked["logical_shift_id"]]},
    )
    assert (
        again.status_code == 202 and again.json()["id"] == allowed.json()["id"]
    )  # one active repair per absence
    drain()
