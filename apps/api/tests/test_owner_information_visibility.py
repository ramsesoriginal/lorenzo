"""Whether a tenant-wide administrator can read GM-only information - the
open question ADR 0085's export audit raised.

`information_visibility` bypasses its filter for `is_tenant_orga` only, and
its docstring says tenant OWNER is "deliberately not folded in". These tests
pin down the actual behavior through the real HTTP read (`GET /entities/{id}`)
so the export runbook (ADR 0085) states what really happens, not what the
docstrings imply.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import update

from lorenzo_api.models import Entity, Item, Membership, MembershipRole


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


async def _set_role(tenant_id: uuid.UUID, user_id: uuid.UUID, role: MembershipRole) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            update(Membership)
            .where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
            .values(role=role)
        )
        await session.commit()


async def test_gm_only_information_visibility_for_owner_versus_orga(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)  # test user is OWNER
    entity_id = await _make_entity(tenant_id)

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
    secret_id = created.json()["id"]

    owner_sees = secret_id in await _visible_information_ids(client, tenant_id, entity_id)

    await _set_role(tenant_id, test_user_id, MembershipRole.ORGA)
    orga_sees = secret_id in await _visible_information_ids(client, tenant_id, entity_id)

    # ORGA bypasses the filter; the finding is what OWNER gets.
    assert orga_sees is True
    print(f"OWNER sees GM-only information: {owner_sees}")
    assert owner_sees is False, (
        "OWNER can read GM-only information - the ADR 0085 export gap does not exist; "
        "update the ADR addendum and this test"
    )

    await delete_tenant(tenant_id)
