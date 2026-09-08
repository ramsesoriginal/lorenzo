from sqlalchemy import text

from lorenzo_api.db import async_session_factory, engine
from lorenzo_api.models import Entity, Tenant


async def test_create_and_read_entity() -> None:
    async with async_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()

        entity = Entity(tenant_id=tenant.id, name="Test Entity")
        session.add(entity)
        await session.commit()

        assert entity.id is not None
        assert entity.created_at is not None
        assert entity.updated_at is not None

        fetched = await session.get(Entity, entity.id)
        assert fetched is not None
        assert fetched.tenant_id == tenant.id
        assert fetched.name == "Test Entity"

        await session.delete(fetched)
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


async def test_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """The app's own connection is a superuser and bypasses RLS entirely
    regardless of policy (see ADR 0002/0012) - proving the *policy* itself
    is correct needs a genuinely restricted role, not the app's normal
    connection, so this test creates one rather than reusing app state.
    """
    async with engine.begin() as conn:
        # Real tenant rows - entity.tenant_id has a real FK to tenant.id now
        # (ADR 0012/0013), so a made-up tenant_id would just fail to insert.
        tenant_a = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await conn.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        # Plain "DROP ROLE IF EXISTS" only suppresses "role does not exist" -
        # it still errors if the role exists but still has grants (e.g. left
        # over from an interrupted previous run), so this handles that too.
        await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
        await conn.execute(text("CREATE ROLE rls_test_role NOSUPERUSER NOBYPASSRLS NOLOGIN"))
        await conn.execute(text("GRANT SELECT, INSERT ON entity TO rls_test_role"))
        await conn.execute(
            text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'tenant-A-item')"),
            {"t": tenant_a},
        )
        await conn.execute(
            text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'tenant-B-item')"),
            {"t": tenant_b},
        )

    try:
        # SET ROLE is session-level, not transaction-scoped like set_config's
        # is_local=true - it survives this block's commit, so an explicit
        # RESET ROLE is required before the connection goes back to the pool,
        # or a later query on the same pooled connection either runs with
        # unintended privileges or, as found here, trips this same RLS policy
        # against an empty (reset) app.tenant_id and fails casting it to uuid.
        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            names = (await conn.execute(text("SELECT name FROM entity"))).scalars().all()
            assert list(names) == ["tenant-A-item"]
            await conn.execute(text("RESET ROLE"))

        async with engine.begin() as conn:
            await conn.execute(text("SET ROLE rls_test_role"))
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            names = (await conn.execute(text("SELECT name FROM entity"))).scalars().all()
            assert list(names) == ["tenant-B-item"]
            await conn.execute(text("RESET ROLE"))
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await conn.execute(text(_DROP_TEST_ROLE_IF_EXISTS))
