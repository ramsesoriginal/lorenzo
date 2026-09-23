"""Information, knowledge grants, and stat definitions are recorded in the
activity log - see ADR 0084. The important property is what the log does
*not* contain: an information row's title, type and content can be a
GM-only secret, so its entry carries the entity and visibility tier only.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog, Entity, Item


async def _entries(tenant_id: uuid.UUID, prefix: str) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like(f"{prefix}.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _make_item_entity(tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def test_information_create_logs_entity_and_tier_but_never_its_content(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item_entity(tenant_id, "Ashfang")

    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={
            "title": "The duke poisoned it",
            "type": "gm_secret_plot",
            "is_public": False,
            "content": "Betrayal is coming in act three.",
            "locale": "en",
        },
    )
    assert response.status_code == 201, response.text

    ((action, detail),) = await _entries(tenant_id, "information")
    assert action == "information.created"
    assert detail == f"entity={entity_id}, visibility=restricted"
    for secret in ("duke", "gm_secret_plot", "Betrayal", "act three"):
        assert secret not in (detail or "")

    await delete_tenant(tenant_id)


async def test_knower_grants_and_revocations_are_logged_once_each(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item_entity(tenant_id, "Ashfang")
    knower_id = await _make_item_entity(tenant_id, "Alice")
    created = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "t", "type": "secret", "is_public": False, "content": "c", "locale": "en"},
    )
    information_id = created.json()["id"]
    url = f"/tenants/{tenant_id}/information/{information_id}/knowers/{knower_id}"

    assert (await client.put(url)).status_code == 200
    assert (await client.put(url)).status_code == 200  # idempotent: no second entry
    assert (await client.delete(url)).status_code == 200
    assert (await client.delete(url)).status_code == 200  # idempotent: no second entry

    assert await _entries(tenant_id, "information") == [
        ("information.created", f"entity={entity_id}, visibility=restricted"),
        ("information.knower_added", f"knower={knower_id}"),
        ("information.knower_removed", f"knower={knower_id}"),
    ]

    await delete_tenant(tenant_id)


async def test_stat_group_and_definition_creation_are_logged(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    group = await client.post(
        f"/tenants/{tenant_id}/stat-groups", json={"name": "Physical", "priority": 3}
    )
    assert group.status_code == 201, group.text
    group_id = group.json()["id"]
    definition = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": group_id, "name": "weight", "value_type": "int"},
    )
    assert definition.status_code == 201, definition.text

    assert [
        e for prefix in ("stat_group", "stat_definition") for e in await _entries(tenant_id, prefix)
    ] == [
        ("stat_group.created", "priority=3"),
        ("stat_definition.created", f"stat_group={group_id}, value_type=int"),
    ]

    await delete_tenant(tenant_id)
