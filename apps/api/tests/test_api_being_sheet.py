"""ADR 0281: the library's two sheet settings and the sheet read - a being's equipped weapons and
its abilities in one request."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_plain_participant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    Character,
    Containment,
    Entity,
    EntityStat,
    Information,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
    StatDefinition,
    StatGroup,
    Tenant,
)


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str) -> dict:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def _definition(client: AsyncClient, tenant_id: uuid.UUID, group: str, name: str) -> dict:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": group, "name": name, "value_type": "int"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _being(tenant_id: uuid.UUID, name: str = "Brannoch") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _equip(
    tenant_id: uuid.UUID,
    being: uuid.UUID,
    name: str,
    stats: dict[uuid.UUID, int],
    *,
    owner: uuid.UUID | None = None,
) -> uuid.UUID:
    async with admin_session_factory() as session:
        item = Entity(tenant_id=tenant_id, name=name)
        session.add(item)
        await session.flush()
        session.add(ItemInstance(entity_id=item.id, tenant_id=tenant_id))
        await session.flush()
        session.add(
            Containment(child_entity_id=item.id, parent_entity_id=being, tenant_id=tenant_id)
        )
        for definition_id, value in stats.items():
            session.add(
                EntityStat(
                    entity_id=item.id,
                    stat_definition_id=definition_id,
                    tenant_id=tenant_id,
                    value_int=value,
                )
            )
        if owner is not None:
            session.add(Character(entity_id=owner, tenant_id=tenant_id))
            await session.flush()
            session.add(
                Ownership(owned_entity_id=item.id, owner_character_id=owner, tenant_id=tenant_id)
            )
        await session.commit()
        return item.id


async def _note(
    tenant_id: uuid.UUID, being: uuid.UUID, title: str, type_: str, *, public: bool
) -> None:
    async with admin_session_factory() as session:
        session.add(
            Information(
                tenant_id=tenant_id, entity_id=being, title=title, type=type_, is_public=public
            )
        )
        await session.commit()


def _url(tenant_id: uuid.UUID, being: uuid.UUID) -> str:
    return f"/tenants/{tenant_id}/beings/{being}/sheet"


# --- the settings --------------------------------------------------------------


async def test_the_settings_start_unset_and_can_be_set_and_cleared(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Weapons")

    fresh = (await client.get(f"/tenants/{tenant_id}")).json()
    assert (fresh["weapon_stat_group_id"], fresh["ability_information_type"]) == (None, None)

    done = await client.patch(
        f"/tenants/{tenant_id}",
        json={"weapon_stat_group_id": group["id"], "ability_information_type": "ability"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["weapon_stat_group_id"] == group["id"]
    assert done.json()["ability_information_type"] == "ability"

    cleared = await client.patch(f"/tenants/{tenant_id}", json={"weapon_stat_group_id": None})
    assert cleared.json()["weapon_stat_group_id"] is None
    assert cleared.json()["ability_information_type"] == "ability"  # not sent, so kept
    await delete_tenant(tenant_id)


async def test_the_weapon_group_must_be_a_group_of_the_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    foreign = await _group(client, other, "Weapons")

    for group_id in (foreign["id"], str(uuid.uuid4())):
        response = await client.patch(
            f"/tenants/{tenant_id}", json={"weapon_stat_group_id": group_id}
        )
        assert response.status_code == 422, response.text
    await delete_tenant(tenant_id)
    await delete_tenant(other)


async def test_deleting_the_group_clears_the_setting_and_a_tenant_with_one_can_be_deleted(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Weapons")
    await client.patch(f"/tenants/{tenant_id}", json={"weapon_stat_group_id": group["id"]})

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(StatGroup, uuid.UUID(group["id"])))
        await session.commit()
    kept = (await client.get(f"/tenants/{tenant_id}")).json()
    assert kept["weapon_stat_group_id"] is None
    assert kept["name"]  # the row itself, and its tenant_id, are untouched

    again = await _group(client, tenant_id, "Weapons again")
    await client.patch(f"/tenants/{tenant_id}", json={"weapon_stat_group_id": again["id"]})
    await delete_tenant(tenant_id)  # cascades to the group the tenant points at
    async with admin_session_factory() as session:
        assert await session.get(Tenant, tenant_id) is None


# --- the sheet read ------------------------------------------------------------


async def test_an_unconfigured_library_gets_empty_sections_and_the_flags(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    being = await _being(tenant_id)

    sheet = (await client.get(_url(tenant_id, being))).json()

    assert sheet == {
        "weapons_configured": False,
        "abilities_configured": False,
        "weapons": [],
        "abilities": [],
    }
    await delete_tenant(tenant_id)


async def test_the_weapons_are_what_the_being_holds_with_the_weapon_group_stats_in_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weapons = await _group(client, tenant_id, "Weapons")
    other = await _group(client, tenant_id, "Misc")
    reach = await _definition(client, tenant_id, weapons["id"], "reach")
    damage = await _definition(client, tenant_id, weapons["id"], "damage")
    weight = await _definition(client, tenant_id, other["id"], "weight")
    await client.patch(f"/tenants/{tenant_id}", json={"weapon_stat_group_id": weapons["id"]})
    being = await _being(tenant_id)
    ids = {
        k: uuid.UUID(v["id"]) for k, v in (("reach", reach), ("damage", damage), ("weight", weight))
    }
    sword = await _equip(
        tenant_id, being, "Longsword", {ids["damage"]: 8, ids["reach"]: 5, ids["weight"]: 3}
    )
    await _equip(tenant_id, being, "Lantern", {ids["weight"]: 2})  # no weapon stat: not listed
    elsewhere = await _being(tenant_id, "Elsewhere")
    await _equip(tenant_id, elsewhere, "Dagger", {ids["damage"]: 4})  # held by someone else

    sheet = (await client.get(_url(tenant_id, being))).json()

    assert sheet["weapons_configured"] is True
    assert [w["name"] for w in sheet["weapons"]] == ["Longsword"]
    longsword = sheet["weapons"][0]
    assert longsword["entity_id"] == str(sword)
    assert [(s["name"], s["value"]) for s in longsword["stats"]] == [("reach", 5), ("damage", 8)]
    await delete_tenant(tenant_id)


async def test_the_abilities_are_the_information_of_the_set_type_as_the_caller_sees_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    being = await _being(tenant_id)
    await _note(tenant_id, being, "Rage", "ability", public=True)
    await _note(tenant_id, being, "Secret trick", "ability", public=False)
    await _note(tenant_id, being, "Backstory", "note", public=True)
    await client.patch(f"/tenants/{tenant_id}", json={"ability_information_type": "ability"})

    as_admin = (await client.get(_url(tenant_id, being))).json()
    assert as_admin["abilities_configured"] is True
    assert sorted(a["title"] for a in as_admin["abilities"]) == ["Rage", "Secret trick"]

    await make_plain_participant(tenant_id, test_user_id)
    as_player = (await client.get(_url(tenant_id, being))).json()
    assert [a["title"] for a in as_player["abilities"]] == ["Rage"]
    await delete_tenant(tenant_id)


async def test_another_players_being_shows_no_weapons(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weapons = await _group(client, tenant_id, "Weapons")
    damage = await _definition(client, tenant_id, weapons["id"], "damage")
    await client.patch(f"/tenants/{tenant_id}", json={"weapon_stat_group_id": weapons["id"]})
    being = await _being(tenant_id)
    await _equip(tenant_id, being, "Longsword", {uuid.UUID(damage["id"]): 8}, owner=being)
    async with admin_session_factory() as session:  # ORGA reaches every owner (ADR 0040)
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        membership.role = MembershipRole.ORGA
        await session.commit()
    assert len((await client.get(_url(tenant_id, being))).json()["weapons"]) == 1

    await make_plain_participant(tenant_id, test_user_id)
    sheet = (await client.get(_url(tenant_id, being))).json()

    assert sheet["weapons"] == []
    assert sheet["weapons_configured"] is True
    await delete_tenant(tenant_id)


async def test_a_campaign_must_be_one_the_caller_can_read_and_a_non_being_is_not_found(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    being = await _being(tenant_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Table")
        thing = Entity(tenant_id=tenant_id, name="Rock")
        session.add(thing)
        await session.commit()
        campaign_id, thing_id = campaign.id, thing.id

    assert (
        await client.get(_url(tenant_id, being), params={"campaign_id": str(campaign_id)})
    ).status_code == 200
    unknown = await client.get(_url(tenant_id, being), params={"campaign_id": str(uuid.uuid4())})
    assert unknown.status_code == 404
    assert (await client.get(_url(tenant_id, thing_id))).status_code == 404
    assert (await client.get(_url(tenant_id, uuid.uuid4()))).status_code == 404
    await delete_tenant(tenant_id)


async def test_the_definitions_are_not_confused_across_tenants(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    weapons = await _group(client, other, "Weapons")
    damage = await _definition(client, other, weapons["id"], "damage")
    being = await _being(tenant_id)
    sword = await _equip(tenant_id, being, "Longsword", {})
    async with admin_session_factory() as session:
        assert await session.get(StatDefinition, uuid.UUID(damage["id"])) is not None
        assert sword is not None
    assert (await client.get(_url(tenant_id, being))).json()["weapons"] == []
    await delete_tenant(tenant_id)
    await delete_tenant(other)


# --- who may read the vocabulary -----------------------------------------------


async def test_any_participant_reads_the_stat_vocabulary_and_only_an_administrator_writes_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A sheet draws a being for its player, who is no member (ADR 0281)."""
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Vitals")
    definition = await _definition(client, tenant_id, group["id"], "speed")
    await make_plain_participant(tenant_id, test_user_id)

    groups = await client.get(f"/tenants/{tenant_id}/stat-groups")
    definitions = await client.get(f"/tenants/{tenant_id}/stat-definitions")
    one = await client.get(f"/tenants/{tenant_id}/stat-definitions/{definition['id']}")
    refused = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{definition['id']}", json={"pin": True}
    )

    assert [g["name"] for g in groups.json()["items"]] == ["Vitals"]
    assert [d["name"] for d in definitions.json()["items"]] == ["speed"]
    assert one.status_code == 200
    assert refused.status_code == 404
    await delete_tenant(tenant_id)


async def test_someone_with_no_standing_in_the_tenant_does_not_read_its_vocabulary(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        await session.commit()

    for path in ("stat-groups", "stat-definitions"):
        assert (await client.get(f"/tenants/{tenant_id}/{path}")).status_code == 404
    await delete_tenant(tenant_id)
