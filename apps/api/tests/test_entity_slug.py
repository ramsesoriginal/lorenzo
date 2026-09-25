"""entity_slug, the table (ADR 0107): uniqueness, cascades, and RLS."""

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from lorenzo_api.db import engine
from lorenzo_api.models import Entity, EntitySlug, Tenant


async def test_a_slug_is_unique_per_tenant_not_across_tenants() -> None:
    async with admin_session_factory() as session:
        tenant_a, tenant_b = Tenant(), Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        sword_a = Entity(tenant_id=tenant_a.id, name="Ashfang")
        sword_b = Entity(tenant_id=tenant_b.id, name="Ashfang")
        other_a = Entity(tenant_id=tenant_a.id, name="Another Ashfang")
        session.add_all([sword_a, sword_b, other_a])
        await session.flush()
        session.add_all(
            [
                EntitySlug(entity_id=sword_a.id, tenant_id=tenant_a.id, slug="ashfang"),
                EntitySlug(entity_id=sword_b.id, tenant_id=tenant_b.id, slug="ashfang"),
            ]
        )
        await session.commit()
        tenant_ids, other_id = (tenant_a.id, tenant_b.id), other_a.id

        session.add(EntitySlug(entity_id=other_id, tenant_id=tenant_ids[0], slug="ashfang"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        for tenant_id in tenant_ids:
            await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_deleting_an_entity_deletes_its_slug() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        entity = Entity(tenant_id=tenant.id, name="Emberdeep")
        session.add(entity)
        await session.flush()
        session.add(EntitySlug(entity_id=entity.id, tenant_id=tenant.id, slug="emberdeep"))
        await session.commit()

        await session.execute(text("DELETE FROM entity WHERE id = :e"), {"e": entity.id})
        await session.commit()
        remaining = await session.scalar(
            select(EntitySlug).where(EntitySlug.tenant_id == tenant.id)
        )
        assert remaining is None

        await session.delete(tenant)
        await session.commit()


async def test_entity_slug_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """The same ENABLE+FORCE+policy shape as every tenant table, proven for
    this one through the app's own restricted connection (ADR 0021)."""
    async with admin_session_factory() as session:
        tenant_a, tenant_b = Tenant(), Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        entity_a = Entity(tenant_id=tenant_a.id, name="a")
        entity_b = Entity(tenant_id=tenant_b.id, name="b")
        session.add_all([entity_a, entity_b])
        await session.flush()
        session.add_all(
            [
                EntitySlug(entity_id=entity_a.id, tenant_id=tenant_a.id, slug="slug-a"),
                EntitySlug(entity_id=entity_b.id, tenant_id=tenant_b.id, slug="slug-b"),
            ]
        )
        await session.commit()
        ids = (tenant_a.id, tenant_b.id)

    try:
        for tenant_id, expected in zip(ids, (["slug-a"], ["slug-b"]), strict=True):
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                rows = (await conn.execute(text("SELECT slug FROM entity_slug"))).scalars().all()
                assert list(rows) == expected
    finally:
        async with admin_session_factory() as session:
            for tenant_id in ids:
                await session.delete(await session.get_one(Tenant, tenant_id))
            await session.commit()
