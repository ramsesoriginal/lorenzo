"""ADR 0200: a library's GMs read the GM-only text a copy brings, through the real HTTP API with
each person on their own token - and gain nothing about what another campaign's characters hold.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _library_scene import (
    CAMPAIGN_ENTRIES,
    HELD_BY_X,
    HELD_BY_Y,
    LibraryScene,
    build_library,
    set_sharing,
)
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import update
from test_repository_copy import _entity_ids, _share

from lorenzo_api.models import Entity, Information, Item


@dataclass
class _World:
    scene: LibraryScene
    repository_id: uuid.UUID
    people: dict[str, Actor]
    copied: dict[str, uuid.UUID]

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.scene.tenant_id

    async def titles(self, who: str, name: str) -> set[str]:
        """The GM-only notes `who` reads on the entry `name` (in the scene, or copied)."""
        entity_id = self.scene.ids.get(name) or self.copied[name]
        response = await self.people[who].get(
            f"/tenants/{self.tenant_id}/entities/{entity_id}/information"
        )
        assert response.status_code == 200, response.text
        return {row["title"] for row in response.json()["items"]}


async def _world(raw_client: AsyncClient, jwks: FakeJwksServer) -> _World:
    """The library of _library_scene, plus a repository with two catalog items carrying a GM-only
    note each, copied into the library by its Owner."""
    people = {
        label: await make_actor(raw_client, jwks, label)
        for label in ("owner", "gm_x", "gm_x2", "gm_y", "player_x", "player_y", "author")
    }
    scene = await build_library({k: v.user_id for k, v in people.items() if k != "author"})
    repository = await people["author"].create_tenant("Faerûn", kind="repository")
    async with admin_session_factory() as session:
        for name in ("Sword", "Chest"):
            entity = Entity(tenant_id=repository, name=name)
            session.add(entity)
            await session.flush()
            session.add(Item(entity_id=entity.id, tenant_id=repository))
            session.add(
                Information(
                    tenant_id=repository,
                    entity_id=entity.id,
                    title=f"{name} secret",
                    type="note",
                    is_public=False,
                )
            )
        await session.commit()
    await _share(people["author"], repository, scene.tenant_id)
    copied = await people["owner"].post(
        f"/tenants/{scene.tenant_id}/repositories/{repository}/copy"
    )
    assert copied.status_code == 201, copied.text
    names = await _entity_ids(scene.tenant_id)
    return _World(scene, repository, people, {n: names[n] for n in ("Sword", "Chest")})


async def _tear_down(world: _World) -> None:
    await cleanup([world.tenant_id, world.repository_id], list(world.people.values()))


async def test_a_gm_with_no_membership_reads_the_gm_only_text_of_a_copied_item(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)

    # The setting is on by default: every GM of the library, of either campaign.
    for gm in ("gm_x", "gm_x2", "gm_y"):
        assert await world.titles(gm, "Sword") == {"Sword secret"}, gm
        assert await world.titles(gm, "Chest") == {"Chest secret"}, gm
    # The library's Owner reads it as before.
    assert await world.titles("owner", "Sword") == {"Sword secret"}
    # A player, in either campaign, never does.
    for player in ("player_x", "player_y"):
        assert await world.titles(player, "Sword") == set(), player

    await _tear_down(world)


async def test_with_the_setting_off_only_the_authors_gms_read_a_copy(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    off = await world.people["owner"].patch(
        f"/tenants/{world.tenant_id}", json={"npcs_shared_with_gms": False}
    )
    assert off.status_code == 200, off.text

    # The copy credits the Owner, who is no GM and so no co-GM of anyone.
    for gm in ("gm_x", "gm_x2", "gm_y"):
        assert await world.titles(gm, "Sword") == set(), gm
    assert await world.titles("owner", "Sword") == {"Sword secret"}

    # Authored by gm_x: read by them and by their co-GM gm_x2, not by a GM of another campaign.
    async with admin_session_factory() as session:
        await session.execute(
            update(Entity)
            .where(Entity.id == world.copied["Sword"])
            .values(created_by=world.people["gm_x"].user_id)
        )
        await session.commit()
    assert await world.titles("gm_x", "Sword") == {"Sword secret"}
    assert await world.titles("gm_x2", "Sword") == {"Sword secret"}
    assert await world.titles("gm_y", "Sword") == set()
    # What nobody of theirs authored stays unread.
    assert await world.titles("gm_x", "Chest") == set()
    for player in ("player_x", "player_y"):
        assert await world.titles(player, "Sword") == set(), player

    # Switching it back on gives every GM the rest again.
    on = await world.people["owner"].patch(
        f"/tenants/{world.tenant_id}", json={"npcs_shared_with_gms": True}
    )
    assert on.status_code == 200, on.text
    assert await world.titles("gm_y", "Chest") == {"Chest secret"}

    await _tear_down(world)


@pytest.mark.parametrize("shared", [True, False])
async def test_a_gm_gains_nothing_about_what_another_campaigns_characters_hold(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, shared: bool
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    await set_sharing(world.tenant_id, shared)

    for name in HELD_BY_Y:
        # A GM of X reads none of it: the characters hold it, or stand in it, in Y ...
        assert await world.titles("gm_x", name) == set(), (name, shared)
        assert await world.titles("gm_x2", name) == set(), (name, shared)
        # ... and a GM of Y reads all of it, as before.
        assert await world.titles("gm_y", name) == {name}, (name, shared)
    for name in HELD_BY_X:
        assert await world.titles("gm_x", name) == {name}, (name, shared)
        assert await world.titles("gm_y", name) == set(), (name, shared)
    # Nor does any GM gain the entry a campaign carries for itself.
    for name in CAMPAIGN_ENTRIES:
        for gm in ("gm_x", "gm_x2", "gm_y"):
            assert await world.titles(gm, name) == set(), (gm, name, shared)
    # Players read none of it but what is theirs to know: nothing was told to a character.
    for name in (*HELD_BY_X, *HELD_BY_Y, "Lantern", "Crate"):
        assert await world.titles("player_x", name) == set(), name
        assert await world.titles("player_y", name) == set(), name

    await _tear_down(world)


async def test_a_gm_reads_what_no_campaign_owns_by_authorship_when_the_setting_is_off(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Lantern (a catalog item) was authored by gm_x2, Crate (an inventory item nobody owns or
    carries) by gm_y: owned by no campaign, so with the setting on every GM reads them."""
    world = await _world(raw_client, fake_jwks_server)

    for gm in ("gm_x", "gm_x2", "gm_y"):
        for name in ("Lantern", "Crate"):
            assert await world.titles(gm, name) == {name}, (gm, name)

    await set_sharing(world.tenant_id, False)
    assert await world.titles("gm_x", "Lantern") == {"Lantern"}  # authored by a co-GM
    assert await world.titles("gm_x2", "Lantern") == {"Lantern"}  # authored by themselves
    assert await world.titles("gm_y", "Lantern") == set()
    assert await world.titles("gm_y", "Crate") == {"Crate"}  # authored by themselves
    assert await world.titles("gm_x", "Crate") == set()
    assert await world.titles("owner", "Crate") == {"Crate"}

    await _tear_down(world)
