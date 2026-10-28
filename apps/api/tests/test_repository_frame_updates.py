"""A frame, and an entry on it, changed upstream reach the libraries that copied them (ADR 0369)."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import EntityFrame, Frame, RepositoryCopyLinkEntity


async def _local(w: ReleaseWorld, origin: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        return await session.scalar(  # type: ignore[return-value]
            select(RepositoryCopyLinkEntity.entity_id).where(
                RepositoryCopyLinkEntity.tenant_id == w.table,
                RepositoryCopyLinkEntity.source_id == origin,
            )
        )


async def _apply(w: ReleaseWorld, origin: uuid.UUID) -> Any:
    return await w.gm.post(
        f"/tenants/{w.table}/repositories/{w.repository}/updates",
        json={"actions": [{"kind": "entity", "source_id": str(origin), "action": "apply"}]},
    )


async def _library_rows(w: ReleaseWorld) -> tuple[list[tuple[uuid.UUID, str]], list[Any]]:
    async with admin_session_factory() as session:
        designated = [
            (row.entity_id, row.axis)
            for row in await session.scalars(select(Frame).where(Frame.tenant_id == w.table))
        ]
        members = [
            (row.entity_id, row.axis, row.frame_entity_id)
            for row in await session.scalars(
                select(EntityFrame).where(EntityFrame.tenant_id == w.table)
            )
        ]
        return designated, members


async def test_a_frame_and_an_entry_on_it_are_taken_by_a_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        longsword, dagger = w.ids["Longsword"], w.ids["Dagger"]
        base = f"/tenants/{w.repository}/entities"
        assert (await w.author.put(f"{base}/{longsword}/frame-axes/plane")).status_code == 200
        put = await w.author.put(
            f"{base}/{dagger}/frames/plane", json={"frame_entity_id": str(longsword)}
        )
        assert put.status_code == 200, put.text
        await w.publish(label="1.1")

        # The entry on the frame cannot be taken before the frame is: it says so, and nothing moves.
        refused = await _apply(w, dagger)
        assert refused.status_code == 200, refused.text
        assert refused.json()["not_applied"]
        assert await _library_rows(w) == ([], [])

        taken = await _apply(w, longsword)
        assert taken.status_code == 200 and taken.json()["not_applied"] == []
        local_sword = await _local(w, longsword)
        assert await _library_rows(w) == ([(local_sword, "plane")], [])

        again = await _apply(w, dagger)
        assert again.status_code == 200 and again.json()["not_applied"] == []
        local_dagger = await _local(w, dagger)
        assert await _library_rows(w) == (
            [(local_sword, "plane")],
            [(local_dagger, "plane", local_sword)],
        )

        # Taken off upstream, and no longer a frame: both go from the library too.
        assert (await w.author.delete(f"{base}/{dagger}/frames/plane")).status_code == 204
        assert (await w.author.delete(f"{base}/{longsword}/frame-axes/plane")).status_code == 204
        await w.publish(label="1.2")
        for origin in (dagger, longsword):
            done = await _apply(w, origin)
            assert done.status_code == 200 and done.json()["not_applied"] == []
        assert await _library_rows(w) == ([], [])
    finally:
        await w.done()
