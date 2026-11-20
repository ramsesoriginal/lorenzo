"""Undoing a split joins the two texts again, once, and only while nothing else has changed
(ADR 0513)."""

import uuid

from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup
from httpx import AsyncClient


async def test_undo_a_split(raw_client: AsyncClient, fake_jwks_server: FakeJwksServer) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="play")
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    try:
        chapter = (await actor.post(base + "/writing/chapters", json={"name": "Undo me"})).json()[
            "id"
        ]
        original = "First section.\n\nSecond section."
        info = (
            await actor.post(
                base + f"/entities/{chapter}/information",
                json={"title": "Manuscript", "type": "manuscript", "content": original},
            )
        ).json()
        first = info["payloads"][0]["id"]
        points = await actor.get(base + f"/writing/entries/{chapter}/payloads/{first}/split-points")
        offset = points.json()["points"][0]["offset"]
        second = str(uuid.uuid4())
        operation = uuid.uuid4()
        split_url = base + f"/writing/entries/{chapter}/splits/{operation}"
        made = await raw_client.post(
            split_url,
            headers={**actor.headers, "If-Match": points.json()["version"]},
            json={"payload_id": first, "second_payload_id": second, "offset": offset},
        )
        assert made.status_code == 200, made.text

        async def version() -> str:
            return (await actor.get(base + f"/writing/entries/{chapter}")).json()["version"]

        async def texts() -> list[str]:
            fresh = (await actor.get(base + f"/entities/{chapter}")).json()
            manuscript = next(i for i in fresh["information"] if i["type"] == "manuscript")
            return [p["content"] for p in manuscript["payloads"]]

        assert len(await texts()) == 2
        # Needs the version the caller read; a stale one is refused; a stranger finds nothing.
        assert (await actor.delete(split_url)).status_code == 428
        assert (
            await raw_client.delete(split_url, headers={**actor.headers, "If-Match": 'W/"old"'})
        ).status_code == 412
        assert (await world.outsider.delete(split_url)).status_code in {403, 404}
        undone = await raw_client.delete(
            split_url, headers={**actor.headers, "If-Match": await version()}
        )
        assert undone.status_code == 200, undone.text
        assert await texts() == [original]
        # Once: the receipt went with the second text.
        again = await raw_client.delete(
            split_url, headers={**actor.headers, "If-Match": await version()}
        )
        assert again.status_code == 404
    finally:
        await cleanup([], [])
        await world.clean_up()
