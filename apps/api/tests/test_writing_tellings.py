"""Tellings retain independent identity, authorship scope and source authorization."""

import uuid

import pytest
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_shared_and_independent_tellings(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    try:
        actor = world.author
        base = f"/tenants/{world.tenant_id}"
        scene = (await actor.post(base + "/scenes", json={"name": "The crossing"})).json()["id"]
        prose = await actor.post(
            base + f"/entities/{scene}/information",
            json={"type": "manuscript", "title": "Manuscript", "content": "The boat left."},
        )
        assert prose.status_code == 201, prose.text
        bio = await actor.post(base + "/writing/biographies", json={"name": "The ferryman"})
        assert bio.status_code == 201, bio.text
        viewpoint = bio.json()["id"]
        assert (
            await actor.post(
                base + f"/entities/{viewpoint}/information",
                json={"type": "manuscript", "title": "Biography", "content": "He knows the river."},
            )
        ).status_code == 201
        body = {
            "id": str(uuid.uuid4()),
            "name": "Across the river",
            "scene_id": scene,
            "viewpoint_id": viewpoint,
        }
        made = await actor.post(base + "/writing/tellings", json=body)
        assert made.status_code == 201, made.text
        first = made.json()
        assert first["manuscript_source_id"] == scene
        assert first["elements"][0]["id"] == prose.json()["payloads"][0]["id"]
        assert (await actor.post(base + "/writing/tellings", json=body)).status_code == 200
        blocked = await actor.post(
            base + f"/entities/{first['id']}/information",
            json={"type": "manuscript", "title": "Manuscript", "content": "No implicit override"},
        )
        assert blocked.status_code == 409, blocked.text
        second = await actor.post(
            base + "/writing/tellings", json={"name": "Another view", "scene_id": scene}
        )
        assert second.status_code == 201, second.text
        independent_url = base + f"/writing/tellings/{first['id']}/independent"
        assert (await actor.post(independent_url)).status_code == 428
        copied = await raw_client.post(
            independent_url, headers={**actor.headers, "If-Match": first["version"]}
        )
        assert copied.status_code == 200, copied.text
        assert copied.json()["manuscript_source_id"] == first["id"]
        assert copied.json()["elements"][0]["id"] != prose.json()["payloads"][0]["id"]
        assert (await actor.post(independent_url)).status_code == 200
        original = (await actor.get(base + f"/writing/entries/{second.json()['id']}")).json()
        assert original["manuscript_source_id"] == scene
        assert (
            await world.outsider.get(base + f"/writing/entries/{first['id']}")
        ).status_code == 404
        assert (await actor.delete(base + f"/entities/{scene}")).status_code == 409
        assert (await actor.delete(base + f"/entities/{viewpoint}")).status_code == 409
        book = (await actor.post(base + "/writing/books", json={"name": "Journeys"})).json()
        edition = book["editions"][0]["id"]
        outline = (await actor.get(base + f"/writing/entries/{edition}")).json()
        order = await raw_client.put(
            base + f"/writing/entries/{edition}/composition",
            headers={**actor.headers, "If-Match": outline["version"]},
            json={"elements": [first["id"], second.json()["id"]]},
        )
        assert order.status_code == 200, order.text
        assert [e["kind"] for e in order.json()["elements"]] == ["scene_telling", "scene_telling"]
        clone = await actor.post(
            base + "/writing/editions", json={"name": "Revision", "source_edition_id": edition}
        )
        assert clone.status_code == 201, clone.text
        cloned = [
            (await actor.get(base + f"/writing/entries/{el['id']}")).json()
            for el in clone.json()["elements"]
        ]
        assert not cloned[0]["uses_scene_manuscript"]
        assert cloned[1]["uses_scene_manuscript"]
        assert cloned[0]["scene_id"] == scene
        assert cloned[0]["viewpoint_id"] == viewpoint
    finally:
        await world.clean_up()


async def test_shared_telling_does_not_reveal_hidden_source_or_grant_campaign_powers(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from _admin_db import admin_session_factory
    from conftest import make_campaign

    from lorenzo_api.models import EntityAudience, Player

    world = await make_world(raw_client, fake_jwks_server)
    try:
        base = f"/tenants/{world.tenant_id}"
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=world.tenant_id)
            session.add(
                Player(
                    tenant_id=world.tenant_id,
                    campaign_id=campaign.id,
                    user_id=world.outsider.user_id,
                )
            )
            await session.commit()
        scene = (await world.author.post(base + "/scenes", json={"name": "Secret scene"})).json()[
            "id"
        ]
        text = await world.author.post(
            base + f"/entities/{scene}/information",
            json={"type": "manuscript", "title": "Manuscript", "content": "Private text"},
        )
        assert text.status_code == 201, text.text
        telling = (
            await world.author.post(
                base + "/writing/tellings", json={"name": "Visible telling", "scene_id": scene}
            )
        ).json()
        async with admin_session_factory() as session:
            audience = await session.get(EntityAudience, uuid.UUID(telling["id"]))
            assert audience is not None
            audience.is_public = True
            await session.commit()
        read = await world.outsider.get(base + f"/writing/entries/{telling['id']}")
        assert read.status_code == 200, read.text
        assert read.json()["scene_id"] is None
        assert read.json()["manuscript_source_id"] is None
        assert read.json()["elements"] == []
        assert scene not in read.text and "Private text" not in read.text
        assert (
            await world.outsider.get(base + f"/information/{text.json()['id']}")
        ).status_code == 404
        denied = await world.outsider.post(base + f"/writing/tellings/{telling['id']}/independent")
        assert denied.status_code == 403, denied.text
        ordinary = await world.owner.post(
            base + "/entities",
            json={"name": "Campaign NPC", "kinds": ["being"]},
        )
        assert ordinary.status_code == 201, ordinary.text
        changed = await world.author.patch(
            base + f"/entities/{ordinary.json()['id']}", json={"name": "Unauthorized rename"}
        )
        assert changed.status_code == 403, changed.text
        # Even when the Scene entry is visible, its private bundle stays private.
        async with admin_session_factory() as session:
            audience = await session.get(EntityAudience, uuid.UUID(scene))
            assert audience is not None
            audience.is_public = True
            await session.commit()
        read = await world.outsider.get(base + f"/writing/entries/{telling['id']}")
        assert read.json()["scene_id"] == scene
        assert read.json()["elements"] == []
    finally:
        await world.clean_up()
