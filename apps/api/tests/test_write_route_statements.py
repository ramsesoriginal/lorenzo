"""ADR 0285: what a write route costs in statements, and what a request asks the database twice.

The bounds are the measured counts with a little room: they fail when the work a write does comes
back (the tenant and the caller's membership read again for every access check, the GM's reach
resolved for an owner, a response that reads every to-one relationship of the row it just wrote),
not when someone adds a statement of their own.
"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from _admin_db import admin_session_factory
from conftest import (
    delete_tenant,
    make_campaign,
    make_character,
    make_player,
    make_tenant,
)
from httpx import AsyncClient, Response
from sqlalchemy import event
from test_item_read_statements import _ok, _statements

from lorenzo_api.campaign_access import membership_of
from lorenzo_api.models import CampaignGm, CharacterPlayer, Membership


class _World:
    """An owner who also GMs a campaign with three characters, and a small library."""

    tenant: uuid.UUID
    character: uuid.UUID
    item: uuid.UUID
    weight: uuid.UUID
    magical: uuid.UUID


@asynccontextmanager
async def _world(client: AsyncClient, user_id: uuid.UUID) -> AsyncIterator[_World]:
    world = _World()
    world.tenant = await make_tenant(user_id)
    try:
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=world.tenant)
            session.add(
                CampaignGm(tenant_id=world.tenant, user_id=user_id, campaign_id=campaign.id)
            )
            for number in range(3):
                player = await make_player(session, tenant_id=world.tenant, campaign_id=campaign.id)
                character = await make_character(
                    session, tenant_id=world.tenant, name=f"PC{number}", owner_player_id=player.id
                )
                session.add(
                    CharacterPlayer(
                        character_entity_id=character.entity_id,
                        player_id=player.id,
                        tenant_id=world.tenant,
                    )
                )
                world.character = character.entity_id
            await session.commit()
        base = f"/tenants/{world.tenant}"
        group = await _ok(
            await client.post(
                f"{base}/stat-groups", json={"name": "physical", "priority": 0, "mandatory": False}
            )
        )
        world.weight = uuid.UUID(
            (
                await _ok(
                    await client.post(
                        f"{base}/stat-definitions",
                        json={"name": "weight", "stat_group_id": group["id"], "value_type": "int"},
                    )
                )
            )["id"]
        )
        world.magical = uuid.UUID(
            (
                await _ok(
                    await client.post(
                        f"{base}/stat-definitions",
                        json={
                            "name": "is_magical",
                            "stat_group_id": group["id"],
                            "value_type": "bool",
                        },
                    )
                )
            )["id"]
        )
        book = await _ok(
            await client.post(f"{base}/items", json={"name": "Book", "prototype_ids": []})
        )
        spellbook = await _ok(
            await client.post(
                f"{base}/items", json={"name": "Spellbook", "prototype_ids": [book["entity_id"]]}
            )
        )
        for item in (book, spellbook):
            await _ok(
                await client.post(
                    f"{base}/entities/{item['entity_id']}/information",
                    json={
                        "title": "",
                        "type": "description",
                        "is_public": True,
                        "content": "Pages and pages.",
                        "locale": "en",
                    },
                )
            )
        world.item = uuid.UUID(spellbook["entity_id"])
        yield world
    finally:
        await delete_tenant(world.tenant)


async def _statements_of(call: Callable[[], Awaitable[Response]]) -> int:
    assert (await call()).status_code < 300  # the first call warms what is cached
    with _statements() as seen:
        response = await call()
    assert response.status_code < 300, response.text
    return len(seen)


async def test_putting_a_tag_costs_few_statements(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _world(client, test_user_id) as w:
        url = f"/tenants/{w.tenant}/entities/{w.item}/tags/{w.magical}"
        count = await _statements_of(lambda: client.put(url))
    assert count <= 25, count


async def test_putting_a_stat_value_costs_few_statements(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _world(client, test_user_id) as w:
        url = f"/tenants/{w.tenant}/entities/{w.item}/stats/{w.weight}"
        count = await _statements_of(
            lambda: client.put(url, json={"value": 3, "acquire_group": False})
        )
    assert count <= 26, count


async def test_giving_out_an_item_costs_few_statements(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _world(client, test_user_id) as w:
        count = await _statements_of(
            lambda: client.post(
                f"/tenants/{w.tenant}/item-instances",
                json={
                    "prototype_id": str(w.item),
                    "owner_character_id": str(w.character),
                    "container_entity_id": None,
                    "slug": None,
                    "override": False,
                    "quantity": 1,
                },
            )
        )
    assert count <= 32, count


async def test_adding_information_costs_few_statements(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _world(client, test_user_id) as w:
        count = await _statements_of(
            lambda: client.post(
                f"/tenants/{w.tenant}/entities/{w.item}/information",
                json={
                    "title": "",
                    "type": "note",
                    "is_public": False,
                    "content": "a note",
                    "locale": "en",
                },
            )
        )
    assert count <= 20, count


async def test_reading_an_entity_costs_few_statements(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _world(client, test_user_id) as w:
        count = await _statements_of(lambda: client.get(f"/tenants/{w.tenant}/entities/{w.item}"))
    assert count <= 18, count


async def test_a_membership_is_read_once_in_a_session(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Every dependency and access check of a request asks for the caller's membership; the
    identity map only holds a row for as long as something else does, so it is held (`hold`)."""
    async with (
        _world(client, test_user_id) as w,
        admin_session_factory() as session,
    ):
        seen: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
            seen.append(statement)

        bind = session.sync_session.get_bind()
        event.listen(bind, "before_cursor_execute", record)
        try:
            first = await membership_of(session, tenant_id=w.tenant, user_id=test_user_id)
            again = await membership_of(session, tenant_id=w.tenant, user_id=test_user_id)
        finally:
            event.remove(bind, "before_cursor_execute", record)
    assert isinstance(first, Membership)
    assert again is first
    assert len(seen) == 1, seen
