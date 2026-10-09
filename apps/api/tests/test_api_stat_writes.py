"""Stat writes that can be checked and undone (ADR 0225, RFC 0039 W1), through the real HTTP API:
a write moves the entry's version, says what it replaced, and an own value can be cleared."""

import uuid
from datetime import datetime
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.etag import etag_for
from lorenzo_api.models import Entity, EntityStat, StatDefinition, StatGroup, StatValueType


async def _stats(tenant_id: uuid.UUID, **types: StatValueType) -> dict[str, uuid.UUID]:
    """A group with a stat definition for each name given, by its type."""
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


def _entity(tenant_id: uuid.UUID, *rest: object) -> str:
    return "/".join([f"/tenants/{tenant_id}/entities", *(str(r) for r in rest)])


async def _make(
    client: AsyncClient, tenant_id: uuid.UUID, name: str, *parents: uuid.UUID
) -> uuid.UUID:
    response = await client.post(
        _entity(tenant_id),
        json={"name": name, "kinds": ["item"], "parents": [str(p) for p in parents]},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _version(client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> str:
    response = await client.get(_entity(tenant_id, entity_id))
    return response.headers["etag"]


async def _own(entity_id: uuid.UUID, stat_id: uuid.UUID) -> EntityStat | None:
    async with admin_session_factory() as session:
        return await session.get(EntityStat, (entity_id, stat_id))


def _put(tenant_id: uuid.UUID, entity_id: uuid.UUID, stat_id: uuid.UUID) -> str:
    return _entity(tenant_id, entity_id, "stats", stat_id)


# --- a write moves the entry's version -------------------------------------------------------


async def test_a_stat_write_moves_the_entrys_version_and_returns_the_new_one(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    before = await _version(client, tenant_id, entity_id)

    response = await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})

    assert response.status_code == 200, response.text
    assert response.headers["etag"] != before
    assert response.headers["etag"] == etag_for(
        datetime.fromisoformat(response.json()["updated_at"])
    )
    assert response.headers["etag"] == await _version(client, tenant_id, entity_id)
    await delete_tenant(tenant_id)


async def test_an_edit_made_against_the_old_version_is_refused_after_a_stat_write(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    seen = await _version(client, tenant_id, entity_id)
    await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})

    rename = await client.patch(
        f"/tenants/{tenant_id}/items/{entity_id}",
        json={"name": "Greataxe"},
        headers={"If-Match": seen},
    )

    assert rename.status_code == 412
    await delete_tenant(tenant_id)


async def test_the_same_value_again_changes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})
    before = await _version(client, tenant_id, entity_id)

    again = await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})

    assert again.status_code == 200
    assert again.headers["etag"] == before
    assert again.json()["previous"] == {"had_own_value": True, "value": 8}
    await delete_tenant(tenant_id)


async def test_acquiring_the_group_with_the_same_value_is_a_change(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})
    before = await _version(client, tenant_id, entity_id)

    again = await client.put(
        _put(tenant_id, entity_id, stats["damage"]), json={"value": 8, "acquire_group": True}
    )

    assert again.headers["etag"] != before
    await delete_tenant(tenant_id)


async def test_the_write_says_who_made_it(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})
    async with admin_session_factory() as session:
        entity = (await session.scalars(select(Entity).where(Entity.id == entity_id))).one()
        assert entity.updated_by == test_user_id
    await delete_tenant(tenant_id)


# --- what it replaced --------------------------------------------------------------------------


async def test_a_first_write_replaced_nothing_and_an_overwrite_says_what(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT, note=StatValueType.TEXT)
    entity_id = await _make(client, tenant_id, "Axe")

    first = await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})
    second = await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 10})
    text = await client.put(_put(tenant_id, entity_id, stats["note"]), json={"value": "a"})
    text2 = await client.put(_put(tenant_id, entity_id, stats["note"]), json={"value": "b"})

    assert first.json()["previous"] == {"had_own_value": False, "value": None}
    assert second.json()["previous"] == {"had_own_value": True, "value": 8}
    assert text.json()["previous"]["had_own_value"] is False
    assert text2.json()["previous"] == {"had_own_value": True, "value": "a"}
    await delete_tenant(tenant_id)


async def test_the_response_is_still_the_entry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """`previous` is added to what the route returned, so a caller of before is unaffected."""
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    response = await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})
    detail = (await client.get(_entity(tenant_id, entity_id))).json()
    body: dict[str, Any] = response.json()
    assert body.pop("previous") == {"had_own_value": False, "value": None}
    assert body == detail
    await delete_tenant(tenant_id)


# --- clearing an own value ---------------------------------------------------------------------


