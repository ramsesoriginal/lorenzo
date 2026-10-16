"""GET /tenants/{t}/entities/export (ADR 0262, RFC 0039 W3): the shape of an entry, the cursor
pages, the ETag and its 304, the gzip, the filtering of information to what the caller may read,
and a test for every kind of write the revision has to follow."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_character, make_plain_participant
from httpx import AsyncClient, Response
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Being,
    CharacterPlayer,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    Information,
    Item,
    ItemInstance,
    Knowledge,
    Membership,
    MembershipRole,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    Player,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
)


async def _tenant(user_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()
        return tenant.id


async def _entity(tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


async def _export_all(client: AsyncClient, tenant_id: uuid.UUID, **params: Any) -> list[Any]:
    items: list[Any] = []
    cursor: str | None = None
    while True:
        query = {**params, **({"cursor": cursor} if cursor else {})}
        response = await client.get(f"/tenants/{tenant_id}/entities/export", params=query)
        assert response.status_code == 200, response.text
        body = response.json()
        items.extend(body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            return items


async def _etag(client: AsyncClient, tenant_id: uuid.UUID) -> str:
    response = await client.get(f"/tenants/{tenant_id}/entities/export", params={"limit": 1})
    assert response.status_code == 200
    return response.headers["ETag"]


async def _plain_description(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    *,
    public: bool,
    text_: str,
    type_: str = "description",
) -> Information:
    info = Information(
        tenant_id=tenant_id,
        entity_id=entity_id,
        title=text_,
        type=type_,
        is_public=public,
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
    return info


async def test_an_entry_is_exported_with_what_a_mirror_is_written_back_from(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        parent = Entity(tenant_id=tenant_id, name="Weapon")
        sword = Entity(tenant_id=tenant_id, name="Sword")
        session.add_all([parent, sword])
        await session.flush()
        session.add_all(
            [
                Item(entity_id=sword.id, tenant_id=tenant_id),
                EntitySlug(entity_id=sword.id, tenant_id=tenant_id, slug="sword"),
                EntityPrototype(entity_id=sword.id, prototype_id=parent.id, tenant_id=tenant_id),
            ]
        )
        group = StatGroup(tenant_id=tenant_id, name="physical")
        session.add(group)
        await session.flush()
        weight = StatDefinition(
            tenant_id=tenant_id, stat_group_id=group.id, name="weight", value_type=StatValueType.INT
        )
        magical = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=group.id,
            name="magical",
            value_type=StatValueType.BOOL,
        )
        session.add_all([weight, magical])
        await session.flush()
        session.add_all(
            [
                EntityStatGroup(entity_id=sword.id, stat_group_id=group.id, tenant_id=tenant_id),
                EntityStat(
                    entity_id=sword.id,
                    stat_definition_id=weight.id,
                    tenant_id=tenant_id,
                    value_int=3,
                ),
                EntityStat(
                    entity_id=sword.id,
                    stat_definition_id=magical.id,
                    tenant_id=tenant_id,
                    value_bool=True,
                ),
            ]
        )
        info = await _plain_description(session, tenant_id, sword.id, public=True, text_="Sharp")
        picture_info = Information(
            tenant_id=tenant_id,
            entity_id=sword.id,
            title="Main picture",
            type="main_picture",
            is_public=True,
        )
        session.add(picture_info)
        await session.flush()
        picture = Payload(tenant_id=tenant_id, information_id=picture_info.id)
        session.add(picture)
        await session.flush()
        session.add(
            PayloadPicture(
                payload_id=picture.id,
                tenant_id=tenant_id,
                data=b"\x89PNG" * 100,
                file_type="image/png",
            )
        )
        await session.commit()
        ids = (parent.id, sword.id, group.id, weight.id, magical.id, info.id, picture.id)
    parent_id, sword_id, group_id, weight_id, magical_id, info_id, picture_id = ids

    response = await client.get(f"/tenants/{tenant_id}/entities/export")
    assert response.status_code == 200
    page = response.json()
    assert page["next_cursor"] is None
    assert response.headers["ETag"] == f'W/"{page["revision"]}"'
    by_id = {item["id"]: item for item in page["items"]}
    assert by_id[str(parent_id)]["kinds"] == []
    assert by_id[str(parent_id)]["slug"] is None
    exported = by_id[str(sword_id)]
    assert exported["name"] == "Sword"
    assert exported["slug"] == "sword"
    assert exported["kinds"] == ["item"]
    assert exported["parent_ids"] == [str(parent_id)]
    assert exported["stat_group_ids"] == [str(group_id)]
    assert {s["stat_definition_id"]: s["value"] for s in exported["stats"]} == {
        str(weight_id): 3,
        str(magical_id): True,
    }
    assert exported["stats"][0]["updated_at"]
    assert exported["updated_at"] and exported["created_at"]
    information = {i["type"]: i for i in exported["information"]}
    assert information["description"]["id"] == str(info_id)
    assert information["description"]["payloads"][0]["content"] == "Sharp"
    [picture_payload] = information["main_picture"]["payloads"]
    assert picture_payload["id"] == str(picture_id)
    assert picture_payload["kind"] == "picture"
    assert picture_payload["file_type"] == "image/png"
    assert picture_payload["url"].endswith(f"/payloads/{picture_id}/content")
    assert "data" not in picture_payload

    await delete_tenant(tenant_id)


async def test_the_export_is_the_same_entry_the_single_read_gives(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Thing")
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        info = await _plain_description(session, tenant_id, entity.id, public=True, text_="Text")
        number = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(number)
        await session.flush()
        session.add(PayloadNumber(payload_id=number.id, tenant_id=tenant_id, value=Decimal("4.5")))
        document = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(document)
        await session.flush()
        session.add(
            PayloadDocument(
                payload_id=document.id,
                tenant_id=tenant_id,
                data=b"%PDF",
                filename="a.pdf",
                file_type="application/pdf",
            )
        )
        await session.commit()
        entity_id = entity.id

    [exported] = await _export_all(client, tenant_id)
    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")).json()
    assert exported["information"] == detail["information"]
    assert exported["updated_at"] == detail["updated_at"]
    assert exported["kinds"] == detail["kinds"]

    await delete_tenant(tenant_id)


async def test_pages_follow_a_cursor_in_id_order_and_cover_every_entry_once(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    for n in range(5):
        await _entity(tenant_id, f"Entry {n}")

    url = f"/tenants/{tenant_id}/entities/export"
    first = await client.get(url, params={"limit": 2})
    second = await client.get(url, params={"limit": 2, "cursor": first.json()["next_cursor"]})
    third = await client.get(url, params={"limit": 2, "cursor": second.json()["next_cursor"]})
    assert [len(p.json()["items"]) for p in (first, second, third)] == [2, 2, 1]
    assert third.json()["next_cursor"] is None
    ids = [i["id"] for p in (first, second, third) for i in p.json()["items"]]
    assert ids == sorted(ids) and len(set(ids)) == 5
    # One export, one token.
    assert first.headers["ETag"] == second.headers["ETag"] == third.headers["ETag"]
    # A page that ends exactly at the end has no cursor either.
    assert (await client.get(url, params={"limit": 5})).json()["next_cursor"] is None

    await delete_tenant(tenant_id)


async def test_a_bad_cursor_is_422_and_a_limit_out_of_range_is_422(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    url = f"/tenants/{tenant_id}/entities/export"
    assert (await client.get(url, params={"cursor": "not-a-cursor"})).status_code == 422
    assert (await client.get(url, params={"limit": 0})).status_code == 422
    assert (await client.get(url, params={"limit": 501})).status_code == 422
    await delete_tenant(tenant_id)


async def test_a_cursor_of_an_export_that_changed_is_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    for n in range(3):
        await _entity(tenant_id, f"Entry {n}")
    url = f"/tenants/{tenant_id}/entities/export"
    cursor = (await client.get(url, params={"limit": 1})).json()["next_cursor"]
    await _entity(tenant_id, "Late")

    response = await client.get(url, params={"cursor": cursor})
    assert response.status_code == 409
    # Starting again works.
    assert len(await _export_all(client, tenant_id)) == 4

    await delete_tenant(tenant_id)


async def test_if_none_match_with_the_current_etag_is_304_and_a_stale_one_is_200(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entity(tenant_id, "One")
    url = f"/tenants/{tenant_id}/entities/export"
    etag = await _etag(client, tenant_id)

    not_modified = await client.get(url, headers={"If-None-Match": etag})
    assert not_modified.status_code == 304
    assert not_modified.headers["ETag"] == etag
    assert not_modified.content == b""
    # Among several, and the strong spelling of the same token.
    assert (
        await client.get(url, headers={"If-None-Match": f'"x", {etag.removeprefix("W/")}'})
    ).status_code == 304
    assert (await client.get(url, headers={"If-None-Match": "*"})).status_code == 304

    await _entity(tenant_id, "Two")
    fresh = await client.get(url, headers={"If-None-Match": etag})
    assert fresh.status_code == 200
    assert fresh.headers["ETag"] != etag

    await delete_tenant(tenant_id)


async def test_if_none_match_is_not_read_on_a_later_page(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    for n in range(3):
        await _entity(tenant_id, f"Entry {n}")
    url = f"/tenants/{tenant_id}/entities/export"
    first = await client.get(url, params={"limit": 1})
    second = await client.get(
        url,
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
        headers={"If-None-Match": first.headers["ETag"]},
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) == 1
    await delete_tenant(tenant_id)


async def test_the_export_is_gzipped_when_asked_and_not_when_not(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        session.add_all([Entity(tenant_id=tenant_id, name=f"Entry {n}") for n in range(40)])
        await session.commit()
    url = f"/tenants/{tenant_id}/entities/export"

    zipped = await client.get(url, headers={"Accept-Encoding": "gzip"})
    assert zipped.headers["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in zipped.headers["Vary"]
    assert len(zipped.json()["items"]) == 40  # httpx has decoded it

    plain = await client.get(url, headers={"Accept-Encoding": "identity"})
    assert "Content-Encoding" not in plain.headers
    assert plain.json() == zipped.json()
    # The ETag does not depend on the encoding.
    assert plain.headers["ETag"] == zipped.headers["ETag"]
    # Other responses are left as they are.
    listing = await client.get(
        f"/tenants/{tenant_id}/entities", headers={"Accept-Encoding": "gzip"}
    )
    assert "Content-Encoding" not in listing.headers

    await delete_tenant(tenant_id)


async def test_information_is_filtered_like_the_single_read_for_a_plain_participant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Vault")
        session.add(entity)
        await session.flush()
        await _plain_description(
            session, tenant_id, entity.id, public=True, text_="Public", type_="note"
        )
        await _plain_description(
            session, tenant_id, entity.id, public=False, text_="GM only", type_="note"
        )
        known = await _plain_description(
            session, tenant_id, entity.id, public=False, text_="Known", type_="note"
        )
        await session.commit()
        entity_id, known_id = entity.id, known.id

    # The owner reads everything.
    as_owner = {e["name"]: e for e in await _export_all(client, tenant_id)}["Vault"]
    assert [i["title"] for i in as_owner["information"]] == ["Public", "GM only", "Known"]
    owner_etag = await _etag(client, tenant_id)

    await make_plain_participant(tenant_id, test_user_id)
    as_plain = {e["name"]: e for e in await _export_all(client, tenant_id)}["Vault"]
    assert [i["title"] for i in as_plain["information"]] == ["Public"]
    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")).json()
    assert as_plain["information"] == detail["information"]
    # Who reads differently has a different ETag, so one's 304 is never the other's.
    plain_etag = await _etag(client, tenant_id)
    assert plain_etag != owner_etag
    plain_revision = plain_etag

    # A character the player controls, who knows one of the restricted rows.
    async with admin_session_factory() as session:
        player = await session.scalar(
            select(Player).where(Player.tenant_id == tenant_id, Player.user_id == test_user_id)
        )
        assert player is not None
        character = await make_character(session, tenant_id=tenant_id, name="Hero")
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id,
                player_id=player.id,
                tenant_id=tenant_id,
            )
        )
        session.add(
            Knowledge(
                tenant_id=tenant_id, information_id=known_id, knower_entity_id=character.entity_id
            )
        )
        await session.commit()
    exported = {e["name"]: e for e in await _export_all(client, tenant_id)}
    assert [i["title"] for i in exported["Vault"]["information"]] == ["Public", "Known"]
    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")).json()
    assert exported["Vault"]["information"] == detail["information"]
    assert await _etag(client, tenant_id) != plain_revision

    await delete_tenant(tenant_id)


async def test_a_stranger_cannot_export(client: AsyncClient) -> None:
    other = uuid.uuid4()
    assert (await client.get(f"/tenants/{other}/entities/export")).status_code == 404


async def test_another_tenants_entries_are_not_exported(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine = await _tenant(test_user_id)
    theirs = await _tenant(test_user_id)
    await _entity(mine, "Mine")
    await _entity(theirs, "Theirs")
    assert [e["name"] for e in await _export_all(client, mine)] == ["Mine"]
    await delete_tenant(mine)
    await delete_tenant(theirs)


# --- the revision moves on every kind of write -----------------------------------------------


class World:
    """A tenant with one entry of every shape a write below needs, ids kept for the writes."""

    tenant_id: uuid.UUID
    entity_id: uuid.UUID
    other_id: uuid.UUID
    third_id: uuid.UUID
    group_id: uuid.UUID
    definition_id: uuid.UUID
    information_id: uuid.UUID
    description_id: uuid.UUID
    number_id: uuid.UUID
    picture_id: uuid.UUID
    document_id: uuid.UUID
    knowledge_id: uuid.UUID


async def _world(user_id: uuid.UUID) -> World:
    world = World()
    world.tenant_id = tenant_id = await _tenant(user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Entry")
        other = Entity(tenant_id=tenant_id, name="Other")
        third = Entity(tenant_id=tenant_id, name="Third")
        session.add_all([entity, other, third])
        await session.flush()
        session.add_all(
            [
                Item(entity_id=entity.id, tenant_id=tenant_id),
                EntitySlug(entity_id=entity.id, tenant_id=tenant_id, slug="entry"),
                EntityPrototype(entity_id=entity.id, prototype_id=other.id, tenant_id=tenant_id),
            ]
        )
        group = StatGroup(tenant_id=tenant_id, name="group")
        session.add(group)
        await session.flush()
        definition = StatDefinition(
            tenant_id=tenant_id, stat_group_id=group.id, name="weight", value_type=StatValueType.INT
        )
        session.add(definition)
        await session.flush()
        session.add_all(
            [
                EntityStat(
                    entity_id=entity.id,
                    stat_definition_id=definition.id,
                    tenant_id=tenant_id,
                    value_int=1,
                ),
                EntityStatGroup(entity_id=entity.id, stat_group_id=group.id, tenant_id=tenant_id),
            ]
        )
        info = await _plain_description(session, tenant_id, entity.id, public=False, text_="Text")
        description = await session.scalar(select(Payload).where(Payload.information_id == info.id))
        assert description is not None
        number = Payload(tenant_id=tenant_id, information_id=info.id)
        picture = Payload(tenant_id=tenant_id, information_id=info.id)
        document = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add_all([number, picture, document])
        await session.flush()
        session.add_all(
            [
                PayloadNumber(payload_id=number.id, tenant_id=tenant_id, value=Decimal(1)),
                PayloadPicture(
                    payload_id=picture.id, tenant_id=tenant_id, data=b"a", file_type="image/png"
                ),
                PayloadDocument(
                    payload_id=document.id,
                    tenant_id=tenant_id,
                    data=b"a",
                    filename="a.txt",
                    file_type="text/plain",
                ),
            ]
        )
        knowledge = Knowledge(
            tenant_id=tenant_id, information_id=info.id, knower_entity_id=other.id
        )
        session.add(knowledge)
        await session.commit()
        world.entity_id, world.other_id, world.third_id = entity.id, other.id, third.id
        world.group_id, world.definition_id = group.id, definition.id
        world.information_id, world.description_id = info.id, description.id
        world.number_id, world.picture_id, world.document_id = number.id, picture.id, document.id
        world.knowledge_id = knowledge.id
    return world


Write = Callable[[AsyncSession, World], Awaitable[None]]


async def _new_entity(s: AsyncSession, w: World) -> None:
    s.add(Entity(tenant_id=w.tenant_id, name="New"))


async def _rename(s: AsyncSession, w: World) -> None:
    await s.execute(update(Entity).where(Entity.id == w.entity_id).values(name="Renamed"))


async def _delete_entity(s: AsyncSession, w: World) -> None:
    await s.execute(delete(Entity).where(Entity.id == w.other_id))


async def _add_kind(s: AsyncSession, w: World) -> None:
    s.add(ItemInstance(entity_id=w.entity_id, tenant_id=w.tenant_id))


async def _add_being_kind(s: AsyncSession, w: World) -> None:
    s.add(Being(entity_id=w.other_id, tenant_id=w.tenant_id))


async def _drop_kind(s: AsyncSession, w: World) -> None:
    await s.execute(delete(Item).where(Item.entity_id == w.entity_id))


async def _set_kind_column(s: AsyncSession, w: World) -> None:
    await s.execute(
        update(Item).where(Item.entity_id == w.entity_id).values(in_public_catalog=True)
    )


async def _new_slug(s: AsyncSession, w: World) -> None:
    s.add(EntitySlug(entity_id=w.other_id, tenant_id=w.tenant_id, slug="other"))


async def _change_slug(s: AsyncSession, w: World) -> None:
    await s.execute(
        update(EntitySlug).where(EntitySlug.entity_id == w.entity_id).values(slug="changed")
    )


async def _drop_slug(s: AsyncSession, w: World) -> None:
    await s.execute(delete(EntitySlug).where(EntitySlug.entity_id == w.entity_id))


async def _add_parent(s: AsyncSession, w: World) -> None:
    s.add(EntityPrototype(entity_id=w.third_id, prototype_id=w.entity_id, tenant_id=w.tenant_id))


async def _drop_parent(s: AsyncSession, w: World) -> None:
    await s.execute(delete(EntityPrototype).where(EntityPrototype.entity_id == w.entity_id))


async def _stat_inserted(s: AsyncSession, w: World) -> None:
    s.add(
        EntityStat(
            entity_id=w.other_id,
            stat_definition_id=w.definition_id,
            tenant_id=w.tenant_id,
            value_int=2,
        )
    )


async def _stat_changed(s: AsyncSession, w: World) -> None:
    await s.execute(
        update(EntityStat).where(EntityStat.entity_id == w.entity_id).values(value_int=9)
    )


async def _stat_cleared(s: AsyncSession, w: World) -> None:
    await s.execute(delete(EntityStat).where(EntityStat.entity_id == w.entity_id))


async def _group_added(s: AsyncSession, w: World) -> None:
    s.add(EntityStatGroup(entity_id=w.other_id, stat_group_id=w.group_id, tenant_id=w.tenant_id))


async def _group_removed(s: AsyncSession, w: World) -> None:
    await s.execute(delete(EntityStatGroup).where(EntityStatGroup.entity_id == w.entity_id))


async def _information_added(s: AsyncSession, w: World) -> None:
    await _plain_description(s, w.tenant_id, w.other_id, public=True, text_="New")


async def _information_changed(s: AsyncSession, w: World) -> None:
    await s.execute(update(Information).where(Information.id == w.information_id).values(title="T"))


async def _information_removed(s: AsyncSession, w: World) -> None:
    await s.execute(delete(Information).where(Information.id == w.information_id))


async def _text_edited(s: AsyncSession, w: World) -> None:
    await s.execute(
        update(PayloadDescription)
        .where(PayloadDescription.payload_id == w.description_id)
        .values(content="Edited")
    )


async def _number_edited(s: AsyncSession, w: World) -> None:
    await s.execute(
        update(PayloadNumber).where(PayloadNumber.payload_id == w.number_id).values(value=2)
    )


async def _picture_replaced(s: AsyncSession, w: World) -> None:
    await s.execute(
        update(PayloadPicture).where(PayloadPicture.payload_id == w.picture_id).values(data=b"bb")
    )


async def _document_replaced(s: AsyncSession, w: World) -> None:
    await s.execute(
        update(PayloadDocument)
        .where(PayloadDocument.payload_id == w.document_id)
        .values(data=b"bb")
    )


async def _payload_added(s: AsyncSession, w: World) -> None:
    payload = Payload(tenant_id=w.tenant_id, information_id=w.information_id)
    s.add(payload)
    await s.flush()
    s.add(PayloadNumber(payload_id=payload.id, tenant_id=w.tenant_id, value=Decimal(3)))


async def _payload_removed(s: AsyncSession, w: World) -> None:
    await s.execute(delete(Payload).where(Payload.id == w.picture_id))


async def _knower_added(s: AsyncSession, w: World) -> None:
    s.add(
        Knowledge(
            tenant_id=w.tenant_id, information_id=w.information_id, knower_entity_id=w.entity_id
        )
    )


async def _knower_removed(s: AsyncSession, w: World) -> None:
    await s.execute(delete(Knowledge).where(Knowledge.id == w.knowledge_id))


WRITES: dict[str, Write] = {
    "entry created": _new_entity,
    "entry renamed": _rename,
    "entry deleted": _delete_entity,
    "kind added (item_instance)": _add_kind,
    "kind added (being)": _add_being_kind,
    "kind removed": _drop_kind,
    "kind column changed": _set_kind_column,
    "link name set": _new_slug,
    "link name changed": _change_slug,
    "link name cleared": _drop_slug,
    "parent added": _add_parent,
    "parents cleared": _drop_parent,
    "stat value written": _stat_inserted,
    "stat value changed": _stat_changed,
    "stat value cleared": _stat_cleared,
    "stat group attached": _group_added,
    "stat group detached": _group_removed,
    "information created": _information_added,
    "information edited": _information_changed,
    "information deleted": _information_removed,
    "description text edited": _text_edited,
    "number edited": _number_edited,
    "picture replaced": _picture_replaced,
    "document replaced": _document_replaced,
    "payload added": _payload_added,
    "payload removed": _payload_removed,
    "knower added": _knower_added,
    "knower removed": _knower_removed,
}


@pytest.mark.parametrize("write", list(WRITES), ids=list(WRITES))
async def test_the_etag_moves_on_this_kind_of_write(
    write: str, client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    before = await _etag(client, world.tenant_id)
    assert await _etag(client, world.tenant_id) == before  # reading moves nothing

    async with admin_session_factory() as session:
        await WRITES[write](session, world)
        await session.commit()

    after = await _etag(client, world.tenant_id)
    assert after != before
    assert (
        await client.get(
            f"/tenants/{world.tenant_id}/entities/export", headers={"If-None-Match": before}
        )
    ).status_code == 200
    await delete_tenant(world.tenant_id)


async def test_every_table_the_export_reads_has_a_trigger() -> None:
    """The kinds of write above are the tables below: a table that carries a trigger but is not
    written in the list, or the reverse, shows here."""
    async with admin_session_factory() as session:
        triggered = set(
            (
                await session.execute(
                    text(
                        "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                        "WHERE t.tgname LIKE '%\\_export\\_revision' AND NOT t.tgisinternal"
                    )
                )
            ).scalars()
        )
    assert triggered == {
        "fact",
        "entity_audience",
        "entity_knowledge",
        "fact_about",
        "entity",
        "item",
        "item_instance",
        "being",
        "character",
        "entity_slug",
        "entity_prototype",
        "entity_stat",
        "entity_stat_group",
        "information",
        "payload",
        "payload_description",
        "payload_number",
        "payload_picture",
        "payload_document",
        "knowledge",
    }


async def test_the_etag_moves_on_a_character_being_made(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        being_entity = Entity(tenant_id=tenant_id, name="Hero")
        session.add(being_entity)
        await session.flush()
        session.add(Being(entity_id=being_entity.id, tenant_id=tenant_id))
        await session.commit()
        entity_id = being_entity.id
    before = await _etag(client, tenant_id)
    async with admin_session_factory() as session:
        from lorenzo_api.models import Character

        session.add(Character(entity_id=entity_id, tenant_id=tenant_id))
        await session.commit()
    assert await _etag(client, tenant_id) != before
    await delete_tenant(tenant_id)


async def test_the_etag_moves_on_writes_through_the_routes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    tenant = f"/tenants/{world.tenant_id}"
    seen = {await _etag(client, world.tenant_id)}

    async def moved(response: Response) -> None:
        assert response.status_code < 300, response.text
        etag = await _etag(client, world.tenant_id)
        assert etag not in seen
        seen.add(etag)

    await moved(await client.post(f"{tenant}/entities", json={"name": "Made", "kinds": ["item"]}))
    await moved(
        await client.put(f"{tenant}/entities/{world.entity_id}/parents", json={"parent_ids": []})
    )
    await moved(
        await client.put(
            f"{tenant}/entities/{world.entity_id}/stats/{world.definition_id}", json={"value": 7}
        )
    )
    await moved(
        await client.delete(f"{tenant}/entities/{world.entity_id}/stats/{world.definition_id}")
    )
    await moved(await client.put(f"{tenant}/entities/{world.entity_id}/slug", json={"slug": "new"}))
    await moved(await client.delete(f"{tenant}/entities/{world.entity_id}/slug"))
    await moved(
        await client.patch(f"{tenant}/information/{world.information_id}", json={"title": "Other"})
    )
    await moved(
        await client.patch(
            f"{tenant}/payloads/{world.description_id}", json={"content": "Rewritten"}
        )
    )
    await moved(
        await client.put(
            f"{tenant}/entities/{world.entity_id}/picture",
            files={"file": ("p.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        )
    )
    await moved(await client.delete(f"{tenant}/entities/{world.entity_id}/picture"))
    await moved(await client.delete(f"{tenant}/information/{world.information_id}"))
    await moved(await client.delete(f"{tenant}/entities/{world.other_id}"))
    await delete_tenant(world.tenant_id)


async def test_a_transaction_moves_the_revision_once_however_many_rows_it_writes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)

    async def revision() -> int:
        async with admin_session_factory() as session:
            return int(
                await session.scalar(select(Tenant.export_revision).where(Tenant.id == tenant_id))
                or 0
            )

    start = await revision()
    async with admin_session_factory() as session:
        session.add_all([Entity(tenant_id=tenant_id, name=f"E{n}") for n in range(25)])
        await session.commit()
    assert await revision() == start + 1
    async with admin_session_factory() as session:
        await session.execute(update(Entity).where(Entity.tenant_id == tenant_id).values(name="x"))
        await session.commit()
    assert await revision() == start + 2
    await delete_tenant(tenant_id)


async def test_a_rolled_back_write_and_another_tenants_write_move_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine = await _tenant(test_user_id)
    theirs = await _tenant(test_user_id)
    before = await _etag(client, mine)

    async with admin_session_factory() as session:
        session.add(Entity(tenant_id=mine, name="Never"))
        await session.flush()
        await session.rollback()
    async with admin_session_factory() as session:
        session.add(Entity(tenant_id=mine, name="Not kept"))
        await session.flush()
        savepoint = await session.begin_nested()
        session.add(Entity(tenant_id=mine, name="Also not kept"))
        await session.flush()
        await savepoint.rollback()
        await session.rollback()
    await _entity(theirs, "Elsewhere")
    assert await _etag(client, mine) == before

    # A write rolled back to a savepoint, then followed by one kept, still moves it, once.
    async with admin_session_factory() as session:
        savepoint = await session.begin_nested()
        session.add(Entity(tenant_id=mine, name="Dropped"))
        await session.flush()
        await savepoint.rollback()
        session.add(Entity(tenant_id=mine, name="Kept"))
        await session.commit()
    assert await _etag(client, mine) != before
    await delete_tenant(mine)
    await delete_tenant(theirs)


async def test_deleting_a_tenant_with_content_still_works(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await delete_tenant(world.tenant_id)
    async with admin_session_factory() as session:
        assert await session.get(Tenant, world.tenant_id) is None


async def test_writers_in_one_tenant_do_not_wait_for_each_other_until_commit(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The counter is bumped at commit (a deferred trigger), so a writer holds the tenant row for
    the length of its commit, not its transaction: two open transactions writing different
    entries both get through, and the one that commits second is not left waiting on the first
    (ADR 0262). With an immediate trigger the second write below would block until the first
    transaction ended."""
    tenant_id = await _tenant(test_user_id)
    first = await _entity(tenant_id, "First")
    second = await _entity(tenant_id, "Second")
    before = await _etag(client, tenant_id)

    async with admin_session_factory() as a, admin_session_factory() as b:
        await a.execute(update(Entity).where(Entity.id == first).values(name="A"))
        await asyncio.wait_for(
            b.execute(update(Entity).where(Entity.id == second).values(name="B")), timeout=10
        )
        await asyncio.wait_for(b.commit(), timeout=10)
        await asyncio.wait_for(a.commit(), timeout=10)

    assert await _etag(client, tenant_id) != before
    async with admin_session_factory() as session:
        revision = await session.scalar(
            select(Tenant.export_revision).where(Tenant.id == tenant_id)
        )
    assert revision is not None and revision >= 4  # two creates, then one for each writer
    await delete_tenant(tenant_id)
