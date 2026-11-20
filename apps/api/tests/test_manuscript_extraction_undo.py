"""Undoing a Chapter or Scene extraction puts the writing back (ADR 0515, 0517)."""

import uuid

from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient


async def test_undo_a_chapter_extraction(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="play")
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    try:
        book = (await actor.post(base + "/writing/books", json={"name": "Voyage"})).json()
        source = book["editions"][0]["id"]
        info = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "Kept words."},
            )
        ).json()
        payload = info["payloads"][0]["id"]
        child = (await actor.post(base + "/writing/chapters", json={"name": "A child"})).json()[
            "id"
        ]
        outline = (await actor.get(base + f"/writing/entries/{source}")).json()
        placed = await raw_client.put(
            base + f"/writing/entries/{source}/composition",
            headers={**actor.headers, "If-Match": outline["version"]},
            json={"elements": [payload, child]},
        )
        assert placed.status_code == 200, placed.text
        outline = (await actor.get(base + f"/writing/entries/{source}")).json()
        chapter, operation = str(uuid.uuid4()), uuid.uuid4()
        url = base + f"/writing/entries/{source}/extractions/{operation}"
        made = await raw_client.post(
            url,
            headers={**actor.headers, "If-Match": outline["version"]},
            json={"chapter_id": chapter, "name": "Carved out", "elements": [payload, child]},
        )
        assert made.status_code == 200, made.text

        async def version() -> str:
            return (await actor.get(base + f"/writing/entries/{source}")).json()["version"]

        assert (await actor.delete(url)).status_code == 428
        assert (
            await raw_client.delete(url, headers={**actor.headers, "If-Match": 'W/"old"'})
        ).status_code == 412
        assert (await world.outsider.delete(url)).status_code in {403, 404}
        undone = await raw_client.delete(
            url, headers={**actor.headers, "If-Match": await version()}
        )
        assert undone.status_code == 200, undone.text
        back = (await actor.get(base + f"/writing/entries/{source}")).json()
        assert [el["id"] for el in back["elements"]] == [payload, child]
        assert (await actor.get(base + f"/entities/{chapter}")).status_code == 404
        fresh = (await actor.get(base + f"/entities/{source}")).json()
        manuscript = next(i for i in fresh["information"] if i["type"] == "manuscript")
        assert [p["content"] for p in manuscript["payloads"]] == ["Kept words."]
        again = await raw_client.delete(url, headers={**actor.headers, "If-Match": await version()})
        assert again.status_code == 404
    finally:
        await world.clean_up()


async def test_undo_a_scene_extraction(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="play")
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    try:
        book = (await actor.post(base + "/writing/books", json={"name": "Voyage"})).json()
        source = book["editions"][0]["id"]
        info = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "Scene words."},
            )
        ).json()
        payload = info["payloads"][0]["id"]
        child = (await actor.post(base + "/writing/chapters", json={"name": "A child"})).json()[
            "id"
        ]
        outline = (await actor.get(base + f"/writing/entries/{source}")).json()
        placed = await raw_client.put(
            base + f"/writing/entries/{source}/composition",
            headers={**actor.headers, "If-Match": outline["version"]},
            json={"elements": [payload, child]},
        )
        assert placed.status_code == 200, placed.text
        outline = (await actor.get(base + f"/writing/entries/{source}")).json()
        scene, telling, operation = str(uuid.uuid4()), str(uuid.uuid4()), uuid.uuid4()
        made = await raw_client.post(
            base + f"/writing/entries/{source}/scene-extractions/{operation}",
            headers={**actor.headers, "If-Match": outline["version"]},
            json={
                "scene_id": scene,
                "telling_id": telling,
                "name": "Carved",
                "elements": [payload],
            },
        )
        assert made.status_code == 200, made.text
        url = base + f"/writing/entries/{source}/extractions/{operation}"

        async def version() -> str:
            return (await actor.get(base + f"/writing/entries/{source}")).json()["version"]

        assert (await world.outsider.delete(url)).status_code in {403, 404}
        undone = await raw_client.delete(
            url, headers={**actor.headers, "If-Match": await version()}
        )
        assert undone.status_code == 200, undone.text
        back = (await actor.get(base + f"/writing/entries/{source}")).json()
        assert [el["id"] for el in back["elements"]] == [payload, child]
        assert (await actor.get(base + f"/entities/{scene}")).status_code == 404
        assert (await actor.get(base + f"/entities/{telling}")).status_code == 404
        fresh = (await actor.get(base + f"/entities/{source}")).json()
        manuscript = next(i for i in fresh["information"] if i["type"] == "manuscript")
        assert [p["content"] for p in manuscript["payloads"]] == ["Scene words."]
    finally:
        await world.clean_up()
