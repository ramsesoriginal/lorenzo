import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from lorenzo_api.db import async_session_factory, engine
from lorenzo_api.models import (
    Entity,
    EntityStat,
    EntityStatGroup,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
)


async def test_stat_group_definition_and_value_end_to_end() -> None:
    """No resolution/inheritance here (ADR 0014) - just proving an entity can
    acquire a stat group (n:m) and hold a direct value for one of its stats.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        entity = Entity(tenant_id=tenant.id, name="Test Sword")
        stat_group = StatGroup(tenant_id=tenant.id, name="physical", priority=1)
        session.add_all([entity, stat_group])
        await session.flush()

        stat_definition = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=stat_group.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        session.add(stat_definition)
        await session.flush()

        session.add(
            EntityStatGroup(entity_id=entity.id, stat_group_id=stat_group.id, tenant_id=tenant.id)
        )
        session.add(
            EntityStat(
                entity_id=entity.id,
                stat_definition_id=stat_definition.id,
                tenant_id=tenant.id,
                value_int=5,
            )
        )
        await session.commit()

        acquired = await session.get(EntityStatGroup, (entity.id, stat_group.id))
        assert acquired is not None

        value = await session.get(EntityStat, (entity.id, stat_definition.id))
        assert value is not None
        assert value.value_int == 5
        assert value.value_text is None
        assert value.value_float is None
        assert value.value_bool is None

        # Deleting the tenant cascades through entity/stat_group/
        # stat_definition/entity_stat/entity_stat_group automatically -
        # relationship()+ondelete=CASCADE (ADR 0018) gives the unit of work
        # real dependency ordering, no manual per-row deletes needed.
        await session.delete(tenant)
        await session.commit()


async def test_entity_stat_requires_exactly_one_value() -> None:
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        entity = Entity(tenant_id=tenant.id, name="Test Item")
        stat_group = StatGroup(tenant_id=tenant.id, name="physical")
        session.add_all([entity, stat_group])
        await session.flush()
        stat_definition = StatDefinition(
            tenant_id=tenant.id,
            stat_group_id=stat_group.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        session.add(stat_definition)
        await session.flush()

        # No value_* set at all.
        session.add(
            EntityStat(
                entity_id=entity.id, stat_definition_id=stat_definition.id, tenant_id=tenant.id
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()

        # The failed commit rolls back the whole transaction, including the
        # tenant/entity/stat_group/stat_definition flushed earlier in it -
        # nothing was actually persisted, so there's nothing to clean up.
        await session.rollback()


async def test_stat_group_name_is_unique_per_tenant() -> None:
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add_all(
            [
                StatGroup(tenant_id=tenant.id, name="combat"),
                StatGroup(tenant_id=tenant.id, name="combat"),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()

        # Same reasoning as above - nothing was actually persisted.
        await session.rollback()


_DROP_TEST_ROLE_IF_EXISTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rls_test_role') THEN
        EXECUTE 'DROP OWNED BY rls_test_role';
        EXECUTE 'DROP ROLE rls_test_role';
    END IF;
END $$;
"""


async def test_stat_group_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """stat_definition/entity_stat_group/entity_stat use the byte-for-byte
    same ENABLE+FORCE+policy pattern (confirmed via psql inspection when this
    migration was written) - this proves the pattern actually works for the
    new tables at least once more, rather than purely extrapolating from
    test_entity.py's equivalent proof for the entity table.
    """
    async with engine.begin() as conn:
        tenant_a = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
        await conn.execute(text("CREATE ROLE rls_test_role NOSUPERUSER NOBYPASSRLS NOLOGIN"))
        await conn.execute(text("GRANT SELECT, INSERT ON stat_group TO rls_test_role"))
        await conn.execute(
            text("INSERT INTO stat_group (tenant_id, name) VALUES (:t, 'tenant-A-group')"),
            {"t": tenant_a},
        )
        await conn.execute(
            text("INSERT INTO stat_group (tenant_id, name) VALUES (:t, 'tenant-B-group')"),
            {"t": tenant_b},
        )

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            names = (await conn.execute(text("SELECT name FROM stat_group"))).scalars().all()
            assert list(names) == ["tenant-A-group"]
            await conn.execute(text("RESET ROLE"))

        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            names = (await conn.execute(text("SELECT name FROM stat_group"))).scalars().all()
            assert list(names) == ["tenant-B-group"]
            await conn.execute(text("RESET ROLE"))
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM stat_group WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
