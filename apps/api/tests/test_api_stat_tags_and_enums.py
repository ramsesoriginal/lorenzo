"""ADR 0103: tag endpoints, enum stat values, and mandatory stat groups."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.db import engine
from lorenzo_api.etag import etag_for
from lorenzo_api.models import (
    Entity,
    EntityPrototype,
    EntityStat,
    EntityStatGroup,
    Membership,
    Player,
    StatDefinition,
    StatGroup,
    StatValueType,
)


async def _make_group(tenant_id: uuid.UUID, name: str = "tags") -> uuid.UUID:
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant_id, name=name)
        session.add(group)
        await session.commit()
        return group.id


async def _make_stat(
    tenant_id: uuid.UUID, group_id: uuid.UUID, name: str, value_type: StatValueType
) -> uuid.UUID:
    async with admin_session_factory() as session:
        definition = StatDefinition(
            tenant_id=tenant_id, stat_group_id=group_id, name=name, value_type=value_type
        )
        session.add(definition)
        await session.commit()
        return definition.id


async def _make_entity(tenant_id: uuid.UUID, name: str = "Door") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


def _stat(body: dict, name: str) -> object:
    return {s["name"]: s["value"] for s in body["stats"]}.get(name, "<unset>")


# --- mandatory groups --------------------------------------------------------


async def test_stat_group_mandatory_defaults_false_and_round_trips(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    plain = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": "lore"})
    mandatory = await client.post(
        f"/tenants/{tenant_id}/stat-groups", json={"name": "abilities", "mandatory": True}
    )
    listed = await client.get(f"/tenants/{tenant_id}/stat-groups")

    assert plain.json()["mandatory"] is False
    assert mandatory.json()["mandatory"] is True
    assert {g["name"]: g["mandatory"] for g in listed.json()["items"]} == {
        "lore": False,
        "abilities": True,
    }
    await delete_tenant(tenant_id)


# --- tags --------------------------------------------------------------------


async def test_tag_put_patch_delete_cycle_through_true_false_inherited(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The door built on the `wood` prototype, since rebuilt in metal."""
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    is_wooden = await _make_stat(tenant_id, group_id, "is_wooden", StatValueType.BOOL)
    wood = await _make_entity(tenant_id, "Wood")
    door = await _make_entity(tenant_id, "Door")
    async with admin_session_factory() as session:
        session.add(EntityPrototype(entity_id=door, prototype_id=wood, tenant_id=tenant_id))
        session.add(
            EntityStat(
                entity_id=wood, stat_definition_id=is_wooden, tenant_id=tenant_id, value_bool=True
            )
        )
        await session.commit()
    url = f"/tenants/{tenant_id}/entities/{door}/tags/{is_wooden}"

    inherited = await client.get(f"/tenants/{tenant_id}/entities/{door}")
    explicit_false = await client.patch(url)
    explicit_true = await client.put(url)
    cleared = await client.delete(url)
    cleared_again = await client.delete(url)

    assert _stat(inherited.json(), "is_wooden") is True
    assert explicit_false.status_code == 200, explicit_false.text
    assert _stat(explicit_false.json(), "is_wooden") is False
    # Setting a tag acquires its group (ADR 0037's gap, closed for tags).
    assert [g["id"] for g in explicit_false.json()["stat_groups"]] == [str(group_id)]
    assert _stat(explicit_true.json(), "is_wooden") is True
    assert _stat(cleared.json(), "is_wooden") is True  # inherited from Wood again
    assert cleared_again.status_code == 200
    async with admin_session_factory() as session:
        own = await session.get(EntityStat, (door, is_wooden))
        link = await session.get(EntityStatGroup, (door, group_id))
    assert own is None
    assert link is not None  # DELETE leaves group acquisition alone
    await delete_tenant(tenant_id)


