"""Bring the database schema to the latest migration (Alembic), creating it if empty.

    python -m db.init            # upgrade to head; adopts a pre-Alembic database if it matches 0001
    python -m db.init --drop     # DEVELOPMENT ONLY: drop the public schema first, then upgrade

The schema, app role, grants and RLS policies all live in db/migrations. A database created by the
old create_all-based db.init is adopted only after `db.migrate.adopt` proves it is identical to
revision 0001; otherwise nothing is changed.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from core.config import settings
from db import migrate
from db.session import admin_engine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop", action="store_true", help="drop the public schema first (dev only)")
    args = parser.parse_args()
    url = settings().database_url
    engine = admin_engine()
    if args.drop:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    with engine.connect() as conn:
        tables = set(
            conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars()
        )
    if tables and "alembic_version" not in tables:
        ok, problems = migrate.adopt(url)
        if not ok:
            print("Existing schema does not match migration 0001; nothing was changed:")
            for p in problems:
                print(f"  - {p}")
            return 1
        print("Adopted existing schema as revision 0001.")
    migrate.upgrade(url)
    print("Schema at head.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
