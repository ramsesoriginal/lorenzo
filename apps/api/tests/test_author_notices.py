"""What a person is told about their role, and who is told of a repository's doings (RFC 0040 /
ADR 0219): the three names Owner, Organizer and Author, never the raw value, and the notices that
are for the people who run a library go to its Owners and Organizers, not to its Authors.
"""

from __future__ import annotations

from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient


async def _notices(actor: Actor) -> list[dict[str, str]]:
    response = await actor.get("/me/notifications")
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


async def test_being_added_says_the_role_in_words(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    library = await make_world(raw_client, fake_jwks_server, name="A table")
    repository = await make_world(raw_client, fake_jwks_server, kind="repository", name="Faerûn")
    try:
        (author_notice,) = await _notices(library.author)
        assert author_notice["type"] == "tenant_invite"
        assert author_notice["title"] == "You were added to A table as an Author"
        assert "library" in author_notice["body"]
        (orga_notice,) = await _notices(library.orga)
        assert orga_notice["title"] == "You were added to A table as an Organizer"

        await repository.owner.post(
            f"/tenants/{repository.tenant_id}/memberships",
            json={"user_id": str(library.outsider.user_id), "role": "author"},
        )
        (repository_notice,) = await _notices(library.outsider)
        assert repository_notice["title"] == "You were added to Faerûn as an Author"
        assert "repository" in repository_notice["body"]
        for notice in (author_notice, orga_notice, repository_notice):
            assert "orga" not in notice["body"].replace("Organizer", "")
            assert "access" not in notice["title"]
    finally:
        await library.clean_up()
        await repository.clean_up()


async def test_a_role_change_is_told(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, name="A table")
    try:
        changed = await world.owner.patch(
            f"/tenants/{world.tenant_id}/memberships/{world.author.user_id}",
            json={"role": "orga"},
        )
        assert changed.status_code == 200
        notices = await _notices(world.author)
        assert notices[0]["type"] == "tenant_role_changed"
        assert notices[0]["title"] == "Your role in A table is now Organizer"

        # Asking for the role someone has changes nothing, so says nothing.
        await world.owner.patch(
            f"/tenants/{world.tenant_id}/memberships/{world.author.user_id}",
            json={"role": "orga"},
        )
        assert len(await _notices(world.author)) == len(notices)
    finally:
        await world.clean_up()


async def test_being_removed_does_not_say_tenant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await make_world(raw_client, fake_jwks_server, name="A table")
    try:
        await world.owner.delete(f"/tenants/{world.tenant_id}/memberships/{world.author.user_id}")
        notice = (await _notices(world.author))[0]
        assert notice["type"] == "tenant_membership_removed"
        assert notice["title"] == "Your access to A table has ended"
        assert "tenant" not in (notice["title"] + notice["body"]).lower()
    finally:
        await world.clean_up()


async def test_a_repositorys_notices_go_to_the_admins_of_the_library_not_its_authors(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    library = await make_world(raw_client, fake_jwks_server, name="A table")
    maker = await make_actor(raw_client, fake_jwks_server, "maker")
    repository_id = await maker.create_tenant("Faerûn", kind="repository")
    try:
        before = {
            name: len(await _notices(getattr(library, name)))
            for name in ("owner", "orga", "author")
        }
        granted = await maker.put(f"/tenants/{repository_id}/subscribers/{library.tenant_id}")
        assert granted.status_code == 201, granted.text
        assert (await maker.put(f"/tenants/{repository_id}/published")).status_code == 200

        for name in ("owner", "orga"):
            types = [n["type"] for n in await _notices(getattr(library, name))]
            assert types[:2] == ["repository_published", "repository_granted"], name
        assert len(await _notices(library.author)) == before["author"]
    finally:
        await cleanup([repository_id], [maker])
        await library.clean_up()
