"""B3.1-B3.3 acceptance: drafts, edits, atomic publication, history, compare and restore."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v2 import schemas
from db.session import admin_engine
from seed import v2
from seed.world import uid
from tests.integration.test_api_v2 import IND, MANAGER, STAFF, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
WEEK_URL = f"/v2/outlets/{IND}/schedules/{WEEK}"
GRILL, SERVER = str(uid("skill", "Grill")), str(uid("skill", "Server"))
KARAN = str(uid("employee", "karan"))  # Server only: giving him a Grill shift breaks the skill rule


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def current(c: TestClient) -> dict[str, Any]:
    return c.get(WEEK_URL, headers=MANAGER).json()["current_version"]


def new_draft(c: TestClient, base: str | None, headers: dict[str, str] | None = None) -> Any:
    return c.post(
        f"{WEEK_URL}/drafts",
        headers=MANAGER | (headers or key()),
        json={"base_version_id": base, "copy_from_version_id": None},
    )


def edit(
    c: TestClient, version: dict[str, Any], edits: list[dict[str, Any]], *, preview: bool = False
) -> Any:
    path = "edits/preview" if preview else "edits"
    return c.post(
        f"/v2/schedule-versions/{version['id']}/{path}",
        headers=MANAGER,
        json={"expected_revision": version["revision"], "edits": edits},
    )


def publish(
    c: TestClient, version: dict[str, Any], base: str | None, headers: dict[str, str] | None = None
) -> Any:
    return c.post(
        f"/v2/schedule-versions/{version['id']}/publish",
        headers=MANAGER | (headers or key()),
        json={"expected_base_version_id": base, "expected_revision": version["revision"]},
    )


def grill_shift(version: dict[str, Any]) -> dict[str, Any]:
    return next(sh for sh in version["shifts"] if sh["skill_id"] == GRILL and not sh["locked"])


def sql(statement: str, **params: Any) -> Any:
    with admin_engine().begin() as conn:
        result = conn.execute(text(statement), params)
        return result.all() if result.returns_rows else result.rowcount


def test_draft_edit_preview_and_publish_end_to_end(client: TestClient) -> None:
    base = current(client)
    k = key()
    created = new_draft(client, base["id"], k)
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "draft" and draft["revision"] == 1 and draft["base_version_id"] == base["id"]
    assert {s["logical_shift_id"] for s in draft["shifts"]} == {s["logical_shift_id"] for s in base["shifts"]}
    assert new_draft(client, base["id"], k).json()["id"] == draft["id"]  # idempotent replay

    target = grill_shift(draft)
    bad = [{"op": "update", "logical_shift_id": target["logical_shift_id"], "employee_id": KARAN}]
    preview = edit(client, draft, bad, preview=True)
    assert preview.status_code == 200, preview.text
    p = schemas.EditPreview.model_validate(preview.json())
    assert [c.kinds for c in p.changes] == [["reassigned"]]
    assert any(v.code == "missing_skill" and v.severity == "hard" for v in p.validation.violations)
    assert (
        client.get(f"/v2/schedule-versions/{draft['id']}", headers=MANAGER).json()["revision"] == 1
    )  # no write

    lock = [{"op": "lock", "logical_shift_id": target["logical_shift_id"], "reason": "Confirmed by phone"}]
    applied = edit(client, draft, lock)
    assert applied.status_code == 200, applied.text
    after = applied.json()
    assert after["revision"] == 2
    locked = next(s for s in after["shifts"] if s["logical_shift_id"] == target["logical_shift_id"])
    assert locked["locked"] and locked["lock_reason"] == "Confirmed by phone"
    stale = edit(client, draft, lock)  # still revision 1
    assert stale.status_code == 409 and stale.json()["error"]["details"]["current_revision"] == 2

    pk = key()
    published = publish(client, after, base["id"], pk)
    assert published.status_code == 200, published.text
    result = schemas.PublishResult.model_validate(published.json())
    assert result.superseded_version_id == uuid.UUID(base["id"]) and result.published.status == "published"
    assert publish(client, after, base["id"], pk).json() == published.json()  # idempotent replay
    now = current(client)
    assert now["id"] == after["id"] and now["validation"]["hard_violations"] == 0
    assert client.get(f"/v2/schedule-versions/{base['id']}", headers=MANAGER).json()["status"] == "superseded"
    assert (
        sql(
            "SELECT count(*) FROM outbox_events WHERE topic = 'schedule.published' AND aggregate_id = :v",
            v=after["id"],
        )[0][0]
        == 1
    )
    assert (
        sql(
            "SELECT count(*) FROM audit_log WHERE action = 'SCHEDULE_PUBLISHED' AND target_id = :v",
            v=after["id"],
        )[0][0]
        == 1
    )


def test_publication_refuses_stale_bases_and_hard_violations(client: TestClient) -> None:
    base = current(client)
    racer = new_draft(client, base["id"]).json()
    winner = new_draft(client, base["id"]).json()
    assert publish(client, winner, base["id"]).status_code == 200
    stale = publish(client, racer, base["id"])
    assert stale.status_code == 409 and error_code(stale) == "stale_version"
    assert stale.json()["error"]["details"]["current_version_id"] == winner["id"]

    draft = new_draft(client, winner["id"]).json()
    target = grill_shift(draft)
    broken = edit(
        client,
        draft,
        [{"op": "update", "logical_shift_id": target["logical_shift_id"], "employee_id": KARAN}],
    ).json()
    assert broken["validation"]["hard_violations"] >= 1  # applied, and reported
    blocked = publish(client, broken, winner["id"])
    assert blocked.status_code == 422 and error_code(blocked) == "validation_failed"
    # Karan also works a Server shift then, so the overlap is reported too; both are hard.
    assert "missing_skill" in {v["code"] for v in blocked.json()["error"]["details"]["violations"]}
    assert current(client)["id"] == winner["id"]
    assert client.get(f"/v2/schedule-versions/{broken['id']}", headers=MANAGER).json()["status"] == "draft"


def test_published_and_discarded_versions_cannot_be_edited(client: TestClient) -> None:
    live = current(client)
    r = edit(client, live, [{"op": "lock", "logical_shift_id": grill_shift(live)["logical_shift_id"]}])
    assert r.status_code == 409 and error_code(r) == "conflict"
    draft = new_draft(client, live["id"]).json()
    discarded = client.post(f"/v2/schedule-versions/{draft['id']}/discard", headers=MANAGER)
    assert discarded.status_code == 200 and discarded.json()["status"] == "discarded"
    assert (
        edit(
            client, draft, [{"op": "remove", "logical_shift_id": grill_shift(draft)["logical_shift_id"]}]
        ).status_code
        == 409
    )


def test_structural_edit_errors_are_field_level_422s(client: TestClient) -> None:
    draft = new_draft(client, current(client)["id"]).json()
    unknown = edit(client, draft, [{"op": "remove", "logical_shift_id": str(uuid.uuid4())}])
    assert unknown.status_code == 422 and unknown.json()["error"]["details"]["fields"][0]["path"] == [
        "edits",
        0,
    ]
    target = grill_shift(draft)
    backwards = edit(
        client,
        draft,
        [{"op": "update", "logical_shift_id": target["logical_shift_id"], "end_at": target["start_at"]}],
    )
    assert backwards.status_code == 422


def test_history_compare_and_restore_never_revive_absent_shifts_blindly(client: TestClient) -> None:
    live = current(client)
    history = client.get(f"/v2/schedules/{live['schedule_id']}/versions", headers=MANAGER).json()
    numbers = [v["version_number"] for v in history["items"]]
    assert numbers == sorted(numbers, reverse=True) and history["current_version_id"] == live["id"]
    first = next(v for v in history["items"] if v["version_number"] == 1)
    assert first["status"] == "superseded"

    diff = client.get(
        f"/v2/schedule-versions/{live['id']}/compare", headers=MANAGER, params={"with": first["id"]}
    ).json()
    assert {k for c in diff["changes"] for k in c["kinds"]} == {"lock_changed"}

    original = client.get(f"/v2/schedule-versions/{first['id']}", headers=MANAGER).json()
    victim = next(s for s in original["shifts"] if s["employee_id"])
    sql(
        "INSERT INTO absences (id, org_id, employee_id, start_at, end_at, kind, status, source) "
        "VALUES (:id, :org, :e, :a, :b, 'sick', 'confirmed', 'manager')",
        id=uuid.uuid4(),
        org=uid("org", v2.SPICE),
        e=victim["employee_id"],
        a=victim["start_at"],
        b=victim["end_at"],
    )
    restored = client.post(
        f"/v2/schedule-versions/{first['id']}/restore",
        headers=MANAGER | key(),
        json={"expected_base_version_id": live["id"]},
    )
    assert restored.status_code == 201, restored.text
    draft = restored.json()
    assert draft["source"] == "restore" and draft["reason"] == "Restored from version 1"
    assert any(
        v["code"] == "absent" and victim["logical_shift_id"] in v["logical_shift_ids"]
        for v in draft["validation"]["violations"]
    )
    blocked = publish(client, draft, live["id"])
    assert blocked.status_code == 422 and "absent" in {
        v["code"] for v in blocked.json()["error"]["details"]["violations"]
    }
    stale = client.post(
        f"/v2/schedule-versions/{first['id']}/restore",
        headers=MANAGER | key(),
        json={"expected_base_version_id": first["id"]},
    )
    assert stale.status_code == 409


def test_staff_cannot_draft_or_publish(client: TestClient) -> None:
    r = client.post(
        f"{WEEK_URL}/drafts",
        headers=STAFF | key(),
        json={"base_version_id": current(client)["id"], "copy_from_version_id": None},
    )
    assert r.status_code == 403
