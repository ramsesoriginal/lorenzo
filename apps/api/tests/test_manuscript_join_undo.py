"""Undoing a join splits the Chapter back out and restores both outlines (ADR 0518)."""

import uuid

from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient


async def test_undo_a_join(raw_client: AsyncClient, fake_jwks_server: FakeJwksServer) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="play")
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    try:

        async def read(id: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{id}")
            assert response.status_code == 200, response.text
            return response.json()

        async def chapter(name: str) -> str:
            return (await actor.post(base + "/writing/chapters", json={"name": name})).json()["id"]

        async def manuscript(id: str, prose: str) -> str:
            response = await actor.post(
                base + f"/entities/{id}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": prose},
            )
            assert response.status_code == 201, response.text
            return response.json()["payloads"][0]["id"]

        async def arrange(id: str, ids: list[str]) -> None:
            response = await raw_client.put(
                base + f"/writing/entries/{id}/composition",
                headers={**actor.headers, "If-Match": (await read(id))["version"]},
                json={"elements": ids},
            )
            assert response.status_code == 200, response.text

        book = (await actor.post(base + "/writing/books", json={"name": "Joined book"})).json()
        parent = book["editions"][0]["id"]
        first, second = await chapter("First"), await chapter("Second")
        first_text = await manuscript(first, "First words.")
        second_text = await manuscript(second, "Second words.")
        await arrange(parent, [first, second])

        operation = uuid.uuid4()
        url = base + f"/writing/entries/{second}/joins/{operation}"
        joined = await raw_client.post(
            url,
            headers={**actor.headers, "If-Match": (await read(second))["version"]},
            json={
                "destination_id": first,
                "parent_id": parent,
                "destination_version": (await read(first))["version"],
                "parent_version": (await read(parent))["version"],
            },
        )
        assert joined.status_code == 200, joined.text
        assert [el["id"] for el in (await read(first))["elements"]] == [first_text, second_text]

        r = await actor.delete(url)
        assert r.status_code == 428, r.text
        assert (await world.outsider.delete(url)).status_code in {403, 404}
        undone = await raw_client.delete(
            url, headers={**actor.headers, "If-Match": (await read(first))["version"]}
        )
        assert undone.status_code == 200, undone.text
        assert [el["id"] for el in (await read(first))["elements"]] == [first_text]
        assert [el["id"] for el in (await read(second))["elements"]] == [second_text]
        assert [el["id"] for el in (await read(parent))["elements"]] == [first, second]
        again = await raw_client.delete(
            url, headers={**actor.headers, "If-Match": (await read(first))["version"]}
        )
        assert again.status_code == 404
    finally:
        await world.clean_up()
