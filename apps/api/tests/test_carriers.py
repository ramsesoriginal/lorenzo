"""Carrier references preserve identity, access and repository content (ADR 0379)."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.models import CarrierCoverage, Entity, EntityAudience, Information, Payload


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_carrier_coverage_and_copy(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    copy_id = None
    try:

        async def create(name: str) -> dict:
            response = await actor.post(base + "/writing/carriers", json={"name": name})
            assert response.status_code == 201, response.text
            return response.json()

        async def read(id: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{id}")
            assert response.status_code == 200, response.text
            return response.json()

        async def manuscript(id: str, content: str) -> dict:
            response = await actor.post(
                base + f"/entities/{id}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": content},
            )
            assert response.status_code == 201, response.text
            return response.json()

        vellum, coptic, carrier = [
            await create(name) for name in ("Vellum", "Coptic", "Collected codex")
        ]
        carrier_id = carrier["id"]
        parents = {"parent_ids": [vellum["id"], coptic["id"]]}
        response = await raw_client.put(
            base + f"/writing/carriers/{carrier_id}/parents",
            headers={**actor.headers, "If-Match": carrier["version"]},
            json=parents,
        )
        assert response.status_code == 200, response.text
        parent_entity = (await actor.get(base + f"/entities/{carrier_id}")).json()
        assert set(p["id"] for p in parent_entity["prototypes"]) == set(parents["parent_ids"])
        cycle = await raw_client.put(
            base + f"/writing/carriers/{vellum['id']}/parents",
            headers={**actor.headers, "If-Match": (await read(vellum["id"]))["version"]},
            json={"parent_ids": [carrier_id]},
        )
        assert cycle.status_code == 422, cycle.text
        own = await manuscript(carrier_id, "A note on the binding.")
        first = (await actor.post(base + "/writing/books", json={"name": "First work"})).json()[
            "editions"
        ][0]["id"]
        second = (await actor.post(base + "/writing/books", json={"name": "Second work"})).json()[
            "editions"
        ][0]["id"]
        first_info = await manuscript(first, "The first voyage.")
        await manuscript(second, "The second voyage.")
        selected = first_info["payloads"][0]["id"]
        refs = [
            {"id": str(uuid.uuid4()), "target_entity_id": second},
            {"id": own["payloads"][0]["id"]},
            {"id": str(uuid.uuid4()), "target_payload_id": selected},
            {"id": str(uuid.uuid4()), "target_entity_id": second},
        ]
        url = base + f"/writing/carriers/{carrier_id}/coverage"
        current = await read(carrier_id)
        headers = {**actor.headers, "If-Match": current["version"]}
        assert (await actor.put(url, json={"elements": refs})).status_code == 428
        response = await raw_client.put(url, headers=headers, json={"elements": refs})
        assert response.status_code == 200, response.text
        assert [el["id"] for el in response.json()["elements"]] == [el["id"] for el in refs]
        assert (
            await raw_client.put(url, headers=headers, json={"elements": refs})
        ).json() == response.json()
        assert (
            await raw_client.put(url, headers=headers, json={"elements": refs[:-1]})
        ).status_code == 412
        for invalid in [
            refs + [refs[0]],
            [{"id": str(uuid.uuid4()), "target_entity_id": carrier_id}, refs[1]],
            [
                {"id": str(uuid.uuid4()), "target_entity_id": first, "target_payload_id": selected},
                refs[1],
            ],
            [{**refs[0], "target_entity_id": first}, *refs[1:]],
        ]:
            denied = await raw_client.put(
                url,
                headers={**actor.headers, "If-Match": response.json()["version"]},
                json={"elements": invalid},
            )
            assert denied.status_code in {404, 409}, denied.text
            assert (await read(carrier_id)) == response.json()
        review_url = base + f"/writing/reviews/{first}"
        assert (
            await actor.put(review_url + f"/reviewers/{world.outsider.user_id}")
        ).status_code == 204
        assert (await world.outsider.get(base + f"/writing/entries/{carrier_id}")).status_code in {
            403,
            404,
        }
        # Payload references follow extraction without gaining a different text block.
        source = await read(first)
        extraction = await raw_client.post(
            base + f"/writing/entries/{first}/scene-extractions/{uuid.uuid4()}",
            headers={**actor.headers, "If-Match": source["version"]},
            json={
                "scene_id": str(uuid.uuid4()),
                "telling_id": str(uuid.uuid4()),
                "name": "Voyage Scene",
                "elements": [selected],
            },
        )
        assert extraction.status_code == 200, extraction.text
        current = await read(carrier_id)
        assert current["elements"][2]["target_id"] == extraction.json()["scene_id"]
        assert current["elements"][2]["payload_id"] == selected
        assert (await world.outsider.get(base + f"/writing/entries/{carrier_id}")).status_code in {
            403,
            404,
        }
        assert (await world.outsider.put(url, json={"elements": refs})).status_code in {403, 404}
        if kind == "repository":
            copy_id = await world.owner.create_tenant("Carrier copy")
            await world.owner.put(base + f"/subscribers/{copy_id}")
            published = await world.owner.put(base + "/published")
            assert published.status_code == 200, published.text
            copied = await world.owner.post(
                f"/tenants/{copy_id}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            async with admin_session_factory() as session:
                target = await session.scalar(
                    select(Entity.id).where(
                        Entity.tenant_id == copy_id, Entity.name == "Collected codex"
                    )
                )
                coverage = list(
                    await session.scalars(
                        select(CarrierCoverage).where(CarrierCoverage.tenant_id == copy_id)
                    )
                )
                assert len(coverage) == 3
                assert all(row.id not in {uuid.UUID(ref["id"]) for ref in refs} for row in coverage)
                copied_payload = next(
                    row.target_payload_id for row in coverage if row.target_payload_id
                )
                assert copied_payload != uuid.UUID(selected)
                assert (await session.get(Payload, copied_payload)).tenant_id == copy_id
            copied_entity = (await world.owner.get(f"/tenants/{copy_id}/entities/{target}")).json()
            assert {p["name"] for p in copied_entity["prototypes"]} == {"Vellum", "Coptic"}
            copied_outline = (
                await world.owner.get(f"/tenants/{copy_id}/writing/entries/{target}")
            ).json()
            assert [el["kind"] for el in copied_outline["elements"]] == [
                "coverage",
                "payload",
                "coverage",
                "coverage",
            ]
            copied_refs = [
                {
                    "id": el["id"],
                    "target_entity_id": el.get("target_id")
                    if el["kind"] == "coverage" and not el.get("payload_id")
                    else None,
                    "target_payload_id": el.get("payload_id"),
                }
                for el in copied_outline["elements"]
            ]
            copied_refs[0]["id"] = refs[0]["id"]
            copy_url = f"/tenants/{copy_id}/writing/carriers/{target}/coverage"
            denied = await raw_client.put(
                copy_url,
                headers={**world.owner.headers, "If-Match": copied_outline["version"]},
                json={"elements": copied_refs},
            )
            assert denied.status_code == 409, denied.text
            assert (
                await world.owner.get(f"/tenants/{copy_id}/writing/entries/{target}")
            ).json() == copied_outline
        # Removing a reference leaves the writing intact; local anchor deletion retains coverage.
        removed = await raw_client.put(
            url,
            headers={**actor.headers, "If-Match": current["version"]},
            json={"elements": refs[:-1]},
        )
        assert removed.status_code == 200, removed.text
        assert (await read(second))["elements"]
        async with admin_session_factory() as session:
            await session.delete(await session.get(Payload, uuid.UUID(own["payloads"][0]["id"])))
            await session.commit()
        assert len((await read(carrier_id))["elements"]) == 2
        current = await read(carrier_id)
        replies = await asyncio.gather(
            *[
                raw_client.put(
                    url,
                    headers={**actor.headers, "If-Match": current["version"]},
                    json={"elements": [{"id": str(uuid.uuid4()), "target_entity_id": second}]},
                )
                for _ in range(2)
            ]
        )
        assert sorted(r.status_code for r in replies) == [200, 412], [r.text for r in replies]

    finally:
        if copy_id:
            await cleanup([copy_id], [])
        await world.clean_up()


async def test_carrier_hidden_targets_and_reviewers(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from conftest import make_campaign

    from lorenzo_api.models import Player

    world = await make_world(raw_client, fake_jwks_server)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:
        carrier = (
            await actor.post(base + "/writing/carriers", json={"name": "Visible cover"})
        ).json()
        chapter = (
            await actor.post(base + "/writing/chapters", json={"name": "Secret chapter"})
        ).json()
        info = (
            await actor.post(
                base + f"/entities/{chapter['id']}/information",
                json={"type": "manuscript", "title": "Private", "content": "Hidden prose"},
            )
        ).json()
        body = {
            "elements": [
                {"id": str(uuid.uuid4()), "target_entity_id": chapter["id"]},
                {"id": str(uuid.uuid4()), "target_payload_id": info["payloads"][0]["id"]},
            ]
        }
        response = await raw_client.put(
            base + f"/writing/carriers/{carrier['id']}/coverage",
            headers={**actor.headers, "If-Match": carrier["version"]},
            json=body,
        )
        assert response.status_code == 200, response.text
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
        url = base + f"/writing/entries/{carrier['id']}"
        hidden = await world.outsider.get(url)
        assert hidden.status_code == 200, hidden.text
        assert hidden.json()["elements"] == []
        assert chapter["id"] not in hidden.text and "Secret chapter" not in hidden.text
        async with admin_session_factory() as session:
            (await session.get(EntityAudience, uuid.UUID(chapter["id"]))).is_public = True
            await session.commit()
        visible = (await world.outsider.get(url)).json()
        assert len(visible["elements"]) == 1  # Outer gate alone never exposes the payload.
        async with admin_session_factory() as session:
            (await session.get(Information, uuid.UUID(info["id"]))).is_public = True
            await session.commit()
        assert len((await world.outsider.get(url)).json()["elements"]) == 2
    finally:
        await world.clean_up()


async def test_carrier_tables_force_rls() -> None:
    from lorenzo_api.copyable_tables import CONTENT_TABLES

    async with admin_session_factory() as session:
        for table in ("carrier", "carrier_coverage"):
            assert table in CONTENT_TABLES
            row = (
                await session.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                        "WHERE relname=:name"
                    ),
                    {"name": table},
                )
            ).one()
            assert row == (True, True)


async def test_carrier_picture_reference_and_target_deletion(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from lorenzo_api.models import PayloadPicture

    world = await make_world(raw_client, fake_jwks_server)
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    try:
        scene = (await actor.post(base + "/scenes", json={"name": "Picture idea"})).json()["id"]
        info = (
            await actor.post(
                base + f"/entities/{scene}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "An image idea"},
            )
        ).json()
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
                    data=b"picture bytes",
                    file_type="image/png",
                )
            )
            await session.commit()
        carrier = (
            await actor.post(base + "/writing/carriers", json={"name": "Image tablet"})
        ).json()
        response = await raw_client.put(
            base + f"/writing/carriers/{carrier['id']}/coverage",
            headers={**actor.headers, "If-Match": carrier["version"]},
            json={"elements": [{"id": str(uuid.uuid4()), "target_payload_id": str(picture)}]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["elements"][0]["payload_id"] == str(picture)
        assert response.json()["elements"][0]["target_id"] == scene
        async with admin_session_factory() as session:
            await session.delete(await session.get(Payload, picture))
            await session.commit()
        after = await actor.get(base + f"/writing/entries/{carrier['id']}")
        assert after.json()["elements"] == []
        assert after.json()["version"] != response.json()["version"]
        assert (await actor.get(base + f"/entities/{scene}")).status_code == 200
    finally:
        await world.clean_up()
