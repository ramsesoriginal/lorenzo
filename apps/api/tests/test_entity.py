import uuid

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from lorenzo_api.db import engine
from lorenzo_api.models import Entity, Tenant, User


async def test_create_and_read_entity() -> None:
    """Not RLS-focused - uses the privileged connection throughout, same as
    any other plain ORM/business-logic test (see ADR 0021)."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        entity = Entity(tenant_id=tenant.id, name="Test Entity")
        session.add(entity)
        await session.commit()

        assert entity.id is not None
        assert entity.created_at is not None
        assert entity.updated_at is not None

        fetched = await session.get(Entity, entity.id)
        assert fetched is not None
        assert fetched.tenant_id == tenant.id
        assert fetched.name == "Test Entity"

        await session.delete(fetched)
        await session.delete(tenant)
        await session.commit()


async def test_entity_created_by_updated_by_default_null_and_survive_user_deletion() -> None:
    """ADR 0029: created_by/updated_by are nullable (unlike created_at/
    updated_at, which can never be unknown) and ON DELETE SET NULL - losing
    the attributed user's account clears attribution, it doesn't touch the
    entity it was left on.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        untouched = Entity(tenant_id=tenant.id, name="No attribution yet")
        session.add(untouched)
        await session.commit()
        assert untouched.created_by is None
        assert untouched.updated_by is None

        user = User(authgear_subject_id=f"subject-{uuid.uuid4()}")
        session.add(user)
        await session.flush()
        attributed = Entity(
            tenant_id=tenant.id, name="Attributed", created_by=user.id, updated_by=user.id
        )
        session.add(attributed)
        await session.commit()
        entity_id, user_id, tenant_id = attributed.id, user.id, tenant.id

        await session.delete(await session.get_one(User, user_id))
        await session.commit()

    # Fresh session - passive_deletes=True means the session that issued the
    # delete never learns about the DB-side SET NULL (same gotcha as
    # Being/Character.owner_player_id, ADR 0025).
    async with admin_session_factory() as session:
        still_there = await session.get(Entity, entity_id)
        assert still_there is not None
        assert still_there.created_by is None
        assert still_there.updated_by is None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """`engine` (lorenzo_api.db) is the app's own real connection - a
    genuinely restricted role since ADR 0021, so proving the *policy* is
    correct now means proving it through that real connection, not a
    synthetic stand-in. Cross-tenant fixture setup/teardown still needs a
    privileged connection (admin_session_factory), since inserting/deleting
    rows across two different tenants isn't something a correctly-RLS'd
    connection can do in one go anyway.
    """
    async with admin_session_factory() as session:
        # Real tenant rows - entity.tenant_id has a real FK to tenant.id now
        # (ADR 0012/0013), so a made-up tenant_id would just fail to insert.
        tenant_a = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        await session.execute(
            text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'tenant-A-item')"),
            {"t": tenant_a},
        )
        await session.execute(
            text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'tenant-B-item')"),
            {"t": tenant_b},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            names = (await conn.execute(text("SELECT name FROM entity"))).scalars().all()
            assert list(names) == ["tenant-A-item"]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            names = (await conn.execute(text("SELECT name FROM entity"))).scalars().all()
            assert list(names) == ["tenant-B-item"]

        # Never set at all (not just wrong) - proves real enforcement rather
        # than an installed-but-inert policy: current_setting() raises
        # rather than silently returning every tenant's rows, or none.
        # Confirmed empirically (not assumed) that this is what a genuinely
        # restricted role hits here, unlike the superuser connection this
        # test used before ADR 0021. The exact exception varies with
        # connection-pool reuse (a pooled connection that already called
        # set_config earlier in this same test raises a UUID-cast error
        # instead of "unrecognized configuration parameter" on a genuinely
        # fresh one) - DBAPIError is the common ancestor of both, confirmed
        # via SQLAlchemy's own asyncpg error-translation table.
        async with engine.begin() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT name FROM entity"))
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.commit()
