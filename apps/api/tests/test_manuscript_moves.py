"""Moves preserve identity, reject stale state and never silently add reviewers."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.models import Entity, ManuscriptMove, ManuscriptPlacement


@pytest.mark.parametrize("kind", ["play", "repository"])
async def test_atomic_moves_and_retries(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, kind: str
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind=kind)
    base = f"/tenants/{world.tenant_id}"
    actor = world.author
    copy_id = None
    try:

        async def read(id: str) -> dict:
            reply = await actor.get(base + f"/writing/entries/{id}")
            assert reply.status_code == 200, reply.text
            return reply.json()

        async def arrange(id: str, ids: list[str]) -> None:
            current = await read(id)
            reply = await raw_client.put(
                base + f"/writing/entries/{id}/composition",
                headers={**actor.headers, "If-Match": current["version"]},
                json={"elements": ids},
            )
            assert reply.status_code == 200, reply.text

        async def request(
            child: str, destination: str | None, before: str | None = None
        ) -> tuple[dict, dict]:
            current = await read(child)
            source = current["parent_id"]
            return (
                {
                    "source_parent_id": source,
                    "destination_parent_id": destination,
                    "source_version": (await read(source))["version"] if source else None,
                    "destination_version": (await read(destination))["version"]
                    if destination
                    else None,
                    "before_element_id": before,
                },
                {**actor.headers, "If-Match": current["version"]},
            )

        async def move(child: str, destination: str | None) -> None:
            body, headers = await request(child, destination)
            reply = await raw_client.post(
                base + f"/writing/entries/{child}/moves/{uuid.uuid4()}", headers=headers, json=body
            )
            assert reply.status_code == 200, reply.text

        editions = []
        for name in ["First", "Second"]:
            book = await actor.post(base + "/writing/books", json={"name": name})
            assert book.status_code == 201
            editions.append(book.json()["editions"][0]["id"])
        first, second = editions
        child = (
            await actor.post(base + "/writing/chapters", json={"name": "Travelling chapter"})
        ).json()["id"]
        nested = (await actor.post(base + "/writing/chapters", json={"name": "Subchapter"})).json()[
            "id"
        ]
        text_info = (
            await actor.post(
                base + f"/entities/{child}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "Unchanged prose"},
            )
        ).json()
        note = (
            await actor.post(
                base + f"/entities/{child}/information",
                json={"type": "note", "title": "Research", "content": "Keep this note"},
            )
        ).json()
        target_info = (
            await actor.post(
                base + f"/entities/{second}/information",
                json={"type": "manuscript", "title": "Manuscript", "content": "Destination prose"},
            )
        ).json()
        anchor = target_info["payloads"][0]["id"]
        own = text_info["payloads"][0]["id"]
        await arrange(child, [own, nested])
        await arrange(first, [child])
        body, headers = await request(child, second, anchor)
        operation = uuid.uuid4()
        url = base + f"/writing/entries/{child}/moves/{operation}"
        for key in ["source_version", "destination_version"]:
            stale = await raw_client.post(url, headers=headers, json={**body, key: 'W/"old"'})
            assert stale.status_code == 412, stale.text
            assert (await read(child))["parent_id"] == first
            assert [e["id"] for e in (await read(first))["elements"]] == [child]
            assert [e["id"] for e in (await read(second))["elements"]] == [anchor]
        assert (await actor.post(url, json=body)).status_code == 428
        # Review grants cannot be widened by moving private prose.
        grant_url = base + f"/writing/reviews/{second}/reviewers/{world.outsider.user_id}"
        assert (await actor.put(grant_url)).status_code == 204
        blocked = await raw_client.post(url, headers=headers, json=body)
        assert blocked.status_code == 409, blocked.text
        assert (await read(child))["parent_id"] == first
        assert (
            await actor.put(base + f"/writing/reviews/{first}/reviewers/{world.outsider.user_id}")
        ).status_code == 204
        denied = await raw_client.post(
            url, headers={**world.outsider.headers, "If-Match": headers["If-Match"]}, json=body
        )
        assert denied.status_code in {403, 404}
        moved = await raw_client.post(url, headers=headers, json=body)
        assert moved.status_code == 200, moved.text
        assert (await read(first))["elements"] == []
        assert [e["id"] for e in (await read(second))["elements"]] == [child, anchor]
        assert (await read(nested))["parent_id"] == child
        assert [e["id"] for e in (await read(child))["elements"]] == [own, nested]
        assert (await actor.get(base + f"/information/{note['id']}")).json()["title"] == "Research"
        checkpoint = await actor.get(url)
        assert checkpoint.status_code == 200
        assert checkpoint.json()["checkpoint"]["before"][first] == [child]
        assert checkpoint.json()["checkpoint"]["after"][second] == [child, anchor]
        assert (await world.outsider.get(url)).status_code in {403, 404}
        if kind == "repository":
            copy_id = await world.owner.create_tenant("Moved repository copy")
            assert (await world.owner.put(base + f"/subscribers/{copy_id}")).status_code in {
                200,
                201,
            }
            assert (await world.owner.put(base + "/published")).status_code == 200
            copied = await world.owner.post(
                f"/tenants/{copy_id}/repositories/{world.tenant_id}/copy"
            )
            assert copied.status_code == 201, copied.text
            async with admin_session_factory() as session:
                copied_child = await session.scalar(
                    select(Entity.id).where(
                        Entity.tenant_id == copy_id, Entity.name == "Travelling chapter"
                    )
                )
                assert copied_child is not None
                placement = await session.get(ManuscriptPlacement, copied_child)
                assert placement is not None
                parent = await session.get(Entity, placement.parent_entity_id)
                assert parent is not None and parent.name == "Second"
                assert not list(
                    await session.scalars(
                        select(ManuscriptMove).where(ManuscriptMove.tenant_id == copy_id)
                    )
                )
            # A globally occupied receipt id fails after the outline edits were staged.
            # The request must roll back all of those edits, not just the receipt insert.
            copy_base = f"/tenants/{copy_id}/writing/entries"
            copied_outline = (await world.owner.get(f"{copy_base}/{copied_child}")).json()
            copied_parent = (await world.owner.get(f"{copy_base}/{parent.id}")).json()
            collision = await raw_client.post(
                f"{copy_base}/{copied_child}/moves/{operation}",
                headers={**world.owner.headers, "If-Match": copied_outline["version"]},
                json={
                    "source_parent_id": str(parent.id),
                    "source_version": copied_parent["version"],
                    "destination_parent_id": None,
                },
            )
            assert collision.status_code == 409, collision.text
            assert (await world.owner.get(f"{copy_base}/{copied_child}")).json() == copied_outline
            assert (await world.owner.get(f"{copy_base}/{parent.id}")).json() == copied_parent
        cycle_body, cycle_headers = await request(child, nested)
        cycle = await raw_client.post(
            base + f"/writing/entries/{child}/moves/{uuid.uuid4()}",
            headers=cycle_headers,
            json=cycle_body,
        )
        assert cycle.status_code == 409
        await move(nested, second)  # promotion out of its Chapter
        assert (await read(nested))["parent_id"] == second
        await move(child, None)
        assert (await read(child))["parent_id"] is None
        # A delayed retry acknowledges the first move without undoing a subsequent one.
        retry = await raw_client.post(url, headers=headers, json=body)
        assert retry.status_code == 200 and retry.json() == moved.json()
        assert (await read(child))["parent_id"] is None
        different = await raw_client.post(
            url, headers=headers, json={**body, "before_element_id": None}
        )
        assert different.status_code == 409
        other_actor = await raw_client.post(
            url, headers={**world.owner.headers, "If-Match": headers["If-Match"]}, json=body
        )
        assert other_actor.status_code == 409
        # Competing moves of one unassigned entry cannot both commit.
        await actor.delete(grant_url)
        await actor.delete(base + f"/writing/reviews/{first}/reviewers/{world.outsider.user_id}")
        a, ah = await request(child, first)
        b, bh = await request(child, second)
        replies = await asyncio.gather(
            raw_client.post(
                base + f"/writing/entries/{child}/moves/{uuid.uuid4()}", headers=ah, json=a
            ),
            raw_client.post(
                base + f"/writing/entries/{child}/moves/{uuid.uuid4()}", headers=bh, json=b
            ),
        )
        assert sorted(r.status_code for r in replies) == [200, 412], [r.text for r in replies]
    finally:
        if copy_id is not None:
            await cleanup([copy_id], [])
        await world.clean_up()


async def test_move_receipts_are_private_operational_checkpoints() -> None:
    from lorenzo_api.copyable_tables import EXCLUDED_TABLES

    assert "manuscript_move" in EXCLUDED_TABLES
    async with admin_session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname='manuscript_move'"
                )
            )
        ).one()
    assert row == (True, True)
