"""Demo sandboxes (B6.2): each public demo session gets its own copy of the synthetic template org.

clone() copies every tenant row of the template inside the database, remapping each UUID to
md5(salt || old)::uuid. The mapping is deterministic per sandbox, so every foreign key (including
composite tenant keys and uuid[] columns) stays consistent without a lookup table. Operational
history (runs, proposals, audit, outbox, idempotency keys, imports, notifications) is not copied: a
sandbox starts from the published synthetic weeks. purge() removes a sandbox entirely.

Both run with the admin connection; triggers and foreign-key checks are suspended for the transaction
because the rows are copied or removed as a consistent whole.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Connection, Table, text
from sqlalchemy.dialects.postgresql import UUID

from db import models_v2  # noqa: F401  (registers v2 tables on Base.metadata)
from db.models import Base

SKIP = {
    "audit_log",
    "outbox_events",
    "notification_deliveries",
    "idempotency_keys",
    "import_jobs",
    "import_rows",
    "optimization_runs",
    "optimization_candidates",
    "schedule_proposals",
    "demo_sandboxes",
}


def mapped(salt: str, old: uuid.UUID) -> uuid.UUID:
    """The id a template row gets in the sandbox (the same function clone() applies in SQL)."""
    return uuid.UUID(hashlib.md5(f"{salt}{old}".encode()).hexdigest())


def _tenant_tables() -> list[Table]:
    return [t for t in Base.metadata.sorted_tables if "org_id" in t.columns and t.name not in SKIP]


def _expression(table: Table, column: str) -> str:
    col = table.columns[column]
    if column == "org_id":
        return ":new_org"
    if isinstance(col.type, UUID):
        return f"CASE WHEN {column} IS NULL THEN NULL ELSE md5(:salt || {column}::text)::uuid END"
    if isinstance(col.type, ARRAY) and isinstance(col.type.item_type, UUID):
        return (
            f"ARRAY(SELECT md5(:salt || x::text)::uuid FROM unnest({column}) WITH ORDINALITY AS u(x, n) "
            "ORDER BY n)"
        )
    if table.name == "users" and column == "phone":  # globally unique
        return "'sbx' || left(md5(:salt || phone), 16)"
    return column


def clone(conn: Connection, template_org: uuid.UUID, new_org: uuid.UUID, salt: str) -> None:
    conn.execute(text("SET LOCAL session_replication_role = replica"))
    conn.execute(
        text(
            """INSERT INTO organizations (id, name, plan, timezone)
               SELECT :new_org, name || ' (demo)', 'sandbox', timezone
                 FROM organizations WHERE id = :template"""
        ),
        {"new_org": new_org, "template": template_org},
    )
    for table in _tenant_tables():
        columns = list(table.columns.keys())
        select = ", ".join(_expression(table, c) for c in columns)
        insert = f"INSERT INTO {table.name} ({', '.join(columns)}) SELECT {select} FROM {table.name}"
        conn.execute(
            text(f"{insert} WHERE org_id = :template"),
            {"new_org": new_org, "template": template_org, "salt": salt},
        )
    conn.execute(text("SET LOCAL session_replication_role = origin"))


def purge(conn: Connection, org_id: uuid.UUID) -> None:
    """Delete one sandbox org and everything in it (including runs, audit and notifications)."""
    conn.execute(text("SET LOCAL session_replication_role = replica"))
    for table in reversed(Base.metadata.sorted_tables):
        if "org_id" in table.columns and table.name != "demo_sandboxes":
            conn.execute(table.delete().where(table.c.org_id == org_id))
    conn.execute(text("DELETE FROM demo_sandboxes WHERE org_id = :o"), {"o": org_id})
    conn.execute(text("DELETE FROM organizations WHERE id = :o AND plan = 'sandbox'"), {"o": org_id})
    conn.execute(text("SET LOCAL session_replication_role = origin"))


def purge_expired(conn: Connection, now: datetime) -> int:
    expired = [
        r[0]
        for r in conn.execute(
            text("SELECT org_id FROM demo_sandboxes WHERE expires_at <= :now"), {"now": now}
        )
    ]
    for org_id in expired:
        purge(conn, org_id)
    return len(expired)
