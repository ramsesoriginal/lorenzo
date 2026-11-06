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
from lorenzo_api.manuscript_comparison import chapter_contexts, standalone, update_reason
from lorenzo_api.models import (
    ContentReference,
    Information,
    ManuscriptPlacement,
    Payload,
    PayloadDescription,
    RepositoryCopyLinkEntity,
)
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


@pytest.mark.parametrize("depth", [0, 1, 3])
@pytest.mark.parametrize("public", [False, True])
async def test_explicit_choices_and_stale_review(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    monkeypatch: pytest.MonkeyPatch,
    public: bool,
    depth: int,
):
    from conftest import delete_tenant

    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)
    monkeypatch.setattr(get_settings(), "release_cooldown_seconds", 0)
    placed = depth > 0
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
        if placed:
            book = (await owner.post(source + "/writing/books", json={"name": "Stories"})).json()
            edition = book["editions"][0]["id"]
            for level in range(depth - 1):
                parent = (
                    await owner.post(source + "/writing/chapters", json={"name": f"Part {level}"})
                ).json()["id"]
                outline = (await owner.get(source + f"/writing/entries/{edition}")).json()
                arranged = await raw_client.put(
                    source + f"/writing/entries/{edition}/composition",
                    headers={**owner.headers, "If-Match": outline["version"]},
                    json={"elements": [parent]},
                )
                assert arranged.status_code == 200, arranged.text
                edition = parent
            parent_text = (
                await owner.post(
                    source + f"/entities/{edition}/information",
                    json={
                        "title": "Manuscript",
                        "type": "manuscript",
                        "content": "After the Chapter",
                    },
                )
            ).json()
            parent_bundle = (
                await owner.get(source + f"/information/{parent_text['id']}/editor")
            ).json()
            anchor = parent_bundle["payloads"][0]["id"]
            outline = (await owner.get(source + f"/writing/entries/{edition}")).json()
            arranged = await raw_client.put(
                source + f"/writing/entries/{edition}/composition",
                headers={**owner.headers, "If-Match": outline["version"]},
                json={"elements": [chapter, anchor]},
            )
            assert arranged.status_code == 200, arranged.text
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
        if placed:
            async with admin_session_factory() as session:
                local_placement = await session.scalar(
                    select(ManuscriptPlacement).where(
                        ManuscriptPlacement.tenant_id == uuid.UUID(str(target)),
                        ManuscriptPlacement.child_entity_id == uuid.UUID(local),
                    )
                )
                assert local_placement is not None
                local_edition = str(local_placement.parent_entity_id)
                position = local_placement.position
                local_placement.position += 1
                await session.commit()
            assert (await accept(review)).status_code == 412
            assert not (await compare())["update_allowed"]
            async with admin_session_factory() as session:
                await session.execute(
                    update(ManuscriptPlacement)
                    .where(ManuscriptPlacement.child_entity_id == uuid.UUID(local))
                    .values(position=position)
                )
                link = await session.scalar(
                    select(RepositoryCopyLinkEntity).where(
                        RepositoryCopyLinkEntity.entity_id == uuid.UUID(local)
                    )
                )
                baseline = dict(link.manuscript_baseline)
                link.manuscript_baseline = {k: v for k, v in baseline.items() if k != "composition"}
                await session.commit()
            assert not (await compare())["update_allowed"]
            async with admin_session_factory() as session:
                await session.execute(
                    update(RepositoryCopyLinkEntity)
                    .where(RepositoryCopyLinkEntity.entity_id == uuid.UUID(local))
                    .values(manuscript_baseline=baseline)
                )
                await session.commit()
            # Changing the source placement invalidates a review too, including released reads.
            async with admin_session_factory() as session:
                await session.execute(
                    update(ManuscriptPlacement)
                    .where(ManuscriptPlacement.child_entity_id == uuid.UUID(chapter))
                    .values(position=position + 1)
                )
                await session.commit()
            if public:
                assert (await owner.put(source + "/published")).status_code == 200
            assert (await accept(review)).status_code == 412
            assert not (await compare())["update_allowed"]
            async with admin_session_factory() as session:
                await session.execute(
                    update(ManuscriptPlacement)
                    .where(ManuscriptPlacement.child_entity_id == uuid.UUID(chapter))
                    .values(position=position)
                )
                await session.commit()
            if public:
                assert (await owner.put(source + "/published")).status_code == 200
        if depth > 1:
            # The leaf itself is unchanged, but an ancestor reorder invalidates its review.
            for ancestor, publish in ((local_edition, False), (edition, public)):
                async with admin_session_factory() as session:
                    row = await session.scalar(
                        select(ManuscriptPlacement).where(
                            ManuscriptPlacement.child_entity_id == uuid.UUID(ancestor)
                        )
                    )
                    old_position = row.position
                    row.position += 1
                    await session.commit()
                if publish:
                    assert (await owner.put(source + "/published")).status_code == 200
                assert (await accept(review)).status_code == 412
                assert not (await compare())["update_allowed"]
                async with admin_session_factory() as session:
                    await session.execute(
                        update(ManuscriptPlacement)
                        .where(ManuscriptPlacement.child_entity_id == uuid.UUID(ancestor))
                        .values(position=old_position)
                    )
                    await session.commit()
                if publish:
                    assert (await owner.put(source + "/published")).status_code == 200
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
        if placed:
            reading = await owner.get(base + f"/writing/entries/{local}")
            assert reading.status_code == 200, reading.text
            assert reading.json()["parent_id"] == local_edition
            outline = (await owner.get(base + f"/writing/entries/{local_edition}")).json()
            assert local in json.dumps(outline)
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


