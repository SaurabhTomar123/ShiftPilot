"""The absence and repair fixtures Codex builds against, checked against the live API: same shape, same
statuses, same error messages (closes the caveat in the 3.16 handoff)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scheduling import worker
from tests.integration.test_api_v2 import IND, MANAGER, RAVI, STAFF, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "v2" / "fixtures"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="ascii"))["response"]


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def same_shape(live: Any, fixed: Any, path: str = "$") -> None:
    """Same keys at every level (lists compared by their first element)."""
    if isinstance(fixed, dict):
        assert isinstance(live, dict) and set(live) == set(fixed), f"{path}: {sorted(set(live) ^ set(fixed))}"
        for k in fixed:
            if k != "facts":  # free-form evidence whose keys depend on the violation or reason code
                same_shape(live[k], fixed[k], f"{path}.{k}")
    elif isinstance(fixed, list) and fixed and live:
        same_shape(live[0], fixed[0], f"{path}[0]")


def ravi_shift(c: TestClient) -> dict[str, Any]:
    week = c.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]
    return next(sh for sh in week["shifts"] if sh["employee_id"] == RAVI and not sh["locked"])


def leave(c: TestClient, shift: dict[str, Any], hours: int = 0) -> Any:
    start = datetime.fromisoformat(shift["start_at"]) + timedelta(hours=hours)
    return c.post(
        "/v2/absences",
        headers=STAFF | key(),
        json={
            "employee_id": RAVI,
            "start_at": start.isoformat(),
            "end_at": shift["end_at"],
            "kind": "leave",
            "status": "requested",
            "reason": "Family function",
        },
    )


def test_requested_leave_lifecycle_matches_its_fixtures(client: TestClient) -> None:
    shift = ravi_shift(client)
    r = leave(client, shift)
    assert r.status_code == 201, r.text
    requested = r.json()
    fixed = fixture("absence.report.requested")["body"]
    same_shape(requested, fixed)
    assert requested["absence"]["status"] == "requested" and requested["affected"]
    assert requested["repair_suggested"] is False and requested["repair_run_ids"] == []

    confirmed = client.patch(
        f"/v2/absences/{requested['absence']['id']}", headers=MANAGER, json={"status": "confirmed"}
    )
    assert confirmed.status_code == 200, confirmed.text
    fixed = fixture("absence.update.requested.confirm")["body"]
    same_shape(confirmed.json(), fixed)
    assert confirmed.json()["repair_suggested"] is True and confirmed.json()["repair_run_ids"]

    withdraw = client.patch(
        f"/v2/absences/{requested['absence']['id']}", headers=STAFF, json={"status": "cancelled"}
    )
    expected = fixture("absence.update.withdraw_conflict")
    assert withdraw.status_code == expected["status"] and error_code(withdraw) == "conflict"
    assert withdraw.json()["error"]["message"] == expected["body"]["error"]["message"]

    # The repair the confirmation started: candidate detail and select match the repair fixtures.
    while worker.run_once() is not None:
        pass
    run = client.get(f"/v2/optimization-runs/{confirmed.json()['repair_run_ids'][0]}", headers=MANAGER).json()
    assert run["kind"] == "repair" and run["candidates"], run
    detail = client.get(f"/v2/optimization-candidates/{run['candidates'][0]['id']}", headers=MANAGER)
    same_shape(detail.json(), fixture("candidate.detail.repair")["body"])
    assert detail.json()["base_version_id"] == run["base_version_ids"][0] and detail.json()["diff"]["changed"]
    selected = client.post(
        f"/v2/optimization-candidates/{run['candidates'][0]['id']}/select", headers=MANAGER | key()
    )
    assert selected.status_code == fixture("candidate.select.repair")["status"], selected.text
    same_shape(selected.json(), fixture("candidate.select.repair")["body"])
    assert (
        selected.json()["source"] == "repair"
        and selected.json()["base_version_id"] == run["base_version_ids"][0]
    )


def test_reject_cancel_and_closed_match_their_fixtures(client: TestClient) -> None:
    shift = ravi_shift(client)
    first = leave(client, shift, hours=1).json()
    rejected = client.patch(
        f"/v2/absences/{first['absence']['id']}", headers=MANAGER, json={"status": "rejected"}
    )
    same_shape(rejected.json(), fixture("absence.update.requested.reject")["body"])
    assert rejected.json()["absence"]["status"] == "rejected" and rejected.json()["affected"] == []

    closed = client.patch(
        f"/v2/absences/{first['absence']['id']}", headers=MANAGER, json={"status": "confirmed"}
    )
    expected = fixture("absence.update.already_closed")
    assert closed.status_code == expected["status"]
    assert closed.json()["error"]["message"] == expected["body"]["error"]["message"]

    second = leave(client, shift, hours=2).json()
    cancelled = client.patch(
        f"/v2/absences/{second['absence']['id']}", headers=STAFF, json={"status": "cancelled"}
    )
    same_shape(cancelled.json(), fixture("absence.update.requested.cancel")["body"])
    assert cancelled.json()["absence"]["status"] == "cancelled"


def test_find_cover_through_a_draft_matches_its_fixtures(client: TestClient) -> None:
    week = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]
    shift = next(sh for sh in week["shifts"] if sh["employee_id"] and not sh["locked"])
    rec = client.post(
        "/v2/recommendations/replacements",
        headers=MANAGER,
        json={"version_id": week["id"], "logical_shift_id": shift["logical_shift_id"]},
    )
    assert rec.status_code == 200 and rec.json()["recommendations"], rec.text
    edit = rec.json()["recommendations"][0]["edit"]

    stale = client.post(
        f"/v2/outlets/{IND}/schedules/{WEEK}/drafts",
        headers=MANAGER | key(),
        json={"base_version_id": str(uuid.uuid4()), "copy_from_version_id": None},
    )
    expected = fixture("draft.create.cover.stale_base")
    assert stale.status_code == expected["status"]
    assert stale.json()["error"]["message"] == expected["body"]["error"]["message"]

    draft = client.post(
        f"/v2/outlets/{IND}/schedules/{WEEK}/drafts",
        headers=MANAGER | key(),
        json={"base_version_id": week["id"], "copy_from_version_id": None},
    )
    assert draft.status_code == 201, draft.text
    same_shape(draft.json(), fixture("draft.create.cover")["body"])
    url = f"/v2/schedule-versions/{draft.json()['id']}/edits"
    preview = client.post(f"{url}/preview", headers=MANAGER, json={"expected_revision": 1, "edits": [edit]})
    assert preview.status_code == 200, preview.text
    same_shape(preview.json(), fixture("edits.preview.cover")["body"])
    # The cover adds no hard violation (the week may already carry one from an earlier test's absence).
    assert preview.json()["validation"]["hard_violations"] <= draft.json()["validation"]["hard_violations"]
    assert [c["kinds"] for c in preview.json()["changes"]] == [["reassigned"]]
    applied = client.post(url, headers=MANAGER | key(), json={"expected_revision": 1, "edits": [edit]})
    assert applied.status_code == 200 and applied.json()["revision"] == 2, applied.text
    same_shape(applied.json(), fixture("edits.apply.cover")["body"])
    again = client.post(url, headers=MANAGER | key(), json={"expected_revision": 1, "edits": [edit]})
    expected = fixture("edits.apply.cover.stale")
    assert (
        again.status_code == expected["status"] and again.json()["error"]["details"]["current_revision"] == 2
    )
