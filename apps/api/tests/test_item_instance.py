from _admin_db import admin_session_factory

from lorenzo_api.models import Entity, EntityPrototype, Item, ItemInstance, Tenant


async def test_create_and_read_item_instance() -> None:
    """RFC 0001's own example: "My Shovel" inherits from "Shovel", which is
    item-typed. Ownership is a separate concern (ADR 0025's `ownership`
    table), not a column on item_instance itself.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        shovel = Entity(tenant_id=tenant.id, name="Shovel")
        my_shovel = Entity(tenant_id=tenant.id, name="My Shovel")
        session.add_all([shovel, my_shovel])
        await session.flush()

        session.add(Item(entity_id=shovel.id, tenant_id=tenant.id))
        session.add(
            EntityPrototype(entity_id=my_shovel.id, prototype_id=shovel.id, tenant_id=tenant.id)
        )
        session.add(ItemInstance(entity_id=my_shovel.id, tenant_id=tenant.id))
        await session.commit()
        my_shovel_id = my_shovel.id

        fetched = await session.get(ItemInstance, my_shovel_id)
        assert fetched is not None
        assert fetched.entity_id == my_shovel_id

        await session.delete(tenant)
        await session.commit()


async def test_deleting_entity_cascades_item_instance() -> None:
    """item_instance.entity_id is both PK and FK, ON DELETE CASCADE (ADR
    0018/0019) - the instance can't outlive its own entity.

    Uses a fresh session rather than the one that issued the delete:
    passive_deletes=True means SQLAlchemy never learns about the DB-side
    CASCADE - it just deletes the parent row and trusts Postgres. Checking
    through the same session's identity map would return a stale,
    unrefreshed Python object instead of noticing the row is really gone -
    confirmed the hard way, not assumed.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        session.add(sword)
        await session.flush()
        tenant_id, sword_id = tenant.id, sword.id
        session.add(ItemInstance(entity_id=sword_id, tenant_id=tenant_id))
        await session.commit()

        await session.delete(sword)
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(ItemInstance, sword_id) is None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()
