"""GET /tenants/{t}/entities/{id}/preview (ADR 0264): the card per kind, inheritance, and that
it shows no more than the single read does."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_character, make_plain_participant
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Being,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    Information,
    Item,
    ItemInstance,
    Membership,
    MembershipRole,
    Payload,
    PayloadDescription,
    PayloadPicture,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
)

_MADE: list[uuid.UUID] = []


@pytest.fixture(autouse=True)
async def _remove_the_tenants_made() -> AsyncGenerator[None]:
    """Every test here makes a library the shared test user owns; left behind, it makes the user
    the sole owner of something and the `DELETE /me` tests that follow in the same worker answer
    409."""
    yield
    while _MADE:
        await delete_tenant(_MADE.pop())


async def _tenant(user_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()
        _MADE.append(tenant.id)
        return tenant.id


async def _text(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    text_: str,
    *,
    public: bool = True,
    type_: str = "description",
) -> None:
    info = Information(
        tenant_id=tenant_id, entity_id=entity_id, title=text_, type=type_, is_public=public
    )
    session.add(info)
    await session.flush()
    payload = Payload(tenant_id=tenant_id, information_id=info.id)
    session.add(payload)
    await session.flush()
    session.add(
        PayloadDescription(
            payload_id=payload.id, tenant_id=tenant_id, locale="en-US", content=text_
        )
    )
    await session.flush()


async def _picture(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID, *, public: bool = True
) -> uuid.UUID:
    info = Information(
        tenant_id=tenant_id,
        entity_id=entity_id,
        title="Picture",
        type="main_picture",
        is_public=public,
    )
    session.add(info)
    await session.flush()
    payload = Payload(tenant_id=tenant_id, information_id=info.id)
    session.add(payload)
    await session.flush()
    session.add(
        PayloadPicture(
            payload_id=payload.id, tenant_id=tenant_id, data=b"\x89PNG", file_type="image/png"
        )
    )
    await session.flush()
    return payload.id


async def _stats(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID, **values: int
) -> None:
    """Gives the entry these stats, creating each definition (named once per library) in a
    group of its own the first time it is asked for."""
    for name, value in values.items():
        definition = await session.scalar(
            select(StatDefinition).where(
                StatDefinition.tenant_id == tenant_id, StatDefinition.name == name
            )
        )
        if definition is None:
            group = StatGroup(tenant_id=tenant_id, name=f"group-{name}")
            session.add(group)
            await session.flush()
            definition = StatDefinition(
                tenant_id=tenant_id,
                stat_group_id=group.id,
                name=name,
                value_type=StatValueType.INT,
            )
            session.add(definition)
            await session.flush()
        session.add(
            EntityStatGroup(
                entity_id=entity_id, stat_group_id=definition.stat_group_id, tenant_id=tenant_id
            )
        )
        session.add(
            EntityStat(
                entity_id=entity_id,
                stat_definition_id=definition.id,
                tenant_id=tenant_id,
                value_int=value,
            )
        )
    await session.flush()


async def test_an_item_card_has_the_templates_stats_the_picture_and_the_excerpt(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        sword = Entity(tenant_id=tenant_id, name="Longsword")
        session.add(sword)
        await session.flush()
        session.add_all(
            [
                Item(entity_id=sword.id, tenant_id=tenant_id),
                EntitySlug(entity_id=sword.id, tenant_id=tenant_id, slug="longsword"),
            ]
        )
        await _stats(session, tenant_id, sword.id, weight=3, price=15, hp=9)
        await _text(session, tenant_id, sword.id, "A **sharp** blade. " + "More. " * 100)
        payload_id = await _picture(session, tenant_id, sword.id)
        await session.commit()
        sword_id = sword.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{sword_id}/preview")
    assert response.status_code == 200, response.text
    card = response.json()
    assert card["entity_id"] == str(sword_id)
    assert (card["name"], card["slug"], card["kinds"]) == ("Longsword", "longsword", ["item"])
    assert card["template"] == "item"
    # hp is not on an item card; weight and price are, in the template's order.
    assert card["stats"] == [{"name": "weight", "value": 3}, {"name": "price", "value": 15}]
    assert card["excerpt"].startswith("A sharp blade. More.")
    assert card["excerpt"].endswith("…") and len(card["excerpt"]) <= 201
    assert card["picture_url"].endswith(f"/tenants/{tenant_id}/payloads/{payload_id}/content")
    assert (await client.get(card["picture_url"])).status_code == 200


async def test_an_instance_shows_what_it_inherits_and_a_being_has_its_own_template(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        sword = Entity(tenant_id=tenant_id, name="Longsword")
        blade = Entity(tenant_id=tenant_id, name="Aldra's blade")
        session.add_all([sword, blade])
        await session.flush()
        session.add_all(
            [
                Item(entity_id=sword.id, tenant_id=tenant_id),
                ItemInstance(entity_id=blade.id, tenant_id=tenant_id),
                EntityPrototype(entity_id=blade.id, prototype_id=sword.id, tenant_id=tenant_id),
            ]
        )
        await _stats(session, tenant_id, sword.id, weight=3)
        await _text(session, tenant_id, sword.id, "From the catalog.")
        await _picture(session, tenant_id, sword.id)
        being = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(being)
        await session.flush()
        session.add(Being(entity_id=being.id, tenant_id=tenant_id))
        await _stats(session, tenant_id, being.id, hp=30, weight=90)
        await session.commit()
        blade_id, being_id = blade.id, being.id

    card = (await client.get(f"/tenants/{tenant_id}/entities/{blade_id}/preview")).json()
    assert card["template"] == "item_instance"
    assert card["kinds"] == ["item_instance"]
    assert card["stats"] == [{"name": "weight", "value": 3}]
    assert card["excerpt"] == "From the catalog."
    assert card["picture_url"] is not None

    card = (await client.get(f"/tenants/{tenant_id}/entities/{being_id}/preview")).json()
    assert card["template"] == "being"
    assert card["stats"] == [{"name": "hp", "value": 30}]


async def test_a_bare_entry_gets_the_fallback_card(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        group = Entity(tenant_id=tenant_id, name="Weapons")
        session.add(group)
        await session.flush()
        await _stats(session, tenant_id, group.id, weight=3)
        await session.commit()
        group_id = group.id

    card = (await client.get(f"/tenants/{tenant_id}/entities/{group_id}/preview")).json()
    assert card == {
        "entity_id": str(group_id),
        "name": "Weapons",
        "slug": None,
        "kinds": [],
        "template": "entry",
        "picture_url": None,
        "stats": [],
        "excerpt": "",
    }


async def test_a_character_card_does_not_inherit(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        parent = Entity(tenant_id=tenant_id, name="Template")
        session.add(parent)
        await session.flush()
        await _text(session, tenant_id, parent.id, "Parent text.")
        character = await make_character(session, tenant_id=tenant_id, name="Aldra")
        session.add(
            EntityPrototype(
                entity_id=character.entity_id, prototype_id=parent.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id = character.entity_id

    card = (await client.get(f"/tenants/{tenant_id}/entities/{character_id}/preview")).json()
    assert (card["template"], card["kinds"]) == ("character", ["being", "character"])
    assert card["excerpt"] == ""


async def test_a_plain_participant_does_not_get_gm_only_text_or_picture(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        vault = Entity(tenant_id=tenant_id, name="Vault")
        session.add(vault)
        await session.flush()
        session.add(Item(entity_id=vault.id, tenant_id=tenant_id))
        await _text(session, tenant_id, vault.id, "GM secret first.", public=False)
        catalog = Entity(tenant_id=tenant_id, name="Catalog")
        session.add(catalog)
        await session.flush()
        await _text(session, tenant_id, catalog.id, "Public catalog text.")
        session.add(
            EntityPrototype(entity_id=vault.id, prototype_id=catalog.id, tenant_id=tenant_id)
        )
        await _picture(session, tenant_id, vault.id, public=False)
        await session.commit()
        vault_id = vault.id

    url = f"/tenants/{tenant_id}/entities/{vault_id}/preview"
    owner = (await client.get(url)).json()
    assert owner["excerpt"] == "GM secret first."
    assert owner["picture_url"] is not None

    await make_plain_participant(tenant_id, test_user_id)
    plain = (await client.get(url)).json()
    assert plain["excerpt"] == "Public catalog text."
    assert plain["picture_url"] is None
    assert "secret" not in str(plain)


async def test_a_missing_entry_and_a_stranger_get_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    other = uuid.uuid4()
    assert (await client.get(f"/tenants/{tenant_id}/entities/{other}/preview")).status_code == 404
    elsewhere = uuid.uuid4()
    assert (await client.get(f"/tenants/{elsewhere}/entities/{other}/preview")).status_code == 404


async def test_a_location_and_a_map_get_their_own_cards(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    from lorenzo_api.models import EntityAudience, Location, Map

    tenant_id = await _tenant(test_user_id)
    system = {"format": "lorenzo.map-system/1", "kind": "plane", "extent": [0, 0, 10, 10]}
    async with admin_session_factory() as session:
        realm = Entity(tenant_id=tenant_id, name="Realm")
        port = Entity(tenant_id=tenant_id, name="Free port")
        chart = Entity(tenant_id=tenant_id, name="Coast chart")
        crew = Entity(tenant_id=tenant_id, name="Ship")
        session.add_all([realm, port, chart, crew])
        await session.flush()
        session.add_all(
            [
                Location(entity_id=realm.id, tenant_id=tenant_id),
                Location(entity_id=port.id, tenant_id=tenant_id),
                Map(entity_id=chart.id, tenant_id=tenant_id, system=system),
                Location(entity_id=crew.id, tenant_id=tenant_id),
                Being(entity_id=crew.id, tenant_id=tenant_id),
                EntityAudience(entity_id=port.id, tenant_id=tenant_id, is_public=False),
            ]
        )
        await session.flush()
        session.add(EntityPrototype(entity_id=port.id, prototype_id=realm.id, tenant_id=tenant_id))
        await _text(session, tenant_id, realm.id, "A wide **realm** of harbours.")
        await _text(session, tenant_id, chart.id, "The coast as the pilots draw it.")
        await _picture(session, tenant_id, realm.id)
        await session.commit()
        ids = {"realm": realm.id, "port": port.id, "chart": chart.id, "crew": crew.id}

    def url(name: str) -> str:
        return f"/tenants/{tenant_id}/entities/{ids[name]}/preview"

    card = (await client.get(url("realm"))).json()
    assert card["template"] == "location" and card["kinds"] == ["location"]
    assert card["stats"] == [] and card["excerpt"] == "A wide realm of harbours."
    assert card["picture_url"] is not None
    # A part of it with no description of its own shows what it inherits.
    inherited = (await client.get(url("port"))).json()
    assert inherited["template"] == "location"
    assert inherited["excerpt"] == "A wide realm of harbours."
    assert inherited["picture_url"] is not None
    chart_card = (await client.get(url("chart"))).json()
    assert chart_card["template"] == "map" and chart_card["kinds"] == ["map"]
    assert chart_card["excerpt"] == "The coast as the pilots draw it."
    assert chart_card["stats"] == [] and "system" not in chart_card
    assert (await client.get(url("crew"))).json()["template"] == "being"

    # A reader who may not see the restricted place has no card for it, and none says it exists.
    await make_plain_participant(tenant_id, test_user_id)
    missing = await client.get(f"/tenants/{tenant_id}/entities/{uuid.uuid4()}/preview")
    hidden = await client.get(url("port"))
    assert hidden.status_code == missing.status_code == 404
    assert (await client.get(url("realm"))).status_code == 200
