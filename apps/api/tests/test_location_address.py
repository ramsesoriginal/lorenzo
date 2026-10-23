"""The GM's address and the Location lint (ADR 0335)."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from sqlalchemy import func, select
from test_locations import place
from test_placement import character_of, contain, entry, put_at
from test_story_sessions import world

from lorenzo_api.models import (
    EntityLocation,
    LocationPart,
    Ownership,
)


async def address(actor: Any, t: Any, who: Any) -> dict[str, Any]:
    response = await actor.get(f"/tenants/{t}/entities/{who}/address")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def path(steps: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(s["via"], s["name"]) for s in steps]


async def test_the_address_of_an_entry(raw_client, fake_jwks_server):
    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        city = await place(gm, t, "Neverwinter", is_public=True)
        tavern = await place(gm, t, "Rusty Tankard", is_public=True, parent_id=city["id"])
        cellar = await place(gm, t, "Cellar", is_public=True, parent_id=tavern["id"])
        # A thing in a bag at the Tavern: what holds it, where that is, what that is within.
        pack = await entry(gm, t, "Backpack")
        sword = await entry(gm, t, "Sword")
        await contain(t, sword, pack)
        assert (await put_at(gm, t, pack, tavern["id"])).status_code == 200
        found = await address(gm, t, sword)
        assert path(found["segments"]) == [
            ("contained_in", "Backpack"),
            ("at", "Rusty Tankard"),
            ("part_of", "Neverwinter"),
        ]
        assert "interior" not in found
        assert found["segments"][1]["entity_id"] == tavern["id"]
        # Nothing about it: an empty list, and no other key.
        assert await address(gm, t, await entry(gm, t, "Rope")) == {"segments": []}
        # A thing in no container with an owner is with its owner, and so where the owner is.
        bram = await character_of(t, pid)
        assert (await put_at(gm, t, str(bram), cellar["id"])).status_code == 200
        lamp = await entry(gm, t, "Lamp")
        async with admin_session_factory() as session:
            session.add(Ownership(owned_entity_id=lamp, owner_character_id=bram, tenant_id=t))
            await session.commit()
        assert path((await address(gm, t, lamp))["segments"]) == [
            ("with", "Bram"),
            ("at", "Cellar"),
            ("part_of", "Rusty Tankard"),
            ("part_of", "Neverwinter"),
        ]
        # A Location: where it is, and what it is within, kept apart.
        found = await address(gm, t, cellar["id"])
        assert found["segments"] == []
        assert path(found["interior"]) == [("part_of", "Rusty Tankard"), ("part_of", "Neverwinter")]
        assert await address(gm, t, city["id"]) == {"segments": [], "interior": []}
        # A Location that is also a container, itself at a place.
        dock = await place(gm, t, "Dock", is_public=True)
        ship = await place(gm, t, "Ship", is_public=True, parent_id=dock["id"])
        assert (await put_at(gm, t, ship["id"], city["id"])).status_code == 200
        found = await address(gm, t, ship["id"])
        assert path(found["segments"]) == [("at", "Neverwinter")]
        assert path(found["interior"]) == [("part_of", "Dock")]
        # A Location used as a container is the place of what is in it.
        cell = await place(gm, t, "Cell", is_public=True, parent_id=city["id"])
        key = await entry(gm, t, "Key")
        await contain(t, key, cell["id"])
        assert path((await address(gm, t, key))["segments"]) == [
            ("contained_in", "Cell"),
            ("part_of", "Neverwinter"),
        ]
    finally:
        await w.clean_up()


async def test_who_may_read_an_address(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        thing = await entry(gm, t, "Thing")
        assert (await player.get(f"/tenants/{t}/entities/{thing}/address")).status_code == 403
        assert (await player.get(f"/tenants/{t}/lint/locations")).status_code == 403
        missing = await gm.get(f"/tenants/{t}/entities/{uuid.uuid4()}/address")
        assert missing.status_code == 404
        # The reads change nothing.
        before = await rows(t)
        await address(gm, t, thing)
        await gm.get(f"/tenants/{t}/lint/locations")
        assert await rows(t) == before
    finally:
        await w.clean_up()


async def rows(t: Any) -> tuple[int, int]:
    async with admin_session_factory() as session:
        return (
            await session.scalar(
                select(func.count())
                .select_from(EntityLocation)
                .where(EntityLocation.tenant_id == t)
            )
            or 0,
            await session.scalar(
                select(func.count()).select_from(LocationPart).where(LocationPart.tenant_id == t)
            )
            or 0,
        )


async def test_the_lint_names_each_probable_mistake(raw_client, fake_jwks_server):
    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        # Nothing yet: nothing to say.
        empty = await gm.get(f"/tenants/{t}/lint/locations")
        assert empty.status_code == 200 and empty.json()["items"] == []
        tavern = await place(gm, t, "Tavern", is_public=True)
        vault = await place(gm, t, "Vault")  # restricted
        # dormant_place: a row on something that is in a container.
        pack = await entry(gm, t, "Pack")
        coin = await entry(gm, t, "Coin")
        await contain(t, coin, pack)
        async with admin_session_factory() as session:
            session.add(
                EntityLocation(entity_id=coin, location_entity_id=tavern["id"], tenant_id=t)
            )
            await session.commit()
        # place_hidden: a thing everyone can see, at a place they cannot.
        gem = await entry(gm, t, "Gem")
        assert (await put_at(gm, t, gem, vault["id"])).status_code == 200
        # part_hidden: a public Location inside a restricted one.
        await place(gm, t, "Strongroom", is_public=True, parent_id=vault["id"])
        # part_loop: two Locations that are part of one another, as only a copy can make them.
        east = await place(gm, t, "East", is_public=True)
        west = await place(gm, t, "West", is_public=True)
        async with admin_session_factory() as session:
            session.add_all(
                [
                    LocationPart(
                        child_entity_id=east["id"], parent_entity_id=west["id"], tenant_id=t
                    ),
                    LocationPart(
                        child_entity_id=west["id"], parent_entity_id=east["id"], tenant_id=t
                    ),
                ]
            )
            await session.commit()
        listed = await gm.get(f"/tenants/{t}/lint/locations")
        assert listed.status_code == 200, listed.text
        items = listed.json()["items"]
        assert [f["finding"] for f in items] == [
            "dormant_place",
            "place_hidden",
            "part_hidden",
            "part_loop",
        ]
        assert listed.json()["total"] == 4
        by = {f["finding"]: f for f in items}
        assert [e["name"] for e in by["dormant_place"]["entries"]] == ["Coin", "Pack"]
        assert [e["name"] for e in by["place_hidden"]["entries"]] == ["Gem", "Vault"]
        assert [e["name"] for e in by["part_hidden"]["entries"]] == ["Strongroom", "Vault"]
        assert [e["name"] for e in by["part_loop"]["entries"]] == ["East", "West"]
        assert "players" in by["place_hidden"]["message"]
    finally:
        await w.clean_up()
