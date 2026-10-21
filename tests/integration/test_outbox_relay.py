"""B6.3 / architecture v3 section 40: the outbox relay turns committed events into in-app notifications."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from db.session import admin_engine, relay_engine
from jobs import outbox_relay
from scheduling import worker
from tests.integration.test_api_v2 import IND, MANAGER, OWNER, STAFF, WEEK, client

pytestmark = pytest.mark.integration
__all__ = ["client"]
WEEK_URL = f"/v2/outlets/{IND}/schedules/{WEEK}"


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def sql(statement: str, **params: Any) -> Any:
    with admin_engine().begin() as conn:
        result = conn.execute(text(statement), params)
        return result.all() if result.returns_rows else result.rowcount


def drain() -> None:
    outbox_relay.relay_once()  # earlier events (the seed's and other tests') out of the way


def test_publication_notifies_rostered_staff_exactly_once(client: TestClient) -> None:
    drain()
    current = client.get(WEEK_URL, headers=MANAGER).json()["current_version"]
    draft = client.post(
        f"{WEEK_URL}/drafts",
        headers=MANAGER | key(),
        json={"base_version_id": current["id"], "copy_from_version_id": None},
    ).json()
    published = client.post(
        f"/v2/schedule-versions/{draft['id']}/publish",
        headers=MANAGER | key(),
        json={"expected_base_version_id": current["id"], "expected_revision": 1},
    )
    assert published.status_code == 200, published.text
    first = outbox_relay.relay_once()
    assert first["events"] >= 1 and first["deliveries"] >= 1 and first["failed"] == 0
    inbox = client.get("/v2/me/notifications", params={"unread_only": True}, headers=STAFF).json()["items"]
    mine = [n for n in inbox if n["payload"].get("version_id") == draft["id"]]
    assert len(mine) == 1 and mine[0]["topic"] == "schedule.published"
    assert mine[0]["title"].startswith("Your schedule for the week of")
    assert outbox_relay.relay_once()["events"] == 0  # nothing left; nothing delivered twice
    sql("UPDATE outbox_events SET published_at = NULL WHERE aggregate_id = :v", v=draft["id"])
    redelivered = outbox_relay.relay_once()  # a crash before marking published: retried, deduplicated
    assert redelivered["events"] == 1
    again = client.get("/v2/me/notifications", headers=STAFF).json()["items"]
    assert sum(1 for n in again if n["payload"].get("version_id") == draft["id"]) == 1

    read = client.post(f"/v2/me/notifications/{mine[0]['id']}/read", headers=STAFF).json()
    assert read["read_at"] is not None
    assert client.post(f"/v2/me/notifications/{mine[0]['id']}/read", headers=STAFF).json() == read
    assert client.post(f"/v2/me/notifications/{mine[0]['id']}/read", headers=MANAGER).status_code == 404
    unread = client.get("/v2/me/notifications", params={"unread_only": True}, headers=STAFF).json()["items"]
    assert mine[0]["id"] not in {n["id"] for n in unread}


def test_a_finished_repair_reaches_the_outlets_managers(client: TestClient) -> None:
    drain()
    current = client.get(WEEK_URL, headers=MANAGER).json()["current_version"]
    target = next(s for s in current["shifts"] if s["employee_id"] and not s["locked"])
    start = datetime.fromisoformat(target["start_at"])
    reported = client.post(
        "/v2/absences",
        headers=MANAGER | key(),
        json={
            "employee_id": target["employee_id"],
            "start_at": (start - timedelta(hours=1)).isoformat(),
            "end_at": target["end_at"],
            "kind": "sick",
            "status": "confirmed",
            "reason": None,
        },
    ).json()
    while worker.run_once() is not None:
        pass
    outbox_relay.relay_once()
    titles = [n["title"] for n in client.get("/v2/me/notifications", headers=MANAGER).json()["items"]]
    assert "An absence was confirmed; a repair is being prepared." in titles
    assert any(t.startswith("A repair") for t in titles)
    assert any(
        t.startswith("A repair")
        for t in (n["title"] for n in client.get("/v2/me/notifications", headers=OWNER).json()["items"])
    )
    assert reported["repair_run_ids"]


def test_a_failing_event_backs_off_without_blocking_others(client: TestClient) -> None:
    drain()
    org = sql("SELECT org_id FROM outbox_events LIMIT 1")[0][0]
    bad = uuid.uuid4()
    sql(
        "INSERT INTO outbox_events (id, org_id, topic, aggregate_type, aggregate_id, payload) "
        "VALUES (:id, :org, 'schedule.published', 'schedule_version', :id, "
        "'{\"schedule_id\": \"nope\"}'::jsonb)",
        id=bad,
        org=org,
    )
    result = outbox_relay.relay_once()
    assert result["failed"] == 1
    attempts, next_at, error = sql(
        "SELECT attempts, next_attempt_at, last_error FROM outbox_events WHERE id = :id", id=bad
    )[0]
    assert attempts == 1 and next_at > datetime.now(UTC) and error
    assert outbox_relay.relay_once()["events"] == 0  # not retried before its backoff
    sql("DELETE FROM outbox_events WHERE id = :id", id=bad)


def test_the_relay_role_is_least_privilege(client: TestClient) -> None:
    engine = relay_engine()
    assert engine.url.username == "shiftpilot_relay"
    with engine.connect() as conn:
        conn.execute(text("SELECT id, outlet_id FROM employees LIMIT 1"))  # the only employee columns
    for statement in (
        "SELECT name, hourly_rate FROM employees",
        "DELETE FROM outbox_events",
        "UPDATE schedule_versions SET reason = 'x'",
        "SELECT * FROM employee_availability",
    ):
        with engine.connect() as conn, pytest.raises(ProgrammingError, match="permission denied"):
            conn.execute(text(statement))
