"""Content references and backlinks over REST (ADR 0110): what a description
write stores, and GET .../entities/{id}/backlinks."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import ContentReference, Entity, EntitySlug, Item, Tenant


async def _entity(tenant_id: uuid.UUID, name: str, slug: str | None = None) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        if slug is not None:
            session.add(EntitySlug(entity_id=entity.id, tenant_id=tenant_id, slug=slug))
        await session.commit()
        return entity.id


async def _describe(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, content: str, **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "Description", "type": "description", "content": content, **extra},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def _stored(payload_id: str) -> list[tuple[str, str, str]]:
    async with admin_session_factory() as session:
        rows = await session.execute(
            select(ContentReference.kind, ContentReference.hint, ContentReference.target)
            .where(ContentReference.payload_id == uuid.UUID(payload_id))
            .order_by(ContentReference.position)
        )
        return [tuple(row) for row in rows]


async def _backlinks(client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> Any:
    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}/backlinks")
    assert response.status_code == 200, response.text
    return response.json()


async def test_writing_a_description_stores_its_references(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _entity(tenant_id, "Emberdeep")
    too_long = "a" * 101

    created = await _describe(
        client,
        tenant_id,
        entity_id,
        "[[Ashfang]] and [it](being/ashfang), again [[ashfang]].\n\n"
        f"![Map](old-sword) on {{{{date 2026-09-24}}}}, {{{{cal harptos 1492-mirtul-12}}}}, "
        f"[never]({too_long}).",
    )

    assert await _stored(created["payloads"][0]["id"]) == [
        ("entity", "", "ashfang"),
        ("entity", "being", "ashfang"),
        ("image", "", "old-sword"),
        ("date", "", "2026-09-24"),
        ("calendar", "", "harptos 1492-mirtul-12"),
    ]
    await delete_tenant(tenant_id)


async def test_new_text_replaces_the_references_and_a_locale_change_keeps_them(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _entity(tenant_id, "Emberdeep")
    payload_id = (await _describe(client, tenant_id, entity_id, "[[Ashfang]]"))["payloads"][0]["id"]
    url = f"/tenants/{tenant_id}/payloads/{payload_id}"

    assert (await client.patch(url, json={"content": "[[Old Sword]]"})).status_code == 200
    assert await _stored(payload_id) == [("entity", "", "old-sword")]
    assert (await client.patch(url, json={"locale": "de-DE"})).status_code == 200
    assert await _stored(payload_id) == [("entity", "", "old-sword")]
    assert (await client.patch(url, json={"content": "No links left."})).status_code == 200
    assert await _stored(payload_id) == []
    await delete_tenant(tenant_id)


async def test_backlinks_list_each_linking_information_once(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ashfang = await _entity(tenant_id, "Ashfang", slug="ashfang")
    mira = await _entity(tenant_id, "Mira")
    emberdeep = await _entity(tenant_id, "Emberdeep")
    unrelated = await _entity(tenant_id, "Unrelated")
    await _describe(client, tenant_id, mira, "Mira carries [it](being/ashfang).")
    ember = await _describe(client, tenant_id, emberdeep, "[[Ashfang]], drawn: ![a](ashfang)")
    # A calendar expression that happens to read like the slug isn't a link.
    await _describe(client, tenant_id, unrelated, "[[Old Sword]] on {{cal ashfang}}")
    await _describe(client, tenant_id, ashfang, "I am [[Ashfang]].")  # itself: not listed

    page = await _backlinks(client, tenant_id, ashfang)

    assert page["total"] == 2
    assert [item["name"] for item in page["items"]] == ["Emberdeep", "Mira"]
    assert page["items"][0] == {
        "entity_id": str(emberdeep),
        "name": "Emberdeep",
        "kinds": ["item"],
        "information_id": ember["id"],
        "title": "Description",
        "type": "description",
    }
    await delete_tenant(tenant_id)


async def test_a_link_counts_once_its_slug_exists_and_follows_the_slug(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sword = await _entity(tenant_id, "Old Sword")
    emberdeep = await _entity(tenant_id, "Emberdeep")
    await _describe(client, tenant_id, emberdeep, "It hangs by [[Old Sword]].")
    slug_url = f"/tenants/{tenant_id}/entities/{sword}/slug"

    assert (await _backlinks(client, tenant_id, sword))["items"] == []
    assert (await client.put(slug_url, json={"slug": "old-sword"})).status_code == 200
    assert [i["name"] for i in (await _backlinks(client, tenant_id, sword))["items"]] == [
        "Emberdeep"
    ]
    assert (await client.put(slug_url, json={"slug": "ancient-sword"})).status_code == 200
    assert (await _backlinks(client, tenant_id, sword))["items"] == []
    await delete_tenant(tenant_id)


async def test_backlinks_only_come_from_information_the_caller_can_see(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A backlink from GM-only text would reveal that text's secret (RFC 0027 §7)."""
    tenant_id = await make_tenant(test_user_id)
    ashfang = await _entity(tenant_id, "Ashfang", slug="ashfang")
    tavern = await _entity(tenant_id, "Tavern")
    lair = await _entity(tenant_id, "Lair")
    await _describe(client, tenant_id, tavern, "Rumours of [[Ashfang]].", is_public=True)
    await _describe(client, tenant_id, lair, "[[Ashfang]] waits here.", is_public=False)
    assert (await _backlinks(client, tenant_id, ashfang))["total"] == 2

    await make_plain_participant(tenant_id, test_user_id)
    page = await _backlinks(client, tenant_id, ashfang)

    assert page["total"] == 1
    assert [item["name"] for item in page["items"]] == ["Tavern"]
    await delete_tenant(tenant_id)


async def test_backlinks_share_the_entity_read_gate(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    unnamed = await _entity(tenant_id, "No slug")

    assert (await _backlinks(client, tenant_id, unnamed))["items"] == []
    unknown = await client.get(f"/tenants/{tenant_id}/entities/{uuid.uuid4()}/backlinks")
    assert unknown.status_code == 404
    await delete_tenant(tenant_id)

    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        foreign_tenant = tenant.id
    foreign = await _entity(foreign_tenant, "Ashfang", slug="ashfang")
    response = await client.get(f"/tenants/{foreign_tenant}/entities/{foreign}/backlinks")
    assert response.status_code == 404
    await delete_tenant(foreign_tenant)
