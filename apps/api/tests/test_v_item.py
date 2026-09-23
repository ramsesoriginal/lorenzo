import uuid

from _admin_db import admin_session_factory
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from lorenzo_api.db import engine
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    EntityStatGroup,
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
    VEffectiveStat,
    VItem,
    VItemInstance,
)

# A trivial all-seeing visibility context (is_orga=True short-circuits
# can_see unconditionally) - this file proves the eager-load recipe and
# property/method walk work correctly, not information_visibility.py's own
# rules (see test_information_visibility.py and test_api_entities.py for
# that), so there's no real user/tenant/membership to resolve one from.
_SEES_EVERYTHING = InformationVisibility(
    is_orga=True,
    is_admin=True,
    player_ids=frozenset(),
    knower_entity_ids=frozenset(),
    gm_reachable_entity_ids=frozenset(),
)


def _eager_load_options(
    view_entity_attr: InstrumentedAttribute[Entity],
) -> tuple[ORMOption, ORMOption, ORMOption, ORMOption]:
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
        .selectinload(Entity.information)
        .selectinload(Information.knowledge_links),
        selectinload(view_entity_attr)
        .selectinload(Entity.effective_stats)
        .selectinload(VEffectiveStat.stat_definition)
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
        assert sword_view.descriptions(_SEES_EVERYTHING) == [("A gleaming blade.", "en-US")]
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


# --- Effective stat resolution over the prototype graph (ADR 0037/RFC 0008,
# generalized to v_effective_stat and any entity by ADR 0039) ---


async def test_v_item_instance_resolves_stat_inherited_through_two_prototype_hops() -> None:
    """The exact GitHub milestone #1 scenario shape: "Ashfang" (an
    instance) -> "Flaming Sword" (a prototype) -> "Sword" (a base
    prototype). Only Sword sets weight directly - Flaming Sword and Ashfang
    each inherit it, at one and two hops respectively.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        flaming_sword = Entity(tenant_id=tenant.id, name="Flaming Sword")
        ashfang = Entity(tenant_id=tenant.id, name="Ashfang")
        session.add_all([sword, flaming_sword, ashfang])
        await session.flush()

        session.add(Item(entity_id=sword.id, tenant_id=tenant.id))
        session.add(Item(entity_id=flaming_sword.id, tenant_id=tenant.id))
        session.add(ItemInstance(entity_id=ashfang.id, tenant_id=tenant.id))
        session.add(
            EntityPrototype(entity_id=flaming_sword.id, prototype_id=sword.id, tenant_id=tenant.id)
        )
        session.add(
            EntityPrototype(
                entity_id=ashfang.id, prototype_id=flaming_sword.id, tenant_id=tenant.id
            )
        )

        physical = StatGroup(tenant_id=tenant.id, name="physical")
        session.add(physical)
        await session.flush()
        weight_def = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=physical.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        session.add(weight_def)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=sword.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant.id,
                value_int=5,
            )
        )
        await session.commit()
        sword_id, flaming_sword_id, ashfang_id = sword.id, flaming_sword.id, ashfang.id

        sword_view = await session.get(VItem, sword_id)
        flaming_sword_view = await session.get(VItem, flaming_sword_id)
        ashfang_view = await session.get(
            VItemInstance, ashfang_id, options=list(_eager_load_options(VItemInstance.entity))
        )
        assert sword_view is not None
        assert sword_view.weight == 5
        assert flaming_sword_view is not None
        assert flaming_sword_view.weight == 5
        assert ashfang_view is not None
        assert ashfang_view.weight == 5
        # ADR 0039: physical_stats (EntityViewMixin, reading
        # Entity.effective_stats) must agree with the plain `weight` column
        # above - the previously-known gap (ADR 0037) where an inherited
        # value showed up in `weight` but not in `physical_stats` at all.
        assert ashfang_view.physical_stats == [("weight", 5)]

        await session.delete(tenant)
        await session.commit()


async def test_v_item_instance_direct_override_wins_outright_over_inherited_value() -> None:
    """An instance-level override always beats anything inherited, even
    though the inherited candidate is only two hops away and the override
    is zero - RFC 0001's "more specific wins," proven the other direction
    from the previous test.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        flaming_sword = Entity(tenant_id=tenant.id, name="Flaming Sword")
        ashfang = Entity(tenant_id=tenant.id, name="Ashfang")
        session.add_all([sword, flaming_sword, ashfang])
        await session.flush()

        session.add(Item(entity_id=sword.id, tenant_id=tenant.id))
        session.add(Item(entity_id=flaming_sword.id, tenant_id=tenant.id))
        session.add(ItemInstance(entity_id=ashfang.id, tenant_id=tenant.id))
        session.add(
            EntityPrototype(entity_id=flaming_sword.id, prototype_id=sword.id, tenant_id=tenant.id)
        )
        session.add(
            EntityPrototype(
                entity_id=ashfang.id, prototype_id=flaming_sword.id, tenant_id=tenant.id
            )
        )

        physical = StatGroup(tenant_id=tenant.id, name="physical")
        session.add(physical)
        await session.flush()
        weight_def = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=physical.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        session.add(weight_def)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=sword.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant.id,
                value_int=5,
            )
        )
        session.add(
            EntityStat(
                entity_id=ashfang.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant.id,
                value_int=99,
            )
        )
        await session.commit()
        ashfang_id = ashfang.id

        ashfang_view = await session.get(VItemInstance, ashfang_id)
        assert ashfang_view is not None
        assert ashfang_view.weight == 99

        await session.delete(tenant)
        await session.commit()


