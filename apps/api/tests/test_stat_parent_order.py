"""ADR 0266: at equal distance and equal priority the entry's own parent order breaks the tie
(earlier parent wins), and the entity id is the last resort. Nothing else about resolution
(ADR 0037) changes."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Entity,
    EntityPrototype,
    EntityStat,
    EntityStatGroup,
    StatDefinition,
    StatGroup,
    StatValueType,
    VEffectiveStat,
)


async def _entry(session: AsyncSession, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    entity = Entity(tenant_id=tenant_id, name=name)
    session.add(entity)
    await session.flush()
    return entity.id


async def _weight(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    group = StatGroup(tenant_id=tenant_id, name="physical")
    session.add(group)
    await session.flush()
    definition = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="weight", value_type=StatValueType.INT
    )
    session.add(definition)
    await session.flush()
    return definition.id


def _set(tenant_id: uuid.UUID, entity_id: uuid.UUID, definition_id: uuid.UUID, value: int):  # type: ignore[no-untyped-def]
    return EntityStat(
        entity_id=entity_id, stat_definition_id=definition_id, tenant_id=tenant_id, value_int=value
    )


async def _resolved(entity_id: uuid.UUID) -> int | None:
    async with admin_session_factory() as session:
        return await session.scalar(
            select(VEffectiveStat.value_int).where(VEffectiveStat.entity_id == entity_id)
        )


async def _put(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, parents: list[uuid.UUID]
) -> None:
    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/parents",
        json={"parent_ids": [str(p) for p in parents]},
    )
    assert response.status_code == 200, response.text


async def _two_parents(
    tenant_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """child, parent a (weight 10), parent b (weight 20), and the weight definition."""
    async with admin_session_factory() as session:
        definition = await _weight(session, tenant_id)
        child = await _entry(session, tenant_id, "Child")
        a = await _entry(session, tenant_id, "A")
        b = await _entry(session, tenant_id, "B")
        session.add_all([_set(tenant_id, a, definition, 10), _set(tenant_id, b, definition, 20)])
        await session.commit()
        return child, a, b, definition


async def test_the_earlier_parent_wins_and_reordering_flips_the_winner(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    child, a, b, _ = await _two_parents(tenant_id)

    await _put(client, tenant_id, child, [a, b])
    assert await _resolved(child) == 10
    await _put(client, tenant_id, child, [b, a])
    assert await _resolved(child) == 20
    await _put(client, tenant_id, child, [a, b])
    assert await _resolved(child) == 10
    await delete_tenant(tenant_id)


async def test_the_order_is_returned_as_it_was_put(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    child, a, b, _ = await _two_parents(tenant_id)
    for order in ([b, a], [a, b], [b, a]):
        await _put(client, tenant_id, child, order)
        listed = await client.get(f"/tenants/{tenant_id}/entities", params={"q": "Child"})
        assert listed.json()["items"][0]["parent_ids"] == [str(p) for p in order]
    await delete_tenant(tenant_id)


async def test_creating_an_entry_with_parents_keeps_their_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    _, a, b, definition = await _two_parents(tenant_id)
    created = await client.post(
        f"/tenants/{tenant_id}/entities", json={"name": "Born", "parents": [str(b), str(a)]}
    )
    assert created.status_code == 201, created.text
    assert await _resolved(uuid.UUID(created.json()["id"])) == 20
    await delete_tenant(tenant_id)


async def test_a_parent_added_later_goes_last(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    child, a, b, _ = await _two_parents(tenant_id)
    await _put(client, tenant_id, child, [b])
    async with admin_session_factory() as session:
        # A writer that does not name a position (the trigger puts the row last).
        session.add(EntityPrototype(entity_id=child, prototype_id=a, tenant_id=tenant_id))
        await session.commit()
        positions = dict(
            tuple(row)
            for row in (
                await session.execute(
                    select(EntityPrototype.prototype_id, EntityPrototype.position).where(
                        EntityPrototype.entity_id == child
                    )
                )
            ).all()
        )
    assert positions[b] < positions[a]
    assert await _resolved(child) == 20
    await delete_tenant(tenant_id)


async def test_the_entity_id_is_the_last_resort(test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    child, a, b, _ = await _two_parents(tenant_id)
    async with admin_session_factory() as session:
        session.add_all(
            [
                EntityPrototype(entity_id=child, prototype_id=a, tenant_id=tenant_id, position=0),
                EntityPrototype(entity_id=child, prototype_id=b, tenant_id=tenant_id, position=0),
            ]
        )
        await session.commit()
    expected = 10 if a < b else 20
    assert await _resolved(child) == expected
    # Read again: the same answer every time.
    assert await _resolved(child) == expected
    await delete_tenant(tenant_id)


async def test_priority_still_beats_parent_order_and_distance_beats_both(
    test_user_id: uuid.UUID,
) -> None:
    tenant_id = await make_tenant(test_user_id)
    child, a, b, definition = await _two_parents(tenant_id)
    async with admin_session_factory() as session:
        high = StatGroup(tenant_id=tenant_id, name="high", priority=5)
        session.add(high)
        await session.flush()
        # b is the later parent, but acquired the higher-priority group.
        session.add(EntityStatGroup(entity_id=b, stat_group_id=high.id, tenant_id=tenant_id))
        session.add_all(
            [
                EntityPrototype(entity_id=child, prototype_id=a, tenant_id=tenant_id, position=0),
                EntityPrototype(entity_id=child, prototype_id=b, tenant_id=tenant_id, position=1),
            ]
        )
        await session.commit()
        assert await _resolved(child) == 20

        # A direct value of the entry's own beats any parent.
        session.add(_set(tenant_id, child, definition, 1))
        await session.commit()
    assert await _resolved(child) == 1
    await delete_tenant(tenant_id)


async def test_the_order_decides_between_grandparents_through_different_parents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        definition = await _weight(session, tenant_id)
        child = await _entry(session, tenant_id, "Child")
        left = await _entry(session, tenant_id, "Left")
        right = await _entry(session, tenant_id, "Right")
        left_root = await _entry(session, tenant_id, "LeftRoot")
        right_root = await _entry(session, tenant_id, "RightRoot")
        session.add_all(
            [
                _set(tenant_id, left_root, definition, 1),
                _set(tenant_id, right_root, definition, 2),
                EntityPrototype(
                    entity_id=left, prototype_id=left_root, tenant_id=tenant_id, position=0
                ),
                EntityPrototype(
                    entity_id=right, prototype_id=right_root, tenant_id=tenant_id, position=0
                ),
            ]
        )
        await session.commit()
    await _put(client, tenant_id, child, [left, right])
    assert await _resolved(child) == 1
    await _put(client, tenant_id, child, [right, left])
    assert await _resolved(child) == 2
    await delete_tenant(tenant_id)


async def test_an_unchanged_order_does_not_move_the_version(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    child, a, b, _ = await _two_parents(tenant_id)
    await _put(client, tenant_id, child, [a, b])
    before = (await client.get(f"/tenants/{tenant_id}/entities/{child}")).headers["ETag"]
    await _put(client, tenant_id, child, [a, b])
    same = (await client.get(f"/tenants/{tenant_id}/entities/{child}")).headers["ETag"]
    await _put(client, tenant_id, child, [b, a])
    moved = (await client.get(f"/tenants/{tenant_id}/entities/{child}")).headers["ETag"]
    assert before == same
    assert moved != before
    await delete_tenant(tenant_id)
