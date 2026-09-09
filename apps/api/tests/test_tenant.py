from _admin_db import admin_session_factory

from lorenzo_api.models import Tenant


async def test_create_and_read_tenant() -> None:
    """Not RLS-focused - uses the privileged connection (ADR 0021)."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()

        assert tenant.id is not None

        fetched = await session.get(Tenant, tenant.id)
        assert fetched is not None

        await session.delete(fetched)
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