async def test_clearing_an_own_value_inherits_again_and_says_what_it_removed(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    parent = await _make(client, tenant_id, "Weapon")
    child = await _make(client, tenant_id, "Axe", parent)
    await client.put(_put(tenant_id, parent, stats["damage"]), json={"value": 5})
    await client.put(_put(tenant_id, child, stats["damage"]), json={"value": 9})
    before = await _version(client, tenant_id, child)

    response = await client.delete(_put(tenant_id, child, stats["damage"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["previous"] == {"had_own_value": True, "value": 9}
    assert body["stats"] == [{"name": "damage", "value": 5, "own": False}]
    assert response.headers["etag"] != before
    assert await _own(child, stats["damage"]) is None
    assert await _own(parent, stats["damage"]) is not None
    await delete_tenant(tenant_id)


async def test_clearing_what_is_not_there_is_a_200_that_moves_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    before = await _version(client, tenant_id, entity_id)

    response = await client.delete(_put(tenant_id, entity_id, stats["damage"]))

    assert response.status_code == 200
    assert response.json()["previous"] == {"had_own_value": False, "value": None}
    assert response.headers["etag"] == before
    await delete_tenant(tenant_id)


async def test_setting_and_clearing_undo_each_other(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """What `previous` is for: put back what was there, or clear what was not."""
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    url = _put(tenant_id, entity_id, stats["damage"])

    set_ = await client.put(url, json={"value": 8})
    assert set_.json()["previous"]["had_own_value"] is False
    await client.delete(url)  # undo of a first write
    assert await _own(entity_id, stats["damage"]) is None

    await client.put(url, json={"value": 8})
    over = await client.put(url, json={"value": 12})
    await client.put(url, json={"value": over.json()["previous"]["value"]})  # undo of an overwrite
    row = await _own(entity_id, stats["damage"])
    assert row is not None and row.value_int == 8
    await delete_tenant(tenant_id)


async def test_clearing_takes_a_stale_if_match_as_the_write_does(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, damage=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    await client.put(_put(tenant_id, entity_id, stats["damage"]), json={"value": 8})

    stale = await client.delete(
        _put(tenant_id, entity_id, stats["damage"]), headers={"If-Match": 'W/"old"'}
    )

    assert stale.status_code == 412
    assert await _own(entity_id, stats["damage"]) is not None
    await delete_tenant(tenant_id)


async def test_a_bool_is_cleared_through_the_tag_route(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, magic=StatValueType.BOOL)
    entity_id = await _make(client, tenant_id, "Axe")
    response = await client.delete(_put(tenant_id, entity_id, stats["magic"]))
    assert response.status_code == 422
    assert f"/tags/{stats['magic']}" in response.text
    await delete_tenant(tenant_id)


async def test_a_formula_is_not_a_direct_value_to_clear(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, base=StatValueType.INT, derived=StatValueType.INT)
    entity_id = await _make(client, tenant_id, "Axe")
    made = await client.put(
        _entity(tenant_id, entity_id, "computed-stats", stats["derived"]),
        json={
            "kind": "linear",
            "source_stat_definition_id": str(stats["base"]),
            "multiplier": 2,
            "round_mode": "round",
        },
    )
    assert made.status_code in (200, 201), made.text

    response = await client.delete(_put(tenant_id, entity_id, stats["derived"]))

    assert response.status_code == 409
    await delete_tenant(tenant_id)


async def test_a_stat_of_another_library_is_a_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine = await make_tenant(test_user_id)
    theirs = await make_tenant(test_user_id)
    theirs_stats = await _stats(theirs, damage=StatValueType.INT)
    entity_id = await _make(client, mine, "Axe")
    response = await client.delete(_put(mine, entity_id, theirs_stats["damage"]))
    assert response.status_code == 404
    await delete_tenant(mine)
    await delete_tenant(theirs)


# --- tags --------------------------------------------------------------------------------------


async def test_the_tag_routes_move_the_version_and_say_what_they_replaced(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stats = await _stats(tenant_id, magic=StatValueType.BOOL)
    entity_id = await _make(client, tenant_id, "Axe")
    url = _entity(tenant_id, entity_id, "tags", stats["magic"])
    v0 = await _version(client, tenant_id, entity_id)

    on = await client.put(url)
    off = await client.patch(url)
    cleared = await client.delete(url)

    assert on.json()["previous"] == {"had_own_value": False, "value": None}
    assert off.json()["previous"] == {"had_own_value": True, "value": True}
    assert cleared.json()["previous"] == {"had_own_value": True, "value": False}
    versions = [v0, on.headers["etag"], off.headers["etag"], cleared.headers["etag"]]
    assert len(set(versions)) == 4
    again = await client.delete(url)
    assert again.json()["previous"] == {"had_own_value": False, "value": None}
    assert again.headers["etag"] == cleared.headers["etag"]
    await delete_tenant(tenant_id)
