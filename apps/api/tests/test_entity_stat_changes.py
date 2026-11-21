"""The History of a being's sheet: its latest stat changes and who made them (ADR 0525), through
the real HTTP API."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import func, select

from lorenzo_api.models import EntityStatChange, StatDefinition, StatGroup, StatValueType


async def _stats(tenant_id: uuid.UUID, **types: StatValueType) -> dict[str, uuid.UUID]:
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant_id, name="Stats")
        session.add(group)
        await session.flush()
        ids: dict[str, uuid.UUID] = {}
        for name, value_type in types.items():
            definition = StatDefinition(
                tenant_id=tenant_id, stat_group_id=group.id, name=name, value_type=value_type
            )
            session.add(definition)
            await session.flush()
            ids[name] = definition.id
        await session.commit()
        return ids


async def _being(client: AsyncClient, tenant_id: uuid.UUID) -> uuid.UUID:
    response = await client.post(
        f"/tenants/{tenant_id}/entities", json={"name": "Ana's knight", "kinds": ["item"]}
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


def _path(tenant_id: uuid.UUID, entity_id: uuid.UUID, *rest: object) -> str:
    return "/".join([f"/tenants/{tenant_id}/entities/{entity_id}", *(str(r) for r in rest)])


async def test_each_step_of_a_number_is_listed_newest_first_with_who_made_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, hp=StatValueType.INT)
    entity_id = await _being(client, tenant_id)
    stat = _path(tenant_id, entity_id, "stats", stats["hp"])

    for value in (16, 14, 15):
        assert (await client.put(stat, json={"value": value})).status_code == 200
    listed = await client.get(_path(tenant_id, entity_id, "stat-changes"))

    assert listed.status_code == 200, listed.text
    steps = listed.json()
    assert [(s["old"], s["new"]) for s in steps] == [(14, 15), (16, 14), (None, 16)]
    assert {s["stat_name"] for s in steps} == {"hp"}
    assert {s["actor_id"] for s in steps} == {str(test_user_id)}
    assert steps[0]["created_at"] >= steps[1]["created_at"] >= steps[2]["created_at"]
    await delete_tenant(tenant_id)


async def test_the_same_value_again_is_not_a_step(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, hp=StatValueType.INT)
    entity_id = await _being(client, tenant_id)
    stat = _path(tenant_id, entity_id, "stats", stats["hp"])

    await client.put(stat, json={"value": 9})
    await client.put(stat, json={"value": 9})

    steps = (await client.get(_path(tenant_id, entity_id, "stat-changes"))).json()
    assert [(s["old"], s["new"]) for s in steps] == [(None, 9)]
    await delete_tenant(tenant_id)


async def test_clearing_a_value_and_switching_a_tag_are_steps_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, hp=StatValueType.INT, wounded=StatValueType.BOOL)
    entity_id = await _being(client, tenant_id)

    await client.put(_path(tenant_id, entity_id, "stats", stats["hp"]), json={"value": 12})
    await client.delete(_path(tenant_id, entity_id, "stats", stats["hp"]))
    await client.put(_path(tenant_id, entity_id, "tags", stats["wounded"]))
    await client.delete(_path(tenant_id, entity_id, "tags", stats["wounded"]))

    steps = (await client.get(_path(tenant_id, entity_id, "stat-changes"))).json()
    assert [(s["stat_name"], s["old"], s["new"]) for s in steps] == [
        ("wounded", True, None),
        ("wounded", None, True),
        ("hp", 12, None),
        ("hp", None, 12),
    ]
    await delete_tenant(tenant_id)


async def test_only_the_latest_steps_are_kept(
    client: AsyncClient, test_user_id: uuid.UUID, monkeypatch
) -> None:
    monkeypatch.setattr(EntityStatChange, "KEEP", 3)
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, hp=StatValueType.INT)
    entity_id = await _being(client, tenant_id)
    stat = _path(tenant_id, entity_id, "stats", stats["hp"])

    for value in range(1, 8):
        await client.put(stat, json={"value": value})

    async with admin_session_factory() as session:
        kept = await session.scalar(
            select(func.count())
            .select_from(EntityStatChange)
            .where(EntityStatChange.entity_id == entity_id)
        )
    assert kept == 3
    steps = (await client.get(_path(tenant_id, entity_id, "stat-changes"))).json()
    assert [s["new"] for s in steps] == [7, 6, 5]
    await delete_tenant(tenant_id)


async def test_the_limit_is_asked_for_and_bounded(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, hp=StatValueType.INT)
    entity_id = await _being(client, tenant_id)
    for value in (1, 2, 3):
        await client.put(_path(tenant_id, entity_id, "stats", stats["hp"]), json={"value": value})

    two = await client.get(_path(tenant_id, entity_id, "stat-changes"), params={"limit": 2})
    too_many = await client.get(_path(tenant_id, entity_id, "stat-changes"), params={"limit": 101})

    assert [s["new"] for s in two.json()] == [3, 2]
    assert too_many.status_code == 422
    await delete_tenant(tenant_id)


async def test_an_entry_that_is_not_there_has_no_history(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(_path(tenant_id, uuid.uuid4(), "stat-changes"))

    assert response.status_code == 404
    await delete_tenant(tenant_id)
