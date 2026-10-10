"""RFC 0041 section 8: picture payload upload/delete, an entity's main
picture, and reordering an entity's information.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.config import get_settings
from lorenzo_api.models import Entity, Information, Item

_PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-content"


async def _make_item(tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Sword")
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _note(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, title: str = "A note"
) -> dict:
    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": title, "type": "note", "is_public": False, "content": "Text."},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_upload_a_picture_payload_and_fetch_its_bytes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    note = await _note(client, tenant_id, entity_id)

    response = await client.post(
        f"/tenants/{tenant_id}/information/{note['id']}/payloads",
        files={"file": ("a.png", _PNG, "image/png")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "picture"
    assert body["file_type"] == "image/png"
    served = await client.get(f"/tenants/{tenant_id}/payloads/{body['id']}/content")
    assert served.content == _PNG
    await delete_tenant(tenant_id)


async def test_upload_rejects_a_bad_type_and_an_oversize_file(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    note = await _note(client, tenant_id, entity_id)
    url = f"/tenants/{tenant_id}/information/{note['id']}/payloads"

    bad = await client.post(url, files={"file": ("a.txt", b"hi", "text/plain")})
    big = await client.post(
        url,
        files={"file": ("a.png", b"x" * (get_settings().picture_max_bytes + 1), "image/png")},
    )

    assert bad.status_code == 422
    assert big.status_code == 422
    await delete_tenant(tenant_id)


async def test_upload_to_an_unknown_information_is_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/information/{uuid.uuid4()}/payloads",
        files={"file": ("a.png", _PNG, "image/png")},
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_delete_a_picture_payload_but_not_a_description(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    note = await _note(client, tenant_id, entity_id)
    picture = (
        await client.post(
            f"/tenants/{tenant_id}/information/{note['id']}/payloads",
            files={"file": ("a.png", _PNG, "image/png")},
        )
    ).json()
    description_id = note["payloads"][0]["id"]

    refused = await client.delete(f"/tenants/{tenant_id}/payloads/{description_id}")
    removed = await client.delete(f"/tenants/{tenant_id}/payloads/{picture['id']}")
    gone = await client.get(f"/tenants/{tenant_id}/payloads/{picture['id']}/content")

    assert refused.status_code == 409
    assert removed.status_code == 204
    assert gone.status_code == 404
    await delete_tenant(tenant_id)


async def test_put_picture_creates_then_replaces_the_main_picture(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    url = f"/tenants/{tenant_id}/entities/{entity_id}/picture"

    created = await client.put(url, files={"file": ("a.png", _PNG, "image/png")})
    replaced = await client.put(url, files={"file": ("b.png", _PNG + b"2", "image/png")})

    assert created.status_code == 201, created.text
    assert replaced.status_code == 200, replaced.text
    assert created.json()["type"] == "main_picture"
    assert replaced.json()["id"] == created.json()["id"]
    payload = replaced.json()["payloads"][0]
    served = await client.get(f"/tenants/{tenant_id}/payloads/{payload['id']}/content")
    assert served.content == _PNG + b"2"
    await delete_tenant(tenant_id)


async def test_main_picture_refuses_a_second_picture_through_the_payloads_route(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    main = (
        await client.put(
            f"/tenants/{tenant_id}/entities/{entity_id}/picture",
            files={"file": ("a.png", _PNG, "image/png")},
        )
    ).json()

    response = await client.post(
        f"/tenants/{tenant_id}/information/{main['id']}/payloads",
        files={"file": ("a.png", _PNG, "image/png")},
    )

    assert response.status_code == 409
    await delete_tenant(tenant_id)


async def test_delete_picture_is_idempotent_and_removes_the_information(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    url = f"/tenants/{tenant_id}/entities/{entity_id}/picture"
    await client.put(url, files={"file": ("a.png", _PNG, "image/png")})

    first = await client.delete(url)
    second = await client.delete(url)

    assert (first.status_code, second.status_code) == (204, 204)
    async with admin_session_factory() as session:
        rows = (
            await session.scalars(
                select(Information).where(
                    Information.entity_id == entity_id, Information.type == "main_picture"
                )
            )
        ).all()
    assert rows == []
    await delete_tenant(tenant_id)


async def test_deleting_the_main_pictures_payload_removes_its_information(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    main = (
        await client.put(
            f"/tenants/{tenant_id}/entities/{entity_id}/picture",
            files={"file": ("a.png", _PNG, "image/png")},
        )
    ).json()

    response = await client.delete(f"/tenants/{tenant_id}/payloads/{main['payloads'][0]['id']}")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(Information, uuid.UUID(main["id"])) is None
    await delete_tenant(tenant_id)


async def test_reorder_information(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    a = await _note(client, tenant_id, entity_id, "A")
    b = await _note(client, tenant_id, entity_id, "B")
    c = await _note(client, tenant_id, entity_id, "C")
    url = f"/tenants/{tenant_id}/entities/{entity_id}/information/order"

    response = await client.put(url, json={"information_ids": [c["id"], a["id"], b["id"]]})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["title"] for row in body] == ["C", "A", "B"]
    assert [row["order"] for row in body] == sorted(row["order"] for row in body)
    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")).json()
    assert [row["title"] for row in detail["information"]] == ["C", "A", "B"]
    await delete_tenant(tenant_id)


async def test_reorder_refuses_a_list_that_is_not_the_visible_set(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    a = await _note(client, tenant_id, entity_id, "A")
    b = await _note(client, tenant_id, entity_id, "B")
    url = f"/tenants/{tenant_id}/entities/{entity_id}/information/order"

    missing = await client.put(url, json={"information_ids": [a["id"]]})
    duplicate = await client.put(url, json={"information_ids": [a["id"], a["id"], b["id"]]})
    unknown = await client.put(url, json={"information_ids": [a["id"], str(uuid.uuid4())]})

    assert (missing.status_code, duplicate.status_code, unknown.status_code) == (409, 409, 409)
    await delete_tenant(tenant_id)
