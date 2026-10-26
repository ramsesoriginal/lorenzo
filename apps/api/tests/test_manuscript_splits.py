"""Paragraph splitting through the real API, with revisions, reviews and retries."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.models import (
    Edition,
    ManuscriptRevision,
    ManuscriptSplit,
    Payload,
    PayloadDescription,
)


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_split_preserves_source_and_retries(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    copy_id = None
    try:
        book = (await actor.post(base + "/writing/books", json={"name": "Split book"})).json()
        source = book["editions"][0]["id"]
        children = [
            (await actor.post(base + "/writing/chapters", json={"name": name})).json()["id"]
            for name in ["Before", "After"]
        ]
        left = "One.\n\nFirst 🐉[^a].\n\n[^a]: A complete note.\n\n"
        right = "Second [[Eira]] with **bold** text."
        original = left + right
        info = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"title": "Manuscript", "type": "manuscript", "content": original},
            )
        ).json()
        first = info["payloads"][0]["id"]
        note = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"title": "Research", "type": "note", "content": "Do not move"},
            )
        ).json()

        async def outline() -> dict:
            return (await actor.get(base + f"/writing/entries/{source}")).json()

        current = await outline()
        arranged = await raw_client.put(
            base + f"/writing/entries/{source}/composition",
            headers={**actor.headers, "If-Match": current["version"]},
            json={"elements": [children[0], first, children[1]]},
        )
        assert arranged.status_code == 200, arranged.text
        points_url = base + f"/writing/entries/{source}/payloads/{first}/split-points"
        points = await actor.get(points_url)
        assert points.status_code == 200, points.text
        assert points.json()["source"] == original
        assert len(left) in [p["offset"] for p in points.json()["points"]]
        assert (await world.outsider.get(points_url)).status_code in {403, 404}
        second = str(uuid.uuid4())
        operation = uuid.uuid4()
        url = base + f"/writing/entries/{source}/splits/{operation}"
        body = {"payload_id": first, "second_payload_id": second, "offset": len(left)}
        headers = {**actor.headers, "If-Match": points.json()["version"]}
        assert (await actor.post(url, json=body)).status_code == 428
        assert (
            await raw_client.post(url, headers={**headers, "If-Match": 'W/"old"'}, json=body)
        ).status_code == 412
        assert (
            await raw_client.post(url, headers=headers, json={**body, "offset": 1})
        ).status_code == 409
        assert (
            await raw_client.post(
                url, headers=headers, json={**body, "payload_id": str(uuid.uuid4())}
            )
        ).status_code == 409
        assert (
            await raw_client.post(url, headers=headers, json={**body, "second_payload_id": first})
        ).status_code == 409
        assert (await actor.get(points_url)).json()["source"] == original
        review_url = base + f"/writing/reviews/{source}"
        await actor.put(review_url + f"/reviewers/{world.outsider.user_id}")
        assert (await world.outsider.get(points_url)).status_code in {403, 404}
        response = await raw_client.post(url, headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert [e["id"] for e in (await outline())["elements"]] == [
            children[0],
            first,
            second,
            children[1],
        ]
        saved = (await actor.get(base + f"/information/{info['id']}")).json()
        assert [p["id"] for p in saved["payloads"]] == [first, second]
        assert [p["content"] for p in saved["payloads"]] == [left, right]
        assert saved["payloads"][0]["locale"] == saved["payloads"][1]["locale"]
        assert saved["is_public"] == info["is_public"]
        assert (await actor.get(base + f"/information/{note['id']}")).json()["title"] == "Research"
        review = (await world.outsider.get(review_url)).json()
        assert left in [el["content"] for entry in review["entries"] for el in entry["elements"]]
        assert right in [el["content"] for entry in review["entries"] for el in entry["elements"]]
        async with admin_session_factory() as session:
            revision = await session.scalar(
                select(ManuscriptRevision)
                .where(ManuscriptRevision.information_id == uuid.UUID(info["id"]))
                .order_by(ManuscriptRevision.created_at.desc())
            )
            assert revision.snapshot["payloads"][0]["description"]["content"] == original
        # Move the second part into its own Chapter, then retry the original split.
        current = await outline()
        extraction = await raw_client.post(
            base + f"/writing/entries/{source}/extractions/{uuid.uuid4()}",
            headers={**actor.headers, "If-Match": current["version"]},
            json={"chapter_id": str(uuid.uuid4()), "name": "Second part", "elements": [second]},
        )
        assert extraction.status_code == 200, extraction.text
        retry = await raw_client.post(url, headers=headers, json=body)
        assert retry.status_code == 200 and retry.json() == response.json()
        assert (
            await raw_client.post(url, headers=headers, json={**body, "offset": len("One.\n\n")})
        ).status_code == 409
        assert (
            await raw_client.post(
                url, headers={**world.owner.headers, "If-Match": headers["If-Match"]}, json=body
            )
        ).status_code == 409
        if kind == "repository":
            copy_id = await world.owner.create_tenant("Split copy")
            await world.owner.put(base + f"/subscribers/{copy_id}")
            assert (await world.owner.put(base + "/published")).status_code == 200
            copied = await world.owner.post(
                f"/tenants/{copy_id}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            async with admin_session_factory() as session:
                copied_source = await session.scalar(
                    select(Edition.entity_id).where(Edition.tenant_id == copy_id)
                )
                assert not list(
                    await session.scalars(
                        select(ManuscriptSplit).where(ManuscriptSplit.tenant_id == copy_id)
                    )
                )
                copied_texts = list(
                    await session.scalars(
                        select(PayloadDescription.content).where(
                            PayloadDescription.tenant_id == copy_id
                        )
                    )
                )
                assert left in copied_texts and right in copied_texts
            copy_base = f"/tenants/{copy_id}/writing/entries/{copied_source}"
            copied_outline = (await world.owner.get(copy_base)).json()
            copied_first = next(
                e["id"] for e in copied_outline["elements"] if e["kind"] == "payload"
            )
            collision_id = uuid.uuid4()
            collision = await raw_client.post(
                copy_base + f"/splits/{operation}",
                headers={**world.owner.headers, "If-Match": copied_outline["version"]},
                json={
                    "payload_id": copied_first,
                    "second_payload_id": str(collision_id),
                    "offset": len("One.\n\n"),
                },
            )
            assert collision.status_code == 409, collision.text
            assert (await world.owner.get(copy_base)).json() == copied_outline
            async with admin_session_factory() as session:
                assert await session.get(Payload, collision_id) is None
                assert (
                    await session.get(PayloadDescription, uuid.UUID(copied_first))
                ).content == left
        # Both requests read the same source; exactly one can split it.
        current = await outline()
        replies = await asyncio.gather(
            *[
                raw_client.post(
                    base + f"/writing/entries/{source}/splits/{uuid.uuid4()}",
                    headers={**actor.headers, "If-Match": current["version"]},
                    json={
                        "payload_id": first,
                        "second_payload_id": str(uuid.uuid4()),
                        "offset": len("One.\n\n"),
                    },
                )
                for _ in range(2)
            ]
        )
        assert sorted(r.status_code for r in replies) == [200, 412], [r.text for r in replies]
    finally:
        if copy_id:
            await cleanup([copy_id], [])
        await world.clean_up()


async def test_split_receipts_are_private_and_not_published() -> None:
    from lorenzo_api.copyable_tables import EXCLUDED_TABLES

    assert "manuscript_split" in EXCLUDED_TABLES
    async with admin_session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname='manuscript_split'"
                )
            )
        ).one()
        assert row == (True, True)
