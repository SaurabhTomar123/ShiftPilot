"""A3.9 acceptance: staffing templates, week expansion and manual overrides (architecture v3 section 18)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from seed import world
from tests.integration.test_api_v2 import IND, MANAGER, STAFF, WEEK, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "v2" / "fixtures"
TEMPLATES = f"/v2/outlets/{IND}/staffing-templates"
STAFFING = f"/v2/outlets/{IND}/staffing-requirements"
GRILL = str(world.SKILL["Grill"])


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())["response"]["body"]


def normal(body: dict[str, Any]) -> dict[str, Any]:
    return body | {"intervals": sorted(body["intervals"], key=lambda i: (i["interval_start"], i["skill_id"]))}


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def week(c: TestClient) -> dict[str, Any]:
    return dict(c.get(STAFFING, params={"week_start": WEEK}, headers=MANAGER).json())


def expand(c: TestClient, base: int, headers: dict[str, str] | None = None) -> Any:
    return c.post(
        f"{STAFFING}/expand",
        params={"week_start": WEEK},
        headers=MANAGER | (headers or key()),
        json={"base_demand_revision": base},
    )


def test_seeded_template_and_expansion_match_the_contract(client: TestClient) -> None:
    listed = client.get(TEMPLATES, headers=MANAGER)
    assert listed.status_code == 200 and listed.json() == fixture("staffing_templates.list")
    assert client.get(TEMPLATES, headers=STAFF).status_code == 403
    assert week(client)["demand_revision"] == 3
    k = key()
    expanded = expand(client, 3, k)
    assert expanded.status_code == 200, expanded.text
    assert normal(expanded.json()) == normal(fixture("staffing.expand"))  # re-expanding changes nothing
    assert expand(client, 3, k).json() == expanded.json()  # idempotent replay
    stale = expand(client, 3)
    assert stale.status_code == 409 and error_code(stale) == "stale_version"
    assert stale.json()["error"]["details"]["current_demand_revision"] == 4


def test_manual_overrides_survive_re_expansion_and_templates_drive_the_week(client: TestClient) -> None:
    current = week(client)
    lunch = next(
        i for i in current["intervals"] if i["skill_id"] == GRILL and "T12:00" in i["interval_start"]
    )
    override = lunch | {"minimum_required": 3, "preferred_required": 4, "source": "manual"}
    put = client.put(
        STAFFING,
        params={"week_start": WEEK},
        headers=MANAGER,
        json={
            "base_demand_revision": current["demand_revision"],
            "intervals": [override if i == lunch else i for i in current["intervals"]],
        },
    )
    assert put.status_code == 200, put.text
    revision = put.json()["demand_revision"]
    assert revision == current["demand_revision"] + 1

    templates = client.get(TEMPLATES, headers=MANAGER).json()
    overlap = templates["items"][0] | {"start_minute": templates["items"][0]["start_minute"] + 30}
    clash = client.put(
        TEMPLATES, headers=MANAGER, json={"base_revision": 1, "items": [*templates["items"], overlap]}
    )
    assert clash.status_code == 422 and clash.json()["error"]["details"]["fields"][0]["path"][0] == "items"
    busier = [
        b | {"minimum_required": 2, "preferred_required": 4}
        if (b["weekday"], b["skill_id"], b["start_minute"]) == (5, GRILL, 1080)
        else b
        for b in templates["items"]
    ]
    saved = client.put(TEMPLATES, headers=MANAGER, json={"base_revision": 1, "items": busier})
    assert saved.status_code == 200 and saved.json() == fixture("staffing_templates.put")
    stale = client.put(TEMPLATES, headers=MANAGER, json={"base_revision": 1, "items": busier})
    assert stale.status_code == 409 and error_code(stale) == "stale_version"

    after = expand(client, revision)
    assert after.status_code == 200, after.text
    body = after.json()
    assert body["demand_revision"] == revision + 1
    by_slot = {(i["skill_id"], i["interval_start"]): i for i in body["intervals"]}
    kept = by_slot[GRILL, lunch["interval_start"]]
    assert (kept["source"], kept["minimum_required"], kept["preferred_required"]) == ("manual", 3, 4)
    saturday = next(
        i for i in body["intervals"] if i["skill_id"] == GRILL and "-24T19:00" in i["interval_start"]
    )
    assert (saturday["source"], saturday["minimum_required"], saturday["preferred_required"]) == (
        "template",
        2,
        4,
    )
