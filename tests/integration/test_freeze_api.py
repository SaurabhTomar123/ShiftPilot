"""A4.1 acceptance (architecture v4 section 13): run-scoped freeze sets on generate and repair."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scheduling import worker
from tests.integration.test_api_v2 import IND, MANAGER, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
WEEK_URL = f"/v2/outlets/{IND}/schedules/{WEEK}"


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def current(c: TestClient) -> dict[str, Any]:
    return dict(c.get(WEEK_URL, headers=MANAGER).json()["current_version"])


def generate(c: TestClient, base: str | None, freeze: dict[str, Any], week: str = WEEK) -> Any:
    return c.post(
        f"/v2/outlets/{IND}/schedules/{week}/generate",
        headers=MANAGER | key(),
        json={"strategy": "lowest_cost", "base_version_id": base, "time_limit_seconds": 4, "freeze": freeze},
    )


def test_a_frozen_employee_keeps_every_published_shift(client: TestClient) -> None:
    version = current(client)
    person = Counter(s["employee_id"] for s in version["shifts"] if s["employee_id"]).most_common(1)[0][0]
    theirs = {s["logical_shift_id"] for s in version["shifts"] if s["employee_id"] == person}
    run = generate(client, version["id"], {"employee_ids": [person]})
    assert run.status_code == 202, run.text
    assert set(run.json()["frozen_logical_shift_ids"]) == theirs
    while worker.run_once() is not None:
        pass
    done = client.get(f"/v2/optimization-runs/{run.json()['id']}", headers=MANAGER).json()
    assert done["candidates"], done
    for cand in done["candidates"]:
        diff = client.get(f"/v2/optimization-candidates/{cand['id']}", headers=MANAGER).json()["diff"]
        touched = {s["logical_shift_id"] for s in diff["changed"]} | set(diff["removed"])
        assert not touched & theirs


def test_bad_freezes_are_refused(client: TestClient) -> None:
    version = current(client)
    unknown = generate(client, version["id"], {"shift_ids": [str(uuid.uuid4())]})
    assert unknown.status_code == 422 and error_code(unknown) == "validation_failed"
    empty = generate(client, None, {"days": ["2026-11-02"]}, week="2026-11-02")
    assert empty.status_code == 422

    target = next(s for s in version["shifts"] if s["employee_id"] and not s["locked"])
    start = datetime.fromisoformat(target["start_at"])
    absence = client.post(
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
    repair = client.post(
        f"{WEEK_URL}/repair",
        headers=MANAGER | key(),
        json={
            "absence_id": absence["absence"]["id"],
            "base_version_id": version["id"],
            "time_limit_seconds": 3,
            "freeze": {"shift_ids": [target["logical_shift_id"]]},
        },
    )
    assert repair.status_code == 409 and error_code(repair) == "conflict"
    assert repair.json()["error"]["details"]["frozen_logical_shift_ids"] == [target["logical_shift_id"]]
