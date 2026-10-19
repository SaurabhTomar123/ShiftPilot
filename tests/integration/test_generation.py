"""B2.3 acceptance: generation requests, the durable run queue and the fenced worker."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v2 import generation, schemas
from core.auth import Role
from db.session import admin_engine
from scheduling import worker
from seed import v2
from seed.world import uid
from tests.integration.test_api_v2 import IND, KOR, MANAGER, OWNER, STAFF, WEEK, client, error_code, token

pytestmark = pytest.mark.integration
__all__ = ["client"]  # the module-scoped seeded app fixture
NEXT = "2026-10-26"
HSR = str(uid("outlet", "hsr"))
FAST = {"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 3}


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"gen-{uuid.uuid4().hex[:12]}"}


def generate(
    c: TestClient,
    outlet: str,
    week: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    as_: dict[str, str] = OWNER,
) -> Any:
    return c.post(
        f"/v2/outlets/{outlet}/schedules/{week}/generate", headers=as_ | (headers or key()), json=body or FAST
    )


def sql(statement: str, **params: Any) -> Any:
    with admin_engine().begin() as conn:
        result = conn.execute(text(statement), params)
        return result.all() if result.returns_rows else result.rowcount


def test_enqueue_is_idempotent_and_guarded(client: TestClient) -> None:
    k = key()
    first = generate(client, IND, NEXT, headers=k, as_=MANAGER)
    assert first.status_code == 202, first.text
    run = schemas.OptimizationRun.model_validate(first.json())
    assert run.job_state == "queued" and run.poll_after_ms == 500 and run.base_version_ids == []
    replay = generate(client, IND, NEXT, headers=k, as_=MANAGER)
    assert replay.status_code == 202 and replay.json()["id"] == str(run.id)
    clash = generate(client, IND, NEXT, {**FAST, "strategy": "lowest_cost"}, headers=k, as_=MANAGER)
    assert clash.status_code == 409 and error_code(clash) == "idempotency_conflict"
    busy = generate(client, IND, NEXT, as_=MANAGER)
    assert busy.status_code == 409 and error_code(busy) == "run_in_progress"
    assert busy.json()["error"]["details"]["run_id"] == str(run.id)

    assert worker.run_once() == run.id
    done = client.get(f"/v2/optimization-runs/{run.id}", headers=MANAGER).json()
    assert done["job_state"] == "succeeded" and done["solver_status"] in ("OPTIMAL", "FEASIBLE")
    assert done["poll_after_ms"] is None and done["candidates"]
    for cand in done["candidates"]:
        assert cand["validation"]["hard_violations"] == 0
        draft = client.get(f"/v2/schedule-versions/{cand['draft_version_id']}", headers=MANAGER)
        assert draft.status_code == 200 and draft.headers["Cache-Control"] == "private, no-cache"
        body = draft.json()
        assert body["status"] == "draft" and body["source"] == "generate"
        assert body["validation"]["hard_violations"] == 0 and body["metrics"] == cand["metrics"]
    assert sql("SELECT count(*) FROM schedule_run_slots")[0][0] == 0
    assert (
        sql(
            "SELECT count(*) FROM outbox_events WHERE topic = 'run.finished' AND aggregate_id = :r", r=run.id
        )[0][0]
        == 1
    )
    # A new request is accepted once the slot is free (and immediately conflicts while active).
    again = generate(client, IND, NEXT, as_=MANAGER)
    assert again.status_code == 202
    worker.run_once()


def test_stale_base_and_permissions(client: TestClient) -> None:
    stale = generate(client, IND, WEEK, as_=MANAGER)
    assert stale.status_code == 409 and error_code(stale) == "stale_version"
    assert stale.json()["error"]["details"]["current_version_id"]
    assert generate(client, IND, NEXT, as_=STAFF).status_code == 403
    assert generate(client, KOR, NEXT, as_=MANAGER).status_code == 403
    assert client.get(f"/v2/optimization-runs/{uuid.uuid4()}", headers=MANAGER).status_code == 404


def test_regeneration_keeps_locked_shifts_and_never_touches_the_published_week(client: TestClient) -> None:
    week = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()
    current = week["current_version"]
    locked = {sh["logical_shift_id"] for sh in current["shifts"] if sh["locked"]}
    assert locked
    r = generate(client, IND, WEEK, {**FAST, "base_version_id": current["id"]}, as_=MANAGER)
    assert r.status_code == 202, r.text
    worker.run_once()
    run = client.get(f"/v2/optimization-runs/{r.json()['id']}", headers=MANAGER).json()
    assert run["job_state"] == "succeeded" and run["base_version_ids"] == [current["id"]]
    draft = client.get(
        f"/v2/schedule-versions/{run['candidates'][0]['draft_version_id']}", headers=MANAGER
    ).json()
    assert locked <= {sh["logical_shift_id"] for sh in draft["shifts"]}
    assert draft["base_version_id"] == current["id"] and draft["version_number"] > current["version_number"]
    after = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()
    assert after["current_version"]["id"] == current["id"]
    assert {d["id"] for d in after["drafts"]} >= {c["draft_version_id"] for c in run["candidates"]}


def claim(me: str) -> Any:
    with admin_engine().begin() as conn:
        return conn.execute(worker.CLAIM, {"me": me, "lease": 30, "lane": "batch", "max_attempts": 3}).first()


def test_a_worker_that_lost_its_lease_writes_nothing(client: TestClient) -> None:
    run_id = generate(client, HSR, NEXT).json()["id"]
    row = claim("zombie")
    assert str(row.id) == run_id
    sql(
        "UPDATE optimization_runs SET lease_owner = 'winner', attempts = attempts + 1 WHERE id = :r", r=run_id
    )
    assert worker.process(admin_engine(), row, "zombie") == "lost_lease"
    state = sql("SELECT job_state, lease_owner FROM optimization_runs WHERE id = :r", r=run_id)[0]
    assert tuple(state) == ("running", "winner")
    assert sql("SELECT count(*) FROM optimization_candidates WHERE run_id = :r", r=run_id)[0][0] == 0
    # Crash recovery: the winner's lease expires; another worker reclaims and finishes.
    sql("UPDATE optimization_runs SET lease_until = now() - interval '1 second' WHERE id = :r", r=run_id)
    assert str(worker.run_once(me="rescuer")) == run_id
    final = sql("SELECT job_state, attempts FROM optimization_runs WHERE id = :r", r=run_id)[0]
    assert final[0] == "succeeded" and final[1] == 3


def test_exhausted_attempts_are_failed_by_the_sweeper(client: TestClient) -> None:
    run_id = generate(client, KOR, NEXT).json()["id"]
    sql(
        "UPDATE optimization_runs SET job_state = 'running', attempts = 3, lease_owner = 'gone', "
        "lease_until = now() - interval '1 second' WHERE id = :r",
        r=run_id,
    )
    assert worker.sweep(admin_engine()) == 1
    run = client.get(f"/v2/optimization-runs/{run_id}", headers=OWNER).json()
    assert run["job_state"] == "failed" and run["error"]["details"]["reason"] == "ATTEMPTS_EXHAUSTED"
    assert sql("SELECT count(*) FROM schedule_run_slots WHERE run_id = :r", r=run_id)[0][0] == 0


def test_impossible_demand_is_reported_as_infeasible(client: TestClient) -> None:
    sql(
        "UPDATE staffing_requirements SET minimum_required = 9, preferred_required = 9 "
        "WHERE outlet_id = :o AND interval_start >= '2026-11-02' AND interval_start < '2026-11-03' "
        "AND skill_id = :k",
        o=uid("outlet", "koramangala"),
        k=uid("skill", "Grill"),
    )
    sql(
        "INSERT INTO staffing_requirements (id, org_id, outlet_id, skill_id, interval_start, interval_end, "
        "minimum_required, preferred_required, source, demand_revision) "
        "VALUES (gen_random_uuid(), :org, :o, :k, '2026-11-02T13:30:00+00', '2026-11-02T14:00:00+00', 9, 9, "
        "'manual', 1)",
        org=uid("org", v2.SPICE),
        o=uid("outlet", "koramangala"),
        k=uid("skill", "Grill"),
    )
    run_id = generate(client, KOR, "2026-11-02").json()["id"]
    worker.run_once()
    run = client.get(f"/v2/optimization-runs/{run_id}", headers=OWNER).json()
    assert (
        run["job_state"] == "succeeded" and run["solver_status"] == "INFEASIBLE" and run["candidates"] == []
    )
    shortage = run["infeasibility"]["shortages"][0]
    assert shortage["minimum_required"] == 9 and shortage["max_assignable"] < 9
    assert "needs 9 Grill" in run["infeasibility"]["summary"]


def test_org_cap_returns_429_with_retry_after(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generation, "ORG_ACTIVE_CAP", 0)
    r = generate(client, HSR, "2026-11-09")
    assert r.status_code == 429 and error_code(r) == "rate_limited" and r.headers["Retry-After"] == "3"
    assert r.json()["error"]["retryable"] is True


def test_other_tenants_cannot_see_runs(client: TestClient) -> None:
    run_id = sql("SELECT id FROM optimization_runs LIMIT 1")[0][0]
    nw = token(f"{v2.NORTHWIND}:owner", Role.OWNER, org=v2.NORTHWIND)
    assert client.get(f"/v2/optimization-runs/{run_id}", headers=nw).status_code == 404
