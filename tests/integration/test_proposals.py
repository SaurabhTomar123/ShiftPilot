"""A3.4 acceptance: proposals and the four publication outcomes (architecture v3 section 31)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from db.session import admin_engine
from tests.integration.test_api_v2 import IND, MANAGER, STAFF, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
WEEK_URL = f"/v2/outlets/{IND}/schedules/{WEEK}"


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def sql(statement: str, **params: Any) -> Any:
    with admin_engine().begin() as conn:
        result = conn.execute(text(statement), params)
        return result.all() if result.returns_rows else result.rowcount


def current(c: TestClient) -> dict[str, Any]:
    return dict(c.get(WEEK_URL, headers=MANAGER).json()["current_version"])


def draft(c: TestClient) -> dict[str, Any]:
    r = c.post(
        f"{WEEK_URL}/drafts",
        headers=MANAGER | key(),
        json={"base_version_id": current(c)["id"], "copy_from_version_id": None},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def propose(c: TestClient, d: dict[str, Any]) -> dict[str, Any]:
    r = c.post(
        "/v2/proposals",
        headers=MANAGER | key(),
        json={"draft_version_id": d["id"], "expected_revision": d["revision"]},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def approve(
    c: TestClient, p: dict[str, Any], acknowledge: bool = False, k: dict[str, str] | None = None
) -> Any:
    return c.post(
        f"/v2/proposals/{p['id']}/approve",
        headers=MANAGER | (k or key()),
        json={"acknowledge_changes": acknowledge},
    )


def test_published_and_replayed(client: TestClient) -> None:
    before = current(client)
    p = propose(client, draft(client))
    assert p["status"] == "pending" and p["base_version_id"] == before["id"]
    assert p["metrics_at_proposal"] == before["metrics"]
    k = key()
    r = approve(client, p, k=k)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "published" and body["proposal"]["status"] == "approved"
    assert body["superseded_version_id"] == before["id"]
    assert current(client)["id"] == p["draft_version_id"]
    assert approve(client, p, k=k).json() == body  # a double click publishes once
    again = approve(client, p)
    assert again.status_code == 409 and again.json()["error"]["details"]["status"] == "approved"
    assert sql("SELECT count(*) FROM audit_log WHERE action = 'PROPOSAL_APPROVED'")[0][0] == 1


def test_stale_when_someone_published_first_or_the_draft_was_edited(client: TestClient) -> None:
    first, second = propose(client, draft(client)), propose(client, draft(client))
    assert approve(client, first).json()["outcome"] == "published"
    stale = approve(client, second).json()
    assert stale["outcome"] == "stale" and stale["proposal"]["status"] == "stale"
    assert stale["current_version_id"] == first["draft_version_id"]
    assert "changed while you were reviewing" in stale["message"]

    d = draft(client)
    p = propose(client, d)
    shift = next(sh for sh in d["shifts"] if not sh["locked"])
    edited = client.post(
        f"/v2/schedule-versions/{d['id']}/edits",
        headers=MANAGER,
        json={
            "expected_revision": d["revision"],
            "edits": [{"op": "remove", "logical_shift_id": shift["logical_shift_id"]}],
        },
    )
    assert edited.status_code == 200, edited.text
    after_edit = approve(client, p).json()
    assert after_edit["outcome"] == "stale" and "edited after it was proposed" in after_edit["message"]
    assert sql("SELECT count(*) FROM outbox_events WHERE topic = 'proposal.stale'")[0][0] == 2


def test_invalid_when_a_current_fact_breaks_the_plan(client: TestClient) -> None:
    d = draft(client)
    p = propose(client, d)
    shift = next(sh for sh in d["shifts"] if sh["employee_id"] and not sh["locked"])
    start = datetime.fromisoformat(shift["start_at"])
    absence = client.post(
        "/v2/absences",
        headers=MANAGER | key(),
        json={
            "employee_id": shift["employee_id"],
            "start_at": (start - timedelta(hours=1)).isoformat(),
            "end_at": shift["end_at"],
            "kind": "sick",
            "status": "confirmed",
            "reason": None,
        },
    )
    assert absence.status_code == 201, absence.text
    try:
        body = approve(client, p).json()
        assert body["outcome"] == "invalid" and body["proposal"]["status"] == "failed"
        assert any(
            v["code"] == "absent" and shift["logical_shift_id"] in v["logical_shift_ids"]
            for v in body["violations"]
        )
        assert current(client)["id"] != d["id"]
    finally:  # later tests in this module share the database
        cancel = {"status": "cancelled"}
        client.patch(f"/v2/absences/{absence.json()['absence']['id']}", headers=MANAGER, json=cancel)


def test_changed_needs_acknowledgement(client: TestClient) -> None:
    d = draft(client)
    p = propose(client, d)
    rostered = sorted({sh["employee_id"] for sh in d["shifts"] if sh["employee_id"]})
    sql(
        "UPDATE employees SET hourly_rate = hourly_rate * 2 WHERE id = ANY(:ids)",
        ids=[uuid.UUID(e) for e in rostered],
    )
    try:
        changed = approve(client, p).json()
        assert changed["outcome"] == "changed" and changed["proposal"]["status"] == "pending"
        cost = next(x for x in changed["deltas"] if x["metric"] == "labour_cost")
        assert cost["after"] > cost["before"] and "Cost has risen by INR" in cost["message"]
        assert current(client)["id"] != d["id"]
        accepted = approve(client, p, acknowledge=True).json()
        assert accepted["outcome"] == "published" and current(client)["id"] == d["id"]
    finally:
        sql(
            "UPDATE employees SET hourly_rate = hourly_rate / 2 WHERE id = ANY(:ids)",
            ids=[uuid.UUID(e) for e in rostered],
        )


def test_reject_and_staff(client: TestClient) -> None:
    d = draft(client)
    p = propose(client, d)
    assert client.get(f"/v2/proposals/{p['id']}", headers=MANAGER).json() == p
    assert client.get(f"/v2/proposals/{p['id']}", headers=STAFF).status_code == 403
    staff = client.post(f"/v2/proposals/{p['id']}/approve", headers=STAFF | key(), json={})
    assert staff.status_code == 403
    rejected = client.post(f"/v2/proposals/{p['id']}/reject", headers=MANAGER)
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert client.post(f"/v2/proposals/{p['id']}/reject", headers=MANAGER).json()["status"] == "rejected"
    late = approve(client, p)
    assert late.status_code == 409 and error_code(late) == "conflict"
    stale_revision = client.post(
        "/v2/proposals", headers=MANAGER | key(), json={"draft_version_id": d["id"], "expected_revision": 99}
    )
    assert stale_revision.status_code == 409 and error_code(stale_revision) == "stale_version"
    assert client.get(f"/v2/proposals/{uuid.uuid4()}", headers=MANAGER).status_code == 404
