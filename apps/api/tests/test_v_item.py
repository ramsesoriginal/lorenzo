from sqlalchemy import text
from sqlalchemy.orm import selectinload

from lorenzo_api.db import async_session_factory, engine
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    Information,
    Item,
    ItemInstance,
    Payload,
    PayloadDescription,
    PayloadPicture,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
    VItem,
)

_EAGER_LOAD_OPTIONS = (
    selectinload(VItem.entity)
    .selectinload(Entity.information)
    .selectinload(Information.payloads)
    .selectinload(Payload.description),
    selectinload(VItem.entity)
    .selectinload(Entity.information)
    .selectinload(Information.payloads)
    .selectinload(Payload.picture),
    selectinload(VItem.entity)
    .selectinload(Entity.stats)
    .selectinload(EntityStat.stat_definition)
    .selectinload(StatDefinition.stat_group),
)


async def test_v_item_scalar_columns_and_computed_properties() -> None:
    """No resolution/inheritance-walk here (ADR 0019) - v_item surfaces
    direct stats/information/containment only, for both a bare item
    prototype and an item_instance that inherits from it.
    """
    async with async_session_factory() as session:
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
            EntityPrototype(entity_id=my_sword.id, prototype_id=sword.id, tenant_id=tenant.id)
        )
        session.add(
            Containment(
                child_entity_id=my_sword.id, parent_entity_id=chest.id, tenant_id=tenant.id
            )
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
                entity_id=my_sword.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant.id,
                value_int=3,
            )
        )
        session.add(
            EntityStat(
                entity_id=my_sword.id,
                stat_definition_id=magical_def.id,
                tenant_id=tenant.id,
                value_bool=True,
            )
        )

        info = Information(
            tenant_id=tenant.id, entity_id=my_sword.id, title="A fine sword", type="description"
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
        sword_id, my_sword_id, chest_id, tenant_id = sword.id, my_sword.id, chest.id, tenant.id

        my_sword_view = await session.get(VItem, my_sword_id, options=list(_EAGER_LOAD_OPTIONS))
        assert my_sword_view is not None
        assert my_sword_view.title == "A fine sword"
        assert my_sword_view.weight == 3
        assert my_sword_view.height is None
        assert my_sword_view.is_magical is True
        assert my_sword_view.is_cursed is None
        assert my_sword_view.container_entity_id == chest_id
        assert my_sword_view.descriptions == [("A gleaming blade.", "en-US")]
        assert my_sword_view.pictures == [(b"\x89PNG", "image/png")]
        assert my_sword_view.physical_stats == [("weight", 3)]
        assert my_sword_view.tags == [("is_magical", True)]
        assert my_sword_view.economic_stats == []
        assert my_sword_view.destroyable_stats == []
        assert my_sword_view.damaging_stats == []

        # The prototype itself is item-typed, so it appears in v_item too -
        # just with every derived field NULL/empty, since it has no direct
        # stats/information/containment of its own.
        sword_view = await session.get(VItem, sword_id, options=list(_EAGER_LOAD_OPTIONS))
        assert sword_view is not None
        assert sword_view.title is None
        assert sword_view.weight is None
        assert sword_view.descriptions == []
        assert sword_view.physical_stats == []

        # Chest is neither item nor item_instance - not in v_item at all.
        assert await session.get(VItem, chest_id) is None

        await session.delete(tenant)
        await session.commit()


_DROP_TEST_ROLE_IF_EXISTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rls_test_role') THEN
        EXECUTE 'DROP OWNED BY rls_test_role';
        EXECUTE 'DROP ROLE rls_test_role';
    END IF;
END $$;
"""


async def test_v_item_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """v_item is the first view in this schema - security_invoker=true
    (ADR 0019) is what makes RLS apply as the querying role rather than the
    view owner's, but a view's own SELECT grant isn't enough on its own:
    with security_invoker, the querying role also needs its own privileges
    on every underlying table the view reads, exactly like querying them
    directly - confirmed empirically, not assumed from the Postgres docs.
    """
    async with engine.begin() as conn:
        tenant_a = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        entity_a = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_b = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        await conn.execute(
            text("INSERT INTO item_instance (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": entity_a, "t": tenant_a},
        )
        await conn.execute(
            text("INSERT INTO item_instance (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": entity_b, "t": tenant_b},
        )

        await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
        await conn.execute(text("CREATE ROLE rls_test_role NOSUPERUSER NOBYPASSRLS NOLOGIN"))
        await conn.execute(text("GRANT SELECT ON v_item TO rls_test_role"))
        # security_invoker means RLS/permissions apply as this role querying
        # each underlying table directly - granting only v_item itself
        # fails with "permission denied for table information" (confirmed
        # the hard way), since the view's joins still touch every table
        # below even though none of this test's rows populate them.
        for table in (
            "entity",
            "item",
            "item_instance",
            "information",
            "containment",
            "entity_stat",
            "stat_definition",
        ):
            await conn.execute(text(f"GRANT SELECT ON {table} TO rls_test_role"))

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            rows = (
                (await conn.execute(text("SELECT entity_id FROM v_item"))).scalars().all()
            )
            assert list(rows) == [entity_a]
            await conn.execute(text("RESET ROLE"))

        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            rows = (
                (await conn.execute(text("SELECT entity_id FROM v_item"))).scalars().all()
            )
            assert list(rows) == [entity_b]
            await conn.execute(text("RESET ROLE"))
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM item_instance WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
