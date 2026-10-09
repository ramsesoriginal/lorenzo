"""A kind changed upstream reaches the libraries that copied the entry, in the diff, the detector
and the publish (ADR 0217, slice K2 of RFC 0041), through the real HTTP API."""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.entity_kinds import PUBLISHABLE_KIND_COMBINATIONS
from lorenzo_api.models import (
    Being,
    Character,
    Entity,
    EntityPrototype,
    Item,
    ItemInstance,
    RepositoryCopyLinkEntity,
)
from lorenzo_api.repository_updates import diff


async def _local(w: ReleaseWorld, origin: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        return await session.scalar(  # type: ignore[return-value]
            select(RepositoryCopyLinkEntity.entity_id).where(
                RepositoryCopyLinkEntity.tenant_id == w.table,
                RepositoryCopyLinkEntity.source_id == origin,
            )
        )


async def _has(model: Any, entity_id: uuid.UUID) -> bool:
    async with admin_session_factory() as session:
        return await session.get(model, entity_id) is not None


async def _kind_row(w: ReleaseWorld, origin: uuid.UUID) -> dict[str, Any] | None:
    for row in (await w.updates())["changed"]:
        if row["source_id"] == str(origin):
            return row  # type: ignore[no-any-return]
    return None


def _field(row: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((f for f in row["fields"] if f["field"] == name), None)


async def _apply(w: ReleaseWorld, origin: uuid.UUID, **extra: Any) -> Any:
    return await w.gm.post(
        f"/tenants/{w.table}/repositories/{w.repository}/updates",
        json={
            "actions": [{"kind": "entity", "source_id": str(origin), "action": "apply", **extra}]
        },
    )


async def _add_kind(w: ReleaseWorld, origin: uuid.UUID, kind: str) -> None:
    response = await w.author.put(f"/tenants/{w.repository}/entities/{origin}/kinds/{kind}")
    assert response.status_code in (200, 201), response.text


async def _remove_kind(w: ReleaseWorld, origin: uuid.UUID, kind: str) -> None:
    response = await w.author.delete(f"/tenants/{w.repository}/entities/{origin}/kinds/{kind}")
    assert response.status_code == 200, response.text


def test_the_diff_shows_a_changed_kind_set_like_any_other_set() -> None:
    changes = diff(
        {"kinds": ["item"]},
        {"kinds": ["being", "item"]},
        {"kinds": ["item"]},
        {},
    )
    assert [(c.field, c.state, c.added, c.removed) for c in changes] == [
        ("kinds", "clean", ["being"], [])
    ]
    # Nothing to do once the library's copy already has what upstream added.
    assert (
        diff({"kinds": ["item"]}, {"kinds": ["being", "item"]}, {"kinds": ["being", "item"]}, {})
        == []
    )
    assert diff({"kinds": ["item"]}, {"kinds": ["item"]}, {"kinds": ["being", "item"]}, {}) == []


async def test_a_kind_added_upstream_is_acknowledged_in_the_release_and_taken_by_a_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        longsword = w.ids["Longsword"]
        await _add_kind(w, longsword, "being")

        refused = await w.author.put(f"/tenants/{w.repository}/published", json={})
        assert refused.status_code == 409
        assert refused.json()["type"] == "release-has-breaking-changes"
        assert [r["reason"] for r in refused.json()["breaking_rows"]] == ["kinds_changed"]
        release = await w.publish(label="1.1", acknowledge_breaking=True)
        assert release["breaking"] is True

        row = await _kind_row(w, longsword)
        assert row is not None
        kinds = _field(row, "kinds")
        assert kinds is not None
        assert (kinds["added"], kinds["removed"], kinds["state"]) == (["being"], [], "clean")
        assert [n["reason"] for n in row["breaking"]] == ["kinds_changed"]

        # A release called it breaking, so taking it needs the library to say so.
        unconfirmed = await _apply(w, longsword)
        assert unconfirmed.status_code == 409
        assert unconfirmed.json()["type"] == "update-needs-confirmation"
        assert not await _has(Being, await _local(w, longsword))

        applied = await _apply(w, longsword, confirm=True)
        assert applied.status_code == 200, applied.text
        assert applied.json()["not_applied"] == []
        local = await _local(w, longsword)
        assert await _has(Being, local) and await _has(Item, local)
        detail = await w.gm.get(f"/tenants/{w.table}/entities/{local}")
        assert detail.json()["kinds"] == ["item", "being"]
        assert await _kind_row(w, longsword) is None
    finally:
        await w.done()


async def test_a_kind_removed_upstream_is_taken_where_the_copy_allows_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        longsword = w.ids["Longsword"]
        await _remove_kind(w, longsword, "item")
        await w.publish(label="1.1", acknowledge_breaking=True)

        row = await _kind_row(w, longsword)
        assert row is not None
        kinds = _field(row, "kinds")
        assert kinds is not None and (kinds["added"], kinds["removed"]) == ([], ["item"])
        applied = await _apply(w, longsword, confirm=True)
        assert applied.status_code == 200, applied.text
        assert applied.json()["not_applied"] == []
        local = await _local(w, longsword)
        assert not await _has(Item, local)
        assert await _has(Entity, local)
        assert await _kind_row(w, longsword) is None
    finally:
        await w.done()


async def test_removing_item_is_refused_where_an_inventory_item_inherits_and_offered_again(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        longsword = w.ids["Longsword"]
        local = await _local(w, longsword)
        async with admin_session_factory() as session:
            mine = Entity(tenant_id=w.table, name="My Longsword")
            session.add(mine)
            await session.flush()
            session.add(ItemInstance(entity_id=mine.id, tenant_id=w.table))
            session.add(EntityPrototype(entity_id=mine.id, prototype_id=local, tenant_id=w.table))
            await session.commit()
        await _remove_kind(w, longsword, "item")
        await w.publish(label="1.1", acknowledge_breaking=True)

        applied = await _apply(w, longsword, confirm=True)
        assert applied.status_code == 200, applied.text
        skipped = applied.json()["not_applied"]
        assert [(n["field"], n["reason"]) for n in skipped] == [
            ("kinds", "an inventory item still inherits from it here")
        ]
        assert await _has(Item, local)
        # Still offered, so it is taken once the inventory item is gone.
        row = await _kind_row(w, longsword)
        assert row is not None and _field(row, "kinds") is not None
    finally:
        await w.done()


async def test_removing_being_is_refused_where_the_copy_is_a_character(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        orc = w.ids["Orc"]
        local = await _local(w, orc)
        async with admin_session_factory() as session:
            session.add(Character(entity_id=local, tenant_id=w.table))
            await session.commit()
        await _remove_kind(w, orc, "being")
        await w.publish(label="1.1", acknowledge_breaking=True)

        applied = await _apply(w, orc, confirm=True)
        assert applied.status_code == 200, applied.text
        assert [(n["field"], n["reason"]) for n in applied.json()["not_applied"]] == [
            ("kinds", "it is a character here")
        ]
        assert await _has(Being, local)
    finally:
        await w.done()


async def test_what_the_library_made_of_its_own_copy_is_not_an_update(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        orc = w.ids["Orc"]
        async with admin_session_factory() as session:
            session.add(Character(entity_id=await _local(w, orc), tenant_id=w.table))
            session.add(Item(entity_id=await _local(w, orc), tenant_id=w.table))
            await session.commit()

        assert await _kind_row(w, orc) is None
    finally:
        await w.done()


@pytest.mark.parametrize(
    ("entry", "change"),
    [
        ("Longsword", ("add", "being")),
        ("Longsword", ("remove", "item")),
        ("Orc", ("add", "item")),
        ("Orc", ("remove", "being")),
    ],
)
async def test_the_detector_and_the_updates_agree_on_what_a_kind_change_is(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, entry: str, change: tuple[str, str]
) -> None:
    """Whatever the detector calls a changed kind set, a library is offered as a change of kinds,
    and a release that changes nothing about kinds is neither."""
    w = await release_world(raw_client, fake_jwks_server, copied=True)
    try:
        origin = w.ids[entry]
        # A rename is a change, and not one of kinds.
        async with admin_session_factory() as session:
            (await session.get_one(Entity, origin)).name = f"{entry} Renamed"
            await session.commit()
        preview = await w.preview()
        assert [b["reason"] for b in preview["breaking"]] == []
        row = await _kind_row(w, origin)
        assert row is not None and _field(row, "kinds") is None

        verb, kind = change
        await (_add_kind if verb == "add" else _remove_kind)(w, origin, kind)
        preview = await w.preview()
        assert [(b["reason"], b["row_id"]) for b in preview["breaking"]] == [
            ("kinds_changed", str(origin))
        ]
        row = await _kind_row(w, origin)
        assert row is not None
        found = _field(row, "kinds")
        assert found is not None
        assert (found["added"], found["removed"]) == (
            ([kind], []) if verb == "add" else ([], [kind])
        )
    finally:
        await w.done()


# --- Publishing -------------------------------------------------------------------------------


async def test_a_draft_may_hold_any_combination_and_publishing_refuses_the_unproven_ones(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        base = f"/tenants/{w.repository}/entities"
        # Made freely in a draft: an item that is also a being that is also a character.
        made = await w.author.post(base, json={"name": "Ashfang", "kinds": ["item", "being"]})
        assert made.status_code == 201, made.text
        ashfang = uuid.UUID(made.json()["id"])
        async with admin_session_factory() as session:
            session.add(Character(entity_id=ashfang, tenant_id=w.repository))
            await session.commit()

        preview = await w.preview()
        assert [(u["id"], u["name"], u["kinds"]) for u in preview["unproven_kinds"]] == [
            (str(ashfang), "Ashfang", ["being", "character", "item"])
        ]
        refused = await w.author.put(f"/tenants/{w.repository}/published", json={})
        assert refused.status_code == 409
        problem = refused.json()
        assert problem["type"] == "repository-has-unproven-kinds"
        assert problem["entries"] == [
            {"id": str(ashfang), "name": "Ashfang", "kinds": ["being", "character", "item"]}
        ]
        assert "“Ashfang” (being and character and item)" in problem["detail"]
        # Not even acknowledging breaks through it, and nothing was published.
        assert (
            await w.author.put(
                f"/tenants/{w.repository}/published", json={"acknowledge_breaking": True}
            )
        ).status_code == 409
        assert await w.releases() == []

        async with admin_session_factory() as session:
            await session.delete(await session.get_one(Character, ashfang))
            await session.commit()
        assert (await w.preview())["unproven_kinds"] == []
        release = await w.publish(label="1.0")
        assert release["label"] == "1.0"
    finally:
        await w.done()


async def test_the_combinations_a_publish_allows_are_the_ones_the_api_lists(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Each listed combination publishes, and one beside them does not."""
    w = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        async with admin_session_factory() as session:
            made: dict[tuple[str, ...], uuid.UUID] = {}
            for kinds in sorted(PUBLISHABLE_KIND_COMBINATIONS):
                entity = Entity(tenant_id=w.repository, name=f"Entry {'-'.join(kinds) or 'bare'}")
                session.add(entity)
                await session.flush()
                made[kinds] = entity.id
                if "item" in kinds:
                    session.add(Item(entity_id=entity.id, tenant_id=w.repository))
                if "item_instance" in kinds:
                    session.add(ItemInstance(entity_id=entity.id, tenant_id=w.repository))
                if "being" in kinds:
                    session.add(Being(entity_id=entity.id, tenant_id=w.repository))
                if "character" in kinds:
                    session.add(Character(entity_id=entity.id, tenant_id=w.repository))
            await session.commit()
        assert (await w.preview())["unproven_kinds"] == []
        assert (
            await w.author.put(f"/tenants/{w.repository}/published", json={})
        ).status_code == 200

        async with admin_session_factory() as session:
            session.add(Item(entity_id=made[("being", "character")], tenant_id=w.repository))
            await session.commit()
        unproven = (await w.preview())["unproven_kinds"]
        assert [u["kinds"] for u in unproven] == [["being", "character", "item"]]
    finally:
        await w.done()
