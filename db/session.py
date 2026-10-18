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
def app_engine() -> Engine:
    return create_engine(settings().app_database_url, pool_pre_ping=True)


@contextmanager
def admin_session() -> Iterator[Session]:
    with sessionmaker(admin_engine())() as s, s.begin():
        yield s


@contextmanager
def tenant_session(caller: Caller) -> Iterator[Session]:
    with sessionmaker(app_engine())() as s, s.begin():
        s.execute(text("select set_config('app.org_id', :org, true)"), {"org": caller.org_id})
        s.execute(text("select set_config('app.user_id', :uid, true)"), {"uid": caller.user_id})
        yield s
