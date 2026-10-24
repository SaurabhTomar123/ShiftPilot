"""A4.8: live progress over server-sent events (architecture v4 section 49)."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.v2 import events
from scheduling import worker
from tests.integration.test_api_v2 import IND, MANAGER, NW_OWNER, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
NEXT = (date.fromisoformat(WEEK) + timedelta(days=7)).isoformat()


def read(c: TestClient, url: str) -> tuple[str, list[tuple[str, dict[str, Any]]]]:
    out = []
    with c.stream("GET", url, headers=MANAGER) as r:
        assert r.status_code == 200, r.read()
        kind = r.headers["content-type"]
        event = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: ") and event:
                out.append((event, json.loads(line[6:])))
    return kind, out


def test_a_finished_run_streams_its_state_then_ends(client: TestClient) -> None:
    r = client.post(
        f"/v2/outlets/{IND}/schedules/{NEXT}/generate",
        headers=MANAGER | {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"},
        json={"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 3},
    )
    assert r.status_code == 202, r.text
    worker.run_once()
    kind, got = read(client, f"/v2/optimization-runs/{r.json()['id']}/events")
    assert kind.startswith("text/event-stream")
    assert [e for e, _ in got] == ["run", "end"]
    assert got[0][1] == client.get(f"/v2/optimization-runs/{r.json()['id']}", headers=MANAGER).json()
    assert got[1][1] == {"reason": "finished"}


def test_errors_are_json_envelopes_before_any_stream(client: TestClient) -> None:
    missing = client.get(f"/v2/optimization-runs/{uuid.uuid4()}/events", headers=MANAGER)
    assert missing.status_code == 404 and error_code(missing) == "not_found"
    assert client.get(f"/v2/forecast-runs/{uuid.uuid4()}/events", headers=MANAGER).status_code == 404
    other_org = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}/events", headers=NW_OWNER)
    assert other_org.status_code in (403, 404)


def test_the_schedule_stream_reports_the_published_version(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(events, "MAX_SECONDS", 0.2)
    _, got = read(client, f"/v2/outlets/{IND}/schedules/{WEEK}/events")
    current = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]
    assert got[0] == ("version", {**got[0][1], "current_version_id": current["id"]})
    assert got[-1] == ("end", {"reason": "reconnect"})
