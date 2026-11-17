"""Atomic manuscript reviews exercise the real API and restricted database role."""

import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import Information, ManuscriptRevision, Payload, PayloadPicture


@pytest.mark.parametrize("take_structure", [False, True])
async def test_new_chapter_and_text_move_are_atomic(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, take_structure: bool
):
    from conftest import delete_tenant

    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    owner = world.owner
    source = f"/tenants/{world.tenant_id}"
    target = None
    try:
        book_response = await owner.post(source + "/writing/books", json={"name": "Chronicle"})
        assert book_response.status_code == 201, book_response.text
        book = book_response.json()
        edition = book["editions"][0]["id"]
        chapter = (await owner.post(source + "/writing/chapters", json={"name": "Opening"})).json()[
            "id"
        ]
        manuscript = await owner.post(
            source + f"/entities/{chapter}/information",
            json={"title": "Opening", "type": "manuscript", "content": "Original opening"},
        )
        assert manuscript.status_code == 201, manuscript.text
        outline = (await owner.get(source + f"/writing/entries/{edition}")).json()
        arranged = await raw_client.put(
            source + f"/writing/entries/{edition}/composition",
            headers={**owner.headers, "If-Match": outline["version"]},
            json={"elements": [chapter]},
        )
        assert arranged.status_code == 200, arranged.text
        target = await owner.create_tenant("Copy")
        assert (await owner.put(source + f"/subscribers/{target}")).status_code in (200, 201)
        assert (await owner.put(source + "/published")).status_code == 200
        base = f"/tenants/{target}"
        copied = await owner.post(base + f"/repositories/{world.tenant_id}/copy")
        assert copied.status_code == 201, copied.text
        entries = (await owner.get(base + "/entities")).json()["items"]
        local_chapter = next(row["id"] for row in entries if row["name"] == "Opening")
        local_book = next(row["id"] for row in entries if row["name"] == "Chronicle")
        local_edition = (await owner.get(base + f"/writing/entries/{local_book}")).json()[
            "editions"
        ][0]["id"]
        url = base + f"/writing/entries/{local_chapter}/repository-updates"
        initial = await owner.get(url)
        assert initial.status_code == 200, initial.text
        assert initial.json()["rows"] == []
        extra = (
            await owner.post(base + "/writing/chapters", json={"name": "Local addition"})
        ).json()["id"]
        local_outline = (await owner.get(base + f"/writing/entries/{local_edition}")).json()
        placed_local = await raw_client.put(
            base + f"/writing/entries/{local_edition}/composition",
            headers={**owner.headers, "If-Match": local_outline["version"]},
            json={"elements": [local_chapter, extra]},
        )
        assert placed_local.status_code == 200, placed_local.text
        second = (
            await owner.post(source + "/writing/chapters", json={"name": "Afterword"})
        ).json()["id"]
        outline = (await owner.get(source + f"/writing/entries/{edition}")).json()
        arranged = await raw_client.put(
            source + f"/writing/entries/{edition}/composition",
            headers={**owner.headers, "If-Match": outline["version"]},
            json={"elements": [second, chapter]},
        )
        assert arranged.status_code == 200, arranged.text
        comparison = await owner.get(url)
        assert comparison.status_code == 200, comparison.text
        rows = comparison.json()["rows"]
        assert extra in comparison.json()["affected_entries"]
        assert any(row["id"] == second + ":entry" for row in rows), rows
        choices = {row["id"]: "upstream" for row in rows if row["selectable"]}
        if not take_structure:
            choices[chapter + ":structure"] = "local"
        if take_structure:
            grant_url = (
                base + f"/writing/reviews/{local_edition}/reviewers/{world.outsider.user_id}"
            )
            assert (await owner.put(grant_url)).status_code == 204
            denied = await raw_client.post(
                url,
                headers={**owner.headers, "If-Match": comparison.headers["etag"]},
                json={"choices": choices},
            )
            assert denied.status_code == 422, denied.text
            assert "reviewers" in denied.text
            assert not any(
                row["name"] == "Afterword"
                for row in (await owner.get(base + "/entities")).json()["items"]
            )
            assert (await world.outsider.get(url)).status_code in (403, 404)
            assert (await owner.delete(grant_url)).status_code == 204
        accepted = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": choices},
        )
        assert accepted.status_code == 200, accepted.text
        result = (await owner.get(base + f"/writing/entries/{local_edition}")).json()
        assert len(result["elements"]) == 3
        assert {element["name"] for element in result["elements"]} == {
            "Opening",
            "Afterword",
            "Local addition",
        }
        repeated = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": choices},
        )
        assert repeated.status_code == 412, repeated.text
        receipt = await owner.get(url + "/checkpoints/" + accepted.json()["checkpoint_id"])
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["choices"] == choices
    finally:
        if target:
            await delete_tenant(target)
        await delete_tenant(world.tenant_id)


