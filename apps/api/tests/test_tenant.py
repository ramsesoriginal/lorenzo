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
