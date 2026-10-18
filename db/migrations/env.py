"""Alembic environment. Migrations always run with the admin URL (never the RLS-bound app role).

    python -m alembic upgrade head
    python -m alembic -x url=postgresql+psycopg://... upgrade head   # explicit database

The URL comes from `-x url=...`, then the Config's `sqlalchemy.url` (tests set it), then
`settings().database_url`.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from core.config import settings
from db import models_v2  # noqa: F401  (registers v2 tables on Base.metadata)
from db.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    return (
        context.get_x_argument(as_dictionary=True).get("url")
        or config.get_main_option("sqlalchemy.url")
        or settings().database_url
    )


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
