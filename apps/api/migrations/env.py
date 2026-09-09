import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.sql.schema import SchemaItem

import lorenzo_api.models  # noqa: F401  # registers all models on Base.metadata for autogenerate
from lorenzo_api.config import get_settings
from lorenzo_api.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Views (currently v_item/v_item_instance - ADR 0019) are hand-written
# CREATE VIEW statements, not op.create_table() - Alembic has no native
# "this is a view" concept, so without this, autogenerate sees a
# declarative Table with no matching real table in the database and tries
# to create one.
_VIEW_TABLE_NAMES = frozenset({"v_item", "v_item_instance"})


def include_object(
    object_: SchemaItem,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    return not (type_ == "table" and name in _VIEW_TABLE_NAMES)


def get_url() -> str:
    # Privileged, not the app's own restricted connection - see ADR 0021.
    return get_settings().migrations_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, include_object=include_object
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
