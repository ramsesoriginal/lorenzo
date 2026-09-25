"""Inheritance made visible (ADR 0111): items show their prototypes'
descriptions and pictures, labelled, and entity stats say whether they're
the entity's own."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_plain_participant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    Entity,
    EntityPrototype,
    EntityStat,
    Information,
    Item,
    ItemInstance,
    Payload,
    PayloadDescription,
    PayloadPicture,
    StatDefinition,
    StatGroup,
    StatValueType,
)


async def _item(
    tenant_id: uuid.UUID,
    name: str,
    *,
    prototypes: tuple[uuid.UUID, ...] = (),
    description: str | None = None,
    public: bool = True,
    picture: bool = False,
    instance: bool = False,
) -> uuid.UUID:
    """A catalog item, or an instance, with an optional description and picture."""
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        kind = ItemInstance if instance else Item
        session.add(kind(entity_id=entity.id, tenant_id=tenant_id))
        for prototype_id in prototypes:
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=prototype_id, tenant_id=tenant_id)
            )
        if description is not None or picture:
            info = Information(
                tenant_id=tenant_id,
                entity_id=entity.id,
                title=f"{name} title",
                type="description",
                is_public=public,
            )
            session.add(info)
            await session.flush()
            if description is not None:
                payload = Payload(tenant_id=tenant_id, information_id=info.id)
                session.add(payload)
                await session.flush()
                session.add(
                    PayloadDescription(
                        payload_id=payload.id,
                        tenant_id=tenant_id,
                        locale="en-GB",
                        content=description,
                    )
                )
            if picture:
                payload = Payload(tenant_id=tenant_id, information_id=info.id)
                session.add(payload)
                await session.flush()
                session.add(
                    PayloadPicture(
                        payload_id=payload.id,
                        tenant_id=tenant_id,
                        data=b"\x89PNG",
                        file_type="image/png",
                    )
                )
        await session.commit()
        return entity.id


def _described(body: dict[str, Any]) -> list[tuple[str, str | None]]:
    """(content, the name it's inherited from) for each description."""
    return [
        (d["content"], d["from_entity"]["name"] if d["from_entity"] else None)
        for d in body["descriptions"]
    ]


async def test_an_instance_shows_its_prototypes_descriptions_nearest_first(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weapon = await _item(tenant_id, "Weapon", description="Made for harm.")
    longsword = await _item(
        tenant_id, "Longsword", prototypes=(weapon,), description="A long blade."
    )
    ashfang = await _item(
        tenant_id, "Ashfang", prototypes=(longsword,), description="It hums.", instance=True
    )

    body = (await client.get(f"/tenants/{tenant_id}/item-instances/{ashfang}")).json()

    assert _described(body) == [
        ("It hums.", None),
        ("A long blade.", "Longsword"),
        ("Made for harm.", "Weapon"),
    ]
    assert body["descriptions"][1]["from_entity"]["id"] == str(longsword)
    assert body["title"] == "Ashfang title"  # its own, never an ancestor's
    await delete_tenant(tenant_id)


async def test_ancestors_count_once_at_their_nearest_and_equal_ones_by_name(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    base = await _item(tenant_id, "Base", description="base")
    beta = await _item(tenant_id, "Beta", prototypes=(base,), description="beta")
    alpha = await _item(tenant_id, "Alpha", prototypes=(base,), description="alpha")
    # Base is two hops away through both parents, and one hop away directly.
    diamond = await _item(tenant_id, "Diamond", prototypes=(beta, alpha))
    close = await _item(tenant_id, "Close", prototypes=(beta, alpha, base))

    diamond_body = (await client.get(f"/tenants/{tenant_id}/items/{diamond}")).json()
    close_body = (await client.get(f"/tenants/{tenant_id}/items/{close}")).json()

    assert _described(diamond_body) == [
        ("alpha", "Alpha"),
        ("beta", "Beta"),
        ("base", "Base"),
    ]
    assert _described(close_body) == [
        ("alpha", "Alpha"),
        ("base", "Base"),
        ("beta", "Beta"),
    ]
    assert diamond_body["title"] == "Diamond"  # no own description: its own name
    await delete_tenant(tenant_id)


async def test_an_inherited_description_passes_the_readers_visibility_check(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    longsword = await _item(tenant_id, "Longsword", description="Secretly cursed.", public=False)
    ashfang = await _item(tenant_id, "Ashfang", prototypes=(longsword,), instance=True)
    url = f"/tenants/{tenant_id}/item-instances/{ashfang}"

    assert _described((await client.get(url)).json()) == [("Secretly cursed.", "Longsword")]
    await make_plain_participant(tenant_id, test_user_id)
    assert _described((await client.get(url)).json()) == []
    await delete_tenant(tenant_id)


async def test_pictures_inherit_labelled_like_descriptions(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    longsword = await _item(tenant_id, "Longsword", picture=True)
    ashfang = await _item(
        tenant_id, "Ashfang", prototypes=(longsword,), picture=True, instance=True
    )

    pictures = (await client.get(f"/tenants/{tenant_id}/item-instances/{ashfang}")).json()[
        "pictures"
    ]

    assert [p["from_entity"]["name"] if p["from_entity"] else None for p in pictures] == [
        None,
        "Longsword",
    ]
    assert (await client.get(pictures[1]["url"])).content == b"\x89PNG"
    await delete_tenant(tenant_id)


async def test_lists_inherit_too(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    weapon = await _item(tenant_id, "Weapon", description="Made for harm.")
    longsword = await _item(tenant_id, "Longsword", prototypes=(weapon,))
    await _item(tenant_id, "Ashfang", prototypes=(longsword,), instance=True)

    items = (await client.get(f"/tenants/{tenant_id}/items", params={"q": "Longsword"})).json()
    instances = (await client.get(f"/tenants/{tenant_id}/item-instances")).json()

    assert [_described(item) for item in items["items"]] == [[("Made for harm.", "Weapon")]]
    assert [_described(item) for item in instances["items"]] == [[("Made for harm.", "Weapon")]]
    await delete_tenant(tenant_id)


async def test_a_stat_says_whether_it_is_the_entitys_own(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    longsword = await _item(tenant_id, "Longsword")
    ashfang = await _item(tenant_id, "Ashfang", prototypes=(longsword,), instance=True)
    async with admin_session_factory() as session:
        tags = StatGroup(tenant_id=tenant_id, name="tags")
        session.add(tags)
        await session.flush()
        magical = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=tags.id,
            name="is_magical",
            value_type=StatValueType.BOOL,
        )
        session.add(magical)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=longsword,
                stat_definition_id=magical.id,
                tenant_id=tenant_id,
                value_bool=True,
            )
        )
        await session.commit()
        magical_id = magical.id
    url = f"/tenants/{tenant_id}/entities/{ashfang}"

    inherited = (await client.get(url)).json()["stats"]
    off = await client.patch(f"{url}/tags/{magical_id}")
    back = await client.delete(f"{url}/tags/{magical_id}")

    assert inherited == [{"name": "is_magical", "value": True, "own": False}]
    assert off.json()["stats"] == [{"name": "is_magical", "value": False, "own": True}]
    assert back.json()["stats"] == [{"name": "is_magical", "value": True, "own": False}]
    await delete_tenant(tenant_id)
