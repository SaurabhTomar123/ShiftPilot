"""B4.5 acceptance (decision 12, architecture v3 sections 12 and 31): a cross-outlet repair publishes
safely. The borrowed employee's new shift is checked against the whole organization's live roster at
publication, under per-employee locks, so the lending outlet cannot then double-book them."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scheduling import worker
from seed.world import IST, SKILL
from tests.integration.test_api_v2 import IND, KOR, MANAGER, OWNER, WEEK, client

pytestmark = pytest.mark.integration
__all__ = ["client"]
WEDNESDAY = date.fromisoformat(WEEK) + timedelta(days=2)
GRILL = str(SKILL["Grill"])


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def drain() -> None:
    while worker.run_once() is not None:
        pass


def week(c: TestClient, outlet: str) -> dict[str, Any]:
    return dict(c.get(f"/v2/outlets/{outlet}/schedules/{WEEK}", headers=OWNER).json()["current_version"])


def on_wednesday(shift: dict[str, Any]) -> bool:
    return datetime.fromisoformat(shift["start_at"]).astimezone(IST).date() == WEDNESDAY


def test_a_borrowed_cook_is_published_once_and_cannot_be_double_booked(client: TestClient) -> None:
    ind = week(client, IND)
    cooks = sorted({s["employee_id"] for s in ind["shifts"] if s["skill_id"] == GRILL and s["employee_id"]})
    whole_day = datetime.combine(WEDNESDAY, datetime.min.time(), IST)
    absences = []
    for cook in cooks:  # every Indiranagar grill cook is off sick on Wednesday
        r = client.post(
            "/v2/absences",
            headers=MANAGER | key(),
            json={
                "employee_id": cook,
                "start_at": whole_day.isoformat(),
                "end_at": (whole_day + timedelta(days=1)).isoformat(),
                "kind": "sick",
                "status": "confirmed",
                "reason": None,
            },
        )
        assert r.status_code == 201, r.text
        absences.append(r.json()["absence"]["id"])
    drain()  # the automatic home-outlet repairs cannot keep minimum staffing

    run = client.post(
        f"/v2/outlets/{IND}/schedules/{WEEK}/repair",
        headers=OWNER | key(),
        json={
            "absence_id": absences[0],
            "base_version_id": ind["id"],
            "allow_cross_outlet": True,
            "time_limit_seconds": 8,
        },
    ).json()
    drain()
    done = client.get(f"/v2/optimization-runs/{run['id']}", headers=OWNER).json()
    assert done["job_state"] == "succeeded" and done["candidates"], (
        done["repair_stages"],
        done["infeasibility"],
    )
    assert next(s for s in done["repair_stages"] if s["result"] == "selected")["stage"] in (
        "other_outlets",
        "overtime",
    )
    best = done["candidates"][0]
    assert best["disruption"]["cross_outlet_moves"] >= 1

    draft = client.post(f"/v2/optimization-candidates/{best['id']}/select", headers=OWNER | key()).json()
    borrowed = next(
        s
        for s in draft["shifts"]
        if on_wednesday(s) and s["skill_id"] == GRILL and s["employee_id"] and s["employee_id"] not in cooks
    )
    proposal = client.post(
        "/v2/proposals", headers=OWNER | key(), json={"draft_version_id": draft["id"], "expected_revision": 1}
    ).json()
    approved = client.post(f"/v2/proposals/{proposal['id']}/approve", headers=OWNER | key(), json={}).json()
    assert approved["outcome"] == "published", approved

    # Koramangala now tries to roster the same person over the same hours: publication refuses it.
    kor = week(client, KOR)
    kor_draft = client.post(
        f"/v2/outlets/{KOR}/schedules/{WEEK}/drafts",
        headers=OWNER | key(),
        json={"base_version_id": kor["id"], "copy_from_version_id": None},
    ).json()
    clash = {
        "op": "add",
        "employee_id": borrowed["employee_id"],
        "skill_id": GRILL,
        "start_at": borrowed["start_at"],
        "end_at": borrowed["end_at"],
        "break_minutes": 0,
    }
    preview = client.post(
        f"/v2/schedule-versions/{kor_draft['id']}/edits/preview",
        headers=OWNER,
        json={"expected_revision": 1, "edits": [clash]},
    ).json()
    assert any(v["code"] == "overlap" for v in preview["validation"]["violations"])
    applied = client.post(
        f"/v2/schedule-versions/{kor_draft['id']}/edits",
        headers=OWNER,
        json={"expected_revision": 1, "edits": [clash]},
    ).json()
    refused = client.post(
        f"/v2/schedule-versions/{kor_draft['id']}/publish",
        headers=OWNER | key(),
        json={"expected_base_version_id": kor["id"], "expected_revision": applied["revision"]},
    )
    assert refused.status_code == 422
    assert any(v["code"] == "overlap" for v in refused.json()["error"]["details"]["violations"])
    assert week(client, KOR)["id"] == kor["id"]
