"""Manuscript recovery through ordinary editing routes (ADR 0328)."""

import base64

import pytest
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_author_manuscript_recovery(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    try:
        actor = world.author
        base = f"/tenants/{world.tenant_id}"
        scene = await actor.post(base + "/scenes", json={"name": "A beginning"})
        assert scene.status_code == 201, scene.text
        entity = scene.json()["id"]
        created = await actor.post(
            base + f"/entities/{entity}/information",
            json={"title": "Manuscript", "type": "manuscript", "content": "First [[road]]."},
        )
        assert created.status_code == 201, created.text
        info = created.json()
        url = base + f"/information/{info['id']}"
        history = url + "/revisions"
        assert (await actor.get(history)).json()["total"] == 0
        duplicate = await actor.post(
            base + f"/entities/{entity}/information",
            json={"title": "Other", "type": "manuscript", "content": "Not another manuscript"},
        )
        assert duplicate.status_code == 409
        payload = info["payloads"][0]
        payload_url = base + f"/payloads/{payload['id']}"
        headers = {**actor.headers, "If-Match": f'W/"{payload["updated_at"]}"'}
        changed = await raw_client.patch(payload_url, json={"content": "Revised."}, headers=headers)
        assert changed.status_code == 200, changed.text
        revisions = await actor.get(history)
        assert revisions.status_code == 200, revisions.text
        assert revisions.headers["cache-control"] == "private, no-store"
        assert revisions.json()["total"] == 1
        saved_url = history + "/" + revisions.json()["items"][0]["id"]
        saved = await actor.get(saved_url)
        assert (
            saved.json()["snapshot"]["payloads"][0]["description"]["content"] == "First [[road]]."
        )
        assert "is_public" not in saved.json()["snapshot"]
        assert (await world.outsider.get(history)).status_code == 404
        assert (await world.outsider.get(saved_url)).status_code == 404
        # Neither a stale save nor an identical save creates another checkpoint.
        assert (
            await raw_client.patch(payload_url, json={"content": "Stale"}, headers=headers)
        ).status_code == 412
        assert (
            await raw_client.patch(
                payload_url,
                json={"content": "Revised."},
                headers={**actor.headers, "If-Match": changed.headers["etag"]},
            )
        ).status_code == 200
        assert (await actor.get(history)).json()["total"] == 1
        picture = await raw_client.post(
            url + "/payloads",
            headers=actor.headers,
            files={"file": ("idea.png", b"picture bytes", "image/png")},
        )
        assert picture.status_code == 201, picture.text
        current = await actor.get(url)
        ids = [p["id"] for p in current.json()["payloads"]]
        ordered = await raw_client.put(
            url + "/payloads/order",
            headers={**actor.headers, "If-Match": current.headers["etag"]},
            json={"payload_ids": list(reversed(ids))},
        )
        assert ordered.status_code == 200, ordered.text
        assert (await actor.get(history)).json()["total"] == 3
        removed = await raw_client.delete(
            base + f"/payloads/{picture.json()['id']}", headers=actor.headers
        )
        assert removed.status_code == 204, removed.text
        newest = (await actor.get(history)).json()["items"][0]["id"]
        snapshot = (await actor.get(history + "/" + newest)).json()["snapshot"]
        assert [p["id"] for p in snapshot["payloads"]] == list(reversed(ids))
        assert base64.b64decode(snapshot["payloads"][0]["picture"]["data"]) == b"picture bytes"
        # Explicitly deleting the bundle also removes recovery history.
        deleted = await raw_client.delete(url, headers=actor.headers)
        assert deleted.status_code == 204, deleted.text
        assert (await actor.get(saved_url)).status_code == 404
    finally:
        await world.clean_up()


async def test_copy_keeps_current_manuscript_without_source_history(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from conftest import delete_tenant

    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    target = await world.owner.create_tenant("Manuscript destination")
    try:
        base = f"/tenants/{world.tenant_id}"
        scene = await world.author.post(base + "/scenes", json={"name": "Story"})
        created = await world.author.post(
            base + f"/entities/{scene.json()['id']}/information",
            json={"title": "Manuscript", "type": "manuscript", "content": "Unpublished wording"},
        )
        info = created.json()
        payload = info["payloads"][0]
        changed = await raw_client.patch(
            base + f"/payloads/{payload['id']}",
            headers={**world.author.headers, "If-Match": f'W/"{payload["updated_at"]}"'},
            json={"content": "Current wording"},
        )
        assert changed.status_code == 200, changed.text
        assert (await world.author.get(base + f"/information/{info['id']}/revisions")).json()[
            "total"
        ] == 1
        assert (await world.owner.put(base + f"/subscribers/{target}")).status_code in (200, 201)
        assert (await world.owner.put(base + "/published")).status_code == 200
        copied = await world.owner.post(f"/tenants/{target}/repositories/{world.tenant_id}/copy")
        assert copied.status_code == 201, copied.text
        entries = (await world.owner.get(f"/tenants/{target}/entities")).json()["items"]
        mine = next(e for e in entries if e["name"] == "Story")
        entity = (await world.owner.get(f"/tenants/{target}/entities/{mine['id']}")).json()
        manuscript = next(i for i in entity["information"] if i["type"] == "manuscript")
        assert manuscript["id"] != info["id"]
        assert manuscript["payloads"][0]["content"] == "Current wording"
        history = await world.owner.get(
            f"/tenants/{target}/information/{manuscript['id']}/revisions"
        )
        assert history.json()["total"] == 0
    finally:
        await delete_tenant(target)
        await world.clean_up()
