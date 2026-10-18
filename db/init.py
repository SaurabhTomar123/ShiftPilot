"""Create schema, the app role and row-level security policies.

    python -m db.init            # create tables + RLS (idempotent)
    python -m db.init --drop     # drop everything first

Alembic can replace create_all once the schema settles (`alembic init db/migrations`).
"""

from __future__ import annotations

import argparse

from sqlalchemy import text

from core.config import settings
from db.models import TENANT_TABLES, Base
from db.session import admin_engine

APP_ROLE = "shiftpilot_app"


def rls_statements(password: str) -> list[str]:
    stmts = [
        "CREATE EXTENSION IF NOT EXISTS vector",
        f"""DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS;
              END IF;
            END $$""",
        f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
        f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}",
        # Audit log is append-only for the app.
        f"REVOKE UPDATE ON audit_log FROM {APP_ROLE}",
        "ALTER TABLE organizations ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation ON organizations",
        "CREATE POLICY tenant_isolation ON organizations "
        "USING (id = nullif(current_setting('app.org_id', true), '')::uuid)",
    ]
    for table in TENANT_TABLES:
        stmts += [
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
            f"DROP POLICY IF EXISTS tenant_isolation ON {table}",
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (org_id = nullif(current_setting('app.org_id', true), '')::uuid) "
            "WITH CHECK (org_id = nullif(current_setting('app.org_id', true), '')::uuid)",
        ]
    return stmts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop", action="store_true")
    args = parser.parse_args()

    engine = admin_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    if args.drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for stmt in rls_statements(settings().app_db_password):
            conn.execute(text(stmt))
    print(f"Schema ready: {len(Base.metadata.tables)} tables, RLS on {len(TENANT_TABLES) + 1}.")


if __name__ == "__main__":
    main()
