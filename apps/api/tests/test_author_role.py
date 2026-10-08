"""The Author role of RFC 0040 / ADR 0210, through the real HTTP API: an Author edits the content of
a library's catalog or a repository and can do nothing that changes who has access, what is
published or what the structure is. Each row of the capability matrix is a test, in a repository
and in a library alike; the route-by-route audit is test_author_route_audit.py.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from _author_world import World, add_member, make_item, make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor
from httpx import AsyncClient

KINDS = ["play", "repository"]


async def _stat_group(actor: Actor, tenant_id: uuid.UUID, name: str = "Abilities") -> uuid.UUID:
    response = await actor.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name})
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _stat_definition(
    actor: Actor, tenant_id: uuid.UUID, group_id: uuid.UUID, **body: object
) -> dict[str, object]:
    payload = {"name": "Strength", "stat_group_id": str(group_id), "value_type": "int", **body}
    response = await actor.post(f"/tenants/{tenant_id}/stat-definitions", json=payload)
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


async def _note(
    actor: Actor, tenant_id: uuid.UUID, entity_id: uuid.UUID, title: str, *, public: bool
) -> uuid.UUID:
    response = await actor.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": title, "type": "note", "is_public": public, "content": f"{title} text"},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _titles(actor: Actor, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> list[str]:
    response = await actor.get(f"/tenants/{tenant_id}/entities/{entity_id}/information")
    assert response.status_code == 200, response.text
    return sorted(n["title"] for n in response.json()["items"])


@pytest.fixture
async def world(
    request: pytest.FixtureRequest, raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> AsyncGenerator[World]:
    built = await make_world(raw_client, fake_jwks_server, kind=request.param)
    yield built
    await built.clean_up()


# --- what an Author can do ----------------------------------------------------------------


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_edits_content(world: World) -> None:
    author, tenant_id = world.author, world.tenant_id

    group_id = await _stat_group(author, tenant_id)
    strength = await _stat_definition(author, tenant_id, group_id)
    alignment = await _stat_definition(
        author, tenant_id, group_id, name="Alignment", value_type="enum", enum_values=["good"]
    )
    added = await author.post(
        f"/tenants/{tenant_id}/stat-definitions/{alignment['id']}/enum-values",
        json={"value": "evil"},
    )
    assert added.status_code == 201, added.text

    item_id = await make_item(author, tenant_id)
    renamed = await author.patch(f"/tenants/{tenant_id}/items/{item_id}", json={"name": "Blade"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Blade"

    stat = await author.put(
        f"/tenants/{tenant_id}/entities/{item_id}/stats/{strength['id']}", json={"value": 16}
    )
    assert stat.status_code == 200, stat.text
    slug = await author.put(f"/tenants/{tenant_id}/entities/{item_id}/slug", json={"slug": "blade"})
    assert slug.status_code == 200, slug.text

    note_id = await _note(author, tenant_id, item_id, "Edge", public=False)
    edited = await author.patch(
        f"/tenants/{tenant_id}/information/{note_id}", json={"title": "Edge, sharpened"}
    )
    assert edited.status_code == 200, edited.text

    # The Owner sees what the Author wrote.
    assert await _titles(world.owner, tenant_id, item_id) == ["Edge, sharpened"]


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_deletes_an_entry_nobody_inherits_from(world: World) -> None:
    item_id = await make_item(world.author, world.tenant_id, "Lonely")
    deleted = await world.author.delete(f"/tenants/{world.tenant_id}/items/{item_id}")
    assert deleted.status_code == 204, deleted.text


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_reads_every_note_on_the_entries_in_reach(world: World) -> None:
    owner, author = world.owner, world.author
    item_id = await make_item(owner, world.tenant_id)
    await _note(owner, world.tenant_id, item_id, "Public", public=True)
    await _note(owner, world.tenant_id, item_id, "GM only", public=False)
    assert await _titles(author, world.tenant_id, item_id) == ["GM only", "Public"]
    # A person who is not a member sees neither.
    assert (
        await world.outsider.get(f"/tenants/{world.tenant_id}/entities/{item_id}/information")
    ).status_code == 404


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_may_leave(world: World) -> None:
    left = await world.author.delete(
        f"/tenants/{world.tenant_id}/memberships/{world.author.user_id}"
    )
    assert left.status_code == 204, left.text
    assert (await world.author.get(f"/tenants/{world.tenant_id}/items")).status_code in (403, 404)


# --- what an Author cannot do -------------------------------------------------------------


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_cannot_delete_structure(world: World) -> None:
    owner, author, tenant_id = world.owner, world.author, world.tenant_id
    group_id = await _stat_group(owner, tenant_id)
    definition = await _stat_definition(
        owner, tenant_id, group_id, name="Alignment", value_type="enum", enum_values=["good"]
    )
    # An enum value is addressed by an id the API does not show, so any id meets the same gate.
    value_path = (
        f"/tenants/{tenant_id}/stat-definitions/{definition['id']}/enum-values/{uuid.uuid4()}"
    )
    for path in (
        value_path,
        f"/tenants/{tenant_id}/stat-definitions/{definition['id']}",
        f"/tenants/{tenant_id}/stat-groups/{group_id}",
    ):
        refused = await author.delete(path)
        assert refused.status_code == 403, f"{path}: {refused.text}"
        assert (await author.get(path.split("/enum-values")[0])).status_code == 200

    # The Owner still can, in the order that leaves nothing in use.
    assert (
        await owner.delete(f"/tenants/{tenant_id}/stat-definitions/{definition['id']}")
    ).status_code == 204
    assert (await owner.delete(f"/tenants/{tenant_id}/stat-groups/{group_id}")).status_code == 204


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_cannot_delete_an_entry_others_inherit_from(world: World) -> None:
    owner, author, tenant_id = world.owner, world.author, world.tenant_id
    parent = await make_item(owner, tenant_id, "Weapon")
    child = await author.post(
        f"/tenants/{tenant_id}/items", json={"name": "Sword", "prototype_ids": [str(parent)]}
    )
    assert child.status_code == 201, child.text

    refused = await author.delete(f"/tenants/{tenant_id}/items/{parent}")
    assert refused.status_code == 403
    assert refused.json()["type"] == "inherited-entry-deletion-forbidden"
    assert (await author.get(f"/tenants/{tenant_id}/items/{parent}")).status_code == 200

    # Once nothing inherits from it, the Author may delete it.
    assert (
        await author.delete(f"/tenants/{tenant_id}/items/{child.json()['entity_id']}")
    ).status_code == 204
    assert (await author.delete(f"/tenants/{tenant_id}/items/{parent}")).status_code == 204


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_cannot_rename_the_tenant_or_change_its_picture(world: World) -> None:
    author, tenant_id = world.author, world.tenant_id
    renamed = await author.patch(f"/tenants/{tenant_id}", json={"name": "Mine now"})
    assert renamed.status_code == 403
    assert (await author.delete(f"/tenants/{tenant_id}/picture")).status_code == 403
    assert (await world.owner.get(f"/tenants/{tenant_id}")).json()["name"] == "World"
    assert (
        await world.orga.patch(f"/tenants/{tenant_id}", json={"name": "Renamed"})
    ).status_code == 200


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_cannot_see_or_manage_people(world: World) -> None:
    author, tenant_id = world.author, world.tenant_id
    assert (await author.get(f"/tenants/{tenant_id}/memberships")).status_code == 403
    assert (await author.get(f"/tenants/{tenant_id}/activity-log")).status_code == 403
    assert (await world.orga.get(f"/tenants/{tenant_id}/memberships")).status_code == 200
    assert (await world.orga.get(f"/tenants/{tenant_id}/activity-log")).status_code == 200

    add = await author.post(
        f"/tenants/{tenant_id}/memberships",
        json={"user_id": str(world.outsider.user_id), "role": "author"},
    )
    assert add.status_code == 403
    promote = await author.patch(
        f"/tenants/{tenant_id}/memberships/{author.user_id}", json={"role": "owner"}
    )
    assert promote.status_code == 403
    remove = await author.delete(f"/tenants/{tenant_id}/memberships/{world.orga.user_id}")
    assert remove.status_code == 403
    assert (await world.owner.get(f"/tenants/{tenant_id}/memberships")).status_code == 200


@pytest.mark.parametrize("world", KINDS, indirect=True)
async def test_an_author_cannot_send_a_notification_to_everyone(world: World) -> None:
    body = {"type": "note", "title": "Hello", "body": "everyone"}
    assert (
        await world.author.post(f"/tenants/{world.tenant_id}/notifications", json=body)
    ).status_code == 403
    assert (
        await world.orga.post(f"/tenants/{world.tenant_id}/notifications", json=body)
    ).status_code == 201


async def test_an_author_cannot_publish_or_hand_out_a_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, kind="repository", name="Faerûn")
    try:
        author, tenant_id = world.author, world.tenant_id
        assert (await author.put(f"/tenants/{tenant_id}/published")).status_code == 403
        assert (await author.delete(f"/tenants/{tenant_id}/published")).status_code == 403
        assert (
            await author.put(f"/tenants/{tenant_id}/subscribers/{uuid.uuid4()}")
        ).status_code == 403
        assert (await author.get(f"/tenants/{tenant_id}/subscribers")).status_code == 403
        assert (await world.orga.put(f"/tenants/{tenant_id}/published")).status_code == 403
        # The Owner publishes; the Author then sees what was published, and may edit.
        assert (await world.owner.put(f"/tenants/{tenant_id}/published")).status_code == 200
        assert (await author.get(f"/tenants/{tenant_id}/releases")).status_code == 200
        assert (await author.get(f"/tenants/{tenant_id}/release-preview")).status_code == 200
    finally:
        await world.clean_up()


async def test_an_author_cannot_create_or_delete_a_campaign(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        author, tenant_id = world.author, world.tenant_id
        body = {"name": "Campaign", "game_system": "5e", "slug": "campaign", "description": ""}
        assert (await author.post(f"/tenants/{tenant_id}/campaigns", json=body)).status_code == 403
        made = await world.orga.post(f"/tenants/{tenant_id}/campaigns", json=body)
        assert made.status_code == 201, made.text
        campaign_id = made.json()["id"]
        assert (
            await author.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
        ).status_code == 403
        assert (
            await author.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out")
        ).status_code == 403
    finally:
        await world.clean_up()


# --- the reach of an Author in a library --------------------------------------------------


async def test_an_author_of_a_library_reaches_the_catalog_and_nothing_in_play(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        owner, author, tenant_id = world.owner, world.author, world.tenant_id
        character = await owner.post(f"/tenants/{tenant_id}/characters", json={"name": "Elminster"})
        assert character.status_code == 201, character.text
        character_id = character.json()["entity_id"]
        await _note(owner, tenant_id, uuid.UUID(character_id), "Secret", public=False)

        # Not the beings, nor what is written about one, nor the people at the table.
        assert (await author.get(f"/tenants/{tenant_id}/beings")).status_code == 404
        assert await _titles(author, tenant_id, uuid.UUID(character_id)) == []
        slug = await author.put(
            f"/tenants/{tenant_id}/entities/{character_id}/slug", json={"slug": "mine"}
        )
        assert slug.status_code == 403
        refused_note = await author.post(
            f"/tenants/{tenant_id}/entities/{character_id}/information",
            json={"title": "Mine", "type": "note", "content": "x"},
        )
        assert refused_note.status_code == 403
        made = await author.post(f"/tenants/{tenant_id}/characters", json={"name": "Elsewhere"})
        assert made.status_code == 403

        # The Organizer's reach is unchanged.
        assert (await world.orga.get(f"/tenants/{tenant_id}/beings")).status_code == 200
    finally:
        await world.clean_up()


async def test_an_author_of_a_repository_reaches_every_entry_in_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A repository has no campaigns, players or owned entries, so every entry is in reach: the
    ones that are not items too (a character seeded by the Owner here)."""
    world = await make_world(raw_client, fake_jwks_server, kind="repository", name="Faerûn")
    try:
        owner, author, tenant_id = world.owner, world.author, world.tenant_id
        character = await owner.post(f"/tenants/{tenant_id}/characters", json={"name": "Elminster"})
        assert character.status_code == 201, character.text
        entity_id = uuid.UUID(character.json()["entity_id"])
        await _note(owner, tenant_id, entity_id, "Secret", public=False)

        assert await _titles(author, tenant_id, entity_id) == ["Secret"]
        slug = await author.put(
            f"/tenants/{tenant_id}/entities/{entity_id}/slug", json={"slug": "elminster"}
        )
        assert slug.status_code == 200, slug.text
        note = await _note(author, tenant_id, entity_id, "Lore", public=True)
        assert note
    finally:
        await world.clean_up()


