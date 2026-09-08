from decimal import Decimal

from sqlalchemy import text

from lorenzo_api.db import async_session_factory
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    EntityStatGroup,
    Information,
    Payload,
    PayloadDescription,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
)

_CASCADE_TABLES = (
    "entity",
    "stat_group",
    "stat_definition",
    "entity_stat",
    "entity_stat_group",
    "entity_prototype",
    "containment",
    "information",
    "payload",
    "payload_description",
)


async def test_deleting_tenant_cascades_through_every_table() -> None:
    """ADR 0018: every foreign key in this schema is ON DELETE CASCADE,
    because every table here represents genuine composition - nothing
    should be able to outlive the tenant it belongs to.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        a = Entity(tenant_id=tenant_id, name="A")
        b = Entity(tenant_id=tenant_id, name="B")
        session.add_all([a, b])
        await session.flush()

        stat_group = StatGroup(tenant_id=tenant_id, name="physical")
        session.add(stat_group)
        await session.flush()
        stat_definition = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        session.add(stat_definition)
        await session.flush()

        info = Information(tenant_id=tenant_id, entity_id=a.id, title="Lore", type="gm-note")
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(payload)
        await session.flush()

        session.add_all(
            [
                EntityStat(
                    entity_id=a.id,
                    stat_definition_id=stat_definition.id,
                    tenant_id=tenant_id,
                    value_int=5,
                ),
                EntityStatGroup(entity_id=a.id, stat_group_id=stat_group.id, tenant_id=tenant_id),
                EntityPrototype(entity_id=a.id, prototype_id=b.id, tenant_id=tenant_id),
                Containment(child_entity_id=a.id, parent_entity_id=b.id, tenant_id=tenant_id),
                PayloadDescription(
                    payload_id=payload.id, tenant_id=tenant_id, locale="en-US", content="x"
                ),
            ]
        )
        await session.commit()

        for table in _CASCADE_TABLES:
            count = (
                await session.execute(
                    text(f"SELECT count(*) FROM {table} WHERE tenant_id = :t"), {"t": tenant_id}
                )
            ).scalar_one()
            assert count > 0, f"expected setup rows in {table} before delete"

        await session.delete(tenant)
        await session.commit()

        for table in _CASCADE_TABLES:
            count = (
                await session.execute(
                    text(f"SELECT count(*) FROM {table} WHERE tenant_id = :t"), {"t": tenant_id}
                )
            ).scalar_one()
            assert count == 0, f"expected {table} rows to be cascade-deleted with the tenant"


async def test_deleting_entity_cascades_its_own_rows_but_not_siblings() -> None:
    """Deleting one Entity must clean up everything that references it
    specifically - without touching a sibling Entity in the same tenant,
    or the tenant itself.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        a = Entity(tenant_id=tenant_id, name="A")
        b = Entity(tenant_id=tenant_id, name="B")
        session.add_all([a, b])
        await session.flush()
        a_id, b_id = a.id, b.id

        stat_group = StatGroup(tenant_id=tenant_id, name="physical")
        session.add(stat_group)
        await session.flush()
        stat_definition = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="weight",
            value_type=StatValueType.FLOAT,
        )
        session.add(stat_definition)
        await session.flush()

        info = Information(tenant_id=tenant_id, entity_id=a_id, title="Lore", type="gm-note")
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(payload)
        await session.flush()

        session.add_all(
            [
                EntityStat(
                    entity_id=a_id,
                    stat_definition_id=stat_definition.id,
                    tenant_id=tenant_id,
                    value_float=1.5,
                ),
                EntityStatGroup(entity_id=a_id, stat_group_id=stat_group.id, tenant_id=tenant_id),
                # A inherits from B, and B contains A - both edges reference
                # A from a different FK column (prototype_id/parent_entity_id
                # on the "surviving" side), so deleting A must remove only
                # the edge row, never cascade into deleting B.
                EntityPrototype(entity_id=a_id, prototype_id=b_id, tenant_id=tenant_id),
                Containment(child_entity_id=a_id, parent_entity_id=b_id, tenant_id=tenant_id),
                PayloadDescription(
                    payload_id=payload.id, tenant_id=tenant_id, locale="en-US", content="x"
                ),
            ]
        )
        await session.commit()

        await session.delete(await session.get_one(Entity, a_id))
        await session.commit()

        assert await session.get(Entity, a_id) is None
        assert await session.get(Entity, b_id) is not None
        assert await session.get(Tenant, tenant_id) is not None
        assert await session.get(StatGroup, stat_group.id) is not None
        assert await session.get(StatDefinition, stat_definition.id) is not None

        for table, column in (
            ("entity_stat", "entity_id"),
            ("entity_stat_group", "entity_id"),
            ("entity_prototype", "entity_id"),
            ("containment", "child_entity_id"),
            ("information", "entity_id"),
        ):
            count = (
                await session.execute(
                    text(f"SELECT count(*) FROM {table} WHERE {column} = :a"), {"a": a_id}
                )
            ).scalar_one()
            assert count == 0, f"expected {table} rows referencing the deleted entity to be gone"

        payload_count = (
            await session.execute(text("SELECT count(*) FROM payload WHERE tenant_id = :t"), {"t": tenant_id})
        ).scalar_one()
        assert payload_count == 0, "expected payload (and its payload_description) to cascade via information"

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()
