"""Saved export source is lossless, conditional and permission scoped (ADR 0478)."""

import base64
import io
import json
import uuid
import zipfile

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from sqlalchemy import update

from lorenzo_api.models import PayloadDescription


async def test_source_archive_saved_text_and_stale_guard(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:
        chapter = (await actor.post(base + "/writing/chapters", json={"name": "Crossing"})).json()
        id = chapter["id"]
        content = "\ufeff# Crossing\r\n\r\nA river — and **a boat**.\n"
        made = await actor.post(
            base + f"/entities/{id}/information",
            json={"title": "Manuscript", "type": "manuscript", "content": content},
        )
        assert made.status_code == 201, made.text
        url = base + f"/writing/entries/{id}/export"
        preview = await actor.get(url)
        assert preview.status_code == 200, preview.text
        snapshot = preview.json()
        assert preview.headers["cache-control"] == "private, no-store"
        assert snapshot["payloads"][0]["content"] == content
        assert (await actor.get(url + "/source")).status_code == 428
        download = await raw_client.get(
            url + "/source", headers={**actor.headers, "If-Match": snapshot["version"]}
        )
        assert download.status_code == 200, download.text
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            payload = manifest["payloads"][0]
            assert archive.read(payload["path"]) == content.encode("utf-8")
            assert manifest["entries"][0]["id"] == id
            assert "content" not in payload
        assert (await world.outsider.get(url)).status_code in {403, 404}
        payload = made.json()["payloads"][0]
        extra = await raw_client.patch(
            base + f"/payloads/{payload['id']}",
            headers={**actor.headers, "If-Match": f'W/"{payload["updated_at"]}"'},
            json={"content": "Later."},
        )
        assert extra.status_code == 200, extra.text
        stale = await raw_client.get(
            url + "/source", headers={**actor.headers, "If-Match": snapshot["version"]}
        )
        assert stale.status_code == 412, stale.text
    finally:
        await world.clean_up()


async def test_review_export_shared_scene_picture_and_revocation(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:
        book = (await actor.post(base + "/writing/books", json={"name": "Voyage"})).json()
        edition = book["editions"][0]["id"]
        scene = (await actor.post(base + "/scenes", json={"name": "Private identity"})).json()["id"]
        info = (
            await actor.post(
                base + f"/entities/{scene}/information",
                json={"type": "manuscript", "title": "Writing", "content": "A crossing."},
            )
        ).json()
        picture = await raw_client.post(
            base + f"/information/{info['id']}/payloads",
            headers=actor.headers,
            files={"file": ("map.png", b"original image bytes", "image/png")},
        )
        assert picture.status_code == 201, picture.text
        telling = (
            await actor.post(base + "/writing/tellings", json={"name": "Voyage", "scene_id": scene})
        ).json()["id"]
        view = (await actor.get(base + f"/writing/entries/{edition}")).json()
        placed = await raw_client.put(
            base + f"/writing/entries/{edition}/composition",
            headers={**actor.headers, "If-Match": view["version"]},
            json={"elements": [telling]},
        )
        assert placed.status_code == 200, placed.text
        review = base + f"/writing/reviews/{edition}"
        grant = review + f"/reviewers/{world.outsider.user_id}"
        assert (await actor.put(grant)).status_code == 204
        response = await world.outsider.get(review + "/export")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        assert scene not in response.text and "Private identity" not in response.text
        assert {entry["id"] for entry in snapshot["entries"]} == {edition, telling}
        assert (
            next(entry for entry in snapshot["entries"] if entry["id"] == telling)[
                "uses_scene_manuscript"
            ]
            is True
        )
        exported = next(payload for payload in snapshot["payloads"] if payload["kind"] == "picture")
        assert base64.b64decode(exported["data"]) == b"original image bytes"
        downloaded = await raw_client.get(
            review + "/export/source",
            headers={**world.outsider.headers, "If-Match": snapshot["version"]},
        )
        assert downloaded.status_code == 200, downloaded.text
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            image = next(p for p in manifest["payloads"] if p["kind"] == "picture")
            assert archive.read(image["path"]) == b"original image bytes"
        current = (await actor.get(base + f"/writing/entries/{telling}")).json()
        independent = await raw_client.post(
            base + f"/writing/tellings/{telling}/independent",
            headers={**actor.headers, "If-Match": current["version"]},
        )
        assert independent.status_code == 200, independent.text
        changed = await world.outsider.get(review + "/export")
        assert changed.status_code == 200, changed.text
        assert (
            next(e for e in changed.json()["entries"] if e["id"] == telling)[
                "uses_scene_manuscript"
            ]
            is False
        )
        assert changed.json()["version"] != snapshot["version"]
        assert (await actor.delete(grant)).status_code == 204
        revoked = await raw_client.get(
            review + "/export/source",
            headers={**world.outsider.headers, "If-Match": snapshot["version"]},
        )
        assert revoked.status_code == 404, revoked.text
    finally:
        await world.clean_up()


async def test_export_repeatable_read_and_byte_bound(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lorenzo_api import manuscript_export

    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:
        chapter = (await actor.post(base + "/writing/chapters", json={"name": "River"})).json()[
            "id"
        ]
        info = (
            await actor.post(
                base + f"/entities/{chapter}/information",
                json={"type": "manuscript", "title": "Writing", "content": "Before."},
            )
        ).json()
        original = manuscript_export.ordinary_entries

        async def concurrent(*args, **kwargs):
            entries = await original(*args, **kwargs)
            async with admin_session_factory() as session:
                await session.execute(
                    update(PayloadDescription)
                    .where(PayloadDescription.payload_id == uuid.UUID(info["payloads"][0]["id"]))
                    .values(content="After concurrent save.")
                )
                await session.commit()
            return entries

        monkeypatch.setattr(manuscript_export, "ordinary_entries", concurrent)
        url = base + f"/writing/entries/{chapter}/export"
        before = await actor.get(url)
        assert before.status_code == 200, before.text
        assert before.json()["payloads"][0]["content"] == "Before."
        monkeypatch.setattr(manuscript_export, "ordinary_entries", original)
        after = await actor.get(url)
        assert after.json()["payloads"][0]["content"] == "After concurrent save."
        assert after.json()["version"] != before.json()["version"]
        monkeypatch.setattr(manuscript_export, "MAX_BYTES", 5)
        oversized = await actor.get(url)
        assert oversized.status_code == 422, oversized.text
        assert "smaller section" in oversized.text
    finally:
        await world.clean_up()


async def test_carrier_partial_repeated_and_independent_visibility(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    from conftest import make_campaign

    from lorenzo_api.models import EntityAudience, Information, Player

    world = await make_world(raw_client, fake_jwks_server)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:
        carrier = (await actor.post(base + "/writing/carriers", json={"name": "Tablet"})).json()
        chapter = (
            await actor.post(base + "/writing/chapters", json={"name": "Private chapter"})
        ).json()
        info = (
            await actor.post(
                base + f"/entities/{chapter['id']}/information",
                json={"type": "manuscript", "title": "Writing", "content": "Selected prose."},
            )
        ).json()
        picture = await raw_client.post(
            base + f"/information/{info['id']}/payloads",
            headers=actor.headers,
            files={"file": ("secret.png", b"not selected", "image/png")},
        )
        assert picture.status_code == 201, picture.text
        refs = [
            {"id": str(uuid.uuid4()), "target_payload_id": info["payloads"][0]["id"]}
            for _ in range(2)
        ]
        placed = await raw_client.put(
            base + f"/writing/carriers/{carrier['id']}/coverage",
            headers={**actor.headers, "If-Match": carrier["version"]},
            json={"elements": refs},
        )
        assert placed.status_code == 200, placed.text
        url = base + f"/writing/entries/{carrier['id']}/export"
        saved = await actor.get(url)
        assert saved.status_code == 200, saved.text
        assert len(saved.json()["payloads"]) == 1
        assert picture.json()["id"] not in saved.text
        from lorenzo_api import manuscript_export

        with monkeypatch.context() as limits:
            limits.setattr(manuscript_export, "MAX_BYTES", len(b"Selected prose.") + 1)
            assert (await actor.get(url)).status_code == 422

        root = next(entry for entry in saved.json()["entries"] if entry["id"] == carrier["id"])
        assert [element["id"] for element in root["elements"]] == [ref["id"] for ref in refs]
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=world.tenant_id)
            session.add(
                Player(
                    tenant_id=world.tenant_id,
                    campaign_id=campaign.id,
                    user_id=world.outsider.user_id,
                )
            )
            (await session.get(EntityAudience, uuid.UUID(carrier["id"]))).is_public = True
            await session.commit()
        hidden = await world.outsider.get(url)
        assert hidden.status_code == 200, hidden.text
        assert hidden.json()["payloads"] == [] and chapter["id"] not in hidden.text
        async with admin_session_factory() as session:
            (await session.get(EntityAudience, uuid.UUID(chapter["id"]))).is_public = True
            await session.commit()
        still_private = await world.outsider.get(url)
        assert still_private.json()["payloads"] == [] and chapter["id"] not in still_private.text
        async with admin_session_factory() as session:
            (await session.get(Information, uuid.UUID(info["id"]))).is_public = True
            await session.commit()
        visible = await world.outsider.get(url)
        assert visible.status_code == 200, visible.text
        assert len(visible.json()["payloads"]) == 1
        assert "Selected prose." in visible.text and picture.json()["id"] not in visible.text
    finally:
        await world.clean_up()


async def test_nested_numbering_contents_redirect_and_bounds(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lorenzo_api import manuscript_export

    world = await make_world(raw_client, fake_jwks_server, kind="repository")
    actor = world.author
    base = f"/tenants/{world.tenant_id}/writing"
    try:
        book = (await actor.post(base + "/books", json={"name": "River"})).json()
        edition = book["editions"][0]["id"]
        chapters = [
            (await actor.post(base + "/chapters", json={"name": name})).json()["id"]
            for name in ["First", "Second", "Nested"]
        ]
        first, second, nested = chapters

        async def read(id):
            return (await actor.get(base + f"/entries/{id}")).json()

        async def arrange(id, children):
            response = await raw_client.put(
                base + f"/entries/{id}/composition",
                headers={**actor.headers, "If-Match": (await read(id))["version"]},
                json={"elements": children},
            )
            assert response.status_code == 200, response.text

        await arrange(edition, [first, second])
        await arrange(first, [nested])
        for kind in ["numbering", "contents"]:
            url = base + f"/entries/{edition}/{kind}"
            settings = (await actor.get(url)).json()
            saved = await raw_client.put(
                url,
                headers={**actor.headers, "If-Match": settings["version"]},
                json={**settings["settings"], "enabled": True},
            )
            assert saved.status_code == 200, saved.text
        url = base + f"/entries/{edition}/export"
        exported = await actor.get(url)
        assert exported.status_code == 200, exported.text
        entries = {entry["id"]: entry for entry in exported.json()["entries"]}
        assert entries[first]["number"] == "1" and entries[nested]["number"] == "1.1"
        assert [row["label"] for row in entries[edition]["contents"]] == [
            "1 First",
            "1.1 Nested",
            "2 Second",
        ]
        assert entries[edition]["numbering"]["enabled"] is True
        monkeypatch.setattr(manuscript_export, "MAX_ENTRIES", 3)
        assert (await actor.get(url)).status_code == 422
        monkeypatch.setattr(manuscript_export, "MAX_ENTRIES", 5000)
        monkeypatch.setattr(manuscript_export, "MAX_OCCURRENCES", 3)
        assert (await actor.get(url)).status_code == 422
        monkeypatch.setattr(manuscript_export, "MAX_OCCURRENCES", 20000)
        prose = await actor.post(
            f"/tenants/{world.tenant_id}/entities/{second}/information",
            json={"type": "manuscript", "title": "Writing", "content": "Joined passage."},
        )
        assert prose.status_code == 201, prose.text
        joined = await raw_client.post(
            base + f"/entries/{second}/joins/{uuid.uuid4()}",
            headers={**actor.headers, "If-Match": (await read(second))["version"]},
            json={
                "destination_id": first,
                "parent_id": edition,
                "destination_version": (await read(first))["version"],
                "parent_version": (await read(edition))["version"],
            },
        )
        assert joined.status_code == 200, joined.text
        redirected = await actor.get(base + f"/entries/{second}/export")
        assert redirected.status_code == 200, redirected.text
        snapshot = redirected.json()
        assert snapshot["payloads"] == [] and len(snapshot["entries"]) == 1
        assert snapshot["entries"][0]["joined_destination"]["id"] == first
        assert "Joined passage." not in redirected.text
    finally:
        await world.clean_up()


def test_occurrence_walk_is_iterative_and_rejects_cycles() -> None:
    from lorenzo_api.exceptions import ManuscriptExportError
    from lorenzo_api.manuscript_export import ExportEntry, ExportSnapshot, check_occurrences
    from lorenzo_api.routers.writing import Element

    ids = [uuid.uuid4() for _ in range(1200)]
    entries = [
        ExportEntry(
            id=id,
            name="Nested",
            kind="chapter",
            elements=[Element(id=ids[index + 1], kind="chapter")] if index + 1 < len(ids) else [],
        )
        for index, id in enumerate(ids)
    ]
    snapshot = ExportSnapshot(root_id=ids[0], entries=entries)
    check_occurrences(snapshot)
    entries[-1].elements.append(Element(id=ids[0], kind="chapter"))
    with pytest.raises(ManuscriptExportError) as caught:
        check_occurrences(snapshot)
    assert "cycle" in caught.value.detail
