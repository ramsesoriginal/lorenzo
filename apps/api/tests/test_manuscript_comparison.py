"""Manuscript comparisons retain true copy baselines without changing either side."""

import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from sqlalchemy import select, update

from lorenzo_api.config import get_settings
from lorenzo_api.manuscript_comparison import bundle, copy_baselines
from lorenzo_api.models import (
    Entity,
    Information,
    Payload,
    PayloadDescription,
    RepositoryCopyLinkEntity,
)
from lorenzo_api.repository_content import Content, InformationData, PayloadData


def test_binary_fingerprint_and_stable_order():
    entity, info, first, second = [uuid.uuid4() for _ in range(4)]
    content = Content(tenant_id=uuid.uuid4())
    content.information[info] = InformationData(entity, "Manuscript", "manuscript", False, 0)
    content.payloads[first] = PayloadData(
        info, 1, "picture", {"data": b"image", "file_type": "image/png"}
    )
    content.payloads[second] = PayloadData(
        info, 0, "description", {"content": "Text", "locale": "en"}
    )
    snapshot = bundle(content, entity)
    assert snapshot is not None
    assert [p["id"] for p in snapshot["payloads"]] == [str(second), str(first)]
    picture = snapshot["payloads"][1]["fields"]
    assert len(picture["data_sha256"]) == 64 and "data" not in picture

    local_entity, local_info, local_first, local_second = [uuid.uuid4() for _ in range(4)]
    saved = copy_baselines(content, {info: local_info}, {first: local_first, second: local_second})[
        entity
    ]
    local = Content(tenant_id=uuid.uuid4())
    local.information[local_info] = InformationData(
        local_entity, "Manuscript", "manuscript", False, 0
    )
    local.payloads[local_first] = PayloadData(
        local_info, 1, "picture", content.payloads[first].fields
    )
    local.payloads[local_second] = PayloadData(
        local_info, 0, "description", content.payloads[second].fields
    )
    assert bundle(local, local_entity, saved["identities"]) == saved["bundle"]
    local.payloads[local_first].order = -1
    assert bundle(local, local_entity, saved["identities"]) != saved["bundle"]


@pytest.mark.parametrize("public", [False, True])
async def test_copy_comparison_and_access(
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
        chapter = (
            await world.author.post(source + "/writing/chapters", json={"name": "Crossing"})
        ).json()["id"]
        made = await world.author.post(
            source + f"/entities/{chapter}/information",
            json={"type": "manuscript", "title": "Manuscript", "content": "Original"},
        )
        assert made.status_code == 201, made.text
        source_info = made.json()["id"]
        target = await owner.create_tenant("Subscriber")
        local_base = f"/tenants/{target}"
        assert (await owner.put(source + f"/subscribers/{target}")).status_code in (200, 201)
        published = await owner.put(source + "/published")
        assert published.status_code == 200, published.text
        if public:
            flipped = await owner.put(
                source + "/public", json={"summary": "River stories", "accept_terms": True}
            )
            assert flipped.status_code == 200, flipped.text
        copied = await owner.post(local_base + f"/repositories/{world.tenant_id}/copy")
        assert copied.status_code == 201, copied.text
        rows = (await owner.get(local_base + "/entities")).json()["items"]
        local = next(row["id"] for row in rows if row["name"] == "Crossing")
        url = local_base + f"/writing/entries/{local}/repository-comparison"

        async def read():
            result = await owner.get(url)
            assert result.status_code == 200, result.text
            assert result.headers["cache-control"] == "private, no-store"
            return result.json()

        async def edit(info_id, content):
            async with admin_session_factory() as session:
                payload = await session.scalar(
                    select(Payload.id).where(Payload.information_id == uuid.UUID(str(info_id)))
                )
                await session.execute(
                    update(PayloadDescription)
                    .where(PayloadDescription.payload_id == payload)
                    .values(content=content)
                )
                await session.commit()

        initial = await read()
        assert initial["state"] == "unchanged"
        assert initial["base"] == initial["local"] == initial["upstream"]
        async with admin_session_factory() as session:
            local_info = await session.scalar(
                select(Information.id).where(Information.entity_id == uuid.UUID(local))
            )
        await edit(source_info, "Upstream")
        if public:
            assert (await read())["state"] == "unchanged"
            released = await owner.put(source + "/published")
            assert released.status_code == 200, released.text
        assert (await read())["state"] == "upstream"
        await edit(local_info, "Local")
        assert (await read())["state"] == "conflict"
        await edit(local_info, "Upstream")
        assert (await read())["state"] == "matching"
        await edit(source_info, "Original")
        if public:
            assert (await owner.put(source + "/published")).status_code == 200
        assert (await read())["state"] == "local"

        # Ordinary entity updates preserve the manuscript baseline.
        async with admin_session_factory() as session:
            await session.execute(
                update(Entity).where(Entity.id == uuid.UUID(chapter)).values(name="New title")
            )
            await session.commit()
        if public:
            assert (await owner.put(source + "/published")).status_code == 200
        applied = await owner.post(
            local_base + f"/repositories/{world.tenant_id}/updates",
            json={"actions": [{"kind": "entity", "source_id": chapter, "action": "apply"}]},
        )
        assert applied.status_code == 200, applied.text
        assert (await read())["base"] == initial["base"]
        assert (await world.outsider.get(url)).status_code in (403, 404)
        assert (await owner.get(url.replace(str(target), str(world.tenant_id)))).status_code == 404
        assert (await owner.delete(source + f"/subscribers/{target}")).status_code in (200, 204)
        assert (await owner.get(url)).status_code == (200 if public else 404)
        assert (await owner.put(source + f"/subscribers/{target}")).status_code in (200, 201)

        async with admin_session_factory() as session:
            await session.execute(
                update(Information).where(Information.id == local_info).values(type="note")
            )
            await session.commit()
        unavailable = await read()
        assert unavailable["state"] == "local_unavailable" and unavailable["base"] is None
        async with admin_session_factory() as session:
            await session.execute(
                update(Information).where(Information.id == local_info).values(type="manuscript")
            )
            await session.commit()

        # An older copy has no fabricated baseline, and replacement bundles reveal no retained text.
        async with admin_session_factory() as session:
            await session.execute(
                update(RepositoryCopyLinkEntity)
                .where(RepositoryCopyLinkEntity.tenant_id == target)
                .values(manuscript_baseline=None)
            )
            await session.commit()
        assert (await read())["state"] == "no_baseline"
        assert (await read())["base"] is None
    finally:
        if target:
            await delete_tenant(target)
        await world.clean_up()
