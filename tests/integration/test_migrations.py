"""B1.1 acceptance: migrations, adoption, tenant isolation and version immutability.

Each test gets its own scratch database on the server DATABASE_URL points at (a disposable one —
see docs/runbooks/backend-baseline.md). Needs CREATEDB for the admin role.

    python -m pytest -m integration tests/integration/test_migrations.py
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, create_engine, make_url, text
from sqlalchemy.exc import DBAPIError

from core.config import settings
from db import migrate, models_v2  # noqa: F401  (registers v2 tables for compare_metadata)
from db.models import Base

pytestmark = pytest.mark.integration


@pytest.fixture
def db() -> Iterator[str]:
    with migrate.scratch_database(settings().database_url) as url:
        yield url


def admin(url: str) -> Connection:
    return create_engine(url, isolation_level="AUTOCOMMIT").connect()


def app(url: str, org_id: uuid.UUID) -> Connection:
    """Runtime role connection scoped to one tenant, like db.session.tenant_session."""
    app_url = make_url(settings().app_database_url).set(database=make_url(url).database)
    conn = create_engine(app_url, isolation_level="AUTOCOMMIT").connect()
    conn.execute(text("select set_config('app.org_id', :o, false)"), {"o": str(org_id)})
    return conn


def sqlstate(exc: pytest.ExceptionInfo[DBAPIError]) -> str:
    return getattr(exc.value.orig, "sqlstate", "")


def tables(conn: Connection) -> set[str]:
    return set(conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars())


def tenant(conn: Connection, name: str) -> dict[str, uuid.UUID]:
    """Minimal tenant at head: org, outlet, employee, user, skill."""
    ids = {k: uuid.uuid4() for k in ("org", "ot", "outlet", "employee", "user", "skill")}
    conn.execute(
        text("INSERT INTO organizations (id, name, plan) VALUES (:org, :n, 'demo')"), {**ids, "n": name}
    )
    conn.execute(
        text(
            "INSERT INTO ot_rules (id, org_id, daily_threshold_hrs, weekly_threshold_hrs, multiplier) "
            "VALUES (:ot, :org, 9, 48, 2)"
        ),
        ids,
    )
    conn.execute(
        text(
            "INSERT INTO outlets (id, org_id, name, slug, city, timezone, ot_rule_id) "
            "VALUES (:outlet, :org, 'Main', 'main', 'Bengaluru', 'Asia/Kolkata', :ot)"
        ),
        ids,
    )
    conn.execute(
        text(
            "INSERT INTO employees (id, org_id, outlet_id, name, aliases, job_role, pay_type, hourly_rate, "
            "phone, joined_on, status) VALUES (:employee, :org, :outlet, 'Ravi', '{}', 'cook', 'hourly', "
            "210, '+910000000000', '2025-01-01', 'active')"
        ),
        ids,
    )
    conn.execute(
        text(
            "INSERT INTO users (id, org_id, outlet_id, name, phone, role, is_active) "
            "VALUES (:user, :org, :outlet, 'Mgr', :phone, 'manager', true)"
        ),
        {**ids, "phone": f"+91{uuid.uuid4().int % 10**10:010d}"},
    )
    conn.execute(text("INSERT INTO skills (id, org_id, name) VALUES (:skill, :org, 'Grill')"), ids)
    return ids


def draft_with_shift(
    conn: Connection, t: dict[str, uuid.UUID], week: date = date(2026, 10, 19)
) -> dict[str, Any]:
    ids: dict[str, Any] = {
        **t,
        "schedule": uuid.uuid4(),
        "version": uuid.uuid4(),
        "logical": uuid.uuid4(),
        "shift": uuid.uuid4(),
        "week": week,
    }
    start = datetime(2026, 10, 19, 4, 30, tzinfo=UTC)
    conn.execute(
        text(
            "INSERT INTO schedules (id, org_id, outlet_id, week_start) VALUES (:schedule, :org, :outlet, "
            ":week)"
        ),
        ids,
    )
    conn.execute(
        text(
            "INSERT INTO schedule_versions (id, org_id, schedule_id, version_number, status, source, "
            "input_hash) VALUES (:version, :org, :schedule, 1, 'draft', 'manual', 'h')"
        ),
        ids,
    )
    conn.execute(
        text(
            "INSERT INTO logical_shifts (id, org_id, schedule_id, created_in_version_id) "
            "VALUES (:logical, :org, :schedule, :version)"
        ),
        ids,
    )
    conn.execute(
        text(
            "INSERT INTO version_shifts (id, org_id, schedule_id, version_id, logical_shift_id, outlet_id, "
            "employee_id, skill_id, start_at, end_at) VALUES (:shift, :org, :schedule, :version, :logical, "
            ":outlet, :employee, :skill, :s, :e)"
        ),
        {**ids, "s": start, "e": start + timedelta(hours=8)},
    )
    return ids


def publish(conn: Connection, version: uuid.UUID) -> None:
    conn.execute(
        text("UPDATE schedule_versions SET status = 'published', published_at = now() WHERE id = :v"),
        {"v": version},
    )


# ---------------------------------------------------------------- migrations


def test_fresh_upgrade_matches_models(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []


def test_downgrade_to_base_and_back(db: str) -> None:
    migrate.upgrade(db)
    command.downgrade(migrate.alembic_config(db), "base")
    with admin(db) as conn:
        assert tables(conn) <= {"alembic_version"}
    migrate.upgrade(db)
    with admin(db) as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []


def test_adopt_accepts_an_identical_pre_alembic_schema(db: str) -> None:
    migrate.upgrade(db, "0001")
    with admin(db) as conn:
        conn.execute(text("DROP TABLE alembic_version"))
    ok, problems = migrate.adopt(db)
    assert ok, problems
    with admin(db) as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"


def test_adopt_refuses_a_different_schema_and_changes_nothing(db: str) -> None:
    migrate.upgrade(db, "0001")
    with admin(db) as conn:
        conn.execute(text("DROP TABLE alembic_version"))
        conn.execute(text("DROP POLICY tenant_isolation ON outlets"))
    ok, problems = migrate.adopt(db)
    assert not ok
    assert any(p.startswith("policies: only in revision 0001") and "outlets" in p for p in problems)
    with admin(db) as conn:
        assert "alembic_version" not in tables(conn)


def test_adopt_refuses_empty_and_managed_databases(db: str) -> None:
    assert migrate.adopt(db)[0] is False
    migrate.upgrade(db)
    ok, problems = migrate.adopt(db)
    assert not ok and "already managed" in problems[0]


def test_populated_v1_upgrade_preserves_rows_and_backfills_skills(db: str) -> None:
    migrate.upgrade(db, "0001")
    org, ot, outlet = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with admin(db) as conn:
        conn.execute(
            text("INSERT INTO organizations (id, name, plan) VALUES (:o, 'Old Co', 'demo')"), {"o": org}
        )
        conn.execute(
            text(
                "INSERT INTO ot_rules (id, org_id, daily_threshold_hrs, weekly_threshold_hrs, multiplier) "
                "VALUES (:ot, :o, 9, 48, 2)"
            ),
            {"ot": ot, "o": org},
        )
        conn.execute(
            text(
                "INSERT INTO outlets (id, org_id, name, slug, city, timezone, ot_rule_id) "
                "VALUES (:out, :o, 'Old', 'old', 'Pune', 'Asia/Kolkata', :ot)"
            ),
            {"out": outlet, "o": org, "ot": ot},
        )
        for i, role in enumerate(["cook", "cook", "server"]):
            conn.execute(
                text(
                    "INSERT INTO employees (id, org_id, outlet_id, name, aliases, job_role, pay_type, "
                    "hourly_rate, phone, joined_on, status) VALUES (gen_random_uuid(), :o, :out, :n, '{}', "
                    ":r, 'hourly', 200, '+91', '2025-01-01', 'active')"
                ),
                {"o": org, "out": outlet, "n": f"E{i}", "r": role},
            )
        before = conn.execute(text("SELECT count(*) FROM employees")).scalar()
    migrate.upgrade(db)
    with admin(db) as conn:
        assert conn.execute(text("SELECT count(*) FROM employees")).scalar() == before == 3
        assert set(conn.execute(text("SELECT name FROM skills")).scalars()) == {"Cook", "Server"}
        assert conn.execute(text("SELECT count(*) FROM employee_skills")).scalar() == 3
        row = conn.execute(
            text("SELECT regular_weekly_minutes, max_weekly_minutes, revision FROM employees LIMIT 1")
        ).one()
        assert tuple(row) == (2880, 2880, 1)
        assert conn.execute(text("SELECT timezone FROM organizations")).scalar() == "Asia/Kolkata"


# ---------------------------------------------------------------- tenant isolation


def test_rls_hides_and_rejects_other_tenants_v2_rows(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        a, b = tenant(conn, "A"), tenant(conn, "B")
    with app(db, a["org"]) as conn:
        assert set(conn.execute(text("SELECT id FROM skills")).scalars()) == {a["skill"]}
        with pytest.raises(DBAPIError) as exc:
            conn.execute(
                text("INSERT INTO skills (id, org_id, name) VALUES (gen_random_uuid(), :o, 'Prep')"),
                {"o": b["org"]},
            )
        assert sqlstate(exc) == "42501"  # new row violates row-level security policy


def test_composite_keys_block_cross_tenant_links_even_for_admin(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        a, b = tenant(conn, "A"), tenant(conn, "B")
        with pytest.raises(DBAPIError) as exc:
            conn.execute(
                text("INSERT INTO employee_skills (org_id, employee_id, skill_id) VALUES (:o, :e, :s)"),
                {"o": a["org"], "e": a["employee"], "s": b["skill"]},
            )
        assert sqlstate(exc) == "23503"  # foreign_key_violation


def test_outlet_slugs_are_unique_per_org_not_globally(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        a, b = tenant(conn, "A"), tenant(conn, "B")  # both use slug 'main'
        assert conn.execute(text("SELECT count(*) FROM outlets WHERE slug = 'main'")).scalar() == 2
        with pytest.raises(DBAPIError):
            conn.execute(
                text(
                    "INSERT INTO outlets (id, org_id, name, slug, city, ot_rule_id) "
                    "VALUES (gen_random_uuid(), :o, 'Dup', 'main', 'X', :ot)"
                ),
                {"o": a["org"], "ot": a["ot"]},
            )
        del b


# ---------------------------------------------------------------- immutability


def test_published_version_shifts_are_immutable(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        ids = draft_with_shift(conn, tenant(conn, "A"))
        conn.execute(text("UPDATE version_shifts SET locked = true WHERE id = :shift"), ids)  # draft: allowed
        publish(conn, ids["version"])
        for stmt in (
            "UPDATE version_shifts SET locked = false WHERE id = :shift",
            "DELETE FROM version_shifts WHERE id = :shift",
        ):
            with pytest.raises(DBAPIError) as exc:
                conn.execute(text(stmt), ids)
            assert sqlstate(exc) == "23514"


def test_version_status_transitions_are_enforced(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        ids = draft_with_shift(conn, tenant(conn, "A"))
        publish(conn, ids["version"])
        for stmt in (
            "UPDATE schedule_versions SET status = 'draft', published_at = NULL WHERE id = :version",
            "UPDATE schedule_versions SET reason = 'rewritten' WHERE id = :version",
            "UPDATE schedule_versions SET status = 'superseded', reason = 'sneaky' WHERE id = :version",
        ):
            with pytest.raises(DBAPIError):
                conn.execute(text(stmt), ids)
        conn.execute(text("UPDATE schedule_versions SET status = 'superseded' WHERE id = :version"), ids)
        with pytest.raises(DBAPIError):
            conn.execute(text("UPDATE schedule_versions SET status = 'published' WHERE id = :version"), ids)


def test_current_version_must_belong_to_the_same_schedule(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        t = tenant(conn, "A")
        one = draft_with_shift(conn, t, date(2026, 10, 19))
        two = draft_with_shift(conn, t, date(2026, 10, 26))
        conn.execute(text("UPDATE schedules SET current_version_id = :version WHERE id = :schedule"), one)
        with pytest.raises(DBAPIError) as exc:
            conn.execute(
                text("UPDATE schedules SET current_version_id = :v WHERE id = :s"),
                {"v": two["version"], "s": one["schedule"]},
            )
        assert sqlstate(exc) == "23503"


def test_app_role_cannot_delete_versions_or_rewrite_audit(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        t = tenant(conn, "A")
        ids = draft_with_shift(conn, t)
        conn.execute(
            text(
                "INSERT INTO audit_log (id, org_id, channel, tool, args_redacted, outcome) "
                "VALUES (gen_random_uuid(), :org, 'web', 'publish', '{}', 'ok')"
            ),
            t,
        )
    with app(db, t["org"]) as conn:
        for stmt in (
            "DELETE FROM schedule_versions WHERE id = :version",
            "UPDATE logical_shifts SET created_in_version_id = :version",
            "UPDATE audit_log SET outcome = 'error'",
            "DELETE FROM audit_log",
        ):
            with pytest.raises(DBAPIError) as exc:
                conn.execute(text(stmt), ids)
            assert sqlstate(exc) == "42501", stmt


# ---------------------------------------------------------------- durable work (0004, architecture rev 2)


def queue_run(conn: Connection, t: dict[str, uuid.UUID], key: str, lane: str = "batch") -> uuid.UUID:
    run = uuid.uuid7()
    conn.execute(
        text(
            "INSERT INTO optimization_runs (id, org_id, kind, lane, strategy, outlet_ids, base_version_ids, "
            "idempotency_key, request_hash, input_hash, input_snapshot, config) "
            "VALUES (:id, :org, 'generate', "
            ":lane, 'balanced', ARRAY[CAST(:outlet AS uuid)], '{}', :key, 'r', 'i', '{}', '{}')"
        ),
        {"id": run, "org": t["org"], "outlet": t["outlet"], "key": key, "lane": lane},
    )
    return run


def test_one_active_run_per_schedule(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        t = tenant(conn, "A")
        ids = draft_with_shift(conn, t)
        first, second = queue_run(conn, t, "k1"), queue_run(conn, t, "k2")
        slot = "INSERT INTO schedule_run_slots (org_id, schedule_id, run_id) VALUES (:org, :schedule, :run)"
        conn.execute(text(slot), {**ids, "run": first})
        with pytest.raises(DBAPIError) as exc:
            conn.execute(text(slot), {**ids, "run": second})
        assert sqlstate(exc) == "23505"  # unique_violation -> API answers 409 with the active run
        conn.execute(text("DELETE FROM schedule_run_slots WHERE run_id = :run"), {"run": first})
        conn.execute(text(slot), {**ids, "run": second})


def test_outbox_is_tenant_scoped_and_append_only_for_the_app(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        a, b = tenant(conn, "A"), tenant(conn, "B")
    insert = (
        "INSERT INTO outbox_events (id, org_id, topic, aggregate_type, aggregate_id, payload) "
        "VALUES (:id, :org, 'schedule.published', 'schedule_version', :agg, '{}')"
    )
    with app(db, a["org"]) as conn:
        conn.execute(text(insert), {"id": uuid.uuid7(), "org": a["org"], "agg": uuid.uuid7()})
        for stmt, params in (
            (insert, {"id": uuid.uuid7(), "org": b["org"], "agg": uuid.uuid7()}),
            ("UPDATE outbox_events SET published_at = now()", {}),
            ("DELETE FROM outbox_events", {}),
        ):
            with pytest.raises(DBAPIError) as exc:
                conn.execute(text(stmt), params)
            assert sqlstate(exc) == "42501", stmt
        with pytest.raises(DBAPIError):
            conn.execute(
                text(insert.replace("schedule.published", "made.up")),
                {"id": uuid.uuid7(), "org": a["org"], "agg": uuid.uuid7()},
            )


def test_worker_claim_query_can_use_its_partial_index(db: str) -> None:
    migrate.upgrade(db)
    with admin(db) as conn:
        t = tenant(conn, "A")
        for i in range(3):
            queue_run(conn, t, f"k{i}", lane="interactive" if i else "batch")
        conn.execute(text("SET enable_seqscan = off"))
        plan = "\n".join(
            conn.execute(
                text(
                    "EXPLAIN SELECT id FROM optimization_runs "
                    "WHERE lane = 'interactive' AND job_state = 'queued' "
                    "ORDER BY priority, queued_at FOR UPDATE SKIP LOCKED LIMIT 1"
                )
            ).scalars()
        )
        assert "ix_optimization_runs_claim" in plan, plan


def test_new_rows_get_time_ordered_uuid7_keys() -> None:
    from db.models import AuditLog
    from db.models_v2 import OutboxEvent, VersionShift

    for model in (AuditLog, OutboxEvent, VersionShift):
        default = model.__table__.c.id.default
        assert default is not None and default.arg.__name__ == "uuid7", model.__name__