async def test_extraction_updates_keep_stable_elements_and_rollback_partial_choices(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
):
    from conftest import delete_tenant

    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    owner = world.owner
    source = f"/tenants/{world.tenant_id}"
    target = None
    try:
        parent = (
            await owner.post(source + "/writing/chapters", json={"name": "Collected"})
        ).json()["id"]
        info = (
            await owner.post(
                source + f"/entities/{parent}/information",
                json={"type": "manuscript", "title": "Writing", "content": "A whole passage"},
            )
        ).json()
        payload = info["payloads"][0]["id"]
        carrier = (await owner.post(source + "/writing/carriers", json={"name": "Scroll"})).json()
        coverage_id = str(uuid.uuid4())
        coverage = await raw_client.put(
            source + f"/writing/carriers/{carrier['id']}/coverage",
            headers={**owner.headers, "If-Match": carrier["version"]},
            json={"elements": [{"id": coverage_id, "target_payload_id": payload}]},
        )
        assert coverage.status_code == 200, coverage.text
        target = await owner.create_tenant("Copy")
        await owner.put(source + f"/subscribers/{target}")
        await owner.put(source + "/published")
        base = f"/tenants/{target}"
        copied = await owner.post(base + f"/repositories/{world.tenant_id}/copy")
        assert copied.status_code == 201, copied.text
        entries = (await owner.get(base + "/entities")).json()["items"]
        local_parent = next(row["id"] for row in entries if row["name"] == "Collected")
        local_carrier = next(row["id"] for row in entries if row["name"] == "Scroll")
        before = (await owner.get(base + f"/writing/entries/{local_parent}")).json()
        local_payload = before["elements"][0]["id"]
        coverage_before = (await owner.get(base + f"/writing/entries/{local_carrier}")).json()[
            "elements"
        ][0]
        child = str(uuid.uuid4())
        outline = (await owner.get(source + f"/writing/entries/{parent}")).json()
        extracted = await raw_client.post(
            source + f"/writing/entries/{parent}/extractions/{uuid.uuid4()}",
            headers={**owner.headers, "If-Match": outline["version"]},
            json={"chapter_id": child, "name": "Extracted", "elements": [payload]},
        )
        assert extracted.status_code == 200, extracted.text
        url = base + f"/writing/entries/{local_carrier}/repository-updates"
        comparison = await owner.get(url)
        assert comparison.status_code == 200, comparison.text
        choices = {row["id"]: "upstream" for row in comparison.json()["rows"] if row["selectable"]}
        partial = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": {parent + ":bundle": "upstream"}},
        )
        assert partial.status_code == 422, partial.text
        assert (await owner.get(base + f"/writing/entries/{local_parent}")).json()[
            "elements"
        ] == before["elements"]
        accepted = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": choices},
        )
        assert accepted.status_code == 200, accepted.text
        after = (await owner.get(base + f"/writing/entries/{local_parent}")).json()
        local_child = after["elements"][0]["id"]
        child_outline = (await owner.get(base + f"/writing/entries/{local_child}")).json()
        assert child_outline["elements"][0]["id"] == local_payload
        coverage_after = (await owner.get(base + f"/writing/entries/{local_carrier}")).json()[
            "elements"
        ][0]
        assert coverage_after["id"] == coverage_before["id"]
        assert coverage_after["payload_id"] == local_payload
        async with admin_session_factory() as session:
            old_info = await session.scalar(
                select(Information.id).where(
                    Information.entity_id == uuid.UUID(local_parent),
                    Information.type == "manuscript",
                )
            )
            revisions = list(
                await session.scalars(
                    select(ManuscriptRevision).where(ManuscriptRevision.information_id == old_info)
                )
            )
            assert any("A whole passage" in str(row.snapshot) for row in revisions)
        assert (await owner.get(url)).json()["rows"] == []
    finally:
        if target:
            await delete_tenant(target)
        await delete_tenant(world.tenant_id)


