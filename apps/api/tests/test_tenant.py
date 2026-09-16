import uuid

from _admin_db import admin_session_factory

from lorenzo_api.models import Tenant, User


async def test_create_and_read_tenant() -> None:
    """Not RLS-focused - uses the privileged connection (ADR 0021)."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()

        assert tenant.id is not None
        assert tenant.created_at is not None
        assert tenant.updated_at is not None

        fetched = await session.get(Tenant, tenant.id)
        assert fetched is not None

        await session.delete(fetched)
        await session.commit()


async def test_tenant_created_by_updated_by_default_null_and_survive_user_deletion() -> None:
    """ADR 0029/ADR 0033: created_by/updated_by are nullable (unlike
    created_at/updated_at, which can never be unknown) and ON DELETE SET
    NULL - losing the attributed user's account clears attribution, it
    doesn't touch the tenant it was left on.
    """
    async with admin_session_factory() as session:
        untouched = Tenant()
        session.add(untouched)
        await session.commit()
        assert untouched.created_by is None
        assert untouched.updated_by is None
        untouched_id = untouched.id

        user = User(authgear_subject_id=f"subject-{uuid.uuid4()}")
        session.add(user)
        await session.flush()
        attributed = Tenant(name="Attributed", created_by=user.id, updated_by=user.id)
        session.add(attributed)
        await session.commit()
        tenant_id, user_id = attributed.id, user.id

        await session.delete(await session.get_one(User, user_id))
        await session.commit()

    # Fresh session - passive_deletes=True means the session that issued the
    # delete never learns about the DB-side SET NULL (same gotcha as
    # entity.created_by/updated_by, ADR 0029).
    async with admin_session_factory() as session:
        still_there = await session.get(Tenant, tenant_id)
        assert still_there is not None
        assert still_there.created_by is None
        assert still_there.updated_by is None

        await session.delete(still_there)
        await session.delete(await session.get_one(Tenant, untouched_id))
        await session.commit()


async def test_tenant_name_defaults_when_not_given() -> None:
    """Server-side default, not a Python one (ADR 0022) - the many bare
    Tenant() fixture calls across the suite don't need a name, but a real
    caller can still set one explicitly.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        assert tenant.name == "Unnamed Tenant"

        named = Tenant(name="Rivergate")
        session.add(named)
        await session.commit()
        assert named.name == "Rivergate"

        await session.delete(tenant)
        await session.delete(named)
        await session.commit()
