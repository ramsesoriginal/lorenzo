"""Private length targets, conditional replacement and operational isolation."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from sqlalchemy import text

from lorenzo_api.db import engine


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_personal_targets(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
):
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    actor = world.author
    base = f"/tenants/{world.tenant_id}/writing"
    try:
        book = (await actor.post(base + "/books", json={"name": "River"})).json()
        edition = book["editions"][0]["id"]
        url = base + f"/entries/{edition}/length-goals/direct"

        async def put(target, version='"0"', person=actor):
            return await raw_client.put(
                url, headers={**person.headers, "If-Match": version}, json={"target_words": target}
            )

        initial = await actor.get(url)
        assert initial.status_code == 200, initial.text
        assert initial.json() == {"target_words": None, "version": 0}
        assert initial.headers["cache-control"] == "private, no-store"
        assert initial.headers["etag"] == '"0"'
        assert (await actor.put(url, json={"target_words": 500})).status_code == 428
        made = await put(500)
        assert made.status_code == 200, made.text
        assert made.json() == {"target_words": 500, "version": 1}
        assert (await put(500)).json() == made.json()
        assert (await put(600)).status_code == 412
        assert (await actor.get(url.replace("/direct", "/assembled"))).json()[
            "target_words"
        ] is None
        assert (await world.owner.get(url)).json()["target_words"] is None
        assert (await put(700, person=world.owner)).status_code == 200
        assert (await actor.get(url)).json()["target_words"] == 500
        cloned = await actor.post(
            base + "/editions", json={"name": "Copy", "source_edition_id": edition}
        )
        assert cloned.status_code == 201, cloned.text
        copy_url = url.replace(edition, cloned.json()["id"])
        assert (await actor.get(copy_url)).json()["target_words"] is None
        async with engine.connect() as conn, conn.begin():
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(world.tenant_id)}
            )
            assert await conn.scalar(text("SELECT count(*) FROM manuscript_goal")) == 2
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :id, true)"), {"id": str(uuid.uuid4())}
            )
            assert await conn.scalar(text("SELECT count(*) FROM manuscript_goal")) == 0
        item = await actor.post(f"/tenants/{world.tenant_id}/items", json={"name": "Pen"})
        invalid_url = url.replace(edition, item.json()["entity_id"])
        assert (await actor.get(invalid_url)).status_code == 404
        review = base + f"/reviews/{edition}/reviewers/{world.outsider.user_id}"
        assert (await actor.put(review)).status_code == 204
        assert (await world.outsider.get(url)).status_code == 404
        assert (await put(900, person=world.outsider)).status_code == 404
        for invalid in [0, -1, 100000001, 1.5, True, "500"]:
            assert (await put(invalid, '"1"')).status_code == 422
        raced = await asyncio.gather(put(800, '"1"'), put(900, '"1"'))
        assert sorted(r.status_code for r in raced) == [200, 412]
        cleared = await put(None, '"2"')
        assert cleared.json() == {"target_words": None, "version": 3}
        assert (await put(800, '"1"')).status_code == 412
        assert (await put(None, '"2"')).json() == cleared.json()
        assert (
            await actor.get(base + f"/entries/{book['id']}/length-goals/direct")
        ).status_code == 422
        async with admin_session_factory() as session:
            assert await session.scalar(
                text("SELECT relforcerowsecurity FROM pg_class WHERE relname='manuscript_goal'")
            )
            assert not await session.scalar(
                text(
                    "SELECT count(*) FROM pg_policies WHERE tablename='manuscript_goal' "
                    "AND policyname='repository_read'"
                )
            )
    finally:
        await world.clean_up()
