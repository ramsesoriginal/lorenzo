from _admin_db import admin_session_factory

from lorenzo_api.models import Entity, Item, Tenant


async def test_create_and_read_item() -> None:
    """A bare marker (ADR 0019) - no columns beyond identity."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        session.add(sword)
        await session.flush()
        session.add(Item(entity_id=sword.id, tenant_id=tenant.id))
        await session.commit()
        sword_id = sword.id

        fetched = await session.get(Item, sword_id)
        assert fetched is not None
        assert fetched.tenant_id == tenant.id

        await session.delete(tenant)
        await session.commit()


async def test_deleting_entity_cascades_to_item() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        session.add(sword)
        await session.flush()
        sword_id = sword.id
        session.add(Item(entity_id=sword.id, tenant_id=tenant.id))
        await session.commit()

        await session.delete(sword)
        await session.commit()

        assert await session.get(Item, sword_id) is None

        await session.delete(tenant)
        await session.commit()
