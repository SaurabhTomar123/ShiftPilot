"""A4.6: Scenario Lab (architecture v4 sections 23, 42). Hypothetical state is never operational state."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scheduling import worker
from seed.world import IST
from tests.integration.test_api_v2 import IND, MANAGER, STAFF, WEEK, client, error_code
from tests.integration.test_generation import sql

pytestmark = pytest.mark.integration
__all__ = ["client"]
MONDAY = date.fromisoformat(WEEK)
CREATE = f"/v2/outlets/{IND}/schedules/{WEEK}/scenarios"
FACT_TABLES = ("absences", "staffing_requirements", "scheduling_rules", "employee_availability")


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def facts() -> dict[str, int]:
    return {t: sql(f"SELECT count(*) FROM {t}")[0][0] for t in FACT_TABLES}  # noqa: S608 - fixed names


def published(c: TestClient) -> dict[str, Any]:
    return c.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]


def run_scenario(c: TestClient, scenario_id: str) -> dict[str, Any]:
    r = c.post(f"/v2/scenarios/{scenario_id}/run", headers=MANAGER | key(), json={"time_limit_seconds": 4})
    assert r.status_code == 202, r.text
    run_id = r.json()["id"]
    for _ in range(10):
        if worker.run_once() is None:
            break
    run = c.get(f"/v2/optimization-runs/{run_id}", headers=MANAGER).json()
    assert run["kind"] == "scenario" and run["scenario_id"] == scenario_id and run["job_state"] == "succeeded"
    return run


def test_a_what_if_never_touches_real_facts_and_converts_through_a_draft(client: TestClient) -> None:
    before = facts()
    version = published(client)
    worked = next(sh for sh in version["shifts"] if sh["employee_id"] and not sh["locked"])
    day = datetime.fromisoformat(worked["start_at"]).astimezone(IST).date()
    sick = {
        "type": "absence",
        "payload": {
            "employee_id": worked["employee_id"],
            "start_at": datetime(day.year, day.month, day.day, tzinfo=IST).isoformat(),
            "end_at": (datetime(day.year, day.month, day.day, tzinfo=IST) + timedelta(days=1)).isoformat(),
        },
    }
    busier = {"type": "demand_change", "payload": {"percent": 30, "weekdays": [5], "start_minute": 1080}}
    r = client.post(CREATE, headers=MANAGER, json={"title": "Sick day and a busy Saturday", "events": [sick]})
    assert r.status_code == 201, r.text
    sc = r.json()
    assert sc["status"] == "open" and sc["base_version_id"] == version["id"] and sc["baseline"] is None
    r = client.post(f"/v2/scenarios/{sc['id']}/events", headers=MANAGER, json=busier)
    assert r.status_code == 201 and [e["sequence"] for e in r.json()["events"]] == [1, 2]

    run = run_scenario(client, sc["id"])
    assert run["candidates"] and all(
        c["trace"]["summary"]["compared_to"] == "base_version" for c in run["candidates"]
    )
    view = client.get(f"/v2/scenarios/{sc['id']}", headers=MANAGER).json()
    assert view["latest_run_id"] == run["id"]
    # The current plan under the what-if: the absent person's shift breaks.
    assert view["baseline"]["hard_violations"] >= 1 and "absent" in view["baseline"]["violation_codes"]

    # Isolation: no fact table changed; the hypothetical absence exists nowhere.
    assert facts() == before
    hypothetical = sql(
        "SELECT count(*) FROM absences WHERE employee_id = :e AND start_at = :s",
        e=worked["employee_id"],
        s=sick["payload"]["start_at"],
    )
    assert hypothetical[0][0] == 0

    cand = run["candidates"][0]["id"]
    r = client.post(f"/v2/optimization-candidates/{cand}/select", headers=MANAGER | key())
    assert r.status_code == 409 and error_code(r) == "conflict"

    r = client.post(f"/v2/scenarios/{sc['id']}/convert", headers=MANAGER | key(), json={"candidate_id": cand})
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["source"] == "scenario"
    assert draft["base_version_id"] == version["id"] and draft["validation"]["hard_violations"] == 0
    assert published(client)["id"] == version["id"]  # nothing published
    assert facts() == before
    done = client.get(f"/v2/scenarios/{sc['id']}", headers=MANAGER).json()
    assert done["status"] == "converted" and done["converted_version_id"] == draft["id"]
    r = client.post(f"/v2/scenarios/{sc['id']}/events", headers=MANAGER, json=busier)
    assert r.status_code == 409
    client.post(f"/v2/schedule-versions/{draft['id']}/discard", headers=MANAGER | key())


def test_a_plan_that_only_works_under_the_assumptions_is_not_converted(client: TestClient) -> None:
    saturday = (MONDAY + timedelta(days=5)).isoformat()
    r = client.post(
        CREATE,
        headers=MANAGER,
        json={
            "title": "Closed Saturday",
            "events": [{"type": "outlet_closure", "payload": {"day": saturday}}],
        },
    )
    sc = r.json()
    run = run_scenario(client, sc["id"])
    assert run["candidates"]
    r = client.post(
        f"/v2/scenarios/{sc['id']}/convert",
        headers=MANAGER | key(),
        json={"candidate_id": run["candidates"][0]["id"]},
    )
    assert r.status_code == 409 and error_code(r) == "conflict"
    assert "minimum_coverage" in r.json()["error"]["details"]["violation_codes"]
    assert client.post(f"/v2/scenarios/{sc['id']}/discard", headers=MANAGER).json()["status"] == "discarded"


def test_events_are_validated_and_scenarios_are_for_managers(client: TestClient) -> None:
    bad = client.post(
        CREATE,
        headers=MANAGER,
        json={
            "title": "x",
            "events": [
                {
                    "type": "absence",
                    "payload": {
                        "employee_id": str(uuid.uuid4()),
                        "start_at": "2026-10-20T00:00:00+05:30",
                        "end_at": "2026-10-21T00:00:00+05:30",
                    },
                }
            ],
        },
    )
    assert bad.status_code == 422 and bad.json()["error"]["details"]["fields"][0]["path"][:3] == [
        "events",
        0,
        "payload",
    ]
    unknown = client.post(
        CREATE, headers=MANAGER, json={"title": "x", "events": [{"type": "weather", "payload": {}}]}
    )
    assert unknown.status_code == 422
    assert client.post(CREATE, headers=STAFF, json={"title": "x"}).status_code == 403
    listed = client.get(f"/v2/outlets/{IND}/scenarios", headers=MANAGER, params={"week_start": WEEK})
    assert listed.status_code == 200 and all(x["week_start"] == WEEK for x in listed.json()["items"])
