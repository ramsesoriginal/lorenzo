"""A privileged (migrations_database_url) engine/session factory, for
tests' own cross-tenant fixture setup/teardown - deliberately bypasses RLS,
mirroring lorenzo_api.db's own shape but for the role migrations run as.
The app's own connection (lorenzo_api.db.engine/async_session_factory) is a
genuinely restricted role since ADR 0021 - that's what real assertions
should go through, not this module.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lorenzo_api.config import get_settings

admin_engine = create_async_engine(get_settings().migrations_database_url, pool_pre_ping=True)
admin_session_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
