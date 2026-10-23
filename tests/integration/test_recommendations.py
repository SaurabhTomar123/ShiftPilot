"""A4.5: POST /v2/recommendations/replacements (architecture v4 sections 11, 46)."""

from __future__ import annotations

import uuid

import pytest

from tests.integration.test_api_v2 import IND, MANAGER, OWNER, STAFF, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
URL = "/v2/recommendations/replacements"


def published(c) -> dict:  # type: ignore[no-untyped-def, type-arg]
    return c.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]


def test_ranked_replacements_are_valid_and_write_nothing(client) -> None:  # type: ignore[no-untyped-def]
    version = published(client)
    target = next(sh for sh in version["shifts"] if sh["employee_id"] and not sh["locked"])
    body = {"version_id": version["id"], "logical_shift_id": target["logical_shift_id"]}
    r = client.post(URL, headers=MANAGER, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["basis"] == "direct_assignment" and out["vacating_employee_id"] == target["employee_id"]
    assert out["recommendations"] and out["considered"] >= out["eligible"] >= len(out["recommendations"])
    assert [x["rank"] for x in out["recommendations"]] == list(range(1, len(out["recommendations"]) + 1))
    best = out["recommendations"][0]
    assert best["employee_id"] != target["employee_id"]
    assert best["edit"] == {
        "op": "update",
        "logical_shift_id": target["logical_shift_id"],
        "employee_id": best["employee_id"],
        "skill_id": None,
        "start_at": None,
        "end_at": None,
        "break_start_at": None,
        "break_minutes": None,
    }
    assert all(a["status"] == "rejected" and any(not f["ok"] for f in a["reasons"]) for a in out["rejected"])
    assert published(client)["id"] == version["id"]  # read-only


def test_permissions_and_validation(client) -> None:  # type: ignore[no-untyped-def]
    version = published(client)
    target = version["shifts"][0]
    body = {"version_id": version["id"], "logical_shift_id": target["logical_shift_id"]}
    assert client.post(URL, headers=STAFF, json=body).status_code == 403
    r = client.post(URL, headers=MANAGER, json={**body, "include_other_outlets": True})
    assert r.status_code == 403 and error_code(r) == "permission_denied"
    assert client.post(URL, headers=OWNER, json={**body, "include_other_outlets": True}).status_code == 200
    r = client.post(URL, headers=MANAGER, json={**body, "logical_shift_id": str(uuid.uuid4())})
    assert r.status_code == 422 and error_code(r) == "validation_failed"
    assert (
        client.post(URL, headers=MANAGER, json={**body, "version_id": str(uuid.uuid4())}).status_code == 404
    )
