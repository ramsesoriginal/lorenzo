"""Writing composition through the real tenant-scoped API (ADR 0336)."""

import uuid

import pytest
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_books_chapters_order_and_independent_editions(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    try:
        actor = world.author
        base = f"/tenants/{world.tenant_id}"
        writing = base + "/writing"
        book_body = {
            "id": str(uuid.uuid4()),
            "first_edition_id": str(uuid.uuid4()),
            "name": "River journeys",
        }
        made = await actor.post(writing + "/books", json=book_body)
        assert made.status_code == 201, made.text
        book = made.json()
        edition = book["editions"][0]["id"]
        assert (await actor.post(writing + "/books", json=book_body)).status_code == 200
        first = await actor.post(writing + "/chapters", json={"name": "Departure"})
        assert first.status_code == 201, first.text
        chapter = first.json()["id"]
        second = await actor.post(writing + "/chapters", json={"name": "The crossing"})
        subchapter = second.json()["id"]
        prose = await actor.post(
            base + f"/entities/{edition}/information",
            json={"title": "Manuscript", "type": "manuscript", "content": "Before the journey."},
        )
        assert prose.status_code == 201, prose.text
        payload = prose.json()["payloads"][0]["id"]
        child_prose = await actor.post(
            base + f"/entities/{chapter}/information",
            json={"title": "Manuscript", "type": "manuscript", "content": "Our boat left."},
        )
        assert child_prose.status_code == 201, child_prose.text

        async def arrange(parent: str, ids: list[str]):
            current = await actor.get(writing + f"/entries/{parent}")
            return await raw_client.put(
                writing + f"/entries/{parent}/composition",
                headers={**actor.headers, "If-Match": current.headers["etag"]},
                json={"elements": ids},
            )

        missing_version = await actor.put(
            writing + f"/entries/{edition}/composition", json={"elements": [payload]}
        )
        assert missing_version.status_code == 428, missing_version.text
        ordered = await arrange(edition, [chapter, payload])
        assert ordered.status_code == 200, ordered.text
        assert [x["id"] for x in ordered.json()["elements"]] == [chapter, payload]
        nested = await arrange(chapter, [child_prose.json()["payloads"][0]["id"], subchapter])
        assert nested.status_code == 200, nested.text
        assert (await arrange(subchapter, [chapter])).status_code == 422
        assert (await arrange(edition, [payload, subchapter])).status_code == 422
        stale = await raw_client.put(
            writing + f"/entries/{edition}/composition",
            headers={**actor.headers, "If-Match": 'W/"stale"'},
            json={"elements": [payload, chapter]},
        )
        assert stale.status_code == 412, stale.text
        changed = await arrange(edition, [payload, chapter])
        assert changed.status_code == 200, changed.text
        assert (await world.outsider.get(writing + f"/entries/{edition}")).status_code == 404
        cloned = await actor.post(
            writing + "/editions", json={"name": "Second edition", "source_edition_id": edition}
        )
        assert cloned.status_code == 201, cloned.text
        clone = cloned.json()
        assert clone["book_id"] == book["id"]
        assert len(clone["elements"]) == 2
        assert {x["id"] for x in clone["elements"]}.isdisjoint({payload, chapter})
        clone_chapter = next(x["id"] for x in clone["elements"] if x["kind"] == "chapter")
        cloned_child = (await actor.get(base + f"/entities/{clone_chapter}")).json()
        assert "chapter" in cloned_child["kinds"]
        manuscript = next(i for i in cloned_child["information"] if i["type"] == "manuscript")
        assert manuscript["payloads"][0]["content"] == "Our boat left."
        assert manuscript["is_public"] is False
        assert (await actor.get(base + f"/information/{manuscript['id']}/revisions")).json()[
            "total"
        ] == 0
        # The ordinary delete route must not silently discard a Book's Edition or child tree.
        assert (await actor.delete(base + f"/entities/{book['id']}")).status_code == 409
        assert (await actor.delete(base + f"/entities/{chapter}")).status_code == 409
        if kind == "repository":
            from conftest import delete_tenant

            target = await world.owner.create_tenant("Writing copy")
            try:
                assert (await world.owner.put(base + f"/subscribers/{target}")).status_code in (
                    200,
                    201,
                )
                published = await world.owner.put(base + "/published")
                assert published.status_code == 200, published.text
                copied = await world.owner.post(
                    f"/tenants/{target}/repositories/{world.tenant_id}/copy"
                )
                assert copied.status_code == 201, copied.text
                entries = (
                    await world.owner.get(f"/tenants/{target}/entities", params={"size": 100})
                ).json()["items"]
                copied_edition = next(
                    e for e in entries if "edition" in e["kinds"] and e["name"] == book_body["name"]
                )
                view = await world.owner.get(
                    f"/tenants/{target}/writing/entries/{copied_edition['id']}"
                )
                assert view.status_code == 200, view.text
                assert [e["kind"] for e in view.json()["elements"]] == ["payload", "chapter"]
                assert {e["id"] for e in view.json()["elements"]}.isdisjoint({payload, chapter})
                local_child = view.json()["elements"][1]["id"]
                subtree = (
                    await world.owner.get(f"/tenants/{target}/writing/entries/{local_child}")
                ).json()
                assert [e["kind"] for e in subtree["elements"]] == ["payload", "chapter"]
            finally:
                await delete_tenant(target)
        # Deleting a prose anchor preserves its preceding Chapter at the end.
        assert (await arrange(edition, [chapter, payload])).status_code == 200
        removed = await actor.delete(base + f"/payloads/{payload}")
        assert removed.status_code == 204, removed.text
        after_delete = (await actor.get(writing + f"/entries/{edition}")).json()
        assert [el["id"] for el in after_delete["elements"]] == [chapter]
        detached = await arrange(edition, [])
        assert detached.status_code == 200, detached.text
        assert (await actor.get(writing + f"/entries/{chapter}")).status_code == 200
    finally:
        await world.clean_up()
