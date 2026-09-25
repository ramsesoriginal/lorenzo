"""ADR 0101: editable information - singleton types, `order`, PATCH/DELETE
on information, PATCH on description payloads, and the "sight of the row
or authorship" gate on every edit of an existing row.
"""

import uuid
from decimal import Decimal
from pathlib import Path

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.models import (
    SINGLETON_INFORMATION_TYPES,
    AuditLog,
    CharacterPlayer,
    Entity,
    Information,
    InformationType,
    Item,
    Knowledge,
    Membership,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadNumber,
    Player,
)

_SRC = Path(__file__).resolve().parents[1] / "src" / "lorenzo_api"
_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "b28ed28ca209_editable_information.py"
)


async def _make_item(tenant_id: uuid.UUID, name: str = "Sword") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _create(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, **overrides: object
) -> dict:
    body = {"title": "A note", "type": "note", "is_public": False, "content": "Text."}
    body.update(overrides)
    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information", json=body
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _entries(tenant_id: uuid.UUID, prefix: str) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like(f"{prefix}.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _player_owning_a_sword(tenant_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    """user_id becomes a plain player (no tenant Membership, so no
    administrative bypass) whose own character owns a sword - they have
    self-or-managed standing over it. Returns the sword's entity id.
    """
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, user_id))
        await session.delete(membership)
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = Player(user_id=user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        sword = Entity(tenant_id=tenant_id, name="Sword")
        session.add(sword)
        await session.flush()
        session.add(Item(entity_id=sword.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=sword.id,
                owner_character_id=character.entity_id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        return sword.id


async def _gm_secret(tenant_id: uuid.UUID, entity_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """A GM-only row (not public, no knowers, no author) with one
    description payload. Returns (information_id, payload_id)."""
    async with admin_session_factory() as session:
        info = Information(tenant_id=tenant_id, entity_id=entity_id, title="Curse", type="gm-note")
        session.add(info)
        await session.flush()
        payload = Payload(tenant_id=tenant_id, information_id=info.id)
        session.add(payload)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=payload.id, tenant_id=tenant_id, locale="en", content="It is cursed."
            )
        )
        await session.commit()
        return info.id, payload.id


# --- singleton types and order -------------------------------------------


async def test_non_singleton_types_repeat_and_append_in_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)

    first = await _create(client, tenant_id, entity_id, title="First")
    second = await _create(client, tenant_id, entity_id, title="Second")
    description = await _create(client, tenant_id, entity_id, type="description")

    assert [first["order"], second["order"], description["order"]] == [0, 1, 2]
    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert [info["title"] for info in response.json()["information"]] == [
        "First",
        "Second",
        "A note",
    ]
    await delete_tenant(tenant_id)


async def test_second_singleton_type_is_409(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    await _create(client, tenant_id, entity_id, type="description")

    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "Again", "type": "description", "content": "x"},
    )

    assert response.status_code == 409
    await delete_tenant(tenant_id)


async def test_explicit_order_is_kept_and_a_taken_one_is_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)

    placed = await _create(client, tenant_id, entity_id, order=5)
    appended = await _create(client, tenant_id, entity_id)
    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "x", "type": "note", "content": "x", "order": 5},
    )

    assert placed["order"] == 5
    assert appended["order"] == 6
    assert response.status_code == 409
    await delete_tenant(tenant_id)


async def test_singleton_list_agrees_across_catalog_model_migration_and_index() -> None:
    """ADR 0101: the partial index predicate can't read information_type,
    so the singleton list is kept in several places - this is what catches
    a change that touches only one of them.
    """
    async with admin_session_factory() as session:
        catalog = set(
            (
                await session.execute(
                    select(InformationType.name).where(InformationType.is_singleton)
                )
            )
            .scalars()
            .all()
        )
        index_def = (
            await session.execute(
                text(
                    "SELECT indexdef FROM pg_indexes WHERE indexname = 'information_singleton_type'"
                )
            )
        ).scalar_one()

    assert catalog == set(SINGLETON_INFORMATION_TYPES)
    for name in SINGLETON_INFORMATION_TYPES:
        assert f"'{name}'" in index_def
        assert f'"{name}"' in _MIGRATION.read_text()
    assert index_def.count("::text") == len(SINGLETON_INFORMATION_TYPES)


async def test_app_role_cannot_write_information_type() -> None:
    """A global catalog only migrations change (ADR 0101)."""
    from lorenzo_api.db import engine

    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT count(*) FROM information_type"))
        ).scalar_one() == len(SINGLETON_INFORMATION_TYPES)
        result = await connection.execute(
            text("SELECT has_table_privilege('information_type', 'INSERT')")
        )
        assert result.scalar_one() is False


def test_payload_description_is_only_written_by_write_description() -> None:
    """ADR 0101/RFC 0027: every description write goes through one
    function, which RFC 0027 stage 7 extends - a new direct write would
    silently bypass it.
    """
    offenders = [
        path.relative_to(_SRC).as_posix()
        for path in _SRC.rglob("*.py")
        if "PayloadDescription(" in path.read_text()
        and path.name not in {"description_payloads.py", "payload_description.py"}
    ]
    assert offenders == []


# --- PATCH / DELETE information --------------------------------------------


async def test_patch_information_with_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    created = await _create(client, tenant_id, entity_id)
    url = f"/tenants/{tenant_id}/information/{created['id']}"

    etag = (await client.get(url)).headers["etag"]
    stale = await client.patch(
        url, json={"title": "x"}, headers={"If-Match": 'W/"2000-01-01T00:00:00+00:00"'}
    )
    response = await client.patch(
        url,
        json={"title": "Renamed", "is_public": True, "order": 3},
        headers={"If-Match": etag},
    )

    assert stale.status_code == 412
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["title"], body["is_public"], body["order"]) == ("Renamed", True, 3)
    assert body["type"] == "note"
    assert response.headers["etag"] != etag
    assert (
        await client.patch(url, json={"title": "y"}, headers={"If-Match": etag})
    ).status_code == 412
    # Only the visibility change is logged (ADR 0084), and never the title.
    assert await _entries(tenant_id, "information") == [
        ("information.created", f"entity={entity_id}, visibility=restricted"),
        ("information.visibility_changed", "visibility=public"),
    ]
    await delete_tenant(tenant_id)


async def test_patch_information_type_to_a_held_singleton_is_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    await _create(client, tenant_id, entity_id, type="description")
    note = await _create(client, tenant_id, entity_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/information/{note['id']}", json={"type": "description"}
    )

    assert response.status_code == 409
    await delete_tenant(tenant_id)


async def test_patch_information_to_a_taken_order_is_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    await _create(client, tenant_id, entity_id)
    second = await _create(client, tenant_id, entity_id)

    taken = await client.patch(
        f"/tenants/{tenant_id}/information/{second['id']}", json={"order": 0}
    )
    own = await client.patch(f"/tenants/{tenant_id}/information/{second['id']}", json={"order": 1})

    assert taken.status_code == 409
    assert own.status_code == 200
    await delete_tenant(tenant_id)


async def test_delete_information_with_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    created = await _create(client, tenant_id, entity_id)
    url = f"/tenants/{tenant_id}/information/{created['id']}"
    etag = (await client.get(url)).headers["etag"]

    stale = await client.delete(url, headers={"If-Match": 'W/"2000-01-01T00:00:00+00:00"'})
    response = await client.delete(url, headers={"If-Match": etag})

    assert stale.status_code == 412
    assert response.status_code == 204
    assert (await client.get(url)).status_code == 404
    async with admin_session_factory() as session:
        remaining = (
            await session.execute(select(Payload.id).where(Payload.tenant_id == tenant_id))
        ).all()
    assert remaining == []
    assert (await _entries(tenant_id, "information"))[-1] == (
        "information.deleted",
        f"entity={entity_id}",
    )
    await delete_tenant(tenant_id)


# --- the edit gate: standing plus sight (or authorship) --------------------


async def test_player_cannot_touch_a_gm_secret_about_their_own_sword(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Self-or-managed standing over the sword isn't enough: without sight
    of the row, every edit 404s - the player can't publish it, delete it,
    rewrite it, or grant their own character sight of it.
    """
    tenant_id = await make_tenant(test_user_id)
    sword_id = await _player_owning_a_sword(tenant_id, test_user_id)
    information_id, payload_id = await _gm_secret(tenant_id, sword_id)
    async with admin_session_factory() as session:
        character_id = (
            await session.execute(
                select(Ownership.owner_character_id).where(Ownership.owned_entity_id == sword_id)
            )
        ).scalar_one()
    url = f"/tenants/{tenant_id}/information/{information_id}"

    responses = [
        await client.patch(url, json={"is_public": True}),
        await client.delete(url),
        await client.put(f"{url}/knowers/{character_id}"),
        await client.patch(f"/tenants/{tenant_id}/payloads/{payload_id}", json={"content": "x"}),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404, 404]
    async with admin_session_factory() as session:
        info = await session.get_one(Information, information_id)
        assert info.is_public is False
        knowers = (
            await session.execute(
                select(Knowledge.id).where(Knowledge.information_id == information_id)
            )
        ).all()
        assert knowers == []
    await delete_tenant(tenant_id)


async def test_player_can_edit_a_restricted_note_they_wrote(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A new restricted row has no knowers, so its author can't *see* it -
    the authorship clause is what keeps it editable (ADR 0101)."""
    tenant_id = await make_tenant(test_user_id)
    sword_id = await _player_owning_a_sword(tenant_id, test_user_id)
    created = await _create(client, tenant_id, sword_id, content="Mine.")
    payload_id = created["payloads"][0]["id"]

    patched = await client.patch(
        f"/tenants/{tenant_id}/information/{created['id']}", json={"title": "My note"}
    )
    payload = await client.patch(
        f"/tenants/{tenant_id}/payloads/{payload_id}", json={"content": "Still mine."}
    )
    deleted = await client.delete(f"/tenants/{tenant_id}/information/{created['id']}")

    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "My note"
    assert payload.status_code == 200, payload.text
    assert payload.json()["content"] == "Still mine."
    assert deleted.status_code == 204
    await delete_tenant(tenant_id)


async def test_seeing_a_public_row_without_standing_is_403(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    await _player_owning_a_sword(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        other = Entity(tenant_id=tenant_id, name="Someone else's shield")
        session.add(other)
        await session.flush()
        info = Information(
            tenant_id=tenant_id, entity_id=other.id, title="Shield", type="note", is_public=True
        )
        session.add(info)
        await session.commit()
        information_id = info.id
    # Ownerless entity: the fallback needs campaign management, which a
    # plain player doesn't have.

    response = await client.patch(
        f"/tenants/{tenant_id}/information/{information_id}", json={"title": "Mine now"}
    )

    assert response.status_code == 403
    await delete_tenant(tenant_id)


# --- PATCH description payloads ----------------------------------------------


async def test_patch_description_payload_with_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    created = await _create(client, tenant_id, entity_id, type="description", content="Old.")
    payload = created["payloads"][0]
    url = f"/tenants/{tenant_id}/payloads/{payload['id']}"
    # Built from the response body, as a client does: no read returns a
    # payload's own ETag header (ADR 0101/0108).
    etag = f'W/"{payload["updated_at"]}"'

    stale = await client.patch(
        url, json={"content": "x"}, headers={"If-Match": 'W/"2000-01-01T00:00:00+00:00"'}
    )
    content = await client.patch(
        url, json={"content": "[[Ashfang]] **glows**."}, headers={"If-Match": etag}
    )
    locale = await client.patch(url, json={"locale": "de-DE"})

    assert stale.status_code == 412
    assert content.status_code == 200, content.text
    assert content.json()["content"] == "[[Ashfang]] **glows**."  # stored as given
    assert content.headers["etag"] != etag
    assert content.json()["updated_at"] != payload["updated_at"]
    assert locale.json()["content"] == "[[Ashfang]] **glows**."
    assert locale.json()["locale"] == "de-DE"
    # The old token is now stale.
    assert (
        await client.patch(url, json={"content": "y"}, headers={"If-Match": etag})
    ).status_code == 412
    read = await client.get(f"/tenants/{tenant_id}/information/{created['id']}")
    assert read.json()["payloads"][0]["content"] == "[[Ashfang]] **glows**."
    # Descriptive content: not logged (ADR 0084).
    assert [action for action, _ in await _entries(tenant_id, "information")] == [
        "information.created"
    ]
    await delete_tenant(tenant_id)


async def test_patch_non_description_payload_is_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    created = await _create(client, tenant_id, entity_id, is_public=True)
    async with admin_session_factory() as session:
        payload = Payload(tenant_id=tenant_id, information_id=uuid.UUID(created["id"]))
        session.add(payload)
        await session.flush()
        session.add(PayloadNumber(payload_id=payload.id, tenant_id=tenant_id, value=Decimal(3)))
        await session.commit()
        payload_id = payload.id
        payload_order = payload.order

    response = await client.patch(
        f"/tenants/{tenant_id}/payloads/{payload_id}", json={"content": "x"}
    )

    assert payload_order == 1  # appended after the description payload
    assert response.status_code == 409
    await delete_tenant(tenant_id)


async def test_patch_payload_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/payloads/{uuid.uuid4()}", json={"content": "x"}
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)
