import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from lorenzo_api.db import async_session_factory, engine
from lorenzo_api.models import Containment, Entity, Tenant


async def test_move_entity_between_containers() -> None:
    """The PK is child_entity_id alone (ADR 0016), so moving an entity to a
    new container is a single UPDATE, not a delete-then-insert.
    """
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        backpack = Entity(tenant_id=tenant_id, name="Backpack")
        chest = Entity(tenant_id=tenant_id, name="Chest")
        sword = Entity(tenant_id=tenant_id, name="Sword")
        session.add_all([backpack, chest, sword])
        await session.flush()
        backpack_id, chest_id, sword_id = backpack.id, chest.id, sword.id

        session.add(
            Containment(child_entity_id=sword_id, parent_entity_id=backpack_id, tenant_id=tenant_id)
        )
        await session.commit()

        row = await session.get(Containment, sword_id)
        assert row is not None
        assert row.parent_entity_id == backpack_id

        row.parent_entity_id = chest_id
        await session.commit()

        moved = await session.get(Containment, sword_id)
        assert moved is not None
        assert moved.parent_entity_id == chest_id

        # Deleting the tenant cascades through entity/containment
        # automatically - relationship()+ondelete=CASCADE (ADR 0018).
        await session.delete(tenant)
        await session.commit()


async def test_self_loop_and_cycles_are_allowed() -> None:
    """RFC 0001/ADR 0016: deliberately cycle-tolerant, unlike entity_prototype
    - a direct self-loop and a 2-cycle must both be accepted, not rejected.
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

        session.add(Containment(child_entity_id=a_id, parent_entity_id=a_id, tenant_id=tenant_id))
        await session.commit()

        await session.execute(
            text("DELETE FROM containment WHERE child_entity_id = :c"), {"c": a_id}
        )
        await session.commit()

        session.add_all(
            [
                Containment(child_entity_id=b_id, parent_entity_id=a_id, tenant_id=tenant_id),
                Containment(child_entity_id=a_id, parent_entity_id=b_id, tenant_id=tenant_id),
            ]
        )
        await session.commit()

        rows = (
            (
                await session.execute(
                    text("SELECT child_entity_id FROM containment WHERE tenant_id = :t"),
                    {"t": tenant_id},
                )
            )
            .scalars()
            .all()
        )
        assert set(rows) == {a_id, b_id}

        await session.delete(tenant)
        await session.commit()


async def test_child_can_have_at_most_one_parent() -> None:
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        a = Entity(tenant_id=tenant_id, name="A")
        b = Entity(tenant_id=tenant_id, name="B")
        c = Entity(tenant_id=tenant_id, name="C")
        session.add_all([a, b, c])
        await session.flush()
        a_id, b_id, c_id = a.id, b.id, c.id

        session.add(Containment(child_entity_id=a_id, parent_entity_id=b_id, tenant_id=tenant_id))
        await session.commit()

        # a already has a row (parent b) - a second row for the same child
        # (parent c) must collide on the PK, not create a second parent.
        session.add(Containment(child_entity_id=a_id, parent_entity_id=c_id, tenant_id=tenant_id))
        with pytest.raises(IntegrityError, match="containment_pkey"):
            await session.commit()
        await session.rollback()

        # Re-fetched rather than reusing `tenant` directly: rollback expires
        # every ORM object regardless of expire_on_commit, so the object
        # itself needs a fresh load before its cascade-delete can run.
        await session.delete(await session.get_one(Tenant, tenant_id))
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


async def test_containment_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """Same ENABLE+FORCE+policy pattern as every tenant-scoped table so far -
    proves it works for containment too rather than purely extrapolating
    from the other tables' equivalent proofs.
    """
    async with engine.begin() as conn:
        tenant_a = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        entity_a1 = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a1') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_a2 = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a2') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_b1 = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b1') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        entity_b2 = (
            await conn.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b2') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()

        await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
        await conn.execute(text("CREATE ROLE rls_test_role NOSUPERUSER NOBYPASSRLS NOLOGIN"))
        await conn.execute(text("GRANT SELECT, INSERT ON containment TO rls_test_role"))
        await conn.execute(
            text(
                "INSERT INTO containment (child_entity_id, parent_entity_id, tenant_id) "
                "VALUES (:c, :p, :t)"
            ),
            {"c": entity_a1, "p": entity_a2, "t": tenant_a},
        )
        await conn.execute(
            text(
                "INSERT INTO containment (child_entity_id, parent_entity_id, tenant_id) "
                "VALUES (:c, :p, :t)"
            ),
            {"c": entity_b1, "p": entity_b2, "t": tenant_b},
        )

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            rows = (
                (await conn.execute(text("SELECT child_entity_id FROM containment")))
                .scalars()
                .all()
            )
            assert list(rows) == [entity_a1]
            await conn.execute(text("RESET ROLE"))

        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            rows = (
                (await conn.execute(text("SELECT child_entity_id FROM containment")))
                .scalars()
                .all()
            )
            assert list(rows) == [entity_b1]
            await conn.execute(text("RESET ROLE"))
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM containment WHERE tenant_id IN (:a, :b)"),
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
