"""ADR 0454: the kinds `feature` and `feature_instance`, and `/features` - making a feature, what an
award makes, repeatable and starts_inactive, the switch a formula reads, removal, what an inventory
read leaves out, who may do what, and what goes with a holder or a feature.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import (
    delete_tenant,
    make_being,
    make_campaign,
    make_character,
    make_plain_participant,
    make_tenant,
)
from httpx import AsyncClient
from sqlalchemy import func, select
from test_api_computed_stats import _put, _sheet

from lorenzo_api.models import (
    CharacterPlayer,
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    FeatureInstance,
    Membership,
    MembershipRole,
    Player,
    StatValueType,
)


async def _make(client: AsyncClient, tenant_id: uuid.UUID, body: dict) -> dict:
    response = await client.post(f"/tenants/{tenant_id}/entities", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _feature(
    client: AsyncClient,
    tenant_id: uuid.UUID,
    name: str,
    *,
    parents: list[uuid.UUID] | None = None,
    **columns: bool,
) -> uuid.UUID:
    made = await _make(
        client,
        tenant_id,
        {"name": name, "kinds": ["feature"], "parents": [str(p) for p in parents or []], **columns},
    )
    return uuid.UUID(made["id"])


async def _award(
    client: AsyncClient, tenant_id: uuid.UUID, holder: uuid.UUID, feature: uuid.UUID, **body: bool
):  # type: ignore[no-untyped-def]
    return await client.post(
        f"/tenants/{tenant_id}/entities/{holder}/features",
        json={"feature_id": str(feature), **body},
    )


async def _held(client: AsyncClient, tenant_id: uuid.UUID, holder: uuid.UUID) -> list[dict]:
    response = await client.get(f"/tenants/{tenant_id}/entities/{holder}/features")
    assert response.status_code == 200, response.text
    return response.json()["features"]  # type: ignore[no-any-return]


async def _being(tenant_id: uuid.UUID, name: str = "Hero") -> uuid.UUID:
    async with admin_session_factory() as session:
        being = await make_being(session, tenant_id=tenant_id, name=name)
        await session.commit()
        return being.entity_id


async def _stat_on(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, stat: uuid.UUID, value: int | bool
) -> None:
    async with admin_session_factory() as session:
        session.add(
            EntityStat(
                entity_id=entity_id,
                stat_definition_id=stat,
                tenant_id=tenant_id,
                value_int=None if isinstance(value, bool) else value,
                value_bool=value if isinstance(value, bool) else None,
            )
        )
        await session.commit()


# --- the kinds ---------------------------------------------------------------


async def test_a_feature_is_made_read_and_changed(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    school = await _make(client, tenant_id, {"name": "Evocation", "kinds": []})
    feature = await _feature(
        client, tenant_id, "Fireball", parents=[uuid.UUID(school["id"])], repeatable=True
    )

    read = await client.get(f"/tenants/{tenant_id}/entities/{feature}")
    assert read.json()["kinds"] == ["feature"]
    assert [p["name"] for p in read.json()["prototypes"]] == ["Evocation"]
    columns = await client.get(f"/tenants/{tenant_id}/features/prototypes/{feature}")
    assert columns.json() == {
        "id": str(feature),
        "name": "Fireball",
        "repeatable": True,
        "starts_inactive": False,
    }

    changed = await client.put(
        f"/tenants/{tenant_id}/entities/{feature}/kinds/feature",
        json={"repeatable": False, "starts_inactive": True},
    )
    assert changed.status_code == 200, changed.text
    columns = await client.get(f"/tenants/{tenant_id}/features/prototypes/{feature}")
    assert (columns.json()["repeatable"], columns.json()["starts_inactive"]) == (False, True)
    # A column left out stays as it is.
    await client.put(f"/tenants/{tenant_id}/entities/{feature}/kinds/feature", json={})
    columns = await client.get(f"/tenants/{tenant_id}/features/prototypes/{feature}")
    assert (columns.json()["repeatable"], columns.json()["starts_inactive"]) == (False, True)

    listed = await client.get(f"/tenants/{tenant_id}/entities", params={"kind": "feature"})
    assert [e["name"] for e in listed.json()["items"]] == ["Fireball"]
    # An entry that is not a feature has no columns.
    assert (
        await client.get(f"/tenants/{tenant_id}/features/prototypes/{school['id']}")
    ).status_code == 404
    await delete_tenant(tenant_id)


async def test_a_feature_stands_alone_and_an_instance_is_not_made_by_the_kind_routes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    both = await client.post(
        f"/tenants/{tenant_id}/entities", json={"name": "Both", "kinds": ["feature", "item"]}
    )
    assert both.status_code == 422, both.text
    columns_on_item = await client.post(
        f"/tenants/{tenant_id}/entities",
        json={"name": "Sword", "kinds": ["item"], "repeatable": True},
    )
    assert columns_on_item.status_code == 422
    sword = await _make(client, tenant_id, {"name": "Sword", "kinds": ["item"]})
    on_item = await client.put(f"/tenants/{tenant_id}/entities/{sword['id']}/kinds/feature")
    assert on_item.status_code == 422, on_item.text
    feature = await _feature(client, tenant_id, "Darkvision")
    give_item = await client.put(f"/tenants/{tenant_id}/entities/{feature}/kinds/item")
    assert give_item.status_code == 422, give_item.text
    instance_kind = await client.put(
        f"/tenants/{tenant_id}/entities/{feature}/kinds/feature_instance"
    )
    assert instance_kind.status_code == 422
    # The kind goes when nobody holds the feature.
    removed = await client.delete(f"/tenants/{tenant_id}/entities/{feature}/kinds/feature")
    assert removed.status_code == 200
    assert removed.json()["kinds"] == []
    await delete_tenant(tenant_id)


# --- awarding and reading ------------------------------------------------------


async def test_an_award_gives_the_holder_an_instance_of_the_feature(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, bonus=StatValueType.INT, uses_spent=StatValueType.INT)
    school = await _make(client, tenant_id, {"name": "Evocation", "kinds": []})
    feature = await _feature(client, tenant_id, "Fireball", parents=[uuid.UUID(school["id"])])
    await _stat_on(tenant_id, feature, sheet["bonus"], 3)
    hero = await _being(tenant_id)

    awarded = await _award(client, tenant_id, hero, feature)
    assert awarded.status_code == 201, awarded.text
    body = awarded.json()
    assert body["name"] == "Fireball"
    assert (body["feature"]["id"], body["feature"]["name"]) == (str(feature), "Fireball")
    assert [t["name"] for t in body["types"]] == ["Evocation"]
    assert body["active"] is True
    assert {s["name"]: (s["value"], s["own"]) for s in body["stats"]} == {"bonus": (3, False)}
    assert awarded.headers["location"].endswith(f"/tenants/{tenant_id}/features/{body['id']}")

    # What the holder keeps is the instance's own stat, over what it inherits.
    await _stat_on(tenant_id, uuid.UUID(body["id"]), sheet["uses_spent"], 1)
    held = await _held(client, tenant_id, hero)
    assert [(h["name"], h["active"]) for h in held] == [("Fireball", True)]
    assert {s["name"]: s["value"] for s in held[0]["stats"]} == {"bonus": 3, "uses_spent": 1}
    one = await client.get(f"/tenants/{tenant_id}/features/{body['id']}")
    assert one.status_code == 200
    assert one.json()["id"] == body["id"]

    # The instance is an entry of its own kind, with the feature for its one parent, held.
    entry = await client.get(f"/tenants/{tenant_id}/entities/{body['id']}")
    assert entry.json()["kinds"] == ["feature_instance"]
    assert [p["id"] for p in entry.json()["prototypes"]] == [str(feature)]
    assert entry.json()["parent"]["id"] == str(hero)
    await delete_tenant(tenant_id)


async def test_what_may_hold_a_feature(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Darkvision")
    bare = await _make(client, tenant_id, {"name": "Rock", "kinds": []})
    refused = await _award(client, tenant_id, uuid.UUID(bare["id"]), feature)
    assert refused.status_code == 422, refused.text
    assert (
        await client.get(f"/tenants/{tenant_id}/entities/{bare['id']}/features")
    ).status_code == 422

    # An item instance holds one, and so does a group (an entry that has members).
    async with admin_session_factory() as session:
        from lorenzo_api.models import GroupMember, ItemInstance

        sword = Entity(tenant_id=tenant_id, name="Sword")
        party = Entity(tenant_id=tenant_id, name="Party")
        session.add_all([sword, party])
        await session.flush()
        session.add(ItemInstance(entity_id=sword.id, tenant_id=tenant_id))
        member = await make_being(session, tenant_id=tenant_id, name="Member")
        session.add(
            GroupMember(
                group_entity_id=party.id, character_entity_id=member.entity_id, tenant_id=tenant_id
            )
        )
        await session.commit()
        sword_id, party_id = sword.id, party.id
    for holder in (sword_id, party_id):
        awarded = await _award(client, tenant_id, holder, feature)
        assert awarded.status_code == 201, awarded.text
        assert [h["name"] for h in await _held(client, tenant_id, holder)] == ["Darkvision"]
    not_a_feature = await _award(client, tenant_id, sword_id, uuid.UUID(bare["id"]))
    assert not_a_feature.status_code == 422
    await delete_tenant(tenant_id)


async def test_a_feature_that_is_not_repeatable_is_held_once(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    once = await _feature(client, tenant_id, "Darkvision")
    twice = await _feature(client, tenant_id, "Extra Attack", repeatable=True)
    hero = await _being(tenant_id)

    assert (await _award(client, tenant_id, hero, once)).status_code == 201
    again = await _award(client, tenant_id, hero, once)
    assert again.status_code == 409, again.text
    assert (await _award(client, tenant_id, hero, twice)).status_code == 201
    assert (await _award(client, tenant_id, hero, twice)).status_code == 201
    assert sorted(h["name"] for h in await _held(client, tenant_id, hero)) == [
        "Darkvision",
        "Extra Attack",
        "Extra Attack",
    ]
    await delete_tenant(tenant_id)


async def test_an_instance_starts_as_its_feature_says_or_as_the_award_says(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    attuned = await _feature(client, tenant_id, "Attunement", starts_inactive=True, repeatable=True)
    hero = await _being(tenant_id)

    first = await _award(client, tenant_id, hero, attuned)
    second = await _award(client, tenant_id, hero, attuned, active=True)
    assert (first.json()["active"], second.json()["active"]) == (False, True)
    await delete_tenant(tenant_id)


# --- the switch and what a formula reads ---------------------------------------


async def test_the_switch_is_read_by_a_formula_that_keeps_feature_instances(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, bonus=StatValueType.INT, total=StatValueType.INT)
    hero = await _being(tenant_id)
    rage = await _feature(client, tenant_id, "Rage")
    toughness = await _feature(client, tenant_id, "Toughness")
    await _stat_on(tenant_id, rage, sheet["bonus"], 2)
    await _stat_on(tenant_id, toughness, sheet["bonus"], 5)
    await _put(
        client,
        sheet.formula_url(hero, "total"),
        {
            "kind": "contents",
            "source_stat_definition_id": str(sheet["bonus"]),
            "only_active": True,
            "only_kind": "feature_instance",
        },
    )
    rage_instance = (await _award(client, tenant_id, hero, rage)).json()["id"]
    await _award(client, tenant_id, hero, toughness)

    async def total() -> int:
        read = await client.get(f"/tenants/{tenant_id}/entities/{hero}")
        return {s["name"]: s["value"] for s in read.json()["stats"]}["total"]  # type: ignore[no-any-return]

    assert await total() == 7
    flipped = await client.put(
        f"/tenants/{tenant_id}/features/{rage_instance}/active", json={"active": False}
    )
    assert flipped.status_code == 200, flipped.text
    assert flipped.json()["active"] is False
    assert await total() == 5
    back = await client.put(
        f"/tenants/{tenant_id}/features/{rage_instance}/active", json={"active": True}
    )
    assert back.json()["active"] is True
    assert await total() == 7
    await delete_tenant(tenant_id)


async def test_a_formula_may_keep_feature_instances_and_a_plain_sum_is_unchanged(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, bonus=StatValueType.INT, total=StatValueType.INT)
    hero = await _being(tenant_id)
    feature = await _feature(client, tenant_id, "Rage")
    await _stat_on(tenant_id, feature, sheet["bonus"], 2)
    await _award(client, tenant_id, hero, feature)
    for kind, expected in (("item_instance", 0), ("feature_instance", 2)):
        formula = await client.put(
            sheet.formula_url(hero, "total"),
            json={
                "kind": "contents",
                "source_stat_definition_id": str(sheet["bonus"]),
                "only_kind": kind,
            },
        )
        assert formula.status_code == 200, formula.text
        read = await client.get(f"/tenants/{tenant_id}/entities/{hero}")
        stats = {s["name"]: s["value"] for s in read.json()["stats"]}
        assert stats.get("total", 0) == expected, kind
    await delete_tenant(tenant_id)


# --- removal -------------------------------------------------------------------


async def test_a_feature_is_removed_from_its_holder(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Rage")
    hero = await _being(tenant_id)
    instance = (await _award(client, tenant_id, hero, feature)).json()["id"]

    removed = await client.delete(f"/tenants/{tenant_id}/features/{instance}")
    assert removed.status_code == 204, removed.text
    assert await _held(client, tenant_id, hero) == []
    assert (await client.get(f"/tenants/{tenant_id}/features/{instance}")).status_code == 404
    assert (await client.delete(f"/tenants/{tenant_id}/features/{instance}")).status_code == 404
    # The feature itself stays, and can be awarded again.
    assert (await _award(client, tenant_id, hero, feature)).status_code == 201
    await delete_tenant(tenant_id)


async def test_the_entry_delete_route_does_not_delete_an_instance_or_a_held_feature(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Rage")
    hero = await _being(tenant_id)
    instance = (await _award(client, tenant_id, hero, feature)).json()["id"]

    assert (await client.delete(f"/tenants/{tenant_id}/entities/{instance}")).status_code == 409
    assert (await client.delete(f"/tenants/{tenant_id}/entities/{feature}")).status_code == 409
    assert (
        await client.delete(f"/tenants/{tenant_id}/entities/{feature}/kinds/feature")
    ).status_code == 409
    await client.delete(f"/tenants/{tenant_id}/features/{instance}")
    assert (await client.delete(f"/tenants/{tenant_id}/entities/{feature}")).status_code == 204
    await delete_tenant(tenant_id)


async def test_what_a_holder_has_goes_with_it(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Rage", repeatable=True)
    hero = await _being(tenant_id, "Hero")
    npc = await _being(tenant_id, "Npc")
    await _award(client, tenant_id, hero, feature)
    await _award(client, tenant_id, hero, feature)
    await _award(client, tenant_id, npc, feature)

    # A being that is no character is deleted with the entry route; a permanent deletion of a
    # being goes through settle_inventory.
    deleted = await client.delete(f"/tenants/{tenant_id}/entities/{hero}")
    assert deleted.status_code == 204, deleted.text
    deleted = await client.delete(f"/tenants/{tenant_id}/beings/{npc}")
    assert deleted.status_code in (204, 200), deleted.text
    async with admin_session_factory() as session:
        left = await session.scalar(
            select(func.count())
            .select_from(FeatureInstance)
            .where(FeatureInstance.tenant_id == tenant_id)
        )
        entries = await session.scalar(
            select(func.count()).select_from(Entity).where(Entity.tenant_id == tenant_id)
        )
    assert left == 0
    assert entries == 1  # the feature
    await delete_tenant(tenant_id)


# --- what an inventory read leaves out -----------------------------------------


async def test_a_feature_instance_is_no_inventory(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Rage")
    hero = await _being(tenant_id)
    instance = (await _award(client, tenant_id, hero, feature)).json()["id"]
    # An organizer reaches every holder, so `held-by` answers for the being.
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        membership.role = MembershipRole.ORGA
        await session.commit()

    listed = await client.get(f"/tenants/{tenant_id}/item-instances")
    assert listed.status_code == 200
    assert instance not in str(listed.json())
    held_by = await client.get(f"/tenants/{tenant_id}/item-instances/held-by/{hero}")
    assert held_by.status_code == 200
    assert instance not in str(held_by.json())
    assert (await client.get(f"/tenants/{tenant_id}/item-instances/{instance}")).status_code == 404
    await delete_tenant(tenant_id)


# --- who may do what -----------------------------------------------------------


async def test_a_player_reads_and_flips_their_own_features_and_a_gm_awards_and_removes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Rage")
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
    other = await _being(tenant_id, "Stranger")
    own_instance = other_instance = None
    # The caller plays Pia; they are no longer an administrator.
    await make_plain_participant(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        player = await session.scalar(
            select(Player).where(Player.user_id == test_user_id, Player.tenant_id == tenant_id)
        )
        assert player is not None
        pia = await make_character(
            session, tenant_id=tenant_id, name="Pia", owner_player_id=player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=pia.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        for holder in (pia.entity_id, other):
            instance = Entity(tenant_id=tenant_id, name="Rage")
            session.add(instance)
            await session.flush()
            session.add(FeatureInstance(entity_id=instance.id, tenant_id=tenant_id))
            session.add(
                EntityPrototype(entity_id=instance.id, prototype_id=feature, tenant_id=tenant_id)
            )
            session.add(
                Containment(
                    child_entity_id=instance.id, parent_entity_id=holder, tenant_id=tenant_id
                )
            )
            if holder == other:
                other_instance = instance.id
            else:
                own_instance = instance.id
        await session.commit()
        pia_id = pia.entity_id
    assert campaign is not None

    # Their own list and switch.
    assert [h["name"] for h in await _held(client, tenant_id, pia_id)] == ["Rage"]
    flipped = await client.put(
        f"/tenants/{tenant_id}/features/{own_instance}/active", json={"active": False}
    )
    assert flipped.status_code == 200, flipped.text
    assert flipped.json()["active"] is False
    # Not another being's: 404 for the read, 403 for the switch the caller cannot see.
    assert (await client.get(f"/tenants/{tenant_id}/entities/{other}/features")).status_code == 404
    assert (await client.get(f"/tenants/{tenant_id}/features/{other_instance}")).status_code == 404
    assert (
        await client.put(
            f"/tenants/{tenant_id}/features/{other_instance}/active", json={"active": False}
        )
    ).status_code == 403
    # Not an award or a removal: a player is not the holder's manager.
    assert (await _award(client, tenant_id, pia_id, feature)).status_code == 403
    assert (await client.delete(f"/tenants/{tenant_id}/features/{own_instance}")).status_code == 403
    await delete_tenant(tenant_id)