async def test_tag_routes_reject_a_non_bool_stat(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    weight = await _make_stat(tenant_id, group_id, "weight", StatValueType.INT)
    entity = await _make_entity(tenant_id)
    url = f"/tenants/{tenant_id}/entities/{entity}/tags/{weight}"

    statuses = [(await client.put(url)).status_code, (await client.delete(url)).status_code]

    assert statuses == [422, 422]
    await delete_tenant(tenant_id)


async def test_tag_if_match(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    tag = await _make_stat(tenant_id, group_id, "is_metal", StatValueType.BOOL)
    entity = await _make_entity(tenant_id)
    url = f"/tenants/{tenant_id}/entities/{entity}/tags/{tag}"
    await client.put(url)
    async with admin_session_factory() as session:
        etag = etag_for((await session.get_one(EntityStat, (entity, tag))).updated_at)

    stale = await client.patch(url, headers={"If-Match": 'W/"2000-01-01T00:00:00+00:00"'})
    fresh = await client.patch(url, headers={"If-Match": etag})
    stale_delete = await client.delete(url, headers={"If-Match": etag})

    assert stale.status_code == 412
    assert fresh.status_code == 200
    assert stale_delete.status_code == 412
    await delete_tenant(tenant_id)


async def test_tag_403_for_a_player_without_standing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    tag = await _make_stat(tenant_id, group_id, "is_metal", StatValueType.BOOL)
    entity = await _make_entity(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Membership, (tenant_id, test_user_id)))
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.put(f"/tenants/{tenant_id}/entities/{entity}/tags/{tag}")

    assert response.status_code == 403
    await delete_tenant(tenant_id)


# --- enum values -------------------------------------------------------------


async def _create_rarity(client: AsyncClient, tenant_id: uuid.UUID, group_id: uuid.UUID) -> dict:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={
            "name": "rarity",
            "stat_group_id": str(group_id),
            "value_type": "enum",
            "enum_values": ["common", "rare", "legendary"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_enum_definition_keeps_values_in_given_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id, "economic")

    created = await _create_rarity(client, tenant_id, group_id)
    fetched = await client.get(f"/tenants/{tenant_id}/stat-definitions/{created['id']}")
    listed = await client.get(f"/tenants/{tenant_id}/stat-definitions")

    assert created["value_type"] == "enum"
    assert created["enum_values"] == ["common", "rare", "legendary"]
    assert fetched.json()["enum_values"] == ["common", "rare", "legendary"]
    assert listed.json()["items"][0]["enum_values"] == ["common", "rare", "legendary"]
    await delete_tenant(tenant_id)


async def test_enum_definition_body_validation(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    url = f"/tenants/{tenant_id}/stat-definitions"
    base = {"stat_group_id": str(group_id)}

    missing = await client.post(url, json={**base, "name": "a", "value_type": "enum"})
    empty = await client.post(
        url, json={**base, "name": "b", "value_type": "enum", "enum_values": []}
    )
    duplicate = await client.post(
        url, json={**base, "name": "c", "value_type": "enum", "enum_values": ["x", "x"]}
    )
    on_int = await client.post(
        url, json={**base, "name": "d", "value_type": "int", "enum_values": ["x"]}
    )
    int_without = await client.post(url, json={**base, "name": "e", "value_type": "int"})

    assert [r.status_code for r in (missing, empty, duplicate, on_int)] == [422] * 4
    assert int_without.json()["enum_values"] == []
    await delete_tenant(tenant_id)


async def test_enum_stat_value_must_be_allowed(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    rarity = await _create_rarity(client, tenant_id, group_id)
    entity = await _make_entity(tenant_id, "Ashfang")
    url = f"/tenants/{tenant_id}/entities/{entity}/stats/{rarity['id']}"

    ok = await client.put(url, json={"value": "legendary"})
    not_allowed = await client.put(url, json={"value": "mythic"})
    wrong_type = await client.put(url, json={"value": 3})

    assert ok.status_code == 200, ok.text
    assert _stat(ok.json(), "rarity") == "legendary"
    assert not_allowed.status_code == 422
    assert not_allowed.json()["type"] == "invalid-stat-value"
    assert wrong_type.status_code == 422
    await delete_tenant(tenant_id)


async def test_enum_values_can_grow_and_shrink(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    rarity = await _create_rarity(client, tenant_id, group_id)
    values_url = f"/tenants/{tenant_id}/stat-definitions/{rarity['id']}/enum-values"

    added = await client.post(values_url, json={"value": "mythic"})
    placed = await client.post(values_url, json={"value": "junk", "sort_order": -1})
    duplicate = await client.post(values_url, json={"value": "rare"})
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT value, id FROM stat_definition_enum_value WHERE stat_definition_id = :d"
                ),
                {"d": rarity["id"]},
            )
        ).all()
        ids = {value: value_id for value, value_id in rows}

    entity = await _make_entity(tenant_id, "Ashfang")
    await client.put(
        f"/tenants/{tenant_id}/entities/{entity}/stats/{rarity['id']}", json={"value": "rare"}
    )
    in_use = await client.delete(f"{values_url}/{ids['rare']}")
    removed = await client.delete(f"{values_url}/{ids['common']}")
    unknown = await client.delete(f"{values_url}/{uuid.uuid4()}")

    assert added.status_code == 201
    assert added.json()["enum_values"] == ["common", "rare", "legendary", "mythic"]
    assert placed.json()["enum_values"][0] == "junk"
    assert duplicate.status_code == 409
    assert in_use.status_code == 409
    assert removed.status_code == 200
    assert "common" not in removed.json()["enum_values"]
    assert unknown.status_code == 404
    await delete_tenant(tenant_id)


async def test_enum_values_route_rejects_a_non_enum_definition(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(tenant_id)
    weight = await _make_stat(tenant_id, group_id, "weight", StatValueType.INT)

    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions/{weight}/enum-values", json={"value": "x"}
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_stat_definition_enum_value_rls_isolates_tenants() -> None:
    """FORCE RLS on the new table, through the app's restricted role."""
    tenant_ids = []
    async with admin_session_factory() as session:
        for label in ("A", "B"):
            tenant_id = (
                await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
            ).scalar_one()
            group = StatGroup(tenant_id=tenant_id, name=f"g-{label}")
            session.add(group)
            await session.flush()
            definition = StatDefinition(
                tenant_id=tenant_id,
                stat_group_id=group.id,
                name=f"rarity-{label}",
                value_type=StatValueType.ENUM,
            )
            session.add(definition)
            await session.flush()
            await session.execute(
                text(
                    "INSERT INTO stat_definition_enum_value (tenant_id, stat_definition_id, value)"
                    " VALUES (:t, :d, :v)"
                ),
                {"t": tenant_id, "d": definition.id, "v": f"value-{label}"},
            )
            tenant_ids.append(tenant_id)
        await session.commit()

    try:
        for tenant_id, expected in zip(tenant_ids, (["value-A"], ["value-B"]), strict=True):
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                values = (
                    (await conn.execute(text("SELECT value FROM stat_definition_enum_value")))
                    .scalars()
                    .all()
                )
                assert list(values) == expected
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)


async def test_enum_rows_cascade_with_their_definition() -> None:
    async with admin_session_factory() as session:
        tenant_id = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        group = StatGroup(tenant_id=tenant_id, name="g")
        session.add(group)
        await session.flush()
        definition = StatDefinition(
            tenant_id=tenant_id, stat_group_id=group.id, name="r", value_type=StatValueType.ENUM
        )
        session.add(definition)
        await session.flush()
        await session.execute(
            text(
                "INSERT INTO stat_definition_enum_value (tenant_id, stat_definition_id, value)"
                " VALUES (:t, :d, 'x')"
            ),
            {"t": tenant_id, "d": definition.id},
        )
        await session.commit()
        await session.delete(definition)
        await session.commit()
        remaining = (
            await session.execute(
                select(text("count(*)"))
                .select_from(text("stat_definition_enum_value"))
                .where(text("tenant_id = :t")),
                {"t": tenant_id},
            )
        ).scalar_one()
    assert remaining == 0
    await delete_tenant(tenant_id)
