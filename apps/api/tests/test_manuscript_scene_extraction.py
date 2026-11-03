"""Scene extraction preserves content and reviewer scope (ADR 0378)."""

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
    ManuscriptRevision,
    ManuscriptSceneExtraction,
    Payload,
    PayloadPicture,
    SceneTelling,
)


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_scene_extraction(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    copy_id = None
    try:
        book = (await actor.post(base + "/writing/books", json={"name": "Voyage"})).json()
        source = book["editions"][0]["id"]
        child = (await actor.post(base + "/writing/chapters", json={"name": "Keep child"})).json()[
            "id"
        ]
        prose = "A **whole** passage[^a].\n\n[^a]: A local footnote."
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
            outer.shared_with_participants = True
            bundle = await session.get(Information, uuid.UUID(info["id"]))
            bundle.shared_with_participants = True
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

        async def outline(entry: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{entry}")
            assert response.status_code == 200, response.text
            return response.json()

        current = await outline(source)
        arranged = await raw_client.put(
            base + f"/writing/entries/{source}/composition",
            headers={**actor.headers, "If-Match": current["version"]},
            json={"elements": [payload, str(picture), child]},
        )
        assert arranged.status_code == 200, arranged.text
        current = arranged.json()
        scene, telling, operation = [str(uuid.uuid4()) for _ in range(3)]
        url = base + f"/writing/entries/{source}/scene-extractions/{operation}"
        body = {
            "scene_id": scene,
            "telling_id": telling,
            "name": "Extracted",
            "elements": [payload, str(picture)],
        }
        headers = {**actor.headers, "If-Match": current["version"]}
        assert (await actor.post(url, json=body)).status_code == 428
        assert (
            await raw_client.post(url, headers={**headers, "If-Match": 'W/"old"'}, json=body)
        ).status_code == 412
        for invalid in [
            [payload, str(picture), child],
            [str(picture), payload],
            [payload, payload],
            [str(uuid.uuid4())],
        ]:
            response = await raw_client.post(
                url, headers=headers, json={**body, "elements": invalid}
            )
            assert response.status_code == 409, response.text
        for invalid in [{"scene_id": source}, {"telling_id": source}, {"telling_id": scene}]:
            assert (
                await raw_client.post(url, headers=headers, json={**body, **invalid})
            ).status_code == 409
        assert (await outline(source)) == current
        assert (await world.outsider.post(url, json=body)).status_code in {403, 404}
        review_url = base + f"/writing/reviews/{source}"
        assert (
            await actor.put(review_url + f"/reviewers/{world.outsider.user_id}")
        ).status_code == 204
        response = await raw_client.post(url, headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "operation_id": operation,
            "source_id": source,
            "scene_id": scene,
            "telling_id": telling,
        }
        assert [el["id"] for el in (await outline(source))["elements"]] == [telling, child]
        assert [el["id"] for el in (await outline(scene))["elements"]] == [payload, str(picture)]
        assert (await outline(child))["parent_id"] == source
        assert note["id"] in {
            i["id"] for i in (await actor.get(base + f"/entities/{source}")).json()["information"]
        }
        async with admin_session_factory() as session:
            marker = await session.get(SceneTelling, uuid.UUID(telling))
            assert marker.scene_entity_id == uuid.UUID(scene)
            assert marker.uses_scene_manuscript
            moved = await session.get(Payload, uuid.UUID(payload))
            extracted = await session.get(Information, moved.information_id)
            original = await session.get(Information, uuid.UUID(info["id"]))
            assert extracted.entity_id == uuid.UUID(scene)
            assert extracted.created_by == original.created_by
            assert extracted.is_public == original.is_public
            assert extracted.shared_with_participants == original.shared_with_participants
            assert list(
                await session.scalars(
                    select(Knowledge.knower_entity_id).where(
                        Knowledge.information_id == extracted.id
                    )
                )
            ) == [uuid.UUID(child)]
            for entry_id in (scene, telling):
                assert (
                    await session.get(EntityAudience, uuid.UUID(entry_id))
                ).shared_with_participants
                assert list(
                    await session.scalars(
                        select(EntityKnowledge.knower_entity_id).where(
                            EntityKnowledge.entity_id == uuid.UUID(entry_id)
                        )
                    )
                ) == [uuid.UUID(child)]
            assert (await session.get(PayloadPicture, picture)).data == b"unchanged picture"
            receipt = await session.get(ManuscriptSceneExtraction, uuid.UUID(operation))
            assert receipt.checkpoint["before"][source] == [payload, str(picture), child]
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
        assert review.status_code == 200, review.text
        assert prose in [
            element["content"] for item in review.json()["entries"] for element in item["elements"]
        ]
        assert (
            await world.outsider.get(review_url + f"/pictures/{picture}")
        ).content == b"unchanged picture"
        assert (await world.outsider.get(base + f"/entities/{scene}")).status_code == 404
        assert (await raw_client.post(url, headers=headers, json=body)).json() == response.json()
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
                copied_scene = await session.scalar(
                    select(SceneTelling.scene_entity_id).where(SceneTelling.tenant_id == copy_id)
                )
                assert copied_scene is not None and copied_scene != uuid.UUID(scene)
                assert not list(
                    await session.scalars(
                        select(ManuscriptSceneExtraction).where(
                            ManuscriptSceneExtraction.tenant_id == copy_id
                        )
                    )
                )
                copied_child = await session.scalar(
                    select(Entity.id).where(
                        Entity.tenant_id == copy_id, Entity.name == "Keep child"
                    )
                )
            copied_info = (
                await world.owner.post(
                    f"/tenants/{copy_id}/entities/{copied_child}/information",
                    json={
                        "type": "manuscript",
                        "title": "Manuscript",
                        "content": "Keep on collision",
                    },
                )
            ).json()
            copy_url = f"/tenants/{copy_id}/writing/entries/{copied_child}"
            copy_outline = (await world.owner.get(copy_url)).json()
            collision_ids = [str(uuid.uuid4()) for _ in range(2)]
            collision = await raw_client.post(
                copy_url + f"/scene-extractions/{operation}",
                headers={**world.owner.headers, "If-Match": copy_outline["version"]},
                json={
                    "scene_id": collision_ids[0],
                    "telling_id": collision_ids[1],
                    "name": "Rolled back",
                    "elements": [copied_info["payloads"][0]["id"]],
                },
            )
            assert collision.status_code == 409, collision.text
            assert (await world.owner.get(copy_url)).json() == copy_outline
            for entry_id in collision_ids:
                assert (
                    await world.owner.get(f"/tenants/{copy_id}/entities/{entry_id}")
                ).status_code == 404
        second = (
            await actor.post(
                base + "/writing/tellings", json={"name": "Other telling", "scene_id": scene}
            )
        ).json()
        independent = await raw_client.post(
            base + f"/writing/tellings/{second['id']}/independent",
            headers={**actor.headers, "If-Match": second["version"]},
        )
        assert independent.status_code == 200, independent.text
        assert not independent.json()["uses_scene_manuscript"]
        independent_picture = independent.json()["elements"][1]["id"]
        assert independent_picture != str(picture)
        async with admin_session_factory() as session:
            original_picture = await session.get(PayloadPicture, picture)
            copied_picture = await session.get(PayloadPicture, uuid.UUID(independent_picture))
            assert copied_picture.data == original_picture.data
            assert copied_picture.sha256 == original_picture.sha256
        assert (await outline(telling))["uses_scene_manuscript"]
        fresh = (
            await actor.post(
                base + f"/entities/{child}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "Race"},
            )
        ).json()
        current = await outline(child)
        replies = await asyncio.gather(
            *[
                raw_client.post(
                    base + f"/writing/entries/{child}/scene-extractions/{uuid.uuid4()}",
                    headers={**actor.headers, "If-Match": current["version"]},
                    json={
                        "scene_id": str(uuid.uuid4()),
                        "telling_id": str(uuid.uuid4()),
                        "name": "Race",
                        "elements": [fresh["payloads"][0]["id"]],
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


async def test_scene_extraction_receipts_force_rls_and_are_not_published() -> None:
    from lorenzo_api.copyable_tables import EXCLUDED_TABLES

    assert "manuscript_scene_extraction" in EXCLUDED_TABLES
    async with admin_session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname='manuscript_scene_extraction'"
                )
            )
        ).one()
        assert row == (True, True)


async def test_scene_extraction_rejects_new_contextual_readers(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from conftest import make_campaign

    from lorenzo_api.models import CampaignGm, Tenant

    world = await make_world(raw_client, fake_jwks_server)
    base = f"/tenants/{world.tenant_id}"
    try:
        source = (
            await world.author.post(base + "/writing/chapters", json={"name": "Private draft"})
        ).json()["id"]
        info = (
            await world.author.post(
                base + f"/entities/{source}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "Private prose"},
            )
        ).json()
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=world.tenant_id)
            for person in (world.author, world.outsider):
                session.add(
                    CampaignGm(
                        tenant_id=world.tenant_id, campaign_id=campaign.id, user_id=person.user_id
                    )
                )
            (await session.get(Tenant, world.tenant_id)).npcs_shared_with_gms = False
            (await session.get(Entity, uuid.UUID(source))).created_by = world.orga.user_id
            await session.commit()
        source_url = base + f"/writing/entries/{source}"
        current = (await world.author.get(source_url)).json()
        scene, telling = [str(uuid.uuid4()) for _ in range(2)]
        response = await raw_client.post(
            source_url + f"/scene-extractions/{uuid.uuid4()}",
            headers={**world.author.headers, "If-Match": current["version"]},
            json={
                "scene_id": scene,
                "telling_id": telling,
                "name": "Private Scene",
                "elements": [info["payloads"][0]["id"]],
            },
        )
        assert response.status_code == 409 and "campaign access" in response.text, response.text
        assert (await world.author.get(source_url)).json() == current
        for entry_id in (scene, telling):
            assert (await world.author.get(base + f"/entities/{entry_id}")).status_code == 404
    finally:
        await world.clean_up()
