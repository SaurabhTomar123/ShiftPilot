"""B5.2 / A3.12 acceptance: the rule validation service and rules that bind the optimizer."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from scheduling import worker
from seed.world import IST, uid
from tests.integration.test_api_v2 import IND, MANAGER, OWNER, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "v2" / "fixtures"
NEXT = "2026-10-26"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def employee_rule(employee: str, rule_type: str, **parameters: Any) -> dict[str, Any]:
    return {
        "rule_type": rule_type,
        "scope_level": "employee",
        "scope": {"employee_id": employee},
        "parameters": parameters,
    }


def test_students_rule_previews_creates_and_catches_conflicts(client: TestClient) -> None:
    students = fixture("rules.preview")["request"]["body"]
    preview = client.post("/v2/rules/preview", headers=OWNER, json=students)
    assert preview.status_code == 200 and preview.json() == fixture("rules.preview")["response"]["body"]
    assert client.post("/v2/rules/preview", headers=MANAGER, json=students).status_code == 403  # tag rule

    created = client.post("/v2/rules", headers=OWNER | key(), json=students)
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]
    assert [r["id"] for r in client.get("/v2/rules", headers=OWNER).json()["items"]] == [rule_id]

    friday = fixture("rules.preview.conflict")["request"]["body"]
    clash = client.post("/v2/rules/preview", headers=OWNER, json=friday).json()
    assert not clash["valid"] and clash["conflicts"][0]["rule_id"] == rule_id
    assert clash["conflicts"][0]["employees"] == ["Rohit Verma"]
    refused = client.post("/v2/rules", headers=OWNER | key(), json=friday)
    assert refused.status_code == 409 and error_code(refused) == "conflict"
    assert refused.json()["error"]["details"]["conflicts"][0]["rule_id"] == rule_id
    exception = clash["conflicts"][0]["suggested_exception"]
    assert exception["overrides_rule_id"] == rule_id
    accepted = client.post(
        "/v2/rules", headers=MANAGER | key(), json=exception
    )  # Rohit works at the manager's outlet
    assert accepted.status_code == 201, accepted.text

    archived = client.post(f"/v2/rules/{accepted.json()['id']}/archive", headers=OWNER).json()
    assert archived["status"] == "archived"
    assert {r["id"] for r in client.get("/v2/rules", headers=OWNER).json()["items"]} == {rule_id}
    bad = employee_rule(str(uid("employee", "rohit")), "max_days_per_week", days=9)
    invalid = client.post("/v2/rules/preview", headers=OWNER, json=bad)
    assert invalid.status_code == 422 and error_code(invalid) == "validation_failed"


def test_rules_bind_generation_and_show_on_published_weeks(client: TestClient) -> None:
    published = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]
    by_person = Counter(s["employee_id"] for s in published["shifts"] if s["employee_id"])
    busiest = by_person.most_common(1)[0][0]
    late = next(
        s["employee_id"]
        for s in published["shifts"]
        if s["employee_id"] and s["employee_id"] != busiest and datetime.fromisoformat(s["end_at"]).hour >= 22
    )
    for body in (
        employee_rule(busiest, "max_days_per_week", days=2),
        employee_rule(late, "max_shift_end_time", latest_end_minute=1200, weekdays=list(range(7))),
    ):
        made = client.post("/v2/rules", headers=MANAGER | key(), json=body)
        assert made.status_code == 201, made.text
        assert made.json()["status"] == "active"

    week = client.get(f"/v2/outlets/{IND}/schedules/{WEEK}", headers=MANAGER).json()["current_version"]
    rule_hits = {v["employee_id"] for v in week["validation"]["violations"] if v["code"] == "rule"}
    assert {busiest, late} <= rule_hits  # current facts include the new rules; the week is not edited

    run = client.post(
        f"/v2/outlets/{IND}/schedules/{NEXT}/generate",
        headers=MANAGER | key(),
        json={"strategy": "balanced", "base_version_id": None, "time_limit_seconds": 4},
    ).json()
    while worker.run_once() is not None:
        pass
    done = client.get(f"/v2/optimization-runs/{run['id']}", headers=MANAGER).json()
    assert done["candidates"], done
    shifts = client.get(f"/v2/optimization-candidates/{done['candidates'][0]['id']}", headers=MANAGER).json()
    added = shifts["diff"]["added"]
    days = {
        datetime.fromisoformat(s["start_at"]).astimezone(IST).date()
        for s in added
        if s["employee_id"] == busiest
    }
    assert len(days) <= 2
    assert all(
        datetime.fromisoformat(s["end_at"]).astimezone(IST).hour * 60
        + datetime.fromisoformat(s["end_at"]).minute
        <= 1200
        for s in added
        if s["employee_id"] == late
    )
