"""A tenant OWNER reads GM-only information like an ORGA - ADR 0091.

ADR 0085's export audit found the opposite: `information_visibility`'s
bypass was ORGA-only, so an OWNER's export silently omitted GM-only text
(proven here with a real request, before the change). ADR 0091 widened it.
These tests pin the behavior through the real HTTP read
(`GET /entities/{id}`), and pin what did *not* change: an opted-out
administrator still sees only what a non-admin sees, and ADR 0040's
item-instance inventory tier stays ORGA-only (tests/test_api_item_instances.py).
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import update

from lorenzo_api.models import (
    Entity,
    Item,
    Membership,
    MembershipRole,
    TenantAdminCampaignOptOut,
)


async def _make_entity(tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _visible_information_ids(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> set[str]:
    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert response.status_code == 200, response.text
    return {row["id"] for row in response.json()["information"]}


async def _make_gm_only_information(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> str:
    created = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={
            "title": "GM only",
            "type": "gm_secret",
            "is_public": False,
            "content": "secret",
            "locale": "en",
        },
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def test_owner_and_orga_both_read_gm_only_information(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)  # test user is OWNER
    entity_id = await _make_entity(tenant_id)
    secret_id = await _make_gm_only_information(client, tenant_id, entity_id)

    assert secret_id in await _visible_information_ids(client, tenant_id, entity_id)

    async with admin_session_factory() as session:
        await session.execute(
            update(Membership)
            .where(Membership.tenant_id == tenant_id, Membership.user_id == test_user_id)
            .values(role=MembershipRole.ORGA)
        )
        await session.commit()
    assert secret_id in await _visible_information_ids(client, tenant_id, entity_id)

    await delete_tenant(tenant_id)


async def test_an_opted_out_owner_no_longer_sees_gm_only_information(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_entity(tenant_id)
    secret_id = await _make_gm_only_information(client, tenant_id, entity_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
            )
        )
        await session.commit()

    assert secret_id not in await _visible_information_ids(client, tenant_id, entity_id)

    await delete_tenant(tenant_id)
