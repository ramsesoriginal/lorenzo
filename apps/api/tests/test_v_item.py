from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from lorenzo_api.db import engine
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityStat,
    Information,
    Item,
    ItemInstance,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadPicture,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
    VItem,
    VItemInstance,
)


def _eager_load_options(
    view_entity_attr: InstrumentedAttribute[Entity],
) -> tuple[ORMOption, ORMOption, ORMOption]:
    return (
        selectinload(view_entity_attr)
        .selectinload(Entity.information)
        .selectinload(Information.payloads)
        .selectinload(Payload.description),
        selectinload(view_entity_attr)
        .selectinload(Entity.information)
        .selectinload(Information.payloads)
        .selectinload(Payload.picture),
        selectinload(view_entity_attr)
        .selectinload(Entity.stats)
        .selectinload(EntityStat.stat_definition)
        .selectinload(StatDefinition.stat_group),
    )


async def test_v_item_covers_only_the_item_table() -> None:
    """ADR 0019 (revised): v_item and v_item_instance are separate views -
    a single merged view gave no way to tell "find all base items" from
    "find all item instances" without joining item/item_instance back in
    anyway, defeating the point.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        my_sword = Entity(tenant_id=tenant.id, name="My Sword")
        chest = Entity(tenant_id=tenant.id, name="Chest")
        session.add_all([sword, my_sword, chest])
        await session.flush()

        session.add(Item(entity_id=sword.id, tenant_id=tenant.id))
        session.add(ItemInstance(entity_id=my_sword.id, tenant_id=tenant.id))
        session.add(
            Containment(child_entity_id=sword.id, parent_entity_id=chest.id, tenant_id=tenant.id)
        )

        physical = StatGroup(tenant_id=tenant.id, name="physical")
        tags = StatGroup(tenant_id=tenant.id, name="tags")
        session.add_all([physical, tags])
        await session.flush()

        weight_def = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=physical.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        magical_def = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=tags.id,
            name="is_magical",
            value_type=StatValueType.BOOL,
        )
        session.add_all([weight_def, magical_def])
        await session.flush()

        session.add(
            EntityStat(
                entity_id=sword.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant.id,
                value_int=3,
            )
        )
        session.add(
            EntityStat(
                entity_id=sword.id,
                stat_definition_id=magical_def.id,
                tenant_id=tenant.id,
                value_bool=True,
            )
        )

        info = Information(
            tenant_id=tenant.id, entity_id=sword.id, title="A fine sword", type="description"
        )
        session.add(info)
        await session.flush()
        description_payload = Payload(tenant_id=tenant.id, information_id=info.id)
        picture_payload = Payload(tenant_id=tenant.id, information_id=info.id)
        session.add_all([description_payload, picture_payload])
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=description_payload.id,
                tenant_id=tenant.id,
                locale="en-US",
                content="A gleaming blade.",
            )
        )
        session.add(
            PayloadPicture(
                payload_id=picture_payload.id,
                tenant_id=tenant.id,
                data=b"\x89PNG",
                file_type="image/png",
            )
        )
        await session.commit()
        sword_id, my_sword_id, chest_id = sword.id, my_sword.id, chest.id

        sword_view = await session.get(
            VItem, sword_id, options=list(_eager_load_options(VItem.entity))
        )
        assert sword_view is not None
        assert sword_view.title == "A fine sword"
        assert sword_view.weight == 3
        assert sword_view.is_magical is True
        assert sword_view.container_entity_id == chest_id
        assert sword_view.descriptions == [("A gleaming blade.", "en-US")]
        assert sword_view.pictures == [(b"\x89PNG", "image/png")]
        assert sword_view.physical_stats == [("weight", 3)]
        assert sword_view.tags == [("is_magical", True)]
        assert sword_view.economic_stats == []
        assert sword_view.destroyable_stats == []
        assert sword_view.damaging_stats == []

        # The item_instance entity must not leak into v_item.
        assert await session.get(VItem, my_sword_id) is None

        await session.delete(tenant)
        await session.commit()


async def test_v_item_instance_covers_only_the_item_instance_table_and_has_owner() -> None:
    """owner_entity_id is now derived via a LEFT JOIN against `ownership`
    (ADR 0025), not a column on item_instance itself - this is the
    reconciliation's own proof that the view's external shape didn't
    change.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        my_sword = Entity(tenant_id=tenant.id, name="My Sword")
        owner = Entity(tenant_id=tenant.id, name="Owner")
        session.add_all([sword, my_sword, owner])
        await session.flush()

        session.add(Item(entity_id=sword.id, tenant_id=tenant.id))
        session.add(ItemInstance(entity_id=my_sword.id, tenant_id=tenant.id))
        session.add(
            Ownership(owned_entity_id=my_sword.id, owner_character_id=owner.id, tenant_id=tenant.id)
        )

        stat_group = StatGroup(tenant_id=tenant.id, name="physical")
        session.add(stat_group)
        await session.flush()
        weight_def = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=stat_group.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        session.add(weight_def)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=my_sword.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant.id,
                value_int=4,
            )
        )
        await session.commit()
        sword_id, my_sword_id, owner_id = sword.id, my_sword.id, owner.id

        my_sword_view = await session.get(
            VItemInstance, my_sword_id, options=list(_eager_load_options(VItemInstance.entity))
        )
        assert my_sword_view is not None
        assert my_sword_view.owner_entity_id == owner_id
        assert my_sword_view.weight == 4
        assert my_sword_view.physical_stats == [("weight", 4)]

        # The base item entity must not leak into v_item_instance.
        assert await session.get(VItemInstance, sword_id) is None

        await session.delete(tenant)
        await session.commit()


async def _rls_probe(view_name: str, source_table: str) -> None:
    """Shared by both views below - security_invoker=true (ADR 0019) means
    RLS applies as the querying role rather than the view owner's, but a
    view's own SELECT grant isn't enough on its own: the querying role
    also needs its own privileges on every underlying table the view
    reads, exactly like querying them directly - confirmed empirically
    ("permission denied for table information" until every table was
    granted), not assumed from the Postgres docs. `engine` is the app's own
    real, restricted connection since ADR 0021 - already granted on every
    table/view via ALTER DEFAULT PRIVILEGES, no per-test role needed.
    """
    async with admin_session_factory() as session:
        tenant_a = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        entity_a = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_b = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        await session.execute(
            text(f"INSERT INTO {source_table} (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": entity_a, "t": tenant_a},
        )
        await session.execute(
            text(f"INSERT INTO {source_table} (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": entity_b, "t": tenant_b},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            rows = (await conn.execute(text(f"SELECT entity_id FROM {view_name}"))).scalars().all()
            assert list(rows) == [entity_a]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            rows = (await conn.execute(text(f"SELECT entity_id FROM {view_name}"))).scalars().all()
            assert list(rows) == [entity_b]
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text(f"DELETE FROM {source_table} WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.commit()


async def test_v_item_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    await _rls_probe("v_item", "item")


async def test_v_item_instance_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    await _rls_probe("v_item_instance", "item_instance")
