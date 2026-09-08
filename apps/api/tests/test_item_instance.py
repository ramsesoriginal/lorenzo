from lorenzo_api.db import async_session_factory
from lorenzo_api.models import Entity, EntityPrototype, Item, ItemInstance, Tenant


async def test_create_and_read_item_instance_with_owner() -> None:
    """RFC 0001's own example: "My Shovel" inherits from "Shovel", which is
    item-typed. owner_entity_id references an entity generically (ADR
    0019) since character doesn't exist yet.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        shovel = Entity(tenant_id=tenant.id, name="Shovel")
        my_shovel = Entity(tenant_id=tenant.id, name="My Shovel")
        owner = Entity(tenant_id=tenant.id, name="Some Character")
        session.add_all([shovel, my_shovel, owner])
        await session.flush()

        session.add(Item(entity_id=shovel.id, tenant_id=tenant.id))
        session.add(
            EntityPrototype(entity_id=my_shovel.id, prototype_id=shovel.id, tenant_id=tenant.id)
        )
        session.add(
            ItemInstance(entity_id=my_shovel.id, owner_entity_id=owner.id, tenant_id=tenant.id)
        )
        await session.commit()
        my_shovel_id = my_shovel.id

        fetched = await session.get(ItemInstance, my_shovel_id)
        assert fetched is not None
        assert fetched.owner_entity_id == owner.id

        await session.delete(tenant)
        await session.commit()


async def test_owner_entity_id_is_optional() -> None:
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        loot = Entity(tenant_id=tenant.id, name="Unclaimed Loot")
        session.add(loot)
        await session.flush()
        session.add(ItemInstance(entity_id=loot.id, tenant_id=tenant.id))
        await session.commit()
        loot_id = loot.id

        fetched = await session.get(ItemInstance, loot_id)
        assert fetched is not None
        assert fetched.owner_entity_id is None

        await session.delete(tenant)
        await session.commit()


async def test_deleting_owner_sets_null_but_deleting_own_entity_cascades() -> None:
    """The one deliberate exception to ADR 0018's "cascade everything" rule
    (ADR 0019): losing the owner just leaves the instance ownerless, but
    the instance can't outlive its own entity.

    Both checks use a fresh session rather than the one that issued the
    delete: passive_deletes=True means SQLAlchemy never learns about either
    DB-side effect (the SET NULL or the CASCADE) - it just deletes the
    parent row and trusts Postgres. Checking through the same session's
    identity map would either return a stale, unrefreshed Python object
    (silently passing for the wrong reason) or fail to notice a row is
    really gone - confirmed the hard way, not assumed.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        owner = Entity(tenant_id=tenant.id, name="Owner")
        session.add_all([sword, owner])
        await session.flush()
        tenant_id, sword_id, owner_id = tenant.id, sword.id, owner.id
        session.add(ItemInstance(entity_id=sword_id, owner_entity_id=owner_id, tenant_id=tenant_id))
        await session.commit()

        await session.delete(owner)
        await session.commit()

    async with async_session_factory() as session:
        still_there = await session.get(ItemInstance, sword_id)
        assert still_there is not None
        assert still_there.owner_entity_id is None

        await session.delete(await session.get_one(Entity, sword_id))
        await session.commit()

    async with async_session_factory() as session:
        assert await session.get(ItemInstance, sword_id) is None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()
