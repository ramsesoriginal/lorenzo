"""Item-instance mutations are recorded in the activity log - see ADR 0084.
Only real state changes are logged, bulk operations write one entry per
call with counts, and renames are deliberately not logged.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_player, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, update

from lorenzo_api.models import AuditLog, CharacterPlayer, Containment, Entity, Item, User


async def _entries(tenant_id: uuid.UUID) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like("item_instance.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _actions(tenant_id: uuid.UUID) -> list[str]:
    return [action for action, _ in await _entries(tenant_id)]


async def _make_prototype(tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Sword")
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _make_container(tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Chest")
        session.add(entity)
        await session.commit()
        return entity.id


async def _make_character_id(tenant_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """A character rostered into a campaign - assigning an item to a
    character needs `can_manage_campaign` over one of its campaigns, which
    the tenant OWNER has for any campaign. Returns (character entity id,
    the throwaway player's user id, for the caller to delete).
    """
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        return character.entity_id, player.user_id


async def _delete_user(user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def _create_instance(
    client: AsyncClient, tenant_id: uuid.UUID, prototype_id: uuid.UUID, **extra: object
) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/item-instances", json={"prototype_id": str(prototype_id), **extra}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["entity_id"])


async def test_instance_lifecycle_logs_each_real_change_once(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_prototype(tenant_id)
    character_id, player_user_id = await _make_character_id(tenant_id)
    container_id = await _make_container(tenant_id)
    base = f"/tenants/{tenant_id}/item-instances"

    instance_id = await _create_instance(client, tenant_id, prototype_id)

    owner = {"owner_character_id": str(character_id)}
    assert (await client.put(f"{base}/{instance_id}/owner", json=owner)).status_code == 200
    assert (await client.put(f"{base}/{instance_id}/owner", json=owner)).status_code == 200
    assert (await client.delete(f"{base}/{instance_id}/owner")).status_code == 200
    assert (await client.delete(f"{base}/{instance_id}/owner")).status_code == 200

    box = {"container_entity_id": str(container_id)}
    assert (await client.put(f"{base}/{instance_id}/container", json=box)).status_code == 200
    assert (await client.put(f"{base}/{instance_id}/container", json=box)).status_code == 200
    assert (await client.delete(f"{base}/{instance_id}/container")).status_code == 200
    assert (await client.delete(f"{base}/{instance_id}/container")).status_code == 200

    assert (await client.delete(f"{base}/{instance_id}")).status_code == 204

    # The repeated (idempotent) PUTs and the DELETEs of already-absent
    # relations changed nothing, so they wrote nothing.
    assert await _actions(tenant_id) == [
        "item_instance.created",
        "item_instance.owner_set",
        "item_instance.owner_cleared",
        "item_instance.container_set",
        "item_instance.container_cleared",
        "item_instance.deleted",
    ]

    await delete_tenant(tenant_id)
    await _delete_user(player_user_id)


async def test_renaming_an_instance_is_deliberately_not_logged(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_prototype(tenant_id)
    instance_id = await _create_instance(client, tenant_id, prototype_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/item-instances/{instance_id}", json={"name": "Renamed"}
    )
    assert response.status_code == 200

    assert await _actions(tenant_id) == ["item_instance.created"]

    await delete_tenant(tenant_id)


async def test_split_and_merge_are_logged(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_prototype(tenant_id)
    container_id = await _make_container(tenant_id)
    base = f"/tenants/{tenant_id}/item-instances"

    source_id = await _create_instance(
        client, tenant_id, prototype_id, container_entity_id=str(container_id)
    )
    async with admin_session_factory() as session:
        await session.execute(
            update(Containment)
            .where(Containment.child_entity_id == uuid.UUID(source_id))
            .values(quantity=5)
        )
        await session.commit()

    split = await client.post(f"{base}/{source_id}/split", json={"quantity": 2})
    assert split.status_code == 201, split.text
    new_id = split.json()["entity_id"]

    merge = await client.post(f"{base}/{new_id}/merge", json={"into_entity_id": source_id})
    assert merge.status_code == 200, merge.text

    entries = await _entries(tenant_id)
    assert entries[1] == ("item_instance.split", f"new={new_id}, quantity=2")
    assert entries[2] == ("item_instance.merged", f"source={new_id}, quantity=2")

    await delete_tenant(tenant_id)


async def test_bulk_operations_log_one_entry_per_call_with_counts(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    prototype_id = await _make_prototype(tenant_id)
    character_id, player_user_id = await _make_character_id(tenant_id)
    container_id = await _make_container(tenant_id)
    base = f"/tenants/{tenant_id}/item-instances"

    first = await _create_instance(client, tenant_id, prototype_id)
    second = await _create_instance(client, tenant_id, prototype_id)
    missing = str(uuid.uuid4())

    assign = await client.post(
        f"{base}/bulk-assign",
        json=[
            {"entity_id": first, "owner_character_id": str(character_id)},
            {"entity_id": second, "owner_character_id": str(character_id)},
            {"entity_id": missing, "owner_character_id": str(character_id)},
        ],
    )
    assert assign.status_code == 200

    move = await client.post(
        f"{base}/bulk-move",
        json={
            "to_container_entity_id": str(container_id),
            "items": [{"entity_id": first}, {"entity_id": missing}],
        },
    )
    assert move.status_code == 200

    entries = await _entries(tenant_id)
    assert entries[-2:] == [
        ("item_instance.bulk_assigned", "2 ok, 1 failed"),
        ("item_instance.bulk_moved", "1 ok, 1 failed"),
    ]

    # A bulk call in which nothing succeeds changed nothing - no entry.
    before = len(entries)
    nothing = await client.post(
        f"{base}/bulk-assign",
        json=[{"entity_id": missing, "owner_character_id": str(character_id)}],
    )
    assert nothing.status_code == 200
    assert len(await _entries(tenant_id)) == before

    await delete_tenant(tenant_id)
    await _delete_user(player_user_id)
