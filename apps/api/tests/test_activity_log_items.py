"""Item catalog mutations are recorded in the activity log - see ADR 0084.
Prototype edits change what an item inherits, so they count; renames are
deliberately not logged; bulk operations write one entry per call.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog


async def _entries(tenant_id: uuid.UUID) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like("item.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _create_item(client: AsyncClient, tenant_id: uuid.UUID, name: str) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/items", json={"name": name, "prototype_ids": []}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["entity_id"])


async def test_catalog_mutations_are_logged(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    base = f"/tenants/{tenant_id}/items"

    proto_a = await _create_item(client, tenant_id, "Weapon")
    proto_b = await _create_item(client, tenant_id, "Sword")
    child = await _create_item(client, tenant_id, "Ashfang")
    missing = str(uuid.uuid4())

    replace = await client.put(f"{base}/{child}/prototypes", json={"prototype_ids": [proto_a]})
    assert replace.status_code == 200, replace.text

    add = await client.post(
        f"{base}/bulk-add-prototype", json={"prototype_id": proto_b, "item_ids": [child, missing]}
    )
    assert add.status_code == 200, add.text

    remove = await client.post(
        f"{base}/bulk-remove-prototype", json={"prototype_id": proto_b, "item_ids": [child]}
    )
    assert remove.status_code == 200, remove.text

    reparent = await client.post(
        f"{base}/bulk-reparent-prototype",
        json={"from_prototype_id": proto_a, "to_prototype_id": proto_b},
    )
    assert reparent.status_code == 200, reparent.text

    rename = await client.patch(f"{base}/{child}", json={"name": "Renamed"})
    assert rename.status_code == 200

    assert (await client.delete(f"{base}/{child}")).status_code == 204

    assert await _entries(tenant_id) == [
        ("item.created", "prototypes=0"),
        ("item.created", "prototypes=0"),
        ("item.created", "prototypes=0"),
        ("item.prototypes_replaced", "prototypes=1"),
        ("item.bulk_prototype_added", "1 ok, 1 failed"),
        ("item.bulk_prototype_removed", "1 ok, 0 failed"),
        ("item.bulk_reparented", "1 ok, 0 failed"),
        ("item.deleted", None),
    ]

    await delete_tenant(tenant_id)


async def test_a_bulk_call_where_nothing_succeeds_is_not_logged(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    proto = await _create_item(client, tenant_id, "Weapon")

    response = await client.post(
        f"/tenants/{tenant_id}/items/bulk-add-prototype",
        json={"prototype_id": proto, "item_ids": [str(uuid.uuid4())]},
    )
    assert response.status_code == 200

    assert [action for action, _ in await _entries(tenant_id)] == ["item.created"]

    await delete_tenant(tenant_id)