@pytest.mark.parametrize("public", [False, True])
async def test_all_manuscript_kinds_and_binary_updates(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    monkeypatch: pytest.MonkeyPatch,
    public: bool,
):
    from conftest import delete_tenant

    from lorenzo_api.config import get_settings

    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)
    monkeypatch.setattr(get_settings(), "release_cooldown_seconds", 0)
    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    owner = world.owner
    source = f"/tenants/{world.tenant_id}"
    target = None
    try:
        book = (await owner.post(source + "/writing/books", json={"name": "Book"})).json()
        kinds = {"Book": book["id"], "Edition": book["editions"][0]["id"]}
        for kind, path in (
            ("Chapter", "writing/chapters"),
            ("Carrier", "writing/carriers"),
            ("Scene", "scenes"),
            ("Biography", "writing/biographies"),
        ):
            made = await owner.post(source + "/" + path, json={"name": kind})
            assert made.status_code == 201, made.text
            kinds[kind] = made.json()["id"]
        telling = await owner.post(
            source + "/writing/tellings", json={"name": "Telling", "scene_id": kinds["Scene"]}
        )
        assert telling.status_code == 201, telling.text
        source_infos = {}
        for kind, id in kinds.items():
            made = await owner.post(
                source + f"/entities/{id}/information",
                json={"type": "manuscript", "title": "Writing", "content": kind + " original"},
            )
            assert made.status_code == 201, made.text
            source_infos[kind] = made.json()
        picture = uuid.uuid4()
        async with admin_session_factory() as session:
            session.add(
                Payload(
                    id=picture,
                    tenant_id=world.tenant_id,
                    information_id=uuid.UUID(source_infos["Carrier"]["id"]),
                    order=1,
                )
            )
            await session.flush()
            session.add(
                PayloadPicture(
                    payload_id=picture,
                    tenant_id=world.tenant_id,
                    data=b"old picture",
                    file_type="image/png",
                )
            )
            await session.commit()
        target = await owner.create_tenant("Copy")
        await owner.put(source + f"/subscribers/{target}")
        await owner.put(source + "/published")
        if public:
            flipped = await owner.put(
                source + "/public", json={"summary": "Writing", "accept_terms": True}
            )
            assert flipped.status_code == 200, flipped.text
        base = f"/tenants/{target}"
        copied = await owner.post(base + f"/repositories/{world.tenant_id}/copy")
        assert copied.status_code == 201, copied.text
        from lorenzo_api.models import PayloadDescription, RepositoryCopyLinkEntity

        async with admin_session_factory() as session:
            local_ids = {
                str(link.source_id): str(link.entity_id)
                for link in await session.scalars(
                    select(RepositoryCopyLinkEntity).where(
                        RepositoryCopyLinkEntity.tenant_id == target
                    )
                )
            }
            for info in source_infos.values():
                text = await session.get(PayloadDescription, uuid.UUID(info["payloads"][0]["id"]))
                text.content += " revised"
            image = await session.get(PayloadPicture, picture)
            image.data = b"new picture"
            await session.commit()
        if public:
            unpublished = await owner.get(
                base + f"/writing/entries/{local_ids[kinds['Carrier']]}/repository-updates"
            )
            assert unpublished.status_code == 200, unpublished.text
            assert unpublished.json()["rows"] == []
            assert (await owner.put(source + "/published")).status_code == 200
        # Starting from the shared telling finds and updates its Scene, never an independent copy.
        roots = [local_ids[telling.json()["id"]]] + [
            local_ids[id] for kind, id in kinds.items() if kind != "Scene"
        ]
        for root in roots:
            url = base + f"/writing/entries/{root}/repository-updates"
            comparison = await owner.get(url)
            assert comparison.status_code == 200, comparison.text
            choices = {
                row["id"]: "upstream" for row in comparison.json()["rows"] if row["selectable"]
            }
            if choices:
                accepted = await raw_client.post(
                    url,
                    headers={**owner.headers, "If-Match": comparison.headers["etag"]},
                    json={"choices": choices},
                )
                assert accepted.status_code == 200, accepted.text
        async with admin_session_factory() as session:
            for kind, source_id in kinds.items():
                info = await session.scalar(
                    select(Information).where(
                        Information.entity_id == uuid.UUID(local_ids[source_id]),
                        Information.type == "manuscript",
                    )
                )
                text = await session.scalar(
                    select(PayloadDescription)
                    .join(Payload, Payload.id == PayloadDescription.payload_id)
                    .where(Payload.information_id == info.id)
                )
                assert text.content == kind + " original revised"
            image = await session.scalar(
                select(PayloadPicture)
                .join(Payload, Payload.id == PayloadPicture.payload_id)
                .join(Information, Information.id == Payload.information_id)
                .where(Information.entity_id == uuid.UUID(local_ids[kinds["Carrier"]]))
            )
            assert image.data == b"new picture"
    finally:
        if target:
            await delete_tenant(target)
        await delete_tenant(world.tenant_id)


