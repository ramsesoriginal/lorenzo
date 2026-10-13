"""ADR 0280: a stat definition's display fields and hints travel with a repository - copied,
offered as updates, and part of the digest - through the real HTTP API."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import RepositoryCopyLinkStatDefinition, StatDefinition


async def _patch(w: ReleaseWorld, name: str, **body: Any) -> None:
    response = await w.author.patch(
        f"/tenants/{w.repository}/stat-definitions/{w.ids[name]}", json=body
    )
    assert response.status_code == 200, response.text


async def _local_definition(w: ReleaseWorld, origin: uuid.UUID) -> StatDefinition:
    async with admin_session_factory() as session:
        local = await session.scalar(
            select(RepositoryCopyLinkStatDefinition.stat_definition_id).where(
                RepositoryCopyLinkStatDefinition.tenant_id == w.table,
                RepositoryCopyLinkStatDefinition.source_id == origin,
            )
        )
        return await session.get_one(StatDefinition, local)


async def test_a_copy_takes_the_display_fields_and_remaps_the_hints(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        await _patch(w, "Speed", unit="ft", adjustable_in_play=True, pin=True, signed=True)
        await _patch(
            w, "Strength", max_hint_id=str(w.ids["Speed"]), min_hint_id=str(w.ids["Damage"])
        )
        await w.publish(label="1.0")
        await w.copy()

        speed = await _local_definition(w, w.ids["Speed"])
        strength = await _local_definition(w, w.ids["Strength"])
        assert (speed.unit, speed.adjustable_in_play, speed.pin, speed.signed) == (
            "ft",
            True,
            True,
            True,
        )
        assert strength.max_hint_id == speed.id
        assert strength.min_hint_id == (await _local_definition(w, w.ids["Damage"])).id
        assert speed.id != w.ids["Speed"]
    finally:
        await w.done()


async def test_a_changed_display_field_and_hint_are_offered_and_taken(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        await _patch(w, "Speed", unit="m", pin=True)
        await _patch(w, "Strength", max_hint_id=str(w.ids["Speed"]))
        await w.publish(label="1.1")

        rows = {r["source_id"]: r for r in (await w.updates())["changed"]}
        speed_fields = {f["field"] for f in rows[str(w.ids["Speed"])]["fields"]}
        strength_fields = {f["field"] for f in rows[str(w.ids["Strength"])]["fields"]}
        assert {"unit", "pin"} <= speed_fields
        assert "max_hint" in strength_fields

        actions = [
            {"kind": "stat_definition", "source_id": str(w.ids[n]), "action": "apply"}
            for n in ("Speed", "Strength")
        ]
        applied = await w.gm.post(
            f"/tenants/{w.table}/repositories/{w.repository}/updates", json={"actions": actions}
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["not_applied"] == []
        speed = await _local_definition(w, w.ids["Speed"])
        strength = await _local_definition(w, w.ids["Strength"])
        assert (speed.unit, speed.pin) == ("m", True)
        assert strength.max_hint_id == speed.id
        assert (await w.updates())["changed"] == []
    finally:
        await w.done()


async def test_a_position_alone_is_not_an_update(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        await _patch(w, "Speed", position=9)
        await w.publish(label="1.1")
        assert (await w.updates())["changed"] == []
    finally:
        await w.done()
