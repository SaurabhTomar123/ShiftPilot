"""A4.8: demand forecasting and staffing proposals (architecture v4 sections 21, 22, 37)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jobs import forecast_worker
from tests.integration.test_api_v2 import IND, MANAGER, STAFF, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
NEXT = (date.fromisoformat(WEEK) + timedelta(days=7)).isoformat()
RUNS = f"/v2/outlets/{IND}/forecast-runs"
STAFFING = f"/v2/outlets/{IND}/schedules/{NEXT}/staffing-requirements"


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def staffing(c: TestClient) -> dict[str, Any]:
    r = c.get(f"/v2/outlets/{IND}/staffing-requirements", headers=MANAGER, params={"week_start": NEXT})
    assert r.status_code == 200, r.text
    return r.json()


def forecast(c: TestClient, week: str = NEXT) -> dict[str, Any]:
    r = c.post(RUNS, headers=MANAGER | key(), json={"week_start": week})
    assert r.status_code == 202, r.text
    assert forecast_worker.run_once() is not None
    return c.get(f"/v2/forecast-runs/{r.json()['id']}", headers=MANAGER).json()


def test_a_forecast_proposes_and_only_acceptance_changes_staffing(client: TestClient) -> None:
    # A manual override that every forecast must leave alone.
    week = staffing(client)
    target = next(i for i in week["intervals"] if i["source"] != "manual")
    target_key = (target["skill_id"], target["interval_start"])
    edited = [
        {**i, "source": "manual", "minimum_required": 5, "preferred_required": 5}
        if (i["skill_id"], i["interval_start"]) == target_key
        else i
        for i in week["intervals"]
    ]
    r = client.put(
        f"/v2/outlets/{IND}/staffing-requirements",
        headers=MANAGER,
        params={"week_start": NEXT},
        json={"base_demand_revision": week["demand_revision"], "intervals": edited},
    )
    assert r.status_code == 200, r.text
    before = staffing(client)

    run = forecast(client)
    assert run["job_state"] == "succeeded" and run["quality"] == "passed", run
    assert run["metrics"]["wape"] <= run["metrics"]["thresholds"]["max_wape"] and run["points"]
    assert all(p["lower"] <= p["predicted"] <= p["upper"] for p in run["points"])
    assert staffing(client) == before  # advisory: a forecast changes nothing by itself

    proposal = client.get(f"/v2/staffing-requirement-proposals/{run['proposal_id']}", headers=MANAGER).json()
    assert proposal["status"] == "pending" and proposal["changes"]["manual_kept"] >= 1
    explained = [r for r in proposal["rows"] if r["source"] == "forecast"]
    assert explained and all(r["explanation"]["forecast_orders"] >= 0 for r in explained)
    assert target_key not in {(r["skill_id"], r["interval_start"]) for r in proposal["rows"]}

    # A second forecast proposes against the same demand revision; accepting the first makes it stale.
    second = forecast(client)
    accept = f"/v2/staffing-requirement-proposals/{proposal['id']}/accept"
    k = key()
    r = client.post(accept, headers=MANAGER | k)
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["demand_revision"] == before["demand_revision"] + 1
    kept = next(i for i in after["intervals"] if (i["skill_id"], i["interval_start"]) == target_key)
    assert kept["source"] == "manual" and kept["minimum_required"] == 5
    assert any(i["source"] == "forecast" for i in after["intervals"])
    assert client.post(accept, headers=MANAGER | k).json() == after  # idempotent replay
    assert client.post(accept, headers=MANAGER | key()).status_code == 409  # already accepted

    stale = client.post(
        f"/v2/staffing-requirement-proposals/{second['proposal_id']}/accept", headers=MANAGER | key()
    )
    assert stale.status_code == 409 and error_code(stale) == "stale_version"
    rejected = client.post(
        f"/v2/staffing-requirement-proposals/{second['proposal_id']}/reject", headers=MANAGER
    )
    assert rejected.json()["status"] == "rejected"


def test_not_enough_history_fails_the_run_not_the_week(client: TestClient) -> None:
    early = (date.fromisoformat(WEEK) - timedelta(weeks=3)).isoformat()
    run = forecast(client, early)
    assert run["job_state"] == "failed" and run["proposal_id"] is None
    assert run["error"]["details"]["reason"] == "NOT_ENOUGH_HISTORY"


def test_idempotency_and_permissions(client: TestClient) -> None:
    k = key()
    first = client.post(RUNS, headers=MANAGER | k, json={"week_start": NEXT})
    assert (
        client.post(RUNS, headers=MANAGER | k, json={"week_start": NEXT}).json()["id"] == first.json()["id"]
    )
    other = client.post(RUNS, headers=MANAGER | k, json={"week_start": WEEK})
    assert other.status_code == 409 and error_code(other) == "idempotency_conflict"
    busy = client.post(RUNS, headers=MANAGER | key(), json={"week_start": NEXT})
    assert busy.status_code == 409 and error_code(busy) == "run_in_progress"
    forecast_worker.run_once()
    assert client.post(RUNS, headers=STAFF | key(), json={"week_start": NEXT}).status_code == 403