@pytest.mark.parametrize("legacy", [False, True])
async def test_conflicts_legacy_adoption_and_access(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, legacy: bool
):
    from conftest import delete_tenant

    from lorenzo_api.models import PayloadDescription, RepositoryCopyLinkEntity

    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    owner = world.owner
    source = f"/tenants/{world.tenant_id}"
    target = None
    try:
        chapter = (await owner.post(source + "/writing/chapters", json={"name": "Draft"})).json()[
            "id"
        ]
        made = (
            await owner.post(
                source + f"/entities/{chapter}/information",
                json={"type": "manuscript", "title": "Writing", "content": "Original"},
            )
        ).json()
        target = await owner.create_tenant("Copy")
        await owner.put(source + f"/subscribers/{target}")
        await owner.put(source + "/published")
        base = f"/tenants/{target}"
        assert (await owner.post(base + f"/repositories/{world.tenant_id}/copy")).status_code == 201
        async with admin_session_factory() as session:
            link = await session.get(RepositoryCopyLinkEntity, (target, uuid.UUID(chapter)))
            local_id = link.entity_id
            if legacy:
                link.manuscript_baseline = None
            local_info = await session.scalar(
                select(Information).where(
                    Information.entity_id == local_id, Information.type == "manuscript"
                )
            )
            local_payload = await session.scalar(
                select(PayloadDescription)
                .join(Payload, Payload.id == PayloadDescription.payload_id)
                .where(Payload.information_id == local_info.id)
            )
            local_payload.content = "Local draft"
            upstream = await session.get(PayloadDescription, uuid.UUID(made["payloads"][0]["id"]))
            upstream.content = "Incoming version"
            await session.commit()
        url = base + f"/writing/entries/{local_id}/repository-updates"
        assert (await world.outsider.get(url)).status_code in (403, 404)
        comparison = await owner.get(url)
        assert comparison.status_code == 200, comparison.text
        prose = next(row for row in comparison.json()["rows"] if row["field"] == "bundle")
        assert prose["state"] == ("unknown" if legacy else "conflict")
        assert prose["baseline_known"] is not legacy
        choices = {row["id"]: "local" for row in comparison.json()["rows"] if row["selectable"]}
        assert (await owner.post(url, json={"choices": choices})).status_code == 428
        stale = await raw_client.post(
            url, headers={**owner.headers, "If-Match": '"stale"'}, json={"choices": choices}
        )
        assert stale.status_code == 412
        kept = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": choices},
        )
        assert kept.status_code == 200, kept.text
        assert (await owner.get(url)).json()["rows"] == []
        async with admin_session_factory() as session:
            upstream = await session.get(PayloadDescription, uuid.UUID(made["payloads"][0]["id"]))
            upstream.content = "Later incoming version"
            await session.commit()
        comparison = await owner.get(url)
        choices = {row["id"]: "upstream" for row in comparison.json()["rows"] if row["selectable"]}
        accepted = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": choices},
        )
        assert accepted.status_code == 200, accepted.text
        entity = (await owner.get(base + f"/entities/{local_id}")).json()
        assert (
            next(info for info in entity["information"] if info["type"] == "manuscript")[
                "payloads"
            ][0]["content"]
            == "Later incoming version"
        )
        revoked = await owner.delete(source + f"/subscribers/{target}")
        assert revoked.status_code in (200, 204), revoked.text
        assert (await owner.get(url)).status_code == 404
    finally:
        if target:
            await delete_tenant(target)
        await delete_tenant(world.tenant_id)


