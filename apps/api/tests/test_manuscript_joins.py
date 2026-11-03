"""Joins keep one editable manuscript and independently authorize source links."""

import asyncio
import hashlib
import json
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.models import (
    Entity,
    EntityAudience,
    Information,
    ManuscriptJoin,
    ManuscriptRedirect,
    ManuscriptRevision,
    Payload,
    PayloadPicture,
)


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_join_preserves_identity_and_guards_old_source(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    kind: str,
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    copy_id = None
    try:

        async def read(id: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{id}")
            assert response.status_code == 200, response.text
            return response.json()

        async def arrange(id: str, ids: list[str]) -> None:
            response = await raw_client.put(
                base + f"/writing/entries/{id}/composition",
                headers={**actor.headers, "If-Match": (await read(id))["version"]},
                json={"elements": ids},
            )
            assert response.status_code == 200, response.text

        async def chapter(name: str) -> str:
            return (await actor.post(base + "/writing/chapters", json={"name": name})).json()["id"]

        async def manuscript(id: str, prose: str) -> dict:
            response = await actor.post(
                base + f"/entities/{id}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": prose},
            )
            assert response.status_code == 201, response.text
            return response.json()

        book = (await actor.post(base + "/writing/books", json={"name": "Joined book"})).json()
        parent = book["editions"][0]["id"]
        earlier, first, second, child = [
            await chapter(name) for name in ("Earlier", "First", "Second", "Child")
        ]
        first_text = "# Dawn\n\nThe **first** account[^a].\n\n[^a]: First local note."
        second_text = "# Dawn\n\nThe second [[Eira]] account[^a].\n\n[^a]: Different local note."
        first_info = await manuscript(first, first_text)
        second_info = await manuscript(second, second_text)
        first_payload, second_payload = (
            first_info["payloads"][0]["id"],
            second_info["payloads"][0]["id"],
        )
        note = (
            await actor.post(
                base + f"/entities/{second}/information",
                json={"type": "note", "title": "Research", "content": "Keep this note here"},
            )
        ).json()
        picture = uuid.uuid4()
        async with admin_session_factory() as session:
            session.add(
                Payload(
                    id=picture,
                    tenant_id=world.tenant_id,
                    information_id=uuid.UUID(second_info["id"]),
                    order=1,
                )
            )
            await session.flush()
            session.add(
                PayloadPicture(
                    payload_id=picture,
                    tenant_id=world.tenant_id,
                    data=b"original picture",
                    file_type="image/png",
                )
            )
            await session.commit()
        await arrange(second, [second_payload, child, str(picture)])
        await arrange(parent, [earlier, first, second])

        async def request(source: str, destination: str) -> tuple[dict, dict]:
            return (
                {
                    "destination_id": destination,
                    "parent_id": parent,
                    "destination_version": (await read(destination))["version"],
                    "parent_version": (await read(parent))["version"],
                },
                {**actor.headers, "If-Match": (await read(source))["version"]},
            )

        operation = uuid.uuid4()
        url = base + f"/writing/entries/{second}/joins/{operation}"
        body, headers = await request(second, first)
        assert (await actor.post(url, json=body)).status_code == 428
        assert (
            await raw_client.post(url, headers={**headers, "If-Match": 'W/"old"'}, json=body)
        ).status_code == 412
        assert (
            await raw_client.post(
                url, headers=headers, json={**body, "destination_version": 'W/"old"'}
            )
        ).status_code == 412
        nonadjacent, h = await request(second, earlier)
        assert (await raw_client.post(url, headers=h, json=nonadjacent)).status_code == 409
        async with admin_session_factory() as session:
            audience = await session.get(EntityAudience, uuid.UUID(second))
            audience.is_public = True
            await session.commit()
        assert (await raw_client.post(url, headers=headers, json=body)).status_code == 409
        async with admin_session_factory() as session:
            (await session.get(EntityAudience, uuid.UUID(second))).is_public = False
            (await session.get(Information, uuid.UUID(second_info["id"]))).is_public = True
            await session.commit()
        body, headers = await request(second, first)
        assert (await raw_client.post(url, headers=headers, json=body)).status_code == 409
        async with admin_session_factory() as session:
            (await session.get(Information, uuid.UUID(second_info["id"]))).is_public = False
            await session.commit()
        body, headers = await request(second, first)
        assert (await world.outsider.post(url, json=body)).status_code in {403, 404}
        if kind == "repository":
            collision_tenant = await world.owner.create_tenant("Occupied receipt")
            try:
                occupied = [
                    (
                        await world.owner.post(
                            f"/tenants/{collision_tenant}/writing/chapters", json={"name": name}
                        )
                    ).json()["id"]
                    for name in ("Other source", "Other destination")
                ]
                async with admin_session_factory() as session:
                    session.add(
                        ManuscriptJoin(
                            id=operation,
                            tenant_id=collision_tenant,
                            source_id=uuid.UUID(occupied[0]),
                            destination_id=uuid.UUID(occupied[1]),
                            actor_id=world.owner.user_id,
                            request_hash="occupied",
                            checkpoint={},
                        )
                    )
                    await session.commit()
                before = [await read(key) for key in (first, second, parent)]
                collision = await raw_client.post(url, headers=headers, json=body)
                assert collision.status_code == 409, collision.text
                assert [await read(key) for key in (first, second, parent)] == before
            finally:
                await cleanup([collision_tenant], [])
        response = await raw_client.post(url, headers=headers, json=body)
        assert response.status_code == 200, response.text
        # Default-mode retries made before ADR 0374 keep the original fingerprint.
        old_hash = hashlib.sha256(
            json.dumps(
                {"source": second, "version": headers["If-Match"], "body": body},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        async with admin_session_factory() as session:
            assert (await session.get(ManuscriptJoin, operation)).request_hash == old_hash
        assert [e["id"] for e in (await read(parent))["elements"]] == [earlier, first]
        assert [e["id"] for e in (await read(first))["elements"]] == [
            first_payload,
            second_payload,
            child,
            str(picture),
        ]
        source = await read(second)
        assert source["joined"] and source["elements"] == [] and source["parent_id"] is None
        assert source["joined_destination"] == {
            "id": first,
            "name": "First",
            "element_id": second_payload,
        }
        assert note["id"] in {
            info["id"]
            for info in (await actor.get(base + f"/entities/{second}")).json()["information"]
        }
        combined = (await actor.get(base + f"/information/{first_info['id']}")).json()
        assert [p["content"] for p in combined["payloads"] if p["kind"] == "description"] == [
            first_text,
            second_text,
        ]
        async with admin_session_factory() as session:
            assert (await session.get(PayloadPicture, picture)).data == b"original picture"
            snapshots = list(
                await session.scalars(
                    select(ManuscriptRevision).where(
                        ManuscriptRevision.information_id == uuid.UUID(second_info["id"])
                    )
                )
            )
            assert any(
                r.snapshot["payloads"]
                and r.snapshot["payloads"][0]["description"]["content"] == second_text
                for r in snapshots
            )
        history = await actor.get(base + f"/information/{second_info['id']}/revisions")
        assert history.status_code == 200 and history.json()["items"]
        assert (
            await actor.post(
                base + f"/information/{second_info['id']}/texts",
                json={"content": "Duplicate"},
            )
        ).status_code == 409
        assert (
            await actor.patch(base + f"/information/{second_info['id']}", json={"type": "note"})
        ).status_code == 409
        assert (
            await actor.post(
                base + f"/entities/{second}/information",
                json={"type": "manuscript", "title": "Again", "content": "Duplicate"},
            )
        ).status_code == 409
        denied = await raw_client.put(
            base + f"/writing/entries/{parent}/composition",
            headers={**actor.headers, "If-Match": (await read(parent))["version"]},
            json={"elements": [earlier, first, second]},
        )
        assert denied.status_code == 409, denied.text
        assert (
            await actor.patch(base + f"/information/{note['id']}", json={"title": "Still editable"})
        ).status_code == 200
        replay = await raw_client.post(url, headers=headers, json=body)
        assert replay.json() == response.json()
        assert (
            await raw_client.post(
                url, headers={**world.owner.headers, "If-Match": headers["If-Match"]}, json=body
            )
        ).status_code == 409

        # A subsequent join flattens incoming redirects while retaining the stable anchor.
        next_body, next_headers = await request(first, earlier)
        next_url = base + f"/writing/entries/{first}/joins/{uuid.uuid4()}"
        joined = await raw_client.post(next_url, headers=next_headers, json=next_body)
        assert joined.status_code == 200, joined.text
        assert (await read(second))["joined_destination"]["id"] == earlier
        assert (await read(second))["joined_destination"]["element_id"] == second_payload
        assert (await raw_client.post(url, headers=headers, json=body)).json() == response.json()
        if kind == "repository":
            copy_id = await world.owner.create_tenant("Join copy")
            await world.owner.put(base + f"/subscribers/{copy_id}")
            assert (await world.owner.put(base + "/published")).status_code == 200
            copied = await world.owner.post(
                f"/tenants/{copy_id}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            async with admin_session_factory() as session:
                copied_source = await session.scalar(
                    select(Entity.id).where(Entity.tenant_id == copy_id, Entity.name == "Second")
                )
                redirect = await session.get(ManuscriptRedirect, copied_source)
                assert redirect.destination_id != uuid.UUID(
                    earlier
                ) and redirect.payload_id != uuid.UUID(second_payload)
                assert not list(
                    await session.scalars(
                        select(ManuscriptJoin).where(ManuscriptJoin.tenant_id == copy_id)
                    )
                )
            copied_read = await world.owner.get(
                f"/tenants/{copy_id}/writing/entries/{copied_source}"
            )
            assert copied_read.json()["joined_destination"]["name"] == "Earlier"
        else:
            from conftest import make_campaign

            from lorenzo_api.models import Player

            async with admin_session_factory() as session:
                campaign = await make_campaign(session, tenant_id=world.tenant_id)
                session.add(
                    Player(
                        tenant_id=world.tenant_id,
                        campaign_id=campaign.id,
                        user_id=world.outsider.user_id,
                    )
                )
                (await session.get(EntityAudience, uuid.UUID(second))).is_public = True
                await session.commit()
            hidden = await world.outsider.get(base + f"/writing/entries/{second}")
            assert hidden.status_code == 200, hidden.text
            assert hidden.json()["joined_destination"] is None and earlier not in hidden.text
            async with admin_session_factory() as session:
                (await session.get(EntityAudience, uuid.UUID(earlier))).is_public = True
                await session.commit()
            assert (await world.outsider.get(base + f"/writing/entries/{second}")).json()[
                "joined_destination"
            ] is None
            async with admin_session_factory() as session:
                info_id = (await session.get(Payload, uuid.UUID(second_payload))).information_id
                (await session.get(Information, info_id)).is_public = True
                await session.commit()
            assert (await world.outsider.get(base + f"/writing/entries/{second}")).json()[
                "joined_destination"
            ]["id"] == earlier
        # Removing the anchor retains an unavailable joined marker, never a fresh editor.
        async with admin_session_factory() as session:
            await session.delete(await session.get(Payload, uuid.UUID(second_payload)))
            await session.commit()
        assert (await read(second))["joined"]
        assert (await read(second))["joined_destination"] is None
    finally:
        if copy_id:
            await cleanup([copy_id], [])
        await world.clean_up()


async def test_join_tables_force_rls_and_classify_content() -> None:
    from lorenzo_api.copyable_tables import CONTENT_TABLES, EXCLUDED_TABLES

    assert "manuscript_redirect" in CONTENT_TABLES
    assert "manuscript_join" in EXCLUDED_TABLES
    async with admin_session_factory() as session:
        for table in ("manuscript_redirect", "manuscript_join"):
            row = (
                await session.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                        "WHERE relname=:name"
                    ),
                    {"name": table},
                )
            ).one()
            assert row == (True, True)


async def test_join_contextual_readers_concurrency_and_child_anchor(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from conftest import make_campaign

    from lorenzo_api.models import CampaignGm, Tenant

    world = await make_world(raw_client, fake_jwks_server)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:

        async def read(id: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{id}")
            assert response.status_code == 200, response.text
            return response.json()

        async def arrange(id: str, ids: list[str]) -> None:
            response = await raw_client.put(
                base + f"/writing/entries/{id}/composition",
                headers={**actor.headers, "If-Match": (await read(id))["version"]},
                json={"elements": ids},
            )
            assert response.status_code == 200, response.text

        book = (await actor.post(base + "/writing/books", json={"name": "Join guards"})).json()
        parent = book["editions"][0]["id"]
        destination, source, child = [
            (await actor.post(base + "/writing/chapters", json={"name": name})).json()["id"]
            for name in ("Destination", "Source", "Child anchor")
        ]
        info = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "Private prose"},
            )
        ).json()
        await arrange(source, [child, info["payloads"][0]["id"]])
        await arrange(parent, [destination, source])
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=world.tenant_id)
            session.add(
                CampaignGm(
                    tenant_id=world.tenant_id,
                    campaign_id=campaign.id,
                    user_id=world.outsider.user_id,
                )
            )
            (await session.get(Tenant, world.tenant_id)).npcs_shared_with_gms = False
            for id in (source, destination):
                (await session.get(EntityAudience, uuid.UUID(id))).is_public = True
            (await session.get(Entity, uuid.UUID(destination))).created_by = world.outsider.user_id
            await session.commit()
        body = {
            "destination_id": destination,
            "parent_id": parent,
            "destination_version": (await read(destination))["version"],
            "parent_version": (await read(parent))["version"],
        }
        headers = {**actor.headers, "If-Match": (await read(source))["version"]}
        url = base + f"/writing/entries/{source}/joins/"
        denied = await raw_client.post(url + str(uuid.uuid4()), headers=headers, json=body)
        assert denied.status_code == 409 and "campaign access" in denied.text, denied.text
        assert not (await read(source))["joined"]
        async with admin_session_factory() as session:
            (await session.get(Entity, uuid.UUID(destination))).created_by = actor.user_id
            await session.commit()
        body["destination_version"] = (await read(destination))["version"]
        replies = await asyncio.gather(
            *[
                raw_client.post(url + str(uuid.uuid4()), headers=headers, json=body)
                for _ in range(2)
            ]
        )
        assert sorted(r.status_code for r in replies) == [200, 409], [r.text for r in replies]
        assert (await read(source))["joined_destination"]["element_id"] == child
        async with admin_session_factory() as session:
            await session.delete(await session.get(Entity, uuid.UUID(child)))
            await session.commit()
        assert (await read(source))["joined_destination"] is None
        async with admin_session_factory() as session:
            await session.delete(await session.get(Entity, uuid.UUID(destination)))
            await session.commit()
        state = await read(source)
        assert state["joined"] and state["joined_destination"] is None
    finally:
        await world.clean_up()
