"""ADR 0285: what a read of one catalog item costs in statements, and who it shows what.

The bounds are the measured counts (15 or 16) with a little room: they fail when the work an item
read does comes back (the to-one relationships loaded one by one, information visibility resolved
for rows that are all public, the GM's reach for an admin, the prototype chain one hop at a time),
not when someone adds a statement of their own.
"""

import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from _admin_db import admin_session_factory
from conftest import (
    delete_tenant,
    make_campaign,
    make_character,
    make_plain_participant,
    make_player,
    make_tenant,
)
from httpx import AsyncClient
from sqlalchemy import event

from lorenzo_api.db import engine
from lorenzo_api.models import CampaignGm, CharacterPlayer

_SECRET = "the secret of the first book"


@contextmanager
def _statements() -> Iterator[list[str]]:
    seen: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


async def _ok(response):  # type: ignore[no-untyped-def]
    assert response.status_code < 300, response.text
    return response.json()


async def _library(
    client: AsyncClient, tenant: uuid.UUID, *, public_catalog: bool, secret: bool
) -> uuid.UUID:
    """Book <- Spellbook <- Ornate, each with a description; the first book's is private when
    `secret`. The Spellbook's id is returned: an item with an ancestor above and one below it."""
    base = f"/tenants/{tenant}"
    group = await _ok(
        await client.post(
            f"{base}/stat-groups", json={"name": "physical", "priority": 0, "mandatory": False}
        )
    )
    weight = await _ok(
        await client.post(
            f"{base}/stat-definitions",
            json={"name": "weight", "stat_group_id": group["id"], "value_type": "int"},
        )
    )
    made: list[dict[str, str]] = []
    for name, prototypes in (("Book", []), ("Spellbook", [0]), ("Ornate", [1])):
        item = await _ok(
            await client.post(
                f"{base}/items",
                json={
                    "name": name,
                    "prototype_ids": [made[index]["entity_id"] for index in prototypes],
                    "in_public_catalog": public_catalog,
                },
            )
        )
        made.append(item)
        private = secret and name == "Book"
        await _ok(
            await client.post(
                f"{base}/entities/{item['entity_id']}/information",
                json={
                    "title": "",
                    "type": "description",
                    "is_public": not private,
                    "content": _SECRET if private else f"About the {name}.",
                    "locale": "en",
                },
            )
        )
    await _ok(
        await client.put(
            f"{base}/entities/{made[0]['entity_id']}/stats/{weight['id']}",
            json={"value": 2, "acquire_group": False},
        )
    )
    return uuid.UUID(made[1]["entity_id"])


async def _read(client: AsyncClient, tenant: uuid.UUID, item: uuid.UUID) -> tuple[str, int]:
    url = f"/tenants/{tenant}/items/{item}"
    assert (await client.get(url)).status_code == 200  # the first read warms what is cached
    with _statements() as seen:
        response = await client.get(url)
    assert response.status_code == 200
    return response.text, len(seen)


@asynccontextmanager
async def _tenant(client: AsyncClient, user_id: uuid.UUID) -> AsyncIterator[uuid.UUID]:
    tenant = await make_tenant(user_id)
    try:
        yield tenant
    finally:
        await delete_tenant(tenant)


async def test_an_owner_reads_an_item_in_few_statements(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _tenant(client, test_user_id) as tenant:
        item = await _library(client, tenant, public_catalog=False, secret=False)
        _, count = await _read(client, tenant, item)
    assert count <= 18, count


async def test_an_owner_who_also_gms_reads_it_in_as_few(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A GM's reach (what their campaigns' characters own and contain) used to be resolved for
    every read, though an owner sees every row of information whatever it holds."""
    async with _tenant(client, test_user_id) as tenant:
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(CampaignGm(tenant_id=tenant, user_id=test_user_id, campaign_id=campaign.id))
            for number in range(3):
                player = await make_player(session, tenant_id=tenant, campaign_id=campaign.id)
                character = await make_character(
                    session, tenant_id=tenant, name=f"PC{number}", owner_player_id=player.id
                )
                session.add(
                    CharacterPlayer(
                        character_entity_id=character.entity_id,
                        player_id=player.id,
                        tenant_id=tenant,
                    )
                )
            await session.commit()
        item = await _library(client, tenant, public_catalog=False, secret=False)
        _, count = await _read(client, tenant, item)
    assert count <= 18, count


async def test_a_player_reads_a_public_item_in_few_statements(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _tenant(client, test_user_id) as tenant:
        item = await _library(client, tenant, public_catalog=True, secret=False)
        await make_plain_participant(tenant, test_user_id)
        _, count = await _read(client, tenant, item)
    assert count <= 19, count


async def test_an_owner_reads_a_private_description_of_an_ancestor(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with _tenant(client, test_user_id) as tenant:
        item = await _library(client, tenant, public_catalog=False, secret=True)
        body, count = await _read(client, tenant, item)
    assert "About the Spellbook." in body
    assert _SECRET in body
    # A hidden row is among those read, so the owner's tier is resolved, and not their reach.
    assert count <= 20, count


async def test_a_player_does_not_read_it(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    """The row is hidden from someone who may not read it, and their sight is resolved in full."""
    async with _tenant(client, test_user_id) as tenant:
        item = await _library(client, tenant, public_catalog=True, secret=True)
        await make_plain_participant(tenant, test_user_id)
        body, _ = await _read(client, tenant, item)
    assert "About the Spellbook." in body
    assert _SECRET not in body
