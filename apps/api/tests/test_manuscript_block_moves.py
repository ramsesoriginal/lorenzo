"""A text moves from one Chapter's manuscript to another's (ADR 0520)."""

import uuid

from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient


async def test_move_a_text_to_another_chapter(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="play")
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    try:

        async def read(id: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{id}")
            assert response.status_code == 200, response.text
            return response.json()

        async def chapter(name: str, prose: str) -> tuple[str, str]:
            made = (await actor.post(base + "/writing/chapters", json={"name": name})).json()["id"]
            info = await actor.post(
                base + f"/entities/{made}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": prose},
            )
            assert info.status_code == 201, info.text
            return made, info.json()["payloads"][0]["id"]

        first, first_text = await chapter("First", "First words.")
        second, second_text = await chapter("Second", "Second words.")
        url = base + f"/writing/entries/{first}/payloads/{first_text}/move"
        body = {"destination_id": second, "destination_version": (await read(second))["version"]}
        assert (await actor.post(url, json=body)).status_code == 428
        stale = await raw_client.post(
            url, headers={**actor.headers, "If-Match": 'W/"old"'}, json=body
        )
        assert stale.status_code == 412
        assert (await world.outsider.post(url, json=body)).status_code in {403, 404, 428}
        moved = await raw_client.post(
            url, headers={**actor.headers, "If-Match": (await read(first))["version"]}, json=body
        )
        assert moved.status_code == 200, moved.text
        assert [el["id"] for el in (await read(first))["elements"]] == []
        assert [el["id"] for el in (await read(second))["elements"]] == [second_text, first_text]
        again = await raw_client.post(
            url, headers={**actor.headers, "If-Match": (await read(first))["version"]}, json=body
        )
        # A repeat is refused: the destination has changed since the body was written.
        assert again.status_code == 412
        wrong = await raw_client.post(
            base + f"/writing/entries/{second}/payloads/{uuid.uuid4()}/move",
            headers={**actor.headers, "If-Match": (await read(second))["version"]},
            json={"destination_id": first, "destination_version": (await read(first))["version"]},
        )
        assert wrong.status_code == 409
        fresh = (await actor.get(base + f"/entities/{second}")).json()
        manuscript = next(i for i in fresh["information"] if i["type"] == "manuscript")
        assert sorted(p["content"] for p in manuscript["payloads"]) == [
            "First words.",
            "Second words.",
        ]
    finally:
        await world.clean_up()
