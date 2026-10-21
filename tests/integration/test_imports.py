"""B5.4 acceptance: employee CSV onboarding (architecture v3 section 19)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from db.session import admin_engine
from importer.employees_csv import COLUMNS
from jobs import retention
from tests.integration.test_api_v2 import MANAGER, NW_OWNER, OWNER, STAFF, client, error_code

pytestmark = pytest.mark.integration
__all__ = ["client"]
WEEK = ",".join(["10:00", "22:00"] * 5 + [""] * 4)


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"k-{uuid.uuid4().hex[:12]}"}


def csv(*rows: str) -> str:
    return chr(10).join([",".join(COLUMNS), *rows])


def stage(c: TestClient, content: str, as_: dict[str, str] = MANAGER) -> Any:
    return c.post(
        "/v2/imports/employees", headers=as_ | key(), json={"filename": "staff.csv", "content": content}
    )


def count(statement: str, **params: Any) -> int:
    with admin_engine().begin() as conn:
        return int(conn.execute(text(statement), params).scalar_one())


def test_template_and_permissions(client: TestClient) -> None:
    t = client.get("/v2/imports/employees/template", headers=MANAGER)
    assert t.status_code == 200 and t.json()["columns"] == list(COLUMNS)
    assert client.get("/v2/imports/employees/template", headers=STAFF).status_code == 403
    assert stage(client, csv(), as_=STAFF).status_code == 403


def test_valid_file_commits_every_employee_in_one_transaction(client: TestClient) -> None:
    before = count("SELECT count(*) FROM employees")
    staged = stage(
        client,
        csv(
            f"Asha Nair,Indiranagar,Grill;Prep,190,48,40,{WEEK}",
            f"Dev Sharma,indiranagar,Server,170,40,,{WEEK}",
        ),
    )
    assert staged.status_code == 201, staged.text
    job = staged.json()
    assert job["status"] == "staged" and job["error_count"] == 0 and len(job["rows"]) == 2
    assert count("SELECT count(*) FROM employees") == before  # staging writes no business rows

    k = key()
    done = client.post(f"/v2/imports/{job['id']}/commit", headers=MANAGER | k)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "committed" and all(r["employee_id"] for r in body["rows"])
    assert count("SELECT count(*) FROM employees") == before + 2
    assert client.post(f"/v2/imports/{job['id']}/commit", headers=MANAGER | k).json() == body  # replay
    again = client.post(f"/v2/imports/{job['id']}/commit", headers=MANAGER | key())
    assert again.status_code == 409 and again.json()["error"]["details"]["status"] == "committed"

    asha = client.get(f"/v2/employees/{body['rows'][0]['employee_id']}", headers=MANAGER).json()
    assert asha["name"] == "Asha Nair" and asha["hourly_rate"]["amount_paise"] == 19000
    assert asha["max_weekly_minutes"] == 2880 and asha["preferred_weekly_minutes"] == 2400
    assert len(asha["skills"]) == 2 and not asha["overtime_allowed"]
    windows = client.get(f"/v2/employees/{asha['id']}/availability", headers=MANAGER).json()["windows"]
    assert len(windows) == 5 and windows[0]["start_minute"] == 600
    assert count("SELECT count(*) FROM audit_log WHERE action = 'IMPORT_COMMITTED'") == 1


def test_invalid_rows_are_reported_and_nothing_is_written(client: TestClient) -> None:
    before = count("SELECT count(*) FROM employees")
    r = stage(
        client,
        csv(
            f"Zoe,Mars,Grill;Juggling,190,48,40,{WEEK}",
            f"Ravi Kumar,Indiranagar,Grill,190,48,,{WEEK}",  # already works there
            f"Kiran,Koramangala,Grill,190,48,,{WEEK}",  # outside this manager's outlet
        ),
    )
    job = r.json()
    assert r.status_code == 201 and job["status"] == "invalid" and job["error_count"] == 3
    columns = [{e["column"] for e in row["errors"]} for row in job["rows"]]
    assert columns == [{"outlet", "skills"}, {"name"}, {"outlet"}]
    refused = client.post(f"/v2/imports/{job['id']}/commit", headers=MANAGER | key())
    assert refused.status_code == 409 and error_code(refused) == "conflict"
    assert count("SELECT count(*) FROM employees") == before
    header = stage(client, "name,outlet" + chr(10) + "x,y").json()
    assert header["status"] == "invalid" and header["file_errors"] and header["rows"] == []


def test_staged_imports_expire(client: TestClient) -> None:
    job = stage(client, csv(f"Meera,Indiranagar,Server,160,40,,{WEEK}")).json()
    assert job["status"] == "staged"
    report = retention.run(now=datetime.now(UTC) + timedelta(hours=25))
    assert report["imports_expired"] >= 1 and report["import_rows_deleted"] >= 1
    late = client.post(f"/v2/imports/{job['id']}/commit", headers=MANAGER | key())
    assert late.status_code == 409 and late.json()["error"]["details"]["status"] == "expired"
    assert client.get(f"/v2/imports/{job['id']}", headers=NW_OWNER).status_code == 404  # other tenant
    assert client.get(f"/v2/imports/{job['id']}", headers=OWNER).json()["status"] == "expired"
