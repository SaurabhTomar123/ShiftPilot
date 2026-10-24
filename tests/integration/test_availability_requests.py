"""A4.8: availability-change requests (architecture v4 section 29)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scheduling import worker
from seed.world import IST, uid
from tests.integration.test_api_v2 import IND, MANAGER, RAVI, STAFF, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
NEXT = (date.fromisoformat(WEEK) + timedelta(days=7)).isoformat()
NEXT_URL = f"/v2/outlets/{IND}/schedules/{NEXT}"
AVAILABILITY = f"/v2/employees/{RAVI}/availability"


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


@pytest.fixture(scope="module")
def ravis_shift(client: TestClient) -> dict[str, Any]:
    """Publish next week and return one of Ravi's shifts in it."""
    r = client.post(
        f"{NEXT_URL}/generate",
        headers=MANAGER | key(),
        json={"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 3},
    )
    assert r.status_code == 202, r.text
    worker.run_once()
    run = client.get(f"/v2/optimization-runs/{r.json()['id']}", headers=MANAGER).json()
    candidate = run["candidates"][0]["id"]
    first = client.post(f"/v2/optimization-candidates/{candidate}/select", headers=MANAGER | key()).json()
    shifts = first["shifts"]
    if not any(sh["employee_id"] == RAVI for sh in shifts):
        # Give Ravi one Grill shift on a day he is available (not Tuesday or Sunday) and not working.
        grill = [
            sh
            for sh in shifts
            if sh["skill_id"] == str(uid("skill", "Grill"))
            and datetime.fromisoformat(sh["start_at"]).astimezone(IST).weekday() not in (1, 6)
        ]
        for sh in grill:
            edited = client.post(
                f"/v2/schedule-versions/{first['id']}/edits",
                headers=MANAGER,
                json={
                    "expected_revision": first["revision"],
                    "edits": [
                        {"op": "update", "logical_shift_id": sh["logical_shift_id"], "employee_id": RAVI}
                    ],
                },
            )
            if edited.status_code == 200 and edited.json()["validation"]["hard_violations"] == 0:
                first = edited.json()
                break
    pub = client.post(
        f"/v2/schedule-versions/{first['id']}/publish",
        headers=MANAGER | key(),
        json={"expected_base_version_id": None, "expected_revision": first["revision"]},
    )
    assert pub.status_code == 200, pub.text
    version = client.get(NEXT_URL, headers=MANAGER).json()["current_version"]
    return next(sh for sh in version["shifts"] if sh["employee_id"] == RAVI)


def without_weekday(windows: list[dict[str, Any]], weekday: int) -> list[dict[str, Any]]:
    return [w for w in windows if w["weekday"] != weekday]


def test_the_preview_shows_what_breaks_and_only_acceptance_changes_availability(
    client: TestClient, ravis_shift: dict[str, Any]
) -> None:
    weekday = datetime.fromisoformat(ravis_shift["start_at"]).astimezone(IST).weekday()
    current = client.get(AVAILABILITY, headers=MANAGER).json()
    proposed = without_weekday(current["windows"], weekday)
    r = client.post(
        "/v2/me/availability-requests",
        headers=STAFF,
        json={"base_revision": current["revision"], "windows": proposed, "note": "Evening classes"},
    )
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending" and req["current"] == current["windows"]
    assert ravis_shift["logical_shift_id"] in {a["logical_shift_id"] for a in req["affected"]}
    assert client.get(AVAILABILITY, headers=MANAGER).json() == current  # nothing changed yet
    dup = client.post(
        "/v2/me/availability-requests",
        headers=STAFF,
        json={"base_revision": current["revision"], "windows": proposed},
    )
    assert dup.status_code == 409

    assert client.post(f"/v2/availability-requests/{req['id']}/accept", headers=STAFF).status_code == 403
    pending = client.get(
        f"/v2/outlets/{IND}/availability-requests", headers=MANAGER, params={"status": "pending"}
    )
    assert req["id"] in {x["id"] for x in pending.json()["items"]}
    done = client.post(f"/v2/availability-requests/{req['id']}/accept", headers=MANAGER).json()
    assert done["status"] == "accepted" and done["affected"] == req["affected"]
    now = client.get(AVAILABILITY, headers=MANAGER).json()
    assert now["revision"] == current["revision"] + 1
    assert all(w["weekday"] != weekday for w in now["windows"])
    # The published shift on that day is now invalid until the manager finds cover.
    cover = client.post(
        "/v2/recommendations/replacements",
        headers=MANAGER,
        json={
            "version_id": client.get(NEXT_URL, headers=MANAGER).json()["current_version"]["id"],
            "logical_shift_id": ravis_shift["logical_shift_id"],
        },
    )
    assert cover.status_code == 200 and RAVI not in {
        x["employee_id"] for x in cover.json()["recommendations"]
    }


def test_a_request_overtaken_by_a_manager_edit_is_stale(
    client: TestClient, ravis_shift: dict[str, Any]
) -> None:
    current = client.get(AVAILABILITY, headers=MANAGER).json()
    r = client.post(
        "/v2/me/availability-requests",
        headers=STAFF,
        json={"base_revision": current["revision"], "windows": current["windows"][:-1]},
    )
    assert r.status_code == 201, r.text
    edited = client.put(
        AVAILABILITY,
        headers=MANAGER,
        json={"base_revision": current["revision"], "windows": current["windows"]},
    )
    assert edited.status_code == 200
    stale = client.post(f"/v2/availability-requests/{r.json()['id']}/accept", headers=MANAGER)
    assert stale.status_code == 409 and error_code(stale) == "stale_version"
    assert (
        client.post(f"/v2/availability-requests/{r.json()['id']}/cancel", headers=STAFF).json()["status"]
        == "cancelled"
    )
    assert (
        client.post(
            "/v2/me/availability-requests", headers=MANAGER, json={"base_revision": 1, "windows": []}
        ).status_code
        == 403
    )