def test_placed_context_remaps_anchors_and_refuses_dependencies():
    chapter, edition, book, anchor, other = [uuid.uuid4() for _ in range(5)]
    c = Content(tenant_id=uuid.uuid4())
    c.kinds = {chapter: {"chapter"}, edition: {"edition"}, book: {"book"}}
    c.editions[edition] = book
    c.manuscript_placements[chapter] = {"parent": edition, "before": anchor, "position": 2}
    original = chapter_contexts(c)[chapter]
    mapped = chapter_contexts(c, {str(v): str(v) for v in (edition, book, anchor)})[chapter]
    assert mapped == original
    assert chapter_contexts(c, {})[chapter] != original
    for entry in (chapter, edition, book):
        c.carrier_coverage[other] = {"carrier": other, "entry": entry}
        assert chapter_contexts(c) == {}
        c.carrier_coverage.clear()
        c.manuscript_redirects[other] = {"destination": entry, "child": None}
        assert chapter_contexts(c) == {}
        c.manuscript_redirects.clear()
    c.manuscript_placements[other] = {"parent": chapter, "before": None, "position": 0}
    assert chapter_contexts(c) == {}
    c.manuscript_placements.clear()
    c.manuscript_placements[chapter] = {"parent": other, "before": None, "position": 0}
    assert chapter_contexts(c) == {}


def test_nested_context_covers_every_ancestor_and_refuses_cycles():
    leaf, inner, outer, edition, book, anchor, other = [uuid.uuid4() for _ in range(7)]
    c = Content(tenant_id=uuid.uuid4())
    c.kinds = {
        leaf: {"chapter"},
        inner: {"chapter"},
        outer: {"chapter"},
        edition: {"edition"},
        book: {"book"},
    }
    c.editions[edition] = book
    for child, parent in ((leaf, inner), (inner, outer), (outer, edition)):
        c.manuscript_placements[child] = {"parent": parent, "before": anchor, "position": 0}
    original = chapter_contexts(c)[leaf]
    assert len(original["path"]) == 3
    assert set(chapter_contexts(c)) == {leaf}
    assert (
        chapter_contexts(c, {str(x): str(x) for x in (leaf, inner, outer, edition, book, anchor)})[
            leaf
        ]
        == original
    )
    for ancestor in (inner, outer):
        c.manuscript_placements[ancestor]["position"] = 1
        assert chapter_contexts(c)[leaf] != original
        c.manuscript_placements[ancestor]["position"] = 0
        c.carrier_coverage[other] = {"carrier": other, "entry": ancestor}
        assert chapter_contexts(c) == {}
        c.carrier_coverage.clear()
        c.manuscript_redirects[other] = {"destination": ancestor, "child": None}
        assert chapter_contexts(c) == {}
        c.manuscript_redirects.clear()
    c.manuscript_placements[outer]["parent"] = inner
    assert chapter_contexts(c) == {}
    del c.manuscript_placements[outer]
    assert chapter_contexts(c) == {}


def test_deep_context_does_not_use_recursive_traversal():
    chapters = [uuid.uuid4() for _ in range(1100)]
    edition, book = uuid.uuid4(), uuid.uuid4()
    c = Content(tenant_id=uuid.uuid4())
    c.kinds = {id: {"chapter"} for id in chapters}
    c.kinds.update({edition: {"edition"}, book: {"book"}})
    c.editions[edition] = book
    for child, parent in zip(chapters, [*chapters[1:], edition], strict=True):
        c.manuscript_placements[child] = {"parent": parent, "before": None, "position": 0}
    contexts = chapter_contexts(c)
    assert set(contexts) == {chapters[0]}
    assert len(contexts[chapters[0]]["path"]) == len(chapters)
