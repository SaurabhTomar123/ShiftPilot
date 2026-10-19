"""B1.3 acceptance: deterministic v2 seed, fixture-compatible IDs and tenant-scoped reset."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import Connection, create_engine, make_url, text

from core.config import settings
from db import migrate
from seed import v2
from seed.world import uid

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "v2" / "fixtures"


@pytest.fixture
def db() -> Iterator[str]:
    with migrate.scratch_database(settings().database_url) as url:
        migrate.upgrade(url)
        yield url


def admin(url: str) -> Connection:
    return create_engine(url).connect()


def load(url: str, *orgs: str) -> None:
    with create_engine(url).begin() as conn:
        for org in orgs:
            v2.load_org(conn, org)


def count(conn: Connection, sql: str, **params: object) -> int:
    return int(conn.execute(text(sql), params).scalar_one())


def snapshot(conn: Connection, org: object) -> dict[str, int]:
    tables = [
        "employees",
        "employee_skills",
        "employee_availability",
        "version_shifts",
        "staffing_requirements",
        "demand_inputs",
        "schedules",
        "absences",
        "users",
    ]
    return {t: count(conn, f"SELECT count(*) FROM {t} WHERE org_id = :o", o=org) for t in tables}


def test_seed_builds_the_demo_world(db: str) -> None:
    load(db, v2.SPICE, v2.NORTHWIND)
    org = uid("org", v2.SPICE)
    with admin(db) as conn:
        assert count(conn, "SELECT count(*) FROM outlets WHERE org_id = :o", o=org) == 3
        assert count(conn, "SELECT count(*) FROM employees WHERE org_id = :o", o=org) == 60
        assert count(conn, "SELECT count(*) FROM skills WHERE org_id = :o", o=org) == 5
        published = conn.execute(
            text(
                "SELECT s.outlet_id, count(vs.id) FROM schedules s "
                "JOIN schedule_versions v ON v.id = s.current_version_id AND v.status = 'published' "
                "JOIN version_shifts vs ON vs.version_id = v.id "
                "WHERE s.org_id = :o GROUP BY s.outlet_id"
            ),
            {"o": org},
        ).all()
        assert sorted(n for _, n in published) == [60, 60, 60]
        assert count(conn, "SELECT count(*) FROM demand_inputs WHERE org_id = :o", o=org) == 3 * 28 * 26
        assert count(conn, "SELECT count(*) FROM version_shifts WHERE org_id = :o AND locked", o=org) == 1


def test_seed_ids_match_the_contract_fixtures(db: str) -> None:
    load(db, v2.SPICE)
    week = json.loads((FIXTURES / "schedule_week.published.json").read_text())["response"]["body"]
    roster = json.loads((FIXTURES / "employees.list.json").read_text())["response"]["body"]["items"]
    with admin(db) as conn:
        assert {
            str(r)
            for r in conn.execute(
                text("SELECT id FROM employees WHERE outlet_id = :o"), {"o": uid("outlet", "indiranagar")}
            ).scalars()
        } >= {e["id"] for e in roster}
        seeded = {
            (str(r.logical_shift_id), str(r.employee_id), r.start_at)
            for r in conn.execute(
                text(
                    "SELECT vs.logical_shift_id, vs.employee_id, vs.start_at FROM version_shifts vs "
                    "JOIN schedules s ON s.current_version_id = vs.version_id WHERE s.id = :s"
                ),
                {"s": week["schedule_id"]},
            )
        }
    fixture = {
        (sh["logical_shift_id"], sh["employee_id"], datetime.fromisoformat(sh["start_at"]))
        for sh in week["current_version"]["shifts"]
    }
    assert len(seeded) == 60
    assert seeded == fixture  # aware datetimes compare by instant, whatever the offset


def test_reload_is_idempotent(db: str) -> None:
    load(db, v2.SPICE)
    with admin(db) as conn:
        first = snapshot(conn, uid("org", v2.SPICE))
    load(db, v2.SPICE)
    with admin(db) as conn:
        assert snapshot(conn, uid("org", v2.SPICE)) == first


def test_reset_never_touches_another_tenant(db: str) -> None:
    load(db, v2.SPICE, v2.NORTHWIND)
    with admin(db) as conn:
        before = snapshot(conn, uid("org", v2.NORTHWIND))
    with create_engine(db).begin() as conn:
        v2.reset_org(conn, uid("org", v2.SPICE))
    with admin(db) as conn:
        assert snapshot(conn, uid("org", v2.NORTHWIND)) == before
        assert snapshot(conn, uid("org", v2.SPICE)) == dict.fromkeys(before, 0)
        assert count(conn, "SELECT count(*) FROM organizations") == 1


def test_runtime_role_sees_only_its_tenant(db: str) -> None:
    load(db, v2.SPICE, v2.NORTHWIND)
    app_url = make_url(settings().app_database_url).set(database=make_url(db).database)
    with create_engine(app_url).begin() as conn:
        conn.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(uid("org", v2.NORTHWIND))})
        assert count(conn, "SELECT count(*) FROM employees") == 4
        assert count(conn, "SELECT count(*) FROM version_shifts") == 0