async def test_v_effective_stat_resolves_for_any_entity_not_only_items() -> None:
    """ADR 0039's core generalization: the resolution walk's base case is
    `FROM entity e` (every entity in the tenant), not `item`/`item_instance`
    rows only - proven here with entities that are neither, so no
    v_item/v_item_instance row for them exists at all. Mirrors what makes
    VCharacter's own EntityViewMixin properties able to see inherited stats
    too, not just VItem/VItemInstance's.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        base = Entity(tenant_id=tenant.id, name="Base Being")
        derived = Entity(tenant_id=tenant.id, name="Derived Being")
        session.add_all([base, derived])
        await session.flush()

        session.add(
            EntityPrototype(entity_id=derived.id, prototype_id=base.id, tenant_id=tenant.id)
        )

        physical = StatGroup(tenant_id=tenant.id, name="physical")
        session.add(physical)
        await session.flush()
        hp_def = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=physical.id,
            name="hp",
            value_type=StatValueType.INT,
        )
        session.add(hp_def)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=base.id, stat_definition_id=hp_def.id, tenant_id=tenant.id, value_int=10
            )
        )
        await session.commit()
        derived_id = derived.id

        assert await session.get(VItem, derived_id) is None
        assert await session.get(VItemInstance, derived_id) is None

        rows = (
            (
                await session.execute(
                    select(VEffectiveStat).where(VEffectiveStat.entity_id == derived_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].value_int == 10

        await session.delete(tenant)
        await session.commit()


async def _tie_break_fixture(
    session: AsyncSession, *, tenant_id: uuid.UUID, low_priority: int, high_priority: int
) -> uuid.UUID:
    """Chimera inherits directly from both ProtoLow and ProtoHigh (equally
    close, one hop each), each setting the same "weight" stat to a
    different value. ProtoLow/ProtoHigh acquire (entity_stat_group) their
    own, differently-prioritized stat group - see ADR 0037's own precise
    reading of "the value acquired through the higher-priority stat group
    wins": the priority that decides the tie is each *ancestor's* own
    highest acquired stat_group.priority, not weight's own (fixed, shared)
    stat_group. Returns Chimera's entity_id.
    """
    chimera = Entity(tenant_id=tenant_id, name="Chimera")
    proto_low = Entity(tenant_id=tenant_id, name="ProtoLow")
    proto_high = Entity(tenant_id=tenant_id, name="ProtoHigh")
    session.add_all([chimera, proto_low, proto_high])
    await session.flush()
    session.add(Item(entity_id=chimera.id, tenant_id=tenant_id))
    session.add(Item(entity_id=proto_low.id, tenant_id=tenant_id))
    session.add(Item(entity_id=proto_high.id, tenant_id=tenant_id))
    session.add(
        EntityPrototype(entity_id=chimera.id, prototype_id=proto_low.id, tenant_id=tenant_id)
    )
    session.add(
        EntityPrototype(entity_id=chimera.id, prototype_id=proto_high.id, tenant_id=tenant_id)
    )

    physical = StatGroup(tenant_id=tenant_id, name="physical")
    low_group = StatGroup(tenant_id=tenant_id, name="low", priority=low_priority)
    high_group = StatGroup(tenant_id=tenant_id, name="high", priority=high_priority)
    session.add_all([physical, low_group, high_group])
    await session.flush()
    weight_def = StatDefinition(
        tenant_id=tenant_id,
        stat_group_id=physical.id,
        name="weight",
        value_type=StatValueType.INT,
    )
    session.add(weight_def)
    await session.flush()

    session.add(
        EntityStatGroup(entity_id=proto_low.id, stat_group_id=low_group.id, tenant_id=tenant_id)
    )
    session.add(
        EntityStatGroup(entity_id=proto_high.id, stat_group_id=high_group.id, tenant_id=tenant_id)
    )
    session.add(
        EntityStat(
            entity_id=proto_low.id,
            stat_definition_id=weight_def.id,
            tenant_id=tenant_id,
            value_int=10,
        )
    )
    session.add(
        EntityStat(
            entity_id=proto_high.id,
            stat_definition_id=weight_def.id,
            tenant_id=tenant_id,
            value_int=20,
        )
    )
    await session.commit()
    return chimera.id


async def test_v_item_priority_tie_break_between_equally_close_prototypes() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        chimera_id = await _tie_break_fixture(
            session, tenant_id=tenant.id, low_priority=1, high_priority=5
        )

        chimera_view = await session.get(VItem, chimera_id)
        assert chimera_view is not None
        assert chimera_view.weight == 20  # ProtoHigh's value wins.

        await session.delete(tenant)
        await session.commit()


async def test_v_item_priority_tie_break_is_not_just_insertion_or_id_order() -> None:
    """Same fixture, but ProtoHigh is now the *lower*-priority group -
    proves the previous test's result really tracks priority, not merely
    "whichever prototype was inserted/linked second."
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        chimera_id = await _tie_break_fixture(
            session, tenant_id=tenant.id, low_priority=9, high_priority=2
        )

        chimera_view = await session.get(VItem, chimera_id)
        assert chimera_view is not None
        assert chimera_view.weight == 10  # ProtoLow's value wins this time.

        await session.delete(tenant)
        await session.commit()


