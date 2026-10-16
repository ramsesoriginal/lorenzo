"""Ordered information bundles and lost-response retries (ADR 0306)."""

import asyncio
import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Entity, Membership, Player


async def bundle(client: AsyncClient, user: uuid.UUID) -> tuple[uuid.UUID, str, dict]:
    tenant = await make_tenant(user)
    async with admin_session_factory() as session:
        entry = Entity(tenant_id=tenant, name="A map")
        session.add(entry)
        await session.commit()
        entry_id = entry.id
    created = await client.post(
        f"/tenants/{tenant}/entities/{entry_id}/information",
        json={"title": "Map", "type": "note", "is_public": False, "content": "First text."},
    )
    assert created.status_code == 201, created.text
    return tenant, f"/tenants/{tenant}/information/{created.json()['id']}", created.json()


async def version(client: AsyncClient, base: str) -> dict[str, str]:
    response = await client.get(base)
    assert response.status_code == 200, response.text
    return {"If-Match": response.headers["etag"]}


async def test_text_append_replay_order_and_removal(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, first = await bundle(client, test_user_id)
    try:
        headers = await version(client, base)
        body = {"id": str(uuid.uuid4()), "content": "Second [[road]] text."}
        assert (await client.post(base + "/texts", json=body)).status_code == 428
        added = await client.post(base + "/texts", json=body, headers=headers)
        assert added.status_code == 201, added.text
        replay = await client.post(base + "/texts", json=body, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["id"] == added.json()["id"]
        conflict = await client.post(
            base + "/texts", json={**body, "content": "Different"}, headers=headers
        )
        assert conflict.status_code == 409
        stale = await client.post(base + "/texts", json={"content": "Third"}, headers=headers)
        assert stale.status_code == 412
        current = await client.get(base)
        ids = [p["id"] for p in current.json()["payloads"]]
        assert ids == [first["payloads"][0]["id"], body["id"]]
        order = {"payload_ids": list(reversed(ids))}
        ordered = await client.put(
            base + "/payloads/order", json=order, headers=await version(client, base)
        )
        assert ordered.status_code == 200, ordered.text
        assert [p["id"] for p in ordered.json()["payloads"]] == list(reversed(ids))
        assert (
            await client.put(
                base + "/payloads/order", json=order, headers={"If-Match": current.headers["etag"]}
            )
        ).status_code == 412
        for bad in (ids[:1], [ids[0], ids[0]], [str(uuid.uuid4()), ids[1]]):
            assert (
                await client.put(
                    base + "/payloads/order",
                    json={"payload_ids": bad},
                    headers=await version(client, base),
                )
            ).status_code == 409
        payload_url = f"/tenants/{tenant}/payloads/{body['id']}"
        assert (await client.delete(payload_url)).status_code == 428
        assert (
            await client.delete(
                payload_url,
                headers={"If-Match": f'W/"{ordered.json()["payloads"][0]["updated_at"]}"'},
            )
        ).status_code == 204
        remaining = (await client.get(base)).json()
        assert [p["content"] for p in remaining["payloads"]] == ["First text."]
        assert not remaining["is_public"]
        assert (await client.get(base + "/audience")).json() == {
            "is_public": False,
            "entity_ids": [],
            "player_ids": [],
        }
    finally:
        await delete_tenant(tenant)


async def test_picture_append_replays_without_duplicates_or_sharing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, _ = await bundle(client, test_user_id)
    try:
        headers = await version(client, base)
        payload_id = str(uuid.uuid4())
        image = {"file": ("map.png", b"picture bytes", "image/png")}
        first = await client.post(
            base + "/payloads", files=image, data={"payload_id": payload_id}, headers=headers
        )
        assert first.status_code == 201, first.text
        replay = await client.post(
            base + "/payloads", files=image, data={"payload_id": payload_id}, headers=headers
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["id"] == payload_id
        wrong = await client.post(
            base + "/payloads",
            files={"file": ("map.png", b"other bytes", "image/png")},
            data={"payload_id": payload_id},
            headers=headers,
        )
        assert wrong.status_code == 409
        note = (await client.get(base)).json()
        assert [p["kind"] for p in note["payloads"]] == ["description", "picture"]
        assert not note["is_public"]
        data = await client.get(f"/tenants/{tenant}/payloads/{payload_id}/content")
        assert data.content == b"picture bytes"
    finally:
        await delete_tenant(tenant)


async def test_concurrent_appends_require_one_current_bundle_version(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, _ = await bundle(client, test_user_id)
    try:
        headers = await version(client, base)
        outcomes = await asyncio.gather(
            *[
                client.post(base + "/texts", json={"content": text}, headers=headers)
                for text in ("One", "Two")
            ]
        )
        assert sorted(r.status_code for r in outcomes) == [201, 412]
        assert len((await client.get(base)).json()["payloads"]) == 2
        headers = await version(client, base)
        body = {"id": str(uuid.uuid4()), "content": "One stable append"}
        outcomes = await asyncio.gather(
            *[client.post(base + "/texts", json=body, headers=headers) for _ in range(2)]
        )
        assert sorted(r.status_code for r in outcomes) == [200, 201]
        assert len((await client.get(base)).json()["payloads"]) == 3
    finally:
        await delete_tenant(tenant)


async def test_replay_still_requires_edit_standing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, _ = await bundle(client, test_user_id)
    try:
        body = {"id": str(uuid.uuid4()), "content": "A text"}
        added = await client.post(base + "/texts", json=body, headers=await version(client, base))
        assert added.status_code == 201, added.text
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(Player(tenant_id=tenant, user_id=test_user_id, campaign_id=campaign.id))
            await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
            await session.commit()
        denied = await client.post(base + "/texts", json=body)
        assert denied.status_code == 403, denied.text
    finally:
        await delete_tenant(tenant)


async def test_deleting_text_checks_the_payload_version_not_just_membership(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, info = await bundle(client, test_user_id)
    try:
        payload = info["payloads"][0]
        url = f"/tenants/{tenant}/payloads/{payload['id']}"
        old = {"If-Match": f'W/"{payload["updated_at"]}"'}
        changed = await client.patch(url, json={"content": "A newer explanation"}, headers=old)
        assert changed.status_code == 200, changed.text
        stale = await client.delete(url, headers=old)
        assert stale.status_code == 412, stale.text
        assert (await client.get(base)).json()["payloads"][0]["content"] == "A newer explanation"
    finally:
        await delete_tenant(tenant)


async def test_a_participant_can_read_a_shared_picture_without_author_membership(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, base, _ = await bundle(client, test_user_id)
    try:
        picture = await client.post(
            base + "/payloads", files={"file": ("map.png", b"picture", "image/png")}
        )
        assert picture.status_code == 201, picture.text
        shared = await client.patch(
            base, json={"is_public": True}, headers=await version(client, base)
        )
        assert shared.status_code == 200, shared.text
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(Player(tenant_id=tenant, user_id=test_user_id, campaign_id=campaign.id))
            await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
            await session.commit()
        content = await client.get(f"/tenants/{tenant}/payloads/{picture.json()['id']}/content")
        assert content.status_code == 200, content.text
        assert content.content == b"picture"
    finally:
        await delete_tenant(tenant)
