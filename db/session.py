"""Engines and tenant-scoped sessions.

Runtime code uses `tenant_session(caller)`: it connects as the non-superuser app role and sets
`app.org_id` for the transaction, so Postgres RLS filters every query to the caller's org even if
a tool forgets a WHERE clause.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.auth import Caller
from core.config import settings


@lru_cache
def admin_engine() -> Engine:
    return create_engine(settings().database_url, pool_pre_ping=True)


@lru_cache
def worker_engine() -> Engine:
    """The optimization worker's connection: the shiftpilot_worker role when configured (B6.3)."""
    url = settings().worker_database_url or settings().database_url
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def app_engine() -> Engine:
    return create_engine(settings().app_database_url, pool_pre_ping=True)


@contextmanager
def admin_session() -> Iterator[Session]:
    with sessionmaker(admin_engine())() as s, s.begin():
        yield s


@contextmanager
def tenant_session(caller: Caller, isolation: str | None = None) -> Iterator[Session]:
    """`isolation` (e.g. "REPEATABLE READ") applies to this transaction only; it must be chosen before
    the first statement, which is why it is a parameter here."""
    with sessionmaker(app_engine())() as s, s.begin():
        if isolation:
            s.connection(execution_options={"isolation_level": isolation})
        s.execute(text("select set_config('app.org_id', :org, true)"), {"org": caller.org_id})
        s.execute(text("select set_config('app.user_id', :uid, true)"), {"uid": caller.user_id})
        s.execute(text("select set_config('app.role', :role, true)"), {"role": str(caller.role)})
        yield s
