"""A4.8: employee shift requests (architecture v4 section 28). Every change ends in a manager decision
through the normal publication gate."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.auth import Role
from scheduling import worker
from seed.world import IST, uid
from tests.integration.test_api_v2 import IND, MANAGER, RAVI, STAFF, WEEK, client, error_code, token
from tests.integration.test_generation import sql

pytestmark = pytest.mark.integration
__all__ = ["client"]
NEXT = (date.fromisoformat(WEEK) + timedelta(days=7)).isoformat()
NEXT_URL = f"/v2/outlets/{IND}/schedules/{NEXT}"
ARJUN = str(uid("employee", "arjun"))
ARJUN_STAFF = token("staff_arjun", Role.STAFF, IND, ARJUN)
GRILL = str(uid("skill", "Grill"))


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def day(sh: dict[str, Any]) -> date:
    return datetime.fromisoformat(sh["start_at"]).astimezone(IST).date()


def current(c: TestClient) -> dict[str, Any]:
    return c.get(NEXT_URL, headers=MANAGER).json()["current_version"]


def publish_edits(c: TestClient, edits: list[dict[str, Any]]) -> dict[str, Any]:
    base = current(c)
    draft = c.post(
        f"{NEXT_URL}/drafts",
        headers=MANAGER | key(),
        json={"base_version_id": base["id"], "copy_from_version_id": None},
    ).json()
    edited = c.post(
        f"/v2/schedule-versions/{draft['id']}/edits",
        headers=MANAGER,
        json={"expected_revision": 1, "edits": edits},
    )
    assert edited.status_code == 200, edited.text
    r = c.post(
        f"/v2/schedule-versions/{draft['id']}/publish",
        headers=MANAGER | key(),
        json={"expected_base_version_id": base["id"], "expected_revision": edited.json()["revision"]},
    )
    assert r.status_code == 200, r.text
    return current(c)


@pytest.fixture(scope="module")
def week(client: TestClient) -> dict[str, Any]:
    """Next week generated and published, plus open Grill shifts on days Ravi is free."""
    sql(
        "INSERT INTO users (id, org_id, outlet_id, employee_id, name, phone, role, is_active) "
        "SELECT :u, org_id, outlet_id, id, 'Arjun Rao', '+919700209999', 'staff', true "
        "FROM employees WHERE id = :e",
        u=str(uid("user", "staff_arjun")),
        e=ARJUN,
    )
    r = client.post(
        f"{NEXT_URL}/generate",
        headers=MANAGER | key(),
        json={"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 3},
    )
    assert r.status_code == 202, r.text
    worker.run_once()
    run = client.get(f"/v2/optimization-runs/{r.json()['id']}", headers=MANAGER).json()
    draft = client.post(
        f"/v2/optimization-candidates/{run['candidates'][0]['id']}/select", headers=MANAGER | key()
    ).json()
    ravi_days = {day(sh) for sh in draft["shifts"] if sh["employee_id"] == RAVI}
    free = [
        sh
        for sh in draft["shifts"]
        if sh["skill_id"] == GRILL and day(sh) not in ravi_days and day(sh).weekday() not in (1, 6)
    ]
    assert free, "no Grill shift on a day Ravi is free"
    adds = [
        {
            "op": "add",
            "employee_id": None,
            "skill_id": sh["skill_id"],
            "start_at": sh["start_at"],
            "end_at": sh["end_at"],
            "break_start_at": sh["break_start_at"],
            "break_minutes": sh["break_minutes"],
        }
        for sh in {day(x): x for x in free}.values()
    ][:2]
    edited = client.post(
        f"/v2/schedule-versions/{draft['id']}/edits",
        headers=MANAGER,
        json={"expected_revision": 1, "edits": adds},
    )
    assert edited.status_code == 200, edited.text
    pub = client.post(
        f"/v2/schedule-versions/{draft['id']}/publish",
        headers=MANAGER | key(),
        json={"expected_base_version_id": None, "expected_revision": edited.json()["revision"]},
    )
    assert pub.status_code == 200, pub.text
    return current(client)


def test_claim_an_open_shift_and_the_manager_publishes_it(client: TestClient, week: dict[str, Any]) -> None:
    listed = client.get("/v2/me/open-shifts", headers=STAFF, params={"week_start": NEXT}).json()
    assert listed["items"], "Ravi should be eligible for an open Grill shift"
    assert all(f["ok"] for item in listed["items"] for f in item["reasons"])
    shift = listed["items"][0]["shift"]
    r = client.post(
        "/v2/me/shift-requests",
        headers=STAFF,
        json={"type": "open_shift_claim", "logical_shift_id": shift["logical_shift_id"]},
    )
    assert r.status_code == 201, r.text
    claim = r.json()
    assert claim["status"] == "pending_manager" and claim["base_version_id"] == week["id"]
    again = client.post(
        "/v2/me/shift-requests",
        headers=STAFF,
        json={"type": "open_shift_claim", "logical_shift_id": shift["logical_shift_id"]},
    )
    assert again.status_code == 409
    assert current(client)["id"] == week["id"]  # nothing published by the employee

    assert client.post(f"/v2/shift-requests/{claim['id']}/approve", headers=STAFF).status_code == 403
    pending = client.get(
        f"/v2/outlets/{IND}/shift-requests", headers=MANAGER, params={"status": "pending_manager"}
    ).json()
    assert claim["id"] in {x["id"] for x in pending["items"]}
    done = client.post(f"/v2/shift-requests/{claim['id']}/approve", headers=MANAGER).json()
    assert done["status"] == "approved" and done["published_version_id"]
    now = current(client)
    assert now["id"] == done["published_version_id"] and now["source"] == "request"
    taken = next(sh for sh in now["shifts"] if sh["logical_shift_id"] == shift["logical_shift_id"])
    assert taken["employee_id"] == RAVI
    assert client.post(f"/v2/shift-requests/{claim['id']}/approve", headers=MANAGER).status_code == 409


def test_a_giveaway_needs_a_taker_then_the_manager(client: TestClient, week: dict[str, Any]) -> None:
    now = current(client)
    arjun_days = {day(sh) for sh in now["shifts"] if sh["employee_id"] == ARJUN}
    mine = next(
        (
            sh
            for sh in now["shifts"]
            if sh["employee_id"] == RAVI
            and sh["skill_id"] == GRILL
            and day(sh) not in arjun_days
            and not sh["locked"]
        ),
        None,
    )
    if mine is None:
        pytest.skip("no Ravi Grill shift on a day Arjun is free")
    r = client.post(
        "/v2/me/shift-requests",
        headers=STAFF,
        json={
            "type": "giveaway",
            "logical_shift_id": mine["logical_shift_id"],
            "target_employee_id": ARJUN,
            "note": "Family visit",
        },
    )
    assert r.status_code == 201, r.text
    offer = r.json()
    assert offer["status"] == "open" and offer["target_employee_id"] == ARJUN
    assert offer["id"] in {
        x["id"] for x in client.get("/v2/me/shift-requests", headers=ARJUN_STAFF).json()["items"]
    }
    assert (
        client.post(f"/v2/shift-requests/{offer['id']}/accept", headers=STAFF).status_code == 409
    )  # own request
    taken = client.post(f"/v2/shift-requests/{offer['id']}/accept", headers=ARJUN_STAFF)
    assert taken.status_code == 200, taken.text
    assert taken.json()["status"] == "pending_manager"
    rejected = client.post(f"/v2/shift-requests/{offer['id']}/reject", headers=MANAGER).json()
    assert rejected["status"] == "rejected" and current(client)["id"] == now["id"]


def test_approval_reports_stale_when_the_week_moved(client: TestClient, week: dict[str, Any]) -> None:
    now = current(client)
    target = next(sh for sh in now["shifts"] if sh["employee_id"] == RAVI and not sh["locked"])
    offer = client.post(
        "/v2/me/shift-requests",
        headers=STAFF,
        json={"type": "giveaway", "logical_shift_id": target["logical_shift_id"]},
    )
    assert offer.status_code == 201, offer.text
    # The manager changes that very shift before anyone takes it.
    publish_edits(
        client, [{"op": "update", "logical_shift_id": target["logical_shift_id"], "employee_id": None}]
    )
    took = client.post(f"/v2/shift-requests/{offer.json()['id']}/accept", headers=ARJUN_STAFF).json()
    assert took["status"] == "stale"


def test_requests_are_validated_and_scoped(client: TestClient, week: dict[str, Any]) -> None:
    now = current(client)
    someone_elses = next(sh for sh in now["shifts"] if sh["employee_id"] not in (None, RAVI))
    r = client.post(
        "/v2/me/shift-requests",
        headers=STAFF,
        json={"type": "giveaway", "logical_shift_id": someone_elses["logical_shift_id"]},
    )
    assert r.status_code == 403
    assert (
        client.post(
            "/v2/me/shift-requests",
            headers=MANAGER,
            json={"type": "giveaway", "logical_shift_id": someone_elses["logical_shift_id"]},
        ).status_code
        == 403
    )
    past = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]
    started = next(
        sh
        for sh in past["shifts"]
        if sh["employee_id"] == RAVI and datetime.fromisoformat(sh["start_at"]) < datetime.now(IST)
    )
    late = client.post(
        "/v2/me/shift-requests",
        headers=STAFF,
        json={"type": "giveaway", "logical_shift_id": started["logical_shift_id"]},
    )
    assert late.status_code == 409 and error_code(late) == "conflict"


def test_a_swap_needs_consent_and_publishes_both_changes(client: TestClient, week: dict[str, Any]) -> None:
    # Set up a pair: the manager gives Ravi one Grill shift and Arjun another, on days both are free.
    now = current(client)
    busy = {day(sh) for sh in now["shifts"] if sh["employee_id"] in (RAVI, ARJUN)}
    open_days = sorted(
        {day(sh) for sh in now["shifts"]}
        - busy
        - {d for d in {day(x) for x in now["shifts"]} if d.weekday() in (1, 6)}
    )
    grill = [
        sh for sh in now["shifts"] if not sh["locked"] and sh["skill_id"] == GRILL and day(sh) in open_days
    ]
    pairs = []
    for x in grill:
        for y in grill:
            if day(x) < day(y):
                pairs.append((x, y))
    published_pair = None
    for x, y in pairs[:10]:
        base = current(client)
        draft = client.post(
            f"{NEXT_URL}/drafts",
            headers=MANAGER | key(),
            json={"base_version_id": base["id"], "copy_from_version_id": None},
        ).json()
        edits = [
            {"op": "update", "logical_shift_id": x["logical_shift_id"], "employee_id": RAVI},
            {"op": "update", "logical_shift_id": y["logical_shift_id"], "employee_id": ARJUN},
        ]
        edited = client.post(
            f"/v2/schedule-versions/{draft['id']}/edits",
            headers=MANAGER,
            json={"expected_revision": 1, "edits": edits},
        )
        ok = (
            edited.status_code == 200
            and client.post(
                f"/v2/schedule-versions/{draft['id']}/publish",
                headers=MANAGER | key(),
                json={"expected_base_version_id": base["id"], "expected_revision": edited.json()["revision"]},
            ).status_code
            == 200
        )
        if ok:
            published_pair = (x, y)
            break
        client.post(f"/v2/schedule-versions/{draft['id']}/discard", headers=MANAGER | key())
    assert published_pair is not None, "could not give Ravi and Arjun a Grill shift each"
    now = current(client)
    x, y = published_pair
    pairs = [
        (
            next(sh for sh in now["shifts"] if sh["logical_shift_id"] == x["logical_shift_id"]),
            next(sh for sh in now["shifts"] if sh["logical_shift_id"] == y["logical_shift_id"]),
        )
    ]
    swap, refused = None, 0
    for mine, theirs in pairs[:30]:
        r = client.post(
            "/v2/me/shift-requests",
            headers=STAFF,
            json={
                "type": "swap",
                "logical_shift_id": mine["logical_shift_id"],
                "target_logical_shift_id": theirs["logical_shift_id"],
            },
        )
        if r.status_code == 422:  # the validator refused this pair, with the rule it breaks
            assert r.json()["error"]["details"]["violations"]
            refused += 1
            continue
        assert r.status_code == 201, r.text
        swap = r.json()
        break
    assert swap is not None, f"all {refused} candidate swaps were refused"
    assert swap["status"] == "open" and swap["target_employee_id"] == ARJUN and swap["target_shift"]
    consented = client.post(f"/v2/shift-requests/{swap['id']}/accept", headers=ARJUN_STAFF).json()
    assert consented["status"] == "pending_manager"
    done = client.post(f"/v2/shift-requests/{swap['id']}/approve", headers=MANAGER).json()
    assert done["status"] == "approved", done
    after = {sh["logical_shift_id"]: sh["employee_id"] for sh in current(client)["shifts"]}
    assert after[swap["shift"]["logical_shift_id"]] == ARJUN
    assert after[swap["target_shift"]["logical_shift_id"]] == RAVI