async def test_join_redirect_and_presentation_update_together(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
):
    from conftest import delete_tenant

    from lorenzo_api.chapter_numbering import NumberingSettings
    from lorenzo_api.manuscript_contents import ContentsSettings
    from lorenzo_api.models import ManuscriptContents, ManuscriptNumbering, RepositoryCopyLinkEntity

    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    owner = world.owner
    source = f"/tenants/{world.tenant_id}"
    target = None
    try:
        book = (await owner.post(source + "/writing/books", json={"name": "Joined"})).json()
        edition = book["editions"][0]["id"]
        first, second = [
            (await owner.post(source + "/writing/chapters", json={"name": name})).json()["id"]
            for name in ("First", "Second")
        ]
        for id, prose in ((first, "First prose"), (second, "Second prose")):
            await owner.post(
                source + f"/entities/{id}/information",
                json={"type": "manuscript", "title": "Writing", "content": prose},
            )
        outline = (await owner.get(source + f"/writing/entries/{edition}")).json()
        arranged = await raw_client.put(
            source + f"/writing/entries/{edition}/composition",
            headers={**owner.headers, "If-Match": outline["version"]},
            json={"elements": [first, second]},
        )
        assert arranged.status_code == 200, arranged.text
        target = await owner.create_tenant("Copy")
        await owner.put(source + f"/subscribers/{target}")
        await owner.put(source + "/published")
        base = f"/tenants/{target}"
        assert (await owner.post(base + f"/repositories/{world.tenant_id}/copy")).status_code == 201
        async with admin_session_factory() as session:
            local = {
                str(link.source_id): str(link.entity_id)
                for link in await session.scalars(
                    select(RepositoryCopyLinkEntity).where(
                        RepositoryCopyLinkEntity.tenant_id == target
                    )
                )
            }
            session.add(
                ManuscriptNumbering(
                    tenant_id=world.tenant_id,
                    entity_id=uuid.UUID(edition),
                    settings=NumberingSettings(enabled=True).model_dump(),
                )
            )
            session.add(
                ManuscriptContents(
                    tenant_id=world.tenant_id,
                    entity_id=uuid.UUID(edition),
                    settings=ContentsSettings(enabled=True, depth=2).model_dump(),
                )
            )
            await session.commit()
        second_outline = (await owner.get(source + f"/writing/entries/{second}")).json()
        first_outline = (await owner.get(source + f"/writing/entries/{first}")).json()
        parent_outline = (await owner.get(source + f"/writing/entries/{edition}")).json()
        joined = await raw_client.post(
            source + f"/writing/entries/{second}/joins/{uuid.uuid4()}",
            headers={**owner.headers, "If-Match": second_outline["version"]},
            json={
                "destination_id": first,
                "parent_id": edition,
                "destination_version": first_outline["version"],
                "parent_version": parent_outline["version"],
            },
        )
        assert joined.status_code == 200, joined.text
        url = base + f"/writing/entries/{local[second]}/repository-updates"
        comparison = await owner.get(url)
        assert comparison.status_code == 200, comparison.text
        choices = {row["id"]: "upstream" for row in comparison.json()["rows"] if row["selectable"]}
        async with admin_session_factory() as session:
            destination_info = await session.scalar(
                select(Information).where(
                    Information.entity_id == uuid.UUID(local[first]),
                    Information.type == "manuscript",
                )
            )
            destination_info.is_public = True
            await session.commit()
        wider = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": choices},
        )
        assert wider.status_code == 409, wider.text
        assert "audience" in wider.text
        async with admin_session_factory() as session:
            destination_info = await session.scalar(
                select(Information).where(
                    Information.entity_id == uuid.UUID(local[first]),
                    Information.type == "manuscript",
                )
            )
            destination_info.is_public = False
            await session.commit()
        accepted = await raw_client.post(
            url,
            headers={**owner.headers, "If-Match": comparison.headers["etag"]},
            json={"choices": choices},
        )
        assert accepted.status_code == 200, accepted.text
        source_view = (await owner.get(base + f"/writing/entries/{local[second]}")).json()
        assert source_view["joined"] and source_view["joined_destination"]["id"] == local[first]
        destination = (await owner.get(base + f"/entities/{local[first]}")).json()
        assert [
            p["content"]
            for info in destination["information"]
            if info["type"] == "manuscript"
            for p in info["payloads"]
        ] == ["First prose", "Second prose"]
        async with admin_session_factory() as session:
            assert (await session.get(ManuscriptNumbering, uuid.UUID(local[edition]))).settings[
                "enabled"
            ]
            assert (await session.get(ManuscriptContents, uuid.UUID(local[edition]))).settings[
                "depth"
            ] == 2
        assert (await owner.get(url)).json()["rows"] == []
    finally:
        if target:
            await delete_tenant(target)
        await delete_tenant(world.tenant_id)