async def test_v_item_instance_exposes_containment_quantity() -> None:
    """ADR 0041: v_item_instance.quantity reads straight off the same
    LEFT JOIN containment already producing container_entity_id - NULL
    when uncontained, otherwise the row's own quantity (a stack of 20
    arrows here, not the default 1).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        quiver = Entity(tenant_id=tenant.id, name="Quiver")
        arrows = Entity(tenant_id=tenant.id, name="Arrows")
        loose_dagger = Entity(tenant_id=tenant.id, name="Loose Dagger")
        session.add_all([quiver, arrows, loose_dagger])
        await session.flush()

        session.add(ItemInstance(entity_id=arrows.id, tenant_id=tenant.id))
        session.add(ItemInstance(entity_id=loose_dagger.id, tenant_id=tenant.id))
        session.add(
            Containment(
                child_entity_id=arrows.id,
                parent_entity_id=quiver.id,
                tenant_id=tenant.id,
                quantity=20,
            )
        )
        await session.commit()
        arrows_id, loose_dagger_id = arrows.id, loose_dagger.id

        arrows_view = await session.get(VItemInstance, arrows_id)
        assert arrows_view is not None
        assert arrows_view.quantity == 20

        # Uncontained - no stack concept applies, not "1 by default".
        loose_view = await session.get(VItemInstance, loose_dagger_id)
        assert loose_view is not None
        assert loose_view.quantity is None
        assert loose_view.container_entity_id is None

        await session.delete(tenant)
        await session.commit()


async def test_v_item_instance_container_move_does_not_change_resolved_stats() -> None:
    """Moving an instance between containers (ADR 0032's PUT
    .../container) is a Containment change only - entity_prototype is
    untouched, so the resolved stat set must be identical before and after.
    Proven directly at the view level here (test_api_entity_stats.py's own
    milestone test proves the same thing through the real HTTP endpoint).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        sword = Entity(tenant_id=tenant.id, name="Sword")
        ashfang = Entity(tenant_id=tenant.id, name="Ashfang")
        chest_a = Entity(tenant_id=tenant.id, name="Chest A")
        chest_b = Entity(tenant_id=tenant.id, name="Chest B")
        session.add_all([sword, ashfang, chest_a, chest_b])
        await session.flush()

        session.add(Item(entity_id=sword.id, tenant_id=tenant.id))
        session.add(ItemInstance(entity_id=ashfang.id, tenant_id=tenant.id))
        session.add(
            EntityPrototype(entity_id=ashfang.id, prototype_id=sword.id, tenant_id=tenant.id)
        )
        containment = Containment(
            child_entity_id=ashfang.id, parent_entity_id=chest_a.id, tenant_id=tenant.id
        )
        session.add(containment)

        physical = StatGroup(tenant_id=tenant.id, name="physical")
        session.add(physical)
        await session.flush()
        weight_def = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=physical.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        session.add(weight_def)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=sword.id,
                stat_definition_id=weight_def.id,
                tenant_id=tenant.id,
                value_int=7,
            )
        )
        await session.commit()
        ashfang_id, chest_a_id, chest_b_id = ashfang.id, chest_a.id, chest_b.id

        before = await session.get(VItemInstance, ashfang_id)
        assert before is not None
        assert before.weight == 7
        assert before.container_entity_id == chest_a_id

        containment.parent_entity_id = chest_b_id
        await session.commit()

        # populate_existing=True - VItemInstance is keyed by entity_id in
        # the ORM's identity map like any other mapped class, even though
        # it's backed by a view with no real PK constraint; a plain second
        # session.get() for the same id would otherwise just return the
        # `before` object already cached there instead of re-querying.
        after = await session.get(VItemInstance, ashfang_id, populate_existing=True)
        assert after is not None
        assert after.weight == 7
        assert after.container_entity_id == chest_b_id

        await session.delete(tenant)
        await session.commit()
