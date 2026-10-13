"""ADR 0277: information shows who wrote it - `created_by` and the author's
name wherever a row is read, and nothing for a row the caller cannot see.
"""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_plain_participant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Entity, Information, User


@asynccontextmanager
async def _named(
    user_id: uuid.UUID, *, display_name: str | None, nickname: str | None
) -> AsyncGenerator[None]:
    """The shared test user, with these names for the length of the block."""
    async with admin_session_factory() as session:
        user = await session.get_one(User, user_id)
        user.display_name = display_name
        user.nickname = nickname
        await session.commit()
    try:
        yield
    finally:
        async with admin_session_factory() as session:
            user = await session.get_one(User, user_id)
            user.display_name = None
            user.nickname = None
            await session.commit()


async def _entity(tenant_id: uuid.UUID, name: str = "Brannoch") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


async def _write(client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> dict:
    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "Backstory", "type": "note", "is_public": True, "content": "She left."},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _information_by(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, author: uuid.UUID | None, *, public: bool
) -> uuid.UUID:
    async with admin_session_factory() as session:
        row = Information(
            tenant_id=tenant_id,
            entity_id=entity_id,
            title="Who set the fire",
            type="note",
            is_public=public,
            created_by=author,
        )
        session.add(row)
        await session.commit()
        return row.id


async def _make_user(prefix: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|{prefix}-{uuid.uuid4()}", display_name=prefix)
        session.add(user)
        await session.commit()
        return user.id


async def _delete_user(user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_a_note_says_who_wrote_it_everywhere_it_is_read(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _entity(tenant_id)
    async with _named(test_user_id, display_name="Dana Okafor", nickname="dana"):
        created = await _write(client, tenant_id, entity_id)

        detail = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
        listed = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}/information")
        one = await client.get(f"/tenants/{tenant_id}/information/{created['id']}")

    for body in (created, detail.json()["information"][0], listed.json()["items"][0], one.json()):
        assert body["created_by"] == str(test_user_id)
        assert body["created_by_name"] == "Dana Okafor"
    await delete_tenant(tenant_id)


async def test_the_name_falls_back_to_the_nickname_and_then_to_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _entity(tenant_id)
    async with _named(test_user_id, display_name=None, nickname="dana"):
        by_nickname = await _write(client, tenant_id, entity_id)
    async with _named(test_user_id, display_name=None, nickname=None):
        nameless = await _write(client, tenant_id, entity_id)

    assert by_nickname["created_by_name"] == "dana"
    assert nameless["created_by"] == str(test_user_id)
    assert nameless["created_by_name"] is None
    await delete_tenant(tenant_id)


async def test_a_row_with_no_author_has_neither_field(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A row written before attribution existed, or by an account since deleted."""
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _entity(tenant_id)
    gone = await _make_user("gone")
    old = await _information_by(tenant_id, entity_id, None, public=True)
    orphan = await _information_by(tenant_id, entity_id, gone, public=True)
    await _delete_user(gone)

    for information_id in (old, orphan):
        body = (await client.get(f"/tenants/{tenant_id}/information/{information_id}")).json()
        assert body["created_by"] is None
        assert body["created_by_name"] is None
    await delete_tenant(tenant_id)


async def test_a_row_the_caller_cannot_see_does_not_show_its_author(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The author is exactly as visible as the information: a GM-only note by someone else is
    not in a plain participant's reads at all."""
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _entity(tenant_id)
    gm = await _make_user("gm")
    hidden = await _information_by(tenant_id, entity_id, gm, public=False)
    shown = await _information_by(tenant_id, entity_id, gm, public=True)
    await make_plain_participant(tenant_id, test_user_id)

    listed = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}/information")).json()
    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")).json()

    assert [i["id"] for i in listed["items"]] == [str(shown)]
    assert [i["id"] for i in detail["information"]] == [str(shown)]
    assert str(hidden) not in str(listed) + str(detail)
    assert listed["items"][0]["created_by_name"] == "gm"
    await delete_tenant(tenant_id)
    await _delete_user(gm)
