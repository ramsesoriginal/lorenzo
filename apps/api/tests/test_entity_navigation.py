from lorenzo_api.db import async_session_factory
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntityStatGroup,
    StatGroup,
    Tenant,
)


async def test_stat_groups_convenience_accessor_reads_through_the_join() -> None:
    """entity.stat_groups should return StatGroup objects directly, not the
    EntityStatGroup join rows entity.stat_group_links already exposes.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        physical = StatGroup(tenant_id=tenant.id, name="physical")
        combat = StatGroup(tenant_id=tenant.id, name="combat")
        session.add_all([sword, physical, combat])
        await session.flush()

        session.add_all(
            [
                EntityStatGroup(entity_id=sword.id, stat_group_id=physical.id, tenant_id=tenant.id),
                EntityStatGroup(entity_id=sword.id, stat_group_id=combat.id, tenant_id=tenant.id),
            ]
        )
        await session.commit()
        sword_id = sword.id

        fetched = await session.get(Entity, sword_id)
        assert fetched is not None
        await session.refresh(fetched, attribute_names=["stat_groups"])
        assert sorted(g.name for g in fetched.stat_groups) == ["combat", "physical"]

        await session.delete(tenant)
        await session.commit()


async def test_prototypes_and_instances_are_inverse() -> None:
    """entity.prototypes (what I inherit from) and entity.instances (what
    inherits from me) should read through entity_prototype directly, each
    the mirror image of the other.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        my_shovel = Entity(tenant_id=tenant.id, name="My Shovel")
        shovel = Entity(tenant_id=tenant.id, name="Shovel")
        cursed_item = Entity(tenant_id=tenant.id, name="Cursed Item")
        session.add_all([my_shovel, shovel, cursed_item])
        await session.flush()

        session.add_all(
            [
                EntityPrototype(
                    entity_id=my_shovel.id, prototype_id=shovel.id, tenant_id=tenant.id
                ),
                EntityPrototype(
                    entity_id=my_shovel.id, prototype_id=cursed_item.id, tenant_id=tenant.id
                ),
            ]
        )
        await session.commit()
        my_shovel_id, shovel_id = my_shovel.id, shovel.id

        fetched_shovel_instance = await session.get(Entity, my_shovel_id)
        assert fetched_shovel_instance is not None
        await session.refresh(fetched_shovel_instance, attribute_names=["prototypes"])
        assert sorted(p.name for p in fetched_shovel_instance.prototypes) == [
            "Cursed Item",
            "Shovel",
        ]

        fetched_shovel_prototype = await session.get(Entity, shovel_id)
        assert fetched_shovel_prototype is not None
        await session.refresh(fetched_shovel_prototype, attribute_names=["instances"])
        assert [i.name for i in fetched_shovel_prototype.instances] == ["My Shovel"]

        await session.delete(tenant)
        await session.commit()


async def test_parent_and_children_are_inverse() -> None:
    """entity.parent (my own container, at most one) and entity.children
    (what I contain) should read through containment directly, each the
    mirror image of the other. An uncontained entity has parent=None and
    children=[].
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        room = Entity(tenant_id=tenant.id, name="Room")
        sword = Entity(tenant_id=tenant.id, name="Sword")
        shield = Entity(tenant_id=tenant.id, name="Shield")
        session.add_all([room, sword, shield])
        await session.flush()

        session.add_all(
            [
                Containment(
                    child_entity_id=sword.id, parent_entity_id=room.id, tenant_id=tenant.id
                ),
                Containment(
                    child_entity_id=shield.id, parent_entity_id=room.id, tenant_id=tenant.id
                ),
            ]
        )
        await session.commit()
        room_id, sword_id = room.id, sword.id

        fetched_room = await session.get(Entity, room_id)
        assert fetched_room is not None
        await session.refresh(fetched_room, attribute_names=["children", "parent"])
        assert sorted(c.name for c in fetched_room.children) == ["Shield", "Sword"]
        assert fetched_room.parent is None

        fetched_sword = await session.get(Entity, sword_id)
        assert fetched_sword is not None
        await session.refresh(fetched_sword, attribute_names=["parent", "children"])
        assert fetched_sword.parent is not None
        assert fetched_sword.parent.name == "Room"
        assert fetched_sword.children == []

        await session.delete(tenant)
        await session.commit()
