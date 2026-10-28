"""Whole-element extraction preserves manuscript identities and audiences (ADR 0345)."""

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
    Entity,
    EntityAudience,
    EntityKnowledge,
    Information,
    Knowledge,
    ManuscriptExtraction,
    ManuscriptRevision,
    Payload,
    PayloadPicture,
)


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_extraction_preserves_content_scope_and_retry(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    copy_id = None
    try:
        book = (await actor.post(base + "/writing/books", json={"name": "Voyage"})).json()
        source = book["editions"][0]["id"]
        child = (
            await actor.post(base + "/writing/chapters", json={"name": "Existing child"})
        ).json()["id"]
        prose = (
            "A **whole** passage[^a].\n\n[^a]: A local footnote with [link](https://example.com)."
        )
        info = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": prose},
            )
        ).json()
        note = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"type": "note", "title": "Research", "content": "Keep here"},
            )
        ).json()
        payload = info["payloads"][0]["id"]
        picture = uuid.uuid4()
        async with admin_session_factory() as session:
            session.add(
                Payload(
                    id=picture,
                    tenant_id=world.tenant_id,
                    information_id=uuid.UUID(info["id"]),
                    order=1,
                )
            )
            await session.flush()
            session.add(
                PayloadPicture(
                    payload_id=picture,
                    tenant_id=world.tenant_id,
                    data=b"unchanged picture",
                    file_type="image/png",
                )
            )
            outer = await session.get(EntityAudience, uuid.UUID(source))
            outer.is_public = kind == "play"
            bundle = await session.get(Information, uuid.UUID(info["id"]))
            bundle.is_public = kind == "play"
            session.add(
                EntityKnowledge(
                    tenant_id=world.tenant_id,
                    entity_id=uuid.UUID(source),
                    knower_entity_id=uuid.UUID(child),
                )
            )
            session.add(
                Knowledge(
                    tenant_id=world.tenant_id,
                    information_id=bundle.id,
                    knower_entity_id=uuid.UUID(child),
                )
            )
            await session.commit()
        before_ids = [payload, child, str(picture)]

        async def outline(entry: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{entry}")
            assert response.status_code == 200, response.text
            return response.json()

        current = await outline(source)
        arranged = await raw_client.put(
            base + f"/writing/entries/{source}/composition",
            headers={**actor.headers, "If-Match": current["version"]},
            json={"elements": before_ids},
        )
        assert arranged.status_code == 200, arranged.text
        current = arranged.json()
        chapter = str(uuid.uuid4())
        operation = uuid.uuid4()
        url = base + f"/writing/entries/{source}/extractions/{operation}"
        body = {"chapter_id": chapter, "name": "Extracted", "elements": before_ids}
        headers = {**actor.headers, "If-Match": current["version"]}
        assert (await actor.post(url, json=body)).status_code == 428
        assert (
            await raw_client.post(url, headers={**headers, "If-Match": 'W/"old"'}, json=body)
        ).status_code == 412
        for invalid in [
            [payload, str(picture)],
            [child, payload],
            [payload, payload],
            [str(uuid.uuid4())],
        ]:
            response = await raw_client.post(
                url, headers=headers, json={**body, "elements": invalid}
            )
            assert response.status_code == 409, response.text
        collision = await raw_client.post(url, headers=headers, json={**body, "chapter_id": source})
        assert collision.status_code == 409, collision.text
        assert (await outline(source))["elements"] == current["elements"]
        assert (await world.outsider.post(url, json=body)).status_code in {403, 404}
        review_url = base + f"/writing/reviews/{source}"
        assert (
            await actor.put(review_url + f"/reviewers/{world.outsider.user_id}")
        ).status_code == 204
        # Review notes remain attached to their original identity.
        review_note_id = uuid.uuid4()
        assert (
            await world.outsider.put(
                review_url + f"/notes/{review_note_id}",
                json={"entry_id": child, "content": "Keep this feedback"},
            )
        ).status_code in {200, 201}
        response = await raw_client.post(url, headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert [el["id"] for el in (await outline(source))["elements"]] == [chapter]
        assert [el["id"] for el in (await outline(chapter))["elements"]] == before_ids
        assert (await outline(child))["parent_id"] == chapter
        assert note["id"] in {
            i["id"] for i in (await actor.get(base + f"/entities/{source}")).json()["information"]
        }
        checkpoint = await actor.get(url)
        assert checkpoint.json()["checkpoint"]["before"][source] == before_ids
        async with admin_session_factory() as session:
            moved = await session.get(Payload, uuid.UUID(payload))
            extracted = await session.get(Information, moved.information_id)
            original = await session.get(Information, uuid.UUID(info["id"]))
            assert extracted.entity_id == uuid.UUID(chapter)
            assert extracted.created_by == original.created_by
            assert extracted.is_public == original.is_public
            assert (await session.get(EntityAudience, uuid.UUID(chapter))).is_public == (
                kind == "play"
            )
            assert list(
                await session.scalars(
                    select(EntityKnowledge.knower_entity_id).where(
                        EntityKnowledge.entity_id == uuid.UUID(chapter)
                    )
                )
            ) == [uuid.UUID(child)]
            assert list(
                await session.scalars(
                    select(Knowledge.knower_entity_id).where(
                        Knowledge.information_id == extracted.id
                    )
                )
            ) == [uuid.UUID(child)]
            assert (await session.get(PayloadPicture, picture)).data == b"unchanged picture"
            revisions = list(
                await session.scalars(
                    select(ManuscriptRevision)
                    .where(ManuscriptRevision.information_id == original.id)
                    .order_by(ManuscriptRevision.created_at.desc())
                )
            )
            snapshot = revisions[0].snapshot["payloads"]
            assert [p["id"] for p in snapshot] == [payload, str(picture)]
            assert snapshot[0]["description"]["content"] == prose
        review = await world.outsider.get(review_url)
        assert review.status_code == 200
        assert prose in [
            element["content"] for item in review.json()["entries"] for element in item["elements"]
        ]
        assert str(review_note_id) in review.text
        assert (
            await world.outsider.get(review_url + f"/pictures/{picture}")
        ).content == b"unchanged picture"
        assert (await world.outsider.get(url)).status_code in {403, 404}
        # Replay stays an acknowledgement after a later nested extraction.
        nested_current = await outline(chapter)
        second_body = {"chapter_id": str(uuid.uuid4()), "name": "Nested", "elements": [child]}
        second = await raw_client.post(
            base + f"/writing/entries/{chapter}/extractions/{uuid.uuid4()}",
            headers={**actor.headers, "If-Match": nested_current["version"]},
            json=second_body,
        )
        assert second.status_code == 200, second.text
        replay = await raw_client.post(url, headers=headers, json=body)
        assert replay.json() == response.json()
        assert (await outline(child))["parent_id"] == second_body["chapter_id"]
        assert (
            await raw_client.post(url, headers=headers, json={**body, "name": "Changed"})
        ).status_code == 409
        assert (
            await raw_client.post(
                url, headers={**world.owner.headers, "If-Match": current["version"]}, json=body
            )
        ).status_code == 409
        if kind == "repository":
            copy_id = await world.owner.create_tenant("Extraction copy")
            await world.owner.put(base + f"/subscribers/{copy_id}")
            assert (await world.owner.put(base + "/published")).status_code == 200
            copied = await world.owner.post(
                f"/tenants/{copy_id}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            async with admin_session_factory() as session:
                copied_source = await session.scalar(
                    select(Entity.id).where(Entity.tenant_id == copy_id, Entity.name == "Extracted")
                )
                assert not list(
                    await session.scalars(
                        select(ManuscriptExtraction).where(
                            ManuscriptExtraction.tenant_id == copy_id
                        )
                    )
                )
            copy_url = f"/tenants/{copy_id}/writing/entries/{copied_source}"
            copy_outline = (await world.owner.get(copy_url)).json()
            assert [e["kind"] for e in copy_outline["elements"]] == [
                "payload",
                "chapter",
                "payload",
            ]
            collision_id = str(uuid.uuid4())
            collision = await raw_client.post(
                copy_url + f"/extractions/{operation}",
                headers={**world.owner.headers, "If-Match": copy_outline["version"]},
                json={
                    "chapter_id": collision_id,
                    "name": "Rolled back",
                    "elements": [copy_outline["elements"][0]["id"]],
                },
            )
            assert collision.status_code == 409, collision.text
            assert (await world.owner.get(copy_url)).json() == copy_outline
            assert (
                await world.owner.get(f"/tenants/{copy_id}/entities/{collision_id}")
            ).status_code == 404
        # Competing extractions cannot both apply to the same version.
        current = await outline(chapter)
        replies = await asyncio.gather(
            *[
                raw_client.post(
                    base + f"/writing/entries/{chapter}/extractions/{uuid.uuid4()}",
                    headers={**actor.headers, "If-Match": current["version"]},
                    json={"chapter_id": str(uuid.uuid4()), "name": "Race", "elements": [payload]},
                )
                for _ in range(2)
            ]
        )
        assert sorted(r.status_code for r in replies) == [200, 412], [r.text for r in replies]
    finally:
        if copy_id:
            await cleanup([copy_id], [])
        await world.clean_up()


async def test_extraction_receipts_force_rls_and_are_not_published() -> None:
    from lorenzo_api.copyable_tables import EXCLUDED_TABLES

    assert "manuscript_extraction" in EXCLUDED_TABLES
    async with admin_session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname='manuscript_extraction'"
                )
            )
        ).one()
        assert row == (True, True)
