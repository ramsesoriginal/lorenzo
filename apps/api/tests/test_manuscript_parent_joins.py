"""Absorbing a Chapter preserves the reading position and guarded identities."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import (
    EntityAudience,
    ManuscriptJoin,
    ManuscriptRevision,
    Payload,
    PayloadPicture,
)


@pytest.mark.parametrize("parent_kind", ["chapter", "edition"])
async def test_parent_join_keeps_interleaved_order(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, parent_kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    actor = world.author
    base = f"/tenants/{world.tenant_id}"
    try:

        async def read(id: str) -> dict:
            response = await actor.get(base + f"/writing/entries/{id}")
            assert response.status_code == 200, response.text
            return response.json()

        async def chapter(name: str) -> str:
            return (await actor.post(base + "/writing/chapters", json={"name": name})).json()["id"]

        async def arrange(id: str, ids: list[str]) -> None:
            response = await raw_client.put(
                base + f"/writing/entries/{id}/composition",
                headers={**actor.headers, "If-Match": (await read(id))["version"]},
                json={"elements": ids},
            )
            assert response.status_code == 200, response.text

        async def manuscript(id: str, text: str) -> dict:
            response = await actor.post(
                base + f"/entities/{id}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": text},
            )
            assert response.status_code == 201, response.text
            return response.json()

        book = (await actor.post(base + "/writing/books", json={"name": "Parent join"})).json()
        edition = book["editions"][0]["id"]
        parent = await chapter("Parent") if parent_kind == "chapter" else edition
        if parent != edition:
            await arrange(edition, [parent])
        source, child, tail = [await chapter(name) for name in ("Source", "Child", "Tail")]
        parent_info = await manuscript(parent, "Before[^n].\n\n[^n]: Parent note.")
        info_response = await actor.get(base + f"/information/{parent_info['id']}")
        after = await raw_client.post(
            base + f"/information/{parent_info['id']}/texts",
            headers={**actor.headers, "If-Match": info_response.headers["etag"]},
            json={"content": "After."},
        )
        assert after.status_code == 201, after.text
        after_id = after.json()["id"]
        source_info = await manuscript(source, "Inside[^n].\n\n[^n]: Source note.")
        inside = source_info["payloads"][0]["id"]
        before = parent_info["payloads"][0]["id"]
        picture = uuid.uuid4()
        async with admin_session_factory() as session:
            session.add(
                Payload(
                    id=picture,
                    tenant_id=world.tenant_id,
                    information_id=uuid.UUID(source_info["id"]),
                    order=1,
                )
            )
            await session.flush()
            session.add(
                PayloadPicture(
                    payload_id=picture,
                    tenant_id=world.tenant_id,
                    data=b"unchanged",
                    file_type="image/png",
                )
            )
            await session.commit()
        await arrange(source, [inside, child, str(picture)])
        await arrange(parent, [before, source, after_id, tail])
        note = (
            await actor.post(
                base + f"/entities/{source}/information",
                json={"type": "note", "title": "Research", "content": "Retain"},
            )
        ).json()
        operation = uuid.uuid4()
        url = base + f"/writing/entries/{source}/joins/{operation}"
        body = {
            "mode": "parent",
            "destination_id": parent,
            "parent_id": parent,
            "destination_version": (await read(parent))["version"],
            "parent_version": (await read(parent))["version"],
        }
        headers = {**actor.headers, "If-Match": (await read(source))["version"]}
        for key in ("destination_version", "parent_version"):
            denied = await raw_client.post(url, headers=headers, json={**body, key: 'W/"stale"'})
            assert denied.status_code == 412, denied.text
        assert (
            await raw_client.post(url, headers=headers, json={**body, "destination_id": source})
        ).status_code == 409
        assert (
            await raw_client.post(
                url, headers=headers, json={**body, "parent_id": tail, "destination_id": tail}
            )
        ).status_code == 409
        async with admin_session_factory() as session:
            (await session.get(EntityAudience, uuid.UUID(source))).is_public = True
            await session.commit()
        assert (await raw_client.post(url, headers=headers, json=body)).status_code == 409
        async with admin_session_factory() as session:
            (await session.get(EntityAudience, uuid.UUID(source))).is_public = False
            await session.commit()
        headers["If-Match"] = (await read(source))["version"]
        replies = await asyncio.gather(
            raw_client.post(url, headers=headers, json=body),
            raw_client.post(
                base + f"/writing/entries/{source}/joins/{uuid.uuid4()}", headers=headers, json=body
            ),
        )
        assert sorted(r.status_code for r in replies) == [200, 409], [r.text for r in replies]
        winning = next(r for r in replies if r.status_code == 200)
        replay_url = base + f"/writing/entries/{source}/joins/{winning.json()['operation_id']}"
        assert (
            await raw_client.post(replay_url, headers=headers, json=body)
        ).json() == winning.json()
        expected = [before, inside, child, str(picture), after_id, tail]
        assert [e["id"] for e in (await read(parent))["elements"]] == expected
        assert (await read(child))["parent_id"] == parent
        old = await read(source)
        assert old["joined_destination"] == {
            "id": parent,
            "name": (await read(parent))["name"],
            "element_id": inside,
        }
        assert old["elements"] == [] and old["joined"]
        assert (await actor.get(base + f"/information/{note['id']}")).status_code == 200
        info = (await actor.get(base + f"/information/{parent_info['id']}")).json()
        assert [p["id"] for p in info["payloads"]] == [before, inside, str(picture), after_id]
        assert [p["content"] for p in info["payloads"] if p["kind"] == "description"] == [
            "Before[^n].\n\n[^n]: Parent note.",
            "Inside[^n].\n\n[^n]: Source note.",
            "After.",
        ]
        async with admin_session_factory() as session:
            receipt = await session.get(ManuscriptJoin, uuid.UUID(winning.json()["operation_id"]))
            assert receipt.checkpoint["after"][parent] == expected
            assert (await session.get(PayloadPicture, picture)).data == b"unchanged"
            revisions = list(
                await session.scalars(
                    select(ManuscriptRevision).where(
                        ManuscriptRevision.information_id == uuid.UUID(source_info["id"])
                    )
                )
            )
            assert any(r.snapshot["payloads"] for r in revisions)
    finally:
        await world.clean_up()
