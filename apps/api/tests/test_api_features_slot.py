"""ADR 0457: the `features` slot of a template - what it must say, and the features an entry holds
as it shows them: by type, by name, a cell for each column, only what the caller may read.
"""

import uuid
from typing import Any

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
from sqlalchemy import select
from test_api_computed_stats import _sheet
from test_api_features import _award, _feature, _stat_on

from lorenzo_api.models import CharacterPlayer, Entity, Player, StatValueType


async def _template(client: AsyncClient, tenant: uuid.UUID, **body: Any) -> dict[str, Any]:
    made = await client.post(
        f"/tenants/{tenant}/templates", json={"name": "Sheet", "required_kind": "being", **body}
    )
    assert made.status_code == 201, made.text
    return made.json()  # type: ignore[no-any-return]


async def _view(
    client: AsyncClient, tenant: uuid.UUID, entry: uuid.UUID, template: str
) -> dict[str, Any]:
    response = await client.get(f"/tenants/{tenant}/entities/{entry}/templates/{template}")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def _type(client: AsyncClient, tenant: uuid.UUID, name: str) -> uuid.UUID:
    made = await client.post(f"/tenants/{tenant}/entities", json={"name": name, "kinds": []})
    assert made.status_code == 201, made.text
    return uuid.UUID(made.json()["id"])


async def test_a_features_slot_must_say_its_columns_and_has_no_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, damage=StatValueType.INT)
    url = f"/tenants/{tenant_id}/templates"
    listed = {"kind": "features", "stats": [{"stat_definition_id": str(sheet["damage"])}]}
    made = await client.post(url, json={"name": "A", "slots": [listed]})
    assert made.status_code == 201, made.text
    assert made.json()["slots"][0]["kind"] == "features"
    for bad in (
        {"kind": "features"},
        {**listed, "held_order": "name"},
        {**listed, "information_type": "note"},
        {"kind": "features", "exclude": [str(sheet["damage"])]},
    ):
        refused = await client.post(url, json={"name": "B", "slots": [bad]})
        assert refused.status_code == 422, (bad, refused.text)
    await delete_tenant(tenant_id)


async def test_the_features_an_entry_holds_are_shown_by_type_and_name_with_a_cell_for_each_column(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, damage=StatValueType.INT, uses=StatValueType.INT)
    evocation = await _type(client, tenant_id, "Evocation")
    abjuration = await _type(client, tenant_id, "Abjuration")
    fireball = await _feature(client, tenant_id, "Fireball", parents=[evocation])
    missile = await _feature(client, tenant_id, "Magic Missile", parents=[evocation])
    shield = await _feature(client, tenant_id, "Shield", parents=[abjuration])
    darkvision = await _feature(client, tenant_id, "Darkvision")
    await _stat_on(tenant_id, fireball, sheet["damage"], 8)
    await _stat_on(tenant_id, missile, sheet["damage"], 3)
    async with admin_session_factory() as session:
        hero = (await make_being(session, tenant_id=tenant_id, name="Hero")).entity_id
        await session.commit()
    instances = {}
    for name, feature in (
        ("Fireball", fireball),
        ("Magic Missile", missile),
        ("Shield", shield),
        ("Darkvision", darkvision),
    ):
        instances[name] = (await _award(client, tenant_id, hero, feature)).json()["id"]
    await _stat_on(tenant_id, uuid.UUID(instances["Fireball"]), sheet["uses"], 2)
    template = await _template(
        client,
        tenant_id,
        slots=[
            {"kind": "information", "information_type": "note"},
            {
                "kind": "features",
                "label": "Spells",
                "stats": [
                    {"stat_definition_id": str(sheet["damage"]), "label": "Dmg"},
                    {"stat_definition_id": str(sheet["uses"])},
                ],
            },
        ],
    )

    view = await _view(client, tenant_id, hero, template["id"])
    slot = view["slots"][1]
    assert (slot["kind"], slot["label"]) == ("features", "Spells")
    assert [(c["name"], c["label"]) for c in slot["columns"]] == [
        ("damage", "Dmg"),
        ("uses", "uses"),
    ]
    assert slot["rows"] is None and slot["stats"] is None
    groups = slot["feature_groups"]
    assert [(g["type"]["name"] if g["type"] else None) for g in groups] == [
        "Abjuration",
        "Evocation",
        None,
    ]
    evoked = {f["name"]: f for f in groups[1]["features"]}
    assert list(evoked) == ["Fireball", "Magic Missile"]
    assert [c["value"] for c in evoked["Fireball"]["cells"]] == [8, 2]
    assert [c["value"] for c in evoked["Magic Missile"]["cells"]] == [3, None]
    assert evoked["Fireball"]["id"] == instances["Fireball"] and evoked["Fireball"]["active"]
    assert evoked["Fireball"]["feature"]["id"] == str(fireball)
    assert [f["name"] for f in groups[2]["features"]] == ["Darkvision"]

    # A switch is shown as it is.
    off = await client.put(
        f"/tenants/{tenant_id}/features/{instances['Shield']}/active", json={"active": False}
    )
    assert off.status_code == 200
    again = (await _view(client, tenant_id, hero, template["id"]))["slots"][1]["feature_groups"]
    assert again[0]["features"][0]["active"] is False
    await delete_tenant(tenant_id)


async def test_an_entry_that_holds_nothing_shows_no_features(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, damage=StatValueType.INT)
    async with admin_session_factory() as session:
        hero = (await make_being(session, tenant_id=tenant_id, name="Hero")).entity_id
        await session.commit()
    template = await _template(
        client,
        tenant_id,
        slots=[
            {"kind": "features", "stats": [{"stat_definition_id": str(sheet["damage"])}]},
        ],
    )
    slot = (await _view(client, tenant_id, hero, template["id"]))["slots"][0]
    assert slot["feature_groups"] == []
    assert [c["name"] for c in slot["columns"]] == ["damage"]
    await delete_tenant(tenant_id)


async def test_a_player_sees_the_features_of_what_they_reach_and_not_of_another(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, damage=StatValueType.INT)
    feature = await _feature(client, tenant_id, "Darkvision")
    async with admin_session_factory() as session:
        await make_campaign(session, tenant_id=tenant_id)
        stranger = (await make_being(session, tenant_id=tenant_id, name="Stranger")).entity_id
        await session.commit()
    await _award(client, tenant_id, stranger, feature)
    template = await _template(
        client,
        tenant_id,
        slots=[{"kind": "features", "stats": [{"stat_definition_id": str(sheet["damage"])}]}],
    )
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
        instance = Entity(tenant_id=tenant_id, name="Darkvision")
        session.add(instance)
        await session.flush()
        from lorenzo_api.models import Containment, EntityPrototype, FeatureInstance

        session.add(FeatureInstance(entity_id=instance.id, tenant_id=tenant_id))
        session.add(
            EntityPrototype(entity_id=instance.id, prototype_id=feature, tenant_id=tenant_id)
        )
        session.add(
            Containment(
                child_entity_id=instance.id, parent_entity_id=pia.entity_id, tenant_id=tenant_id
            )
        )
        await session.commit()
        pia_id = pia.entity_id

    own = (await _view(client, tenant_id, pia_id, template["id"]))["slots"][0]
    assert [f["name"] for g in own["feature_groups"] for f in g["features"]] == ["Darkvision"]
    other = (await _view(client, tenant_id, stranger, template["id"]))["slots"][0]
    assert other["feature_groups"] == []
    await delete_tenant(tenant_id)
