"""B5.1 / B5.2 acceptance (architecture v3 sections 33-34): language shortcuts produce previews of
deterministic operations, ask instead of guessing, refuse what they cannot do and never write."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from db.session import admin_engine
from language import adapter
from language.scripted import ScriptedModel
from seed.world import IST, SKILL, uid
from tests.integration.test_api_v2 import IND, MANAGER, OWNER, STAFF, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]


@pytest.fixture(autouse=True)
def scripted() -> Iterator[None]:
    adapter.use(ScriptedModel())
    yield
    adapter.use(None)


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def count(statement: str) -> int:
    with admin_engine().begin() as conn:
        return int(conn.execute(text(statement)).scalar_one())


def parse(c: TestClient, body: dict[str, Any], as_: dict[str, str] = MANAGER) -> Any:
    return c.post("/v2/commands/parse", headers=as_, json=body)


def confirm(c: TestClient, preview: dict[str, Any], as_: dict[str, str] = MANAGER) -> Any:
    action = preview["action"]
    return c.post(action["path"], headers=as_ | key(), json=action["body"])


def next_saturday() -> str:
    today = datetime.now(IST).date()
    return (today + timedelta(days=(5 - today.weekday()) % 7 or 7)).isoformat()


def test_a_command_is_a_preview_and_only_confirmation_writes(client: TestClient) -> None:
    before = count("SELECT count(*) FROM absences")
    preview = parse(client, {"text": "Give Ravi Saturday off"}).json()
    assert preview["status"] == "ready" and preview["intent"] == "give_time_off"
    assert preview["summary"].startswith("Mark Ravi Kumar off on Saturday")
    body = preview["action"]["body"]
    assert preview["action"]["operation_id"] == "reportAbsence" and body["kind"] == "leave"
    assert body["employee_id"] == str(uid("employee", "ravi")) and body["start_at"].startswith(
        next_saturday()
    )
    assert count("SELECT count(*) FROM absences") == before  # parsing wrote nothing
    done = confirm(client, preview)
    assert done.status_code == 201, done.text
    assert count("SELECT count(*) FROM absences") == before + 1


def test_two_ravis_get_a_question_not_a_guess(client: TestClient) -> None:
    made = client.post(
        "/v2/employees",
        headers=MANAGER | key(),
        json={
            "name": "Ravi Shetty",
            "home_outlet_id": IND,
            "status": "active",
            "hourly_rate": {"amount_paise": 15000, "currency": "INR"},
            "skills": [{"skill_id": str(SKILL["Server"]), "level": 1}],
            "tags": [],
            "regular_weekly_minutes": 2400,
            "max_weekly_minutes": 2400,
            "preferred_weekly_minutes": None,
            "overtime_allowed": False,
            "cross_outlet_eligible": False,
        },
    )
    assert made.status_code == 201, made.text
    which = parse(client, {"text": "Ravi is sick tomorrow"}).json()
    assert which["status"] == "needs_clarification" and which["question"] == "Which Ravi?"
    assert {o["name"] for o in which["options"]} == {"Ravi Kumar", "Ravi Shetty"}
    answered = parse(client, {"text": "Ravi is sick tomorrow", "employee_id": made.json()["id"]}).json()
    assert answered["status"] == "ready" and answered["action"]["body"]["kind"] == "sick"
    assert answered["summary"].startswith("Mark Ravi Shetty off sick")
    nobody = parse(client, {"text": "Give Zubin Saturday off"}).json()
    assert nobody["status"] == "needs_clarification" and "Zubin" in nobody["question"]


def test_generate_and_unsupported_and_permissions(client: TestClient) -> None:
    generate = parse(client, {"text": "Generate next week"}).json()
    assert generate["status"] == "ready" and generate["action"]["operation_id"] == "generateSchedule"
    assert confirm(client, generate).status_code == 202
    assert parse(client, {"text": "Order more tomatoes"}).json()["status"] == "unsupported"
    assert parse(client, {"text": "Give Ravi Saturday off"}, as_=STAFF).status_code == 403
    adapter.use(None)  # no model configured in tests
    assert parse(client, {"text": "Give Ravi Saturday off"}).json()["status"] == "unavailable"


def test_a_rule_in_words_runs_through_the_validation_service(client: TestClient) -> None:
    words = "Students cannot work later than 9 PM on weekdays"
    parsed = client.post("/v2/rules/parse", headers=OWNER, json={"text": words}).json()
    assert (
        parsed["status"] == "ready"
        and parsed["preview"]["summary"] == "No shift ends after 21:00 on weekdays"
    )
    rule = parsed["preview"]["rule"]
    assert rule["scope"] == {"tag": "student"} and rule["source_text"] == words
    assert {a["name"] for a in parsed["preview"]["affected"]} == {
        "Rohit Verma",
        "Kabir Malhotra",
        "Yash Chawla",
    }
    created = client.post("/v2/rules", headers=OWNER | key(), json=rule)
    assert created.status_code == 201, created.text
    refused = client.post(
        "/v2/rules/parse", headers=OWNER, json={"text": "Pay seniors more on Sundays"}
    ).json()
    assert refused["status"] == "unsupported" and refused["preview"] is None
    tag_rule = client.post("/v2/rules/parse", headers=MANAGER, json={"text": words})
    assert tag_rule.status_code == 403 and error_code(tag_rule) == "permission_denied"


def test_who_can_cover_previews_the_recommendation_call(client: TestClient) -> None:
    """v4 section 43 FIND_REPLACEMENT: a preview of the read-only recommendation endpoint."""
    week = client.get(f"/v2/outlets/{IND}/schedules/2026-10-19", headers=MANAGER).json()["current_version"]
    shift = next(sh for sh in week["shifts"] if sh["employee_id"] == str(uid("employee", "ravi")))
    day = datetime.fromisoformat(shift["start_at"]).astimezone(IST).date()
    text = f"Who can cover Ravi on {day.isoformat()}?"
    preview = parse(client, {"text": text}).json()
    if preview["status"] == "needs_clarification":  # another Ravi exists in this module: answer the question
        assert preview["question"] == "Which Ravi?"
        preview = parse(client, {"text": text, "employee_id": str(uid("employee", "ravi"))}).json()
    assert preview["status"] == "ready" and preview["intent"] == "find_replacement", preview
    assert preview["summary"].startswith("Find cover for Ravi Kumar's")
    action = preview["action"]
    assert action["operation_id"] == "recommendReplacements" and action["body"]["version_id"] == week["id"]
    assert action["body"]["logical_shift_id"] in {
        sh["logical_shift_id"] for sh in week["shifts"] if sh["employee_id"] == str(uid("employee", "ravi"))
    }
    cover = client.post(action["path"], headers=MANAGER, json=action["body"])
    assert cover.status_code == 200 and cover.json()["vacating_employee_id"] == str(uid("employee", "ravi"))
    nothing = parse(
        client, {"text": "Who can cover Ravi on 2030-01-01?", "employee_id": str(uid("employee", "ravi"))}
    ).json()
    assert nothing["status"] == "needs_clarification" and "no published shift" in nothing["summary"]
