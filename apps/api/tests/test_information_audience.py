"""Atomic sharing (ADR 0304), exercised through the real API and database."""

import asyncio
import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import Entity, Knowledge, Membership, Player


async def setup_note(client: AsyncClient, user: uuid.UUID) -> tuple[uuid.UUID, str, str, uuid.UUID]:
    tenant = await make_tenant(user)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant)
        player = Player(user_id=user, campaign_id=campaign.id, tenant_id=tenant)
        entry = Entity(tenant_id=tenant, name="Map")
        group = Entity(tenant_id=tenant, name="Harpers")
        session.add_all([player, entry, group])
        await session.commit()
        entry_id, group_id, player_id = entry.id, group.id, player.id
    made = await client.post(
        f"/tenants/{tenant}/entities/{entry_id}/information",
        json={"title": "A map", "type": "note", "is_public": False, "content": "The old road."},
    )
    assert made.status_code == 201, made.text
    return tenant, f"/tenants/{tenant}/information/{made.json()['id']}", str(group_id), player_id


async def test_audience_replace_is_atomic_and_versioned(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, group, player = await setup_note(client, test_user_id)
    try:
        before = await client.get(base + "/audience")
        assert before.status_code == 200, before.text
        body = {"is_public": False, "entity_ids": [group], "player_ids": [str(player)]}
        missing = await client.put(base + "/audience", json=body)
        assert missing.status_code == 428
        changed = await client.put(
            base + "/audience", json=body, headers={"If-Match": before.headers["etag"]}
        )
        assert changed.status_code == 200, changed.text
        assert changed.json() == {**body, "shared_with_participants": False}
        assert changed.headers["etag"] != before.headers["etag"]
        # An old form cannot clear a more recent share.
        stale = await client.put(
            base + "/audience",
            json={"is_public": True},
            headers={"If-Match": before.headers["etag"]},
        )
        assert stale.status_code == 412
        unchanged = await client.put(
            base + "/audience", json=body, headers={"If-Match": changed.headers["etag"]}
        )
        assert unchanged.headers["etag"] == changed.headers["etag"]
        bad = await client.put(
            base + "/audience",
            json={"is_public": True, "entity_ids": [str(uuid.uuid4())]},
            headers={"If-Match": changed.headers["etag"]},
        )
        assert bad.status_code == 422
        assert (await client.get(base + "/audience")).json() == {
            **body,
            "shared_with_participants": False,
        }
        cleared = await client.put(
            base + "/audience",
            json={"is_public": True},
            headers={"If-Match": changed.headers["etag"]},
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json() == {
            "is_public": True,
            "shared_with_participants": False,
            "entity_ids": [],
            "player_ids": [],
        }
        async with admin_session_factory() as session:
            assert not (
                await session.execute(select(Knowledge.id).where(Knowledge.tenant_id == tenant))
            ).all()
    finally:
        await delete_tenant(tenant)


async def test_legacy_grant_invalidates_an_open_audience_form(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, group, _ = await setup_note(client, test_user_id)
    try:
        before = await client.get(base + "/audience")
        grant = await client.put(base + "/knowers/" + group)
        assert grant.status_code == 200, grant.text
        stale = await client.put(
            base + "/audience",
            json={"is_public": False},
            headers={"If-Match": before.headers["etag"]},
        )
        assert stale.status_code == 412
        assert (await client.get(base + "/audience")).json()["entity_ids"] == [group]
    finally:
        await delete_tenant(tenant)


async def test_other_library_cannot_read_or_replace_audience(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, _, _ = await setup_note(client, test_user_id)
    other = await make_tenant(test_user_id)
    try:
        wrong = base.replace(str(tenant), str(other)) + "/audience"
        assert (await client.get(wrong)).status_code == 404
        assert (await client.put(wrong, json={"is_public": True})).status_code == 404
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)


async def test_only_one_concurrent_audience_replacement_wins(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, group, player = await setup_note(client, test_user_id)
    try:
        before = await client.get(base + "/audience")
        headers = {"If-Match": before.headers["etag"]}
        responses = await asyncio.gather(
            client.put(
                base + "/audience",
                json={"is_public": False, "entity_ids": [group]},
                headers=headers,
            ),
            client.put(
                base + "/audience",
                json={"is_public": False, "player_ids": [str(player)]},
                headers=headers,
            ),
        )
        assert sorted(response.status_code for response in responses) == [200, 412]
        winner = next(response.json() for response in responses if response.status_code == 200)
        assert (await client.get(base + "/audience")).json() == winner
    finally:
        await delete_tenant(tenant)


async def test_knowing_a_note_does_not_allow_inspecting_or_changing_its_audience(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, _, player = await setup_note(client, test_user_id)
    try:
        before = await client.get(base + "/audience")
        shared = await client.put(
            base + "/audience",
            json={"is_public": False, "player_ids": [str(player)]},
            headers={"If-Match": before.headers["etag"]},
        )
        assert shared.status_code == 200, shared.text
        # The account keeps its campaign seat but loses administrative/authoring standing.
        async with admin_session_factory() as session:
            await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
            await session.commit()
        assert (await client.get(base)).status_code == 200
        assert (await client.get(base + "/audience")).status_code == 403
        assert (
            await client.put(
                base + "/audience",
                json={"is_public": True},
                headers={"If-Match": shared.headers["etag"]},
            )
        ).status_code == 403
    finally:
        await delete_tenant(tenant)
