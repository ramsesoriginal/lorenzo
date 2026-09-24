"""content_reference, the table (ADR 0110): its kinds, cascades, and RLS."""

import uuid

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.db import engine
from lorenzo_api.models import ContentReference, Entity, Information, Payload, Tenant


async def _payload(session: AsyncSession, tenant_id: uuid.UUID) -> Payload:
    entity = Entity(tenant_id=tenant_id, name="Emberdeep")
    session.add(entity)
    await session.flush()
    info = Information(tenant_id=tenant_id, entity_id=entity.id, title="d", type="description")
    session.add(info)
    await session.flush()
    payload = Payload(tenant_id=tenant_id, information_id=info.id)
    session.add(payload)
    await session.flush()
    return payload


def _ref(payload: Payload, position: int, kind: str, target: str) -> ContentReference:
    return ContentReference(
        payload_id=payload.id,
        position=position,
        tenant_id=payload.tenant_id,
        kind=kind,
        target=target,
    )


async def test_only_the_four_reference_kinds_are_stored() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        payload = await _payload(session, tenant.id)
        for position, kind in enumerate(["entity", "image", "date", "calendar"]):
            session.add(_ref(payload, position, kind, "x"))
        # Built, and the id kept, while everything is still loaded.
        other, tenant_id = _ref(payload, 4, "footnote", "x"), tenant.id
        await session.commit()

        session.add(other)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_deleting_the_information_deletes_its_references() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        payload = await _payload(session, tenant.id)
        session.add(_ref(payload, 0, "entity", "ashfang"))
        await session.commit()

        await session.execute(
            text("DELETE FROM information WHERE id = :i"), {"i": payload.information_id}
        )
        await session.commit()
        remaining = await session.scalar(
            select(ContentReference).where(ContentReference.tenant_id == tenant.id)
        )
        assert remaining is None

        await session.delete(tenant)
        await session.commit()


async def test_content_reference_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    """The same ENABLE+FORCE+policy shape as every tenant table, proven for
    this one through the app's own restricted connection (ADR 0021)."""
    async with admin_session_factory() as session:
        tenant_a, tenant_b = Tenant(), Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add(_ref(await _payload(session, tenant_a.id), 0, "entity", "slug-a"))
        session.add(_ref(await _payload(session, tenant_b.id), 0, "entity", "slug-b"))
        await session.commit()
        ids = (tenant_a.id, tenant_b.id)

    try:
        for tenant_id, expected in zip(ids, (["slug-a"], ["slug-b"]), strict=True):
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                query = text("SELECT target FROM content_reference")
                assert list((await conn.execute(query)).scalars().all()) == expected
    finally:
        async with admin_session_factory() as session:
            for tenant_id in ids:
                await session.delete(await session.get_one(Tenant, tenant_id))
            await session.commit()
