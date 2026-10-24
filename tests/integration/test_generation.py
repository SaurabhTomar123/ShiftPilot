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
    # Candidate Portfolio (v4 section 16): requested first, every other strategy shown or explained.
    folio = done["portfolio"]
    assert folio["policy_version"] == 1 and folio["considered"][0] == done["strategy"]
    shown = {c["strategy"] for c in done["candidates"]}
    assert shown | {d["strategy"] for d in folio["dropped"]} == set(folio["considered"])
    # Decision trace (v4 section 18): an empty week is all CREATED; rank 1 has nothing to compare with.
    first = done["candidates"][0]["trace"]
    assert first["summary"]["compared_to"] is None and first["counts"]["CREATED"] > 0
    assert all(c["trace"]["summary"]["compared_to"] == "requested_plan" for c in done["candidates"][1:])
    # Live deltas equal the difference of the displayed metrics (the worker uses one snapshot for both).
    base_m = done["candidates"][0]["metrics"]
    for c in done["candidates"][1:]:
        m, summary = c["metrics"], c["trace"]["summary"]
        assert (
            summary["preferred_gap_delta_minutes"]
            == m["preferred_deficit_minutes"] - base_m["preferred_deficit_minutes"]
        )
        if m["fairness_burden_deviation"] is not None and base_m["fairness_burden_deviation"] is not None:
            assert summary["fairness_delta"] == round(
                m["fairness_burden_deviation"] - base_m["fairness_burden_deviation"], 2
            )
    # Candidates are lightweight (v3 section 23): no version exists until a manager selects one.
    assert sql("SELECT count(*) FROM schedule_versions WHERE optimization_run_id = :r", r=run.id)[0][0] == 0
    for cand in done["candidates"]:
        assert cand["validation"]["hard_violations"] == 0 and cand["materialized_version_id"] is None
        detail = client.get(f"/v2/optimization-candidates/{cand['id']}", headers=MANAGER).json()
        assert (
            detail["base_version_id"] is None and detail["diff"]["changed"] == detail["diff"]["removed"] == []
        )
        assert len(detail["diff"]["added"]) == cand["changed_shifts"] > 0
    first = done["candidates"][0]
    k2 = key()
    selected = client.post(f"/v2/optimization-candidates/{first['id']}/select", headers=MANAGER | k2)
    assert selected.status_code == 201, selected.text
    body = selected.json()
    assert (
        body["status"] == "draft"
        and body["source"] == "generate"
        and body["optimization_run_id"] == str(run.id)
    )
    assert body["validation"]["hard_violations"] == 0 and body["metrics"] == first["metrics"]
    assert len(body["shifts"]) == first["changed_shifts"]
    replay = client.post(f"/v2/optimization-candidates/{first['id']}/select", headers=MANAGER | k2)
    assert replay.json()["id"] == body["id"]
    again = client.post(f"/v2/optimization-candidates/{first['id']}/select", headers=MANAGER | key())
    assert again.json()["id"] == body["id"]  # still a draft: the same one
    polled = client.get(f"/v2/optimization-runs/{run.id}", headers=MANAGER).json()
    assert polled["candidates"][0]["materialized_version_id"] == body["id"]
    assert client.get(f"/v2/optimization-candidates/{first['id']}", headers=STAFF).status_code == 403
    staff_select = client.post(f"/v2/optimization-candidates/{first['id']}/select", headers=STAFF | key())
    assert staff_select.status_code == 403
    assert client.get(f"/v2/optimization-candidates/{uuid.uuid4()}", headers=MANAGER).status_code == 404
    assert sql("SELECT count(*) FROM optimization_runs WHERE job_state IN ('queued', 'running')")[0][0] == 0
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
    assert "stability" in run["portfolio"]["considered"]  # there is a published week to keep stable
    detail = client.get(f"/v2/optimization-candidates/{run['candidates'][0]['id']}", headers=MANAGER).json()
    assert detail["base_version_id"] == current["id"]
    assert not locked & set(detail["diff"]["removed"])  # locked shifts are kept
    trace = run["candidates"][0]["trace"]
    assert trace["summary"]["compared_to"] == "base_version" and trace["counts"]["KEPT"] >= len(locked)
    assert len(detail["trace_changes"]) == sum(v for k, v in trace["counts"].items() if k != "KEPT")
    assert trace["explained_shifts"] == len(run["candidates"][0]["explanations"])
    draft = client.post(
        f"/v2/optimization-candidates/{run['candidates'][0]['id']}/select", headers=MANAGER | key()
    ).json()
    assert locked <= {sh["logical_shift_id"] for sh in draft["shifts"]}
    assert draft["base_version_id"] == current["id"] and draft["version_number"] > current["version_number"]
    after = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()
    assert after["current_version"]["id"] == current["id"]
    assert draft["id"] in {d["id"] for d in after["drafts"]}


