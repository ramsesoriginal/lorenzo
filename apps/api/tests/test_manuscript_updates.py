"""Explicit standalone manuscript updates preserve identity, history and audiences."""

import json
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from sqlalchemy import select, update

from lorenzo_api.config import get_settings
from lorenzo_api.manuscript_comparison import standalone, update_reason
from lorenzo_api.models import ContentReference, Information, Payload, PayloadDescription
from lorenzo_api.repository_content import Content


def test_structural_and_binary_changes_are_not_partial_text_updates():
    id, other = uuid.uuid4(), uuid.uuid4()
    c = Content(tenant_id=uuid.uuid4())
    c.kinds[id] = {"chapter"}
    assert standalone(c, id)
    c.manuscript_placements[other] = {"parent": id}
    assert not standalone(c, id)
    c.manuscript_placements.clear()
    c.tellings[other] = {"scene": id}
    assert not standalone(c, id)
    c.tellings.clear()
    c.carrier_coverage[other] = {"carrier": other, "entry": id}
    assert not standalone(c, id)
    base = {
        "title": "Manuscript",
        "payloads": [{"id": "a", "order": 0, "kind": "picture", "fields": {"data_sha256": "old"}}],
    }
    changed = {
        "title": "Manuscript",
        "payloads": [{"id": "a", "order": 0, "kind": "picture", "fields": {"data_sha256": "new"}}],
    }
    assert "structural" in update_reason(base, base, changed, True)
    assert update_reason(base, base, None, True)
    assert update_reason(base, base, base, False)


@pytest.mark.parametrize("public", [False, True])
async def test_explicit_choices_and_stale_review(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    monkeypatch: pytest.MonkeyPatch,
    public: bool,
):
    from conftest import delete_tenant

    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)
    monkeypatch.setattr(get_settings(), "release_cooldown_seconds", 0)
    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    owner = world.owner
    source = f"/tenants/{world.tenant_id}"
    target = None
    try:
        chapter = (await owner.post(source + "/writing/chapters", json={"name": "Draft"})).json()[
            "id"
        ]
        made = await owner.post(
            source + f"/entities/{chapter}/information",
            json={"title": "Manuscript", "type": "manuscript", "content": "Original"},
        )
        assert made.status_code == 201, made.text
        source_info = made.json()["id"]
        info_url = source + f"/information/{source_info}"
        current = await owner.get(info_url)
        second = await raw_client.post(
            info_url + "/texts",
            headers={**owner.headers, "If-Match": current.headers["etag"]},
            json={"content": "Second original", "locale": "en"},
        )
        assert second.status_code == 201, second.text
        target = await owner.create_tenant("Subscriber")
        assert (await owner.put(source + f"/subscribers/{target}")).status_code in (200, 201)
        assert (await owner.put(source + "/published")).status_code == 200
        if public:
            flipped = await owner.put(
                source + "/public", json={"summary": "Drafts", "accept_terms": True}
            )
            assert flipped.status_code == 200, flipped.text
        base = f"/tenants/{target}"
        copied = await owner.post(base + f"/repositories/{world.tenant_id}/copy")
        assert copied.status_code == 201, copied.text
        local = next(
            row["id"]
            for row in (await owner.get(base + "/entities")).json()["items"]
            if row["name"] == "Draft"
        )
        url = base + f"/writing/entries/{local}/repository-comparison"
        async with admin_session_factory() as session:
            local_info = await session.scalar(
                select(Information.id).where(Information.entity_id == uuid.UUID(local))
            )

        async def change(info, value):
            async with admin_session_factory() as session:
                ids = list(
                    await session.scalars(
                        select(Payload.id).where(Payload.information_id == uuid.UUID(str(info)))
                    )
                )
                await session.execute(
                    update(PayloadDescription)
                    .where(PayloadDescription.payload_id.in_(ids))
                    .values(content=value)
                )
                await session.commit()
            if public and str(info) == source_info:
                assert (await owner.put(source + "/published")).status_code == 200

        async def compare():
            result = await owner.get(url)
            assert result.status_code == 200, result.text
            return result.json()

        async def accept(view, choice="upstream"):
            return await raw_client.post(
                url, headers={**owner.headers, "If-Match": view["version"]}, json={"choice": choice}
            )

        assert (await owner.post(url, json={"choice": "upstream"})).status_code == 428
        await change(source_info, "Repository [[crossing]]")
        review = await compare()
        assert review["update_allowed"] and review["state"] == "upstream"
        await change(local_info, "Local change")
        assert (await accept(review)).status_code == 412
        conflict = await compare()
        assert conflict["state"] == "conflict"
        kept = await accept(conflict, "local")
        assert kept.status_code == 204, kept.text
        assert (await accept(conflict, "local")).status_code == 412
        after_keep = await compare()
        assert after_keep["state"] == "local" and not after_keep["update_allowed"]
        assert all(
            p["fields"]["content"] == "Local change" for p in after_keep["local"]["payloads"]
        )
        await change(source_info, "Next [[crossing]]")
        stale = await compare()
        await change(source_info, "Latest [[crossing]]")
        assert (await accept(stale)).status_code == 412
        view = await compare()
        # Acceptance rechecks repository visibility after the review was opened.
        assert (await owner.delete(source + f"/subscribers/{target}")).status_code in (200, 204)
        if not public:
            assert (await accept(view)).status_code == 404
            assert (await owner.put(source + f"/subscribers/{target}")).status_code in (200, 201)
        accepted = await accept(view)
        assert accepted.status_code == 204, accepted.text
        after = await compare()
        assert after["state"] == "unchanged"
        assert after["local"] == view["upstream"]
        assert [p["id"] for p in after["local"]["payloads"]] == [
            p["id"] for p in view["local"]["payloads"]
        ]
        saved = (await owner.get(base + f"/information/{local_info}/editor")).json()
        assert saved["is_public"] is False
        revisions = (await owner.get(base + f"/information/{local_info}/revisions")).json()["items"]
        latest = (
            await owner.get(base + f"/information/{local_info}/revisions/{revisions[0]['id']}")
        ).json()
        assert json.dumps(latest).count("Local change") == 2
        async with admin_session_factory() as session:
            refs = list(
                await session.scalars(
                    select(ContentReference.target)
                    .join(Payload, Payload.id == ContentReference.payload_id)
                    .where(Payload.information_id == local_info)
                )
            )
        assert refs == ["crossing", "crossing"]
        assert (await accept(view)).status_code == 412

        # Changed payload structure remains a refusal, never a partial text write.
        await change(source_info, "Another version")
        before = await compare()
        current = await owner.get(base + f"/information/{local_info}")
        added = await raw_client.post(
            base + f"/information/{local_info}/texts",
            headers={**owner.headers, "If-Match": current.headers["etag"]},
            json={"content": "Local extra", "locale": "en"},
        )
        assert added.status_code == 201, added.text
        assert (await accept(before)).status_code == 412
        structural = await compare()
        assert not structural["update_allowed"]
        assert (await accept(structural)).status_code == 422
        denied = await raw_client.post(
            url,
            headers={**world.outsider.headers, "If-Match": structural["version"]},
            json={"choice": "upstream"},
        )
        assert denied.status_code in (403, 404)
    finally:
        if target:
            await delete_tenant(target)
        await world.clean_up()
