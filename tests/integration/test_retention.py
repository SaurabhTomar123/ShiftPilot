"""A3.10 acceptance: the retention job enforces each artifact's lifetime (architecture v3 section 25)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from db.session import admin_engine
from jobs import retention
from scheduling import worker
from seed.world import uid
from tests.integration.test_api_v2 import IND, MANAGER, OWNER, WEEK, client

pytestmark = pytest.mark.integration
__all__ = ["client"]
NEXT = "2026-10-26"
HSR = str(uid("outlet", "hsr"))


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def sql(statement: str, **params: Any) -> Any:
    with admin_engine().begin() as conn:
        result = conn.execute(text(statement), params)
        return result.all() if result.returns_rows else result.rowcount


def one(statement: str, **params: Any) -> Any:
    return sql(statement, **params)[0][0]


def test_each_artifact_lives_exactly_as_long_as_v3_says(client: TestClient) -> None:
    # A finished generation with three candidates; one is selected and its draft discarded.
    gen = client.post(
        f"/v2/outlets/{IND}/schedules/{NEXT}/generate",
        headers=MANAGER | key(),
        json={"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 3},
    ).json()
    worker.run_once()
    run = client.get(f"/v2/optimization-runs/{gen['id']}", headers=MANAGER).json()
    assert len(run["candidates"]) >= 2
    chosen = run["candidates"][0]["id"]
    picked = client.post(f"/v2/optimization-candidates/{chosen}/select", headers=MANAGER | key()).json()
    client.post(f"/v2/schedule-versions/{picked['id']}/discard", headers=MANAGER | key())

    # A rejected proposal on a manual draft of the published week.
    current = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]
    draft = client.post(
        f"/v2/outlets/{IND}/schedules/{WEEK}/drafts",
        headers=MANAGER | key(),
        json={"base_version_id": current["id"], "copy_from_version_id": None},
    ).json()
    proposal = client.post(
        "/v2/proposals",
        headers=MANAGER | key(),
        json={"draft_version_id": draft["id"], "expected_revision": 1},
    ).json()
    client.post(f"/v2/proposals/{proposal['id']}/reject", headers=MANAGER)

    # A failed run (attempts exhausted), and every outbox event delivered.
    failed = client.post(
        f"/v2/outlets/{HSR}/schedules/{NEXT}/generate",
        headers=OWNER | key(),
        json={"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 3},
    ).json()
    sql(
        "UPDATE optimization_runs SET job_state = 'running', attempts = 3, lease_owner = 'gone', "
        "lease_until = now() - interval '1 second' WHERE id = :r",
        r=failed["id"],
    )
    assert worker.sweep(admin_engine()) == 1
    sql("UPDATE outbox_events SET published_at = now() WHERE published_at IS NULL")
    now = datetime.now(UTC)

    # Dry run: counts, changes nothing.
    preview = retention.run(now=now + timedelta(hours=1), dry_run=True)
    assert preview["failed_snapshots_cleared"] == 1
    assert one("SELECT input_snapshot <> '{}'::jsonb FROM optimization_runs WHERE id = :r", r=failed["id"])

    # At once: only the failed run's snapshot goes.
    soon = retention.run(now=now + timedelta(hours=1))
    assert (
        soon["failed_snapshots_cleared"] == 1
        and soon["candidates_deleted"] == 0
        and soon["drafts_deleted"] == 0
    )
    assert one("SELECT input_snapshot = '{}'::jsonb FROM optimization_runs WHERE id = :r", r=failed["id"])

    # After 7 days: unselected candidates, the discarded draft, delivered outbox and the proposal's result.
    week = retention.run(now=now + timedelta(days=8))
    assert week["candidates_deleted"] == len(run["candidates"]) - 1
    assert week["drafts_deleted"] == 1 and week["draft_shifts_deleted"] == len(picked["shifts"])
    assert week["candidates_unlinked"] == 1 and week["logical_shifts_deleted"] == len(picked["shifts"])
    assert week["outbox_deleted"] >= 1 and week["proposal_results_cleared"] == 1
    assert one("SELECT count(*) FROM schedule_versions WHERE id = :v", v=picked["id"]) == 0
    assert one("SELECT count(*) FROM schedule_proposals WHERE id = :p", p=proposal["id"]) == 1
    # The rejected proposal still names its (not discarded) draft, so nothing there is touched.
    assert client.get(f"/v2/proposals/{proposal['id']}", headers=MANAGER).json()["status"] == "rejected"

    # After 30 days: the proposal row, the failed run and the applied run's snapshot.
    month = retention.run(now=now + timedelta(days=31))
    assert month["proposals_deleted"] == 1 and month["failed_runs_deleted"] == 1
    assert month["applied_snapshots_cleared"] >= 1
    assert one("SELECT count(*) FROM optimization_runs WHERE id = :r", r=failed["id"]) == 0
    assert week["runs_marked_expired"] >= 1
    kept = client.get(f"/v2/optimization-runs/{gen['id']}", headers=MANAGER).json()
    assert kept["candidates_expired"] and kept["candidates"] == []  # the selected one went with its draft
    assert kept["job_state"] == "succeeded" and kept["input_hash"] == run["input_hash"]  # provenance stays
    assert one("SELECT input_snapshot = '{}'::jsonb FROM optimization_runs WHERE id = :r", r=gen["id"])
    assert one("SELECT (stats->>'snapshot_purged')::bool FROM optimization_runs WHERE id = :r", r=gen["id"])

    # Published history and the audit log are never touched.
    week_view = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()
    assert week_view["current_version"]["id"] == current["id"]
    assert one("SELECT count(*) FROM audit_log WHERE action = 'DRAFT_DISCARDED'") >= 1
    assert retention.run(now=now + timedelta(days=31))["drafts_deleted"] == 0  # idempotent
