"""contracts/v2 stays valid, consistent with the OpenAPI export, and up to date."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.v2 import contract_build, schemas
from api.v2.routes import install

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts" / "v2"
INDEX = json.loads((CONTRACTS / "fixtures" / "index.json").read_text(encoding="utf-8"))
OPENAPI = json.loads((CONTRACTS / "openapi.json").read_text(encoding="utf-8"))


def load(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))


def test_committed_contract_matches_source() -> None:
    for path, text in contract_build.outputs().items():
        assert path.read_text(encoding="utf-8") == text, (
            f"{path.name} is stale: run python -m api.v2.contract_build"
        )
    on_disk = {p.name for p in (CONTRACTS / "fixtures").glob("*.json")}
    assert on_disk == {p.name for p in contract_build.outputs() if p.parent.name == "fixtures"}


def test_index_version_matches_schemas() -> None:
    assert INDEX["contract_version"] == schemas.CONTRACT_VERSION == OPENAPI["info"]["version"]


@pytest.mark.parametrize("entry", INDEX["fixtures"], ids=lambda e: e["name"])
def test_fixture_body_validates(entry: dict[str, Any]) -> None:
    fx = load(entry["name"])
    if fx["response"]["schema"] is None:
        assert fx["response"]["status"] == 304 and fx["response"]["body"] is None
        return
    model = getattr(schemas, fx["response"]["schema"])
    model.model_validate(fx["response"]["body"])


@pytest.mark.parametrize("entry", INDEX["fixtures"], ids=lambda e: e["name"])
def test_fixture_matches_openapi_operation(entry: dict[str, Any]) -> None:
    fx = load(entry["name"])
    op = OPENAPI["paths"][fx["path"]][fx["method"].lower()]
    assert op["operationId"] == fx["operation_id"]
    response = op["responses"][str(fx["response"]["status"])]
    if fx["response"]["schema"] is None:
        assert "content" not in response
    else:
        ref = response["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/" + fx["response"]["schema"])
    for header in fx["response"].get("headers", {}):
        assert header in response.get("headers", {}), f"{header} not declared for {fx['name']}"


def test_contract_files_are_ascii_so_any_decoder_reads_them() -> None:
    for path in [CONTRACTS / "openapi.json", *sorted((CONTRACTS / "fixtures").glob("*.json"))]:
        path.read_bytes().decode("ascii")


def test_employee_update_rejects_explicit_null_but_allows_clearing_preferred_hours() -> None:
    with pytest.raises(ValidationError):
        schemas.EmployeeUpdate.model_validate({"base_revision": 1, "name": None})
    cleared = schemas.EmployeeUpdate.model_validate({"base_revision": 1, "preferred_weekly_minutes": None})
    assert "preferred_weekly_minutes" in cleared.model_fields_set


def test_every_operation_has_a_success_fixture() -> None:
    covered = {(e["operation_id"]) for e in INDEX["fixtures"] if e["status"] < 300}
    declared = {op["operationId"] for ops in OPENAPI["paths"].values() for op in ops.values()}
    missing = declared - covered
    assert not missing, f"operations without a success fixture: {sorted(missing)}"


def test_errors_use_the_envelope_everywhere() -> None:
    assert "HTTPValidationError" not in json.dumps(OPENAPI)
    for ops in OPENAPI["paths"].values():
        for op in ops.values():
            for code, response in op["responses"].items():
                if int(code) >= 400:
                    assert response["content"]["application/json"]["schema"]["$ref"].endswith(
                        "/ErrorResponse"
                    )


def test_published_fixture_has_no_hard_violations_and_honest_coverage() -> None:
    version = load("schedule_week.published")["response"]["body"]["current_version"]
    assert version["validation"]["hard_violations"] == 0
    assert version["metrics"]["minimum_deficit_minutes"] == 0
    cells = version["coverage"]
    covered = sum(min(c["scheduled"], c["preferred_required"]) for c in cells)
    target = sum(c["preferred_required"] for c in cells)
    assert version["metrics"]["coverage_ratio"] == round(covered / target, 4)


def test_every_operation_rejects_missing_credentials_with_the_envelope() -> None:
    """No route is a stub any more, and auth runs before any database access."""
    app = FastAPI()
    install(app)
    client = TestClient(app)
    ids = {
        "outlet_id": uuid.uuid4(),
        "employee_id": uuid.uuid4(),
        "version_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "schedule_id": uuid.uuid4(),
        "absence_id": uuid.uuid4(),
        "candidate_id": uuid.uuid4(),
        "import_id": uuid.uuid4(),
        "notification_id": uuid.uuid4(),
        "rule_id": uuid.uuid4(),
        "proposal_id": uuid.uuid4(),
        "week_start": "2026-10-19",
    }
    for path, ops in OPENAPI["paths"].items():
        for method, op in ops.items():
            url = path.format(**ids)
            response = client.request(method.upper(), url, params={"week_start": "2026-10-19"}, json={})
            if op["operationId"] == "createDemoSession":
                continue  # public by design; covered by the API integration tests
            assert response.status_code == 401, (op["operationId"], response.status_code)
            assert schemas.ErrorResponse.model_validate(response.json()).error.code == "unauthenticated"


def run_body(**changes: Any) -> dict[str, Any]:
    body = load("run.succeeded")["response"]["body"]
    body.update(changes)
    return body


@pytest.mark.parametrize(
    "changes",
    [
        {"solver_status": "INFEASIBLE"},  # infeasible with candidates
        {"solver_status": "UNKNOWN"},  # timeout without a solution cannot carry candidates
        {"job_state": "running"},  # running run already has results
        {"job_state": "failed"},  # failed without error
        {"candidates": []},  # OPTIMAL with nothing to show
    ],
)
def test_inconsistent_run_states_are_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        schemas.OptimizationRun.model_validate(run_body(**changes))


def test_candidate_cannot_claim_optimality_or_carry_hard_violations() -> None:
    candidate = load("run.succeeded")["response"]["body"]["candidates"][0]
    with pytest.raises(ValidationError):
        schemas.Candidate.model_validate({**candidate, "solver_status": "FEASIBLE", "proven_optimal": True})
    bad_validation = {**candidate["validation"], "hard_violations": 1}
    with pytest.raises(ValidationError):
        schemas.Candidate.model_validate({**candidate, "validation": bad_validation})


def test_staffing_preferred_below_minimum_is_rejected() -> None:
    interval = load("staffing.get")["response"]["body"]["intervals"][0]
    with pytest.raises(ValidationError):
        schemas.StaffingInterval.model_validate({**interval, "minimum_required": 3, "preferred_required": 2})


def test_audit_actions_are_registered_and_follow_v3() -> None:
    """A3.12 (architecture v3 section 26): every _audit call uses a registered name."""
    import re

    from api.v2.service import AUDIT_ACTIONS

    api = CONTRACTS.parents[1] / "api" / "v2"
    source = "\n".join(p.read_text(encoding="utf-8") for p in api.glob("*.py"))
    used = set(re.findall(r'_audit\(\s*session,\s*caller,\s*"([A-Z_]+)"', source))
    assert used and used <= AUDIT_ACTIONS
    decisions = {f"ABSENCE_{status.upper()}" for status in ("confirmed", "rejected", "cancelled")}
    assert decisions <= AUDIT_ACTIONS  # built dynamically in absences.update
    assert {"SHIFT_EDITED", "OPTIMIZATION_REQUESTED", "ABSENCE_REPORTED", "PROPOSAL_APPROVED"} <= used
    assert {"SCHEDULE_PUBLISHED", "SCHEDULE_RESTORED"} <= used and "SHIFTS_EDITED" not in AUDIT_ACTIONS
