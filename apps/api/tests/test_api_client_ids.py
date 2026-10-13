"""Creates that carry their own id (ADR 0222, RFC 0039 W2), through the real HTTP API: made under
that id, a second send is a replay that returns the first, and an id that is not the caller's to
use is a generic 409 that says nothing of who has it."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from lorenzo_api.models import AuditLog, Entity, EntitySlug, Information


def _entities(tenant_id: uuid.UUID, *rest: object) -> str:
    return "/".join([f"/tenants/{tenant_id}/entities", *(str(r) for r in rest)])


def _items(tenant_id: uuid.UUID, *rest: object) -> str:
    return "/".join([f"/tenants/{tenant_id}/items", *(str(r) for r in rest)])


async def _count(model: Any, *where: Any) -> int:
    async with admin_session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


async def _activity(tenant_id: uuid.UUID) -> int:
    return await _count(AuditLog, AuditLog.tenant_id == tenant_id)


def _no_trace_of_another_tenant(response: Response, other: uuid.UUID) -> None:
    assert response.status_code == 409, response.text
    assert str(other) not in response.text
    assert "tenant" not in response.text.lower()


# --- POST /entities --------------------------------------------------------------------------


async def test_an_entry_is_made_under_the_id_the_client_chose(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    new_id = uuid.uuid4()
    response = await client.post(
        _entities(tenant_id), json={"id": str(new_id), "name": "Axe", "kinds": ["item"]}
    )

    assert response.status_code == 201, response.text
    assert response.json()["id"] == str(new_id)
    assert response.headers["location"].endswith(_entities(tenant_id, new_id))
    assert (await client.get(_entities(tenant_id, new_id))).json()["name"] == "Axe"
    await delete_tenant(tenant_id)


async def test_the_same_create_sent_again_is_a_replay_that_changes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    body = {"id": str(uuid.uuid4()), "name": "Axe", "slug": "axe", "kinds": ["item"]}
    first = await client.post(_entities(tenant_id), json=body)
    logged = await _activity(tenant_id)
    second = await client.post(_entities(tenant_id), json=body)

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json() == first.json()
    assert second.headers["etag"] == first.headers["etag"]
    assert await _count(Entity, Entity.tenant_id == tenant_id) == 1
    assert await _count(EntitySlug, EntitySlug.tenant_id == tenant_id) == 1
    assert await _activity(tenant_id) == logged
    await delete_tenant(tenant_id)


async def test_an_id_that_another_tenant_holds_is_a_generic_409_and_changes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine = await make_tenant(test_user_id)
    theirs = await make_tenant(test_user_id)
    taken = uuid.UUID((await client.post(_entities(theirs), json={"name": "Theirs"})).json()["id"])

    response = await client.post(_entities(mine), json={"id": str(taken), "name": "Mine"})

    _no_trace_of_another_tenant(response, theirs)
    assert await _count(Entity, Entity.tenant_id == mine) == 0
    assert (await client.get(_entities(theirs, taken))).json()["name"] == "Theirs"
    await delete_tenant(mine)
    await delete_tenant(theirs)


async def test_a_create_without_an_id_is_as_it_was(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    a = await client.post(_entities(tenant_id), json={"name": "Same"})
    b = await client.post(_entities(tenant_id), json={"name": "Same"})
    assert (a.status_code, b.status_code) == (201, 201)
    assert a.json()["id"] != b.json()["id"]
    await delete_tenant(tenant_id)


async def test_an_id_that_is_not_a_uuid_is_a_422(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    response = await client.post(_entities(tenant_id), json={"id": "nope", "name": "Axe"})
    assert response.status_code == 422
    await delete_tenant(tenant_id)


# --- POST /items -----------------------------------------------------------------------------


async def test_an_item_is_made_under_the_id_and_a_second_send_returns_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    new_id = uuid.uuid4()
    body = {"id": str(new_id), "name": "Sword", "slug": "sword"}
    first = await client.post(_items(tenant_id), json=body)
    second = await client.post(_items(tenant_id), json=body)

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["entity_id"] == second.json()["entity_id"] == str(new_id)
    assert await _count(Entity, Entity.tenant_id == tenant_id) == 1
    await delete_tenant(tenant_id)


async def test_an_item_id_of_an_entry_that_is_not_an_item_is_a_generic_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    bare = uuid.UUID((await client.post(_entities(tenant_id), json={"name": "Group"})).json()["id"])
    response = await client.post(_items(tenant_id), json={"id": str(bare), "name": "Sword"})
    assert response.status_code == 409
    assert response.json()["title"] == "Id not available"
    await delete_tenant(tenant_id)


async def test_an_item_id_that_another_tenant_holds_is_a_generic_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine = await make_tenant(test_user_id)
    theirs = await make_tenant(test_user_id)
    taken = (await client.post(_items(theirs), json={"name": "Theirs"})).json()["entity_id"]
    response = await client.post(_items(mine), json={"id": taken, "name": "Mine"})
    _no_trace_of_another_tenant(response, theirs)
    assert await _count(Entity, Entity.tenant_id == mine) == 0
    await delete_tenant(mine)
    await delete_tenant(theirs)


# --- POST /entities/{id}/information -----------------------------------------------------------


def _note(**extra: Any) -> dict[str, Any]:
    return {"title": "Note", "type": "note", "content": "Hello", **extra}


async def test_a_note_is_made_under_its_id_and_a_second_send_returns_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entry = (await client.post(_entities(tenant_id), json={"name": "Axe"})).json()["id"]
    note_id = uuid.uuid4()
    url = _entities(tenant_id, entry, "information")
    first = await client.post(url, json=_note(id=str(note_id)))
    second = await client.post(url, json=_note(id=str(note_id)))

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"] == str(note_id)
    assert await _count(Information, Information.entity_id == uuid.UUID(entry)) == 1
    await delete_tenant(tenant_id)


async def test_a_singleton_replay_does_not_trip_the_one_per_entry_rule(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entry = (await client.post(_entities(tenant_id), json={"name": "Axe"})).json()["id"]
    url = _entities(tenant_id, entry, "information")
    body = {"id": str(uuid.uuid4()), "title": "Axe", "type": "description", "content": "Sharp"}
    assert (await client.post(url, json=body)).status_code == 201
    assert (await client.post(url, json=body)).status_code == 200
    await delete_tenant(tenant_id)


async def test_a_note_id_that_belongs_to_another_entry_is_a_generic_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    one = (await client.post(_entities(tenant_id), json={"name": "One"})).json()["id"]
    two = (await client.post(_entities(tenant_id), json={"name": "Two"})).json()["id"]
    note_id = str(uuid.uuid4())
    assert (
        await client.post(_entities(tenant_id, one, "information"), json=_note(id=note_id))
    ).status_code == 201
    response = await client.post(_entities(tenant_id, two, "information"), json=_note(id=note_id))
    assert response.status_code == 409
    assert response.json()["title"] == "Id not available"
    await delete_tenant(tenant_id)


async def test_a_note_id_that_another_tenant_holds_is_a_generic_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine = await make_tenant(test_user_id)
    theirs = await make_tenant(test_user_id)
    their_entry = (await client.post(_entities(theirs), json={"name": "T"})).json()["id"]
    my_entry = (await client.post(_entities(mine), json={"name": "M"})).json()["id"]
    note = (await client.post(_entities(theirs, their_entry, "information"), json=_note())).json()[
        "id"
    ]
    response = await client.post(_entities(mine, my_entry, "information"), json=_note(id=note))
    _no_trace_of_another_tenant(response, theirs)
    assert await _count(Information, Information.tenant_id == mine) == 0
    await delete_tenant(mine)
    await delete_tenant(theirs)
