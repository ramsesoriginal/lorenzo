import pytest
from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from lorenzo_api.db import engine
from lorenzo_api.models import Entity, EntityPrototype, Tenant


async def test_multiple_inheritance_and_chain() -> None:
    """No resolution/inheritance-walk here (ADR 0015) - just proving the
    graph itself can hold a chain (a->b->c) and multiple inheritance
    (d from both b and c, a diamond via shared ancestor b/c->... no cycle).
    Not RLS-focused - uses the privileged connection throughout (ADR 0021).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        a = Entity(tenant_id=tenant_id, name="A")
        b = Entity(tenant_id=tenant_id, name="B")
        c = Entity(tenant_id=tenant_id, name="C")
        d = Entity(tenant_id=tenant_id, name="D")
        session.add_all([a, b, c, d])
        await session.flush()
        a_id, b_id, c_id, d_id = a.id, b.id, c.id, d.id

        session.add_all(
            [
                EntityPrototype(entity_id=a_id, prototype_id=b_id, tenant_id=tenant_id),
                EntityPrototype(entity_id=b_id, prototype_id=c_id, tenant_id=tenant_id),
                EntityPrototype(entity_id=d_id, prototype_id=b_id, tenant_id=tenant_id),
                EntityPrototype(entity_id=d_id, prototype_id=c_id, tenant_id=tenant_id),
            ]
        )
        await session.commit()

        rows = (
            await session.execute(
                text("SELECT entity_id, prototype_id FROM entity_prototype WHERE tenant_id = :t"),
                {"t": tenant_id},
            )
        ).all()
        assert len(rows) == 4

        # Deleting the tenant cascades through entity/entity_prototype
        # automatically - relationship()+ondelete=CASCADE (ADR 0018) gives
        # the unit of work real dependency ordering.
        await session.delete(tenant)
        await session.commit()


async def test_direct_self_loop_rejected() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        entity = Entity(tenant_id=tenant.id, name="Self")
        session.add(entity)
        await session.flush()

        session.add(
            EntityPrototype(entity_id=entity.id, prototype_id=entity.id, tenant_id=tenant.id)
        )
        with pytest.raises(IntegrityError, match="entity_prototype_no_self_loop"):
            await session.commit()

        # The failed commit rolls back the whole transaction - nothing was
        # actually persisted, so there's nothing to clean up. Nothing below
        # touches an ORM attribute post-rollback (see the other two tests
        # for why that matters), so no capture-before-rollback is needed.
        await session.rollback()


async def test_direct_transitive_cycle_rejected() -> None:
    """A inherits from B; then B attempting to inherit from A directly
    closes a 2-cycle and must be rejected by the BEFORE INSERT trigger
    (the CHECK constraint alone only catches entity_id = prototype_id).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        a = Entity(tenant_id=tenant.id, name="A")
        b = Entity(tenant_id=tenant.id, name="B")
        session.add_all([a, b])
        await session.flush()
        # Captured as plain values before any rollback: session.rollback()
        # unconditionally expires every ORM object regardless of
        # expire_on_commit (that only governs commit), so touching .id on
        # a, b, or tenant after the rollback below would trigger an
        # implicit reload - which this async setup can't do implicitly.
        tenant_id, a_id, b_id = tenant.id, a.id, b.id

        session.add(EntityPrototype(entity_id=a_id, prototype_id=b_id, tenant_id=tenant_id))
        await session.commit()

        session.add(EntityPrototype(entity_id=b_id, prototype_id=a_id, tenant_id=tenant_id))
        with pytest.raises(DBAPIError, match="cycle detected"):
            await session.commit()
        await session.rollback()

        # Re-fetched rather than reusing `tenant` directly: rollback expires
        # every ORM object regardless of expire_on_commit, so the object
        # itself needs a fresh load before its cascade-delete can run.
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_transitive_three_way_cycle_rejected() -> None:
    """A->B, B->C exist; C attempting to inherit from A would close a
    3-cycle (A->B->C->A) - the trigger's recursive CTE must walk through
    B to find A, not just check C's immediate prototype.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        a = Entity(tenant_id=tenant.id, name="A")
        b = Entity(tenant_id=tenant.id, name="B")
        c = Entity(tenant_id=tenant.id, name="C")
        session.add_all([a, b, c])
        await session.flush()
        # See test_direct_transitive_cycle_rejected for why these are
        # captured as plain values before the rollback below.
        tenant_id, a_id, b_id, c_id = tenant.id, a.id, b.id, c.id

        session.add_all(
            [
                EntityPrototype(entity_id=a_id, prototype_id=b_id, tenant_id=tenant_id),
                EntityPrototype(entity_id=b_id, prototype_id=c_id, tenant_id=tenant_id),
            ]
        )
        await session.commit()

        session.add(EntityPrototype(entity_id=c_id, prototype_id=a_id, tenant_id=tenant_id))
        with pytest.raises(DBAPIError, match="cycle detected"):
            await session.commit()
        await session.rollback()

        # See test_direct_transitive_cycle_rejected for why this is
        # re-fetched rather than reusing `tenant` directly.
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_entity_prototype_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """Same ENABLE+FORCE+policy pattern as every tenant-scoped table so far -
    proves it works for entity_prototype too rather than purely
    extrapolating from test_entity.py/test_stats.py's equivalent proofs.
    `engine` is the app's own real, restricted connection since ADR 0021.
    """
    async with admin_session_factory() as session:
        tenant_a = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        entity_a1 = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a1') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_a2 = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a2') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_b1 = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b1') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        entity_b2 = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b2') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()

        await session.execute(
            text(
                "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id) "
                "VALUES (:e, :p, :t)"
            ),
            {"e": entity_a1, "p": entity_a2, "t": tenant_a},
        )
        await session.execute(
            text(
                "INSERT INTO entity_prototype (entity_id, prototype_id, tenant_id) "
                "VALUES (:e, :p, :t)"
            ),
            {"e": entity_b1, "p": entity_b2, "t": tenant_b},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            rows = (
                (await conn.execute(text("SELECT entity_id FROM entity_prototype"))).scalars().all()
            )
            assert list(rows) == [entity_a1]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            rows = (
                (await conn.execute(text("SELECT entity_id FROM entity_prototype"))).scalars().all()
            )
            assert list(rows) == [entity_b1]
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM entity_prototype WHERE tenant_id IN (:a, :b)"),
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