def claim(me: str) -> Any:
    with admin_engine().begin() as conn:
        return conn.execute(
            worker.CLAIM,
            {"me": me, "lease": 30, "kinds": ["repair", "generate", "optimize"], "max_attempts": 3},
        ).first()


@pytest.mark.faults
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


@pytest.mark.faults
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
    assert sql("SELECT job_state FROM optimization_runs WHERE id = :r", r=run_id)[0][0] == "failed"


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
    options = run["infeasibility"]["options"]  # v3 section 13: business options, not a bare error
    assert options and options[-1]["kind"] == "reduced_minimum"
    assert {o["kind"] for o in options} <= {"overtime", "cross_outlet", "reduced_minimum"}
    # v4 section 17: the diagnosed conflict set names the business constraints, never facts.
    conflict = run["infeasibility"]["conflict_set"]
    assert conflict and any(c["kind"] == "minimum_coverage" for c in conflict)
    assert {c["kind"] for c in conflict} <= {"minimum_coverage", "no_overtime", "rule", "labour_cap"}
    for o in options:
        if o["kind"] == "cross_outlet":  # other outlets' staff are in the snapshot for exactly this
            assert all(e["home_outlet_id"] != KOR for e in o["employees"])


def test_org_cap_returns_429_with_retry_after(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generation, "ORG_ACTIVE_CAP", 0)
    r = generate(client, HSR, "2026-11-09")
    assert r.status_code == 429 and error_code(r) == "rate_limited" and r.headers["Retry-After"] == "3"
    assert r.json()["error"]["retryable"] is True


def test_other_tenants_cannot_see_runs(client: TestClient) -> None:
    run_id = sql("SELECT id FROM optimization_runs LIMIT 1")[0][0]
    nw = token(f"{v2.NORTHWIND}:owner", Role.OWNER, org=v2.NORTHWIND)
    assert client.get(f"/v2/optimization-runs/{run_id}", headers=nw).status_code == 404


def test_the_worker_role_is_least_privilege(client: TestClient) -> None:
    """B6.3: the worker crosses tenants but touches only runs, base shifts, candidates and the outbox."""
    from sqlalchemy.exc import ProgrammingError

    from db.session import worker_engine

    engine = worker_engine()
    assert engine.url.username == "shiftpilot_worker"
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM optimization_runs")).scalar_one() >= 1  # all tenants
    for statement in (
        "SELECT name, hourly_rate FROM employees",
        "SELECT * FROM absences",
        "DELETE FROM optimization_runs",
        "UPDATE schedule_versions SET reason = 'x'",
        "INSERT INTO audit_log (id) VALUES (gen_random_uuid())",
    ):
        with engine.connect() as conn, pytest.raises(ProgrammingError, match="permission denied"):
            conn.execute(text(statement))


@pytest.mark.faults
def test_concurrent_generation_requests_admit_exactly_one_run(client: TestClient) -> None:
    """v3 section 28 under real concurrency: the partial unique index admits one active batch run."""
    import threading

    barrier = threading.Barrier(2)
    codes: list[int] = []
    errors: list[str] = []

    def go() -> None:
        barrier.wait()
        try:
            codes.append(generate(client, HSR, "2026-11-16").status_code)
        except Exception as exc:  # surfaced below
            codes.append(-1)
            errors.append(repr(exc)[:600])

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert sorted(codes) == [202, 409], errors
    worker.run_once()