# --- a role is one of three, everywhere it is reported ------------------------------------


async def test_the_role_is_reported_as_author(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    library = await make_world(raw_client, fake_jwks_server, name="A table")
    repository = await make_world(raw_client, fake_jwks_server, kind="repository", name="Faerûn")
    try:
        author = library.author
        # The same person is an Author of the repository too.
        await add_member(repository.owner, repository.tenant_id, author, "author")

        me = (await author.get("/me")).json()
        roles = {m["tenant_id"]: m["role"] for m in me["memberships"]}
        assert roles == {str(library.tenant_id): "author", str(repository.tenant_id): "author"}

        listed = (await author.get("/tenants")).json()["items"]
        assert {t["id"]: t["role"] for t in listed} == roles

        managed = (await author.get("/me/managed")).json()["tenants"]
        assert {t["tenant_id"]: t["role"] for t in managed} == roles
        # An Author runs no campaign of the library.
        assert all(t["campaigns"] == [] for t in managed)
        # An Organizer still lists the library's campaigns (none made here).
        orga_managed = (await library.orga.get("/me/managed")).json()["tenants"]
        assert [t["role"] for t in orga_managed] == ["orga"]
    finally:
        await library.clean_up()
        await repository.clean_up()


async def test_an_owner_changes_a_role_to_and_from_author(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        owner, orga, tenant_id = world.owner, world.orga, world.tenant_id
        to_author = await owner.patch(
            f"/tenants/{tenant_id}/memberships/{orga.user_id}", json={"role": "author"}
        )
        assert to_author.status_code == 200, to_author.text
        assert to_author.json()["role"] == "author"
        # Now an Author: the people list is closed to them.
        assert (await orga.get(f"/tenants/{tenant_id}/memberships")).status_code == 403

        back = await owner.patch(
            f"/tenants/{tenant_id}/memberships/{orga.user_id}", json={"role": "orga"}
        )
        assert back.json()["role"] == "orga"
        assert (await orga.get(f"/tenants/{tenant_id}/memberships")).status_code == 200

        # The last Owner cannot step down into an Author.
        sole = await owner.patch(
            f"/tenants/{tenant_id}/memberships/{owner.user_id}", json={"role": "author"}
        )
        assert sole.status_code == 409
        assert sole.json()["type"] == "last-owner"
        # An unknown role is still refused.
        assert (
            await owner.patch(
                f"/tenants/{tenant_id}/memberships/{orga.user_id}", json={"role": "admin"}
            )
        ).status_code == 422
    finally:
        await world.clean_up()


async def test_the_last_owner_cannot_leave_while_authors_remain(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server)
    try:
        sole = await world.owner.delete(
            f"/tenants/{world.tenant_id}/memberships/{world.owner.user_id}"
        )
        assert sole.status_code == 409
    finally:
        await world.clean_up()
