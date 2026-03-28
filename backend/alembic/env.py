"""Alembic environment configuration for async PostgreSQL."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base and all module models so metadata includes every table.
from lingshu.setting.models import Base  # noqa: F401 – registers setting tables
import lingshu.ontology.models  # noqa: F401 – registers ontology tables
import lingshu.data.models  # noqa: F401 – registers data tables
import lingshu.function.models  # noqa: F401 – registers function tables
import lingshu.copilot.models  # noqa: F401 – registers copilot tables

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Resolve database URL: prefer LINGSHU_DATABASE_URL env var, fall back to settings.
_db_url = os.environ.get("LINGSHU_DATABASE_URL")
if not _db_url:
    from lingshu.config import get_settings

    _db_url = get_settings().database_url

config.set_main_option("sqlalchemy.url", _db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
