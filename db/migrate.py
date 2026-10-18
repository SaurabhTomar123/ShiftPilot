"""Migration helpers around Alembic.

    python -m db.migrate upgrade            # alembic upgrade head (admin URL)
    python -m db.migrate adopt              # stamp a pre-Alembic db.init database as 0001, if identical
    python -m db.migrate fingerprint        # print the schema fingerprint (debugging)

`adopt` never stamps blind: it builds a scratch database at revision 0001, fingerprints both, and
stamps only when they match exactly. Otherwise it prints the differences and changes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Connection

from core.config import settings

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "0001"


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "db" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade(url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(url), revision)


def _rows(conn: Connection, sql: str) -> list[list[Any]]:
    return sorted([list(r) for r in conn.execute(text(sql))], key=json.dumps)


def fingerprint(conn: Connection) -> dict[str, Any]:
    """Everything that defines the schema's behaviour, normalised for comparison."""
    skip = "('alembic_version')"
    return {
        "extensions": _rows(conn, "SELECT extname FROM pg_extension WHERE extname <> 'plpgsql'"),
        "columns": _rows(
            conn,
            f"""
            SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default,
                   character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name NOT IN {skip}""",
        ),
        "constraints": _rows(
            conn,
            f"""
            SELECT c.conrelid::regclass::text, c.conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'public' AND c.conrelid::regclass::text NOT IN {skip}""",
        ),
        "indexes": _rows(
            conn,
            f"""
            SELECT tablename, indexname, indexdef FROM pg_indexes
            WHERE schemaname = 'public' AND tablename NOT IN {skip}""",
        ),
        "rls": _rows(
            conn,
            f"""
            SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r' AND relname NOT IN {skip}""",
        ),
        "policies": _rows(
            conn,
            """
            SELECT tablename, policyname, permissive, roles::text, cmd, qual, with_check
            FROM pg_policies WHERE schemaname = 'public'""",
        ),
        "grants": _rows(
            conn,
            f"""
            SELECT table_name, privilege_type FROM information_schema.role_table_grants
            WHERE grantee = 'shiftpilot_app' AND table_name NOT IN {skip}""",
        ),
        "triggers": _rows(
            conn,
            """
            SELECT event_object_table, trigger_name, action_timing, event_manipulation, action_statement
            FROM information_schema.triggers WHERE trigger_schema = 'public'""",
        ),
    }


def diff(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    out = []
    for key in sorted(set(a) | set(b)):
        left = {json.dumps(r) for r in a.get(key, [])}
        right = {json.dumps(r) for r in b.get(key, [])}
        out += [f"{key}: only in database: {r}" for r in sorted(left - right)]
        out += [f"{key}: only in revision {BASELINE}: {r}" for r in sorted(right - left)]
    return out


@contextmanager
def scratch_database(url: str) -> Iterator[str]:
    """A temporary empty database on the same server (needs CREATEDB, which the admin role has)."""
    name = f"shiftpilot_scratch_{uuid.uuid4().hex[:10]}"
    server = create_engine(make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(url).set(database=name).render_as_string(hide_password=False)
    finally:
        with server.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        server.dispose()


def adopt(url: str) -> tuple[bool, list[str]]:
    """Stamp `url` as BASELINE if (and only if) its schema matches the baseline revision exactly."""
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = set(
            conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars()
        )
        if "alembic_version" in tables:
            return False, ["database is already managed by Alembic; use upgrade"]
        if not tables:
            return False, ["database is empty; use upgrade instead of adopt"]
        current = fingerprint(conn)
    engine.dispose()
    with scratch_database(url) as ref_url:
        upgrade(ref_url, BASELINE)
        ref_engine = create_engine(ref_url)
        with ref_engine.connect() as conn:
            reference = fingerprint(conn)
        ref_engine.dispose()
    problems = diff(current, reference)
    if problems:
        return False, problems
    command.stamp(alembic_config(url), BASELINE)
    return True, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["upgrade", "adopt", "fingerprint"])
    parser.add_argument("--url", default=None, help="admin database URL (default: DATABASE_URL)")
    args = parser.parse_args()
    url = args.url or settings().database_url
    if args.action == "upgrade":
        upgrade(url)
        print("Upgraded to head.")
        return 0
    if args.action == "fingerprint":
        with create_engine(url).connect() as conn:
            print(json.dumps(fingerprint(conn), indent=2, default=str))
        return 0
    ok, problems = adopt(url)
    if ok:
        print(f"Adopted: schema matches revision {BASELINE}; stamped. Now run: python -m db.migrate upgrade")
        return 0
    print("Not adopted; nothing was changed:")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
