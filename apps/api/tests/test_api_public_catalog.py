"""Catalog reads for every tenant participant, and the public catalog - see
ADR 0116. A plain participant (a campaign seat, no membership) reads any one
item, but lists only what's in the public catalog; members list everything,
and only they write.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog, Entity, EntityPrototype, Item, ItemInstance, Tenant


async def _item(
    tenant_id: uuid.UUID, name: str, *, public: bool = False, prototype: uuid.UUID | None = None
) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id, in_public_catalog=public))
        if prototype is not None:
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=prototype, tenant_id=tenant_id)
            )
        await session.commit()
        return entity.id


async def _catalog(tenant_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A public Robe, a secret Crown built on it, and a public Backpack.
    Returns (robe, crown, backpack)."""
    robe = await _item(tenant_id, "Robe", public=True)
    crown = await _item(tenant_id, "Crown of Ash", prototype=robe)
    backpack = await _item(tenant_id, "Backpack", public=True)
    return robe, crown, backpack


def _names(response_json: dict[str, list[dict[str, str]]]) -> set[str]:
    return {item["title"] for item in response_json["items"]}


async def test_a_member_lists_the_whole_catalog_with_its_flag(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    await _catalog(tenant_id)
    response = await client.get(f"/tenants/{tenant_id}/items")
    assert response.status_code == 200, response.text
    flags = {item["title"]: item["in_public_catalog"] for item in response.json()["items"]}
    assert flags == {"Robe": True, "Crown of Ash": False, "Backpack": True}
    await delete_tenant(tenant_id)


async def test_a_player_lists_only_the_public_catalog(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    robe, _, _ = await _catalog(tenant_id)
    await make_plain_participant(tenant_id, test_user_id)
    base = f"/tenants/{tenant_id}/items"

    assert _names((await client.get(base)).json()) == {"Robe", "Backpack"}
    assert _names((await client.get(base, params={"q": "o"})).json()) == {"Robe"}
    # Built on the public Robe, but not public itself: not in the list.
    used_by = await client.get(base, params={"prototype_id": str(robe), "recursive": True})
    assert used_by.status_code == 200, used_by.text
    assert _names(used_by.json()) == set()
    await delete_tenant(tenant_id)


async def test_a_player_reads_any_one_item_and_its_ancestry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    robe, crown, _ = await _catalog(tenant_id)
    await make_plain_participant(tenant_id, test_user_id)

    item = await client.get(f"/tenants/{tenant_id}/items/{crown}")
    assert item.status_code == 200, item.text
    assert (item.json()["title"], item.json()["in_public_catalog"]) == ("Crown of Ash", False)
    ancestry = await client.get(f"/tenants/{tenant_id}/items/{crown}/prototypes/ancestry")
    assert ancestry.status_code == 200, ancestry.text
    assert [a["entity_id"] for a in ancestry.json()] == [str(robe)]
    await delete_tenant(tenant_id)


async def test_a_player_still_cant_write_the_catalog(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    robe, _, _ = await _catalog(tenant_id)
    await make_plain_participant(tenant_id, test_user_id)
    base = f"/tenants/{tenant_id}/items"

    assert (await client.post(base, json={"name": "Wand"})).status_code == 404
    assert (await client.patch(f"{base}/{robe}", json={"name": "Rag"})).status_code == 404
    assert (await client.delete(f"{base}/{robe}")).status_code == 404
    await delete_tenant(tenant_id)


async def test_someone_outside_the_tenant_reads_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id
    robe = await _item(tenant_id, "Robe", public=True)

    assert (await client.get(f"/tenants/{tenant_id}/items")).status_code == 404
    assert (await client.get(f"/tenants/{tenant_id}/items/{robe}")).status_code == 404
    await delete_tenant(tenant_id)


async def test_a_gm_puts_an_item_in_and_out_of_the_public_catalog(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    base = f"/tenants/{tenant_id}/items"

    created = await client.post(base, json={"name": "Robe", "in_public_catalog": True})
    assert created.status_code == 201, created.text
    assert created.json()["in_public_catalog"] is True
    robe = created.json()["entity_id"]
    before = created.json()["updated_at"]

    hidden = await client.patch(f"{base}/{robe}", json={"in_public_catalog": False})
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["in_public_catalog"] is False
    # The change moves the ETag, so a stale edit is caught.
    assert hidden.json()["updated_at"] != before
    renamed = await client.patch(f"{base}/{robe}", json={"name": "Old Robe"})
    assert renamed.json()["in_public_catalog"] is False

    async with admin_session_factory() as session:
        logged = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like("item.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert [tuple(row) for row in logged] == [
        ("item.created", "prototypes=0, in_public_catalog=True"),
        ("item.public_catalog_set", "in_public_catalog=False"),
    ]
    await delete_tenant(tenant_id)


async def test_an_instance_carries_no_catalog_flag(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    robe = await _item(tenant_id, "Robe", public=True)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Robe")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(EntityPrototype(entity_id=entity.id, prototype_id=robe, tenant_id=tenant_id))
        await session.commit()
        instance = entity.id
    response = await client.get(f"/tenants/{tenant_id}/item-instances/{instance}")
    assert response.status_code == 200, response.text
    assert "in_public_catalog" not in response.json()
    await delete_tenant(tenant_id)
