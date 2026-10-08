"""ADR 0198: what a repository is built on, as the asking library sees it,
through the real HTTP API. Every actor is a separate verified user; a
repository's content is authored straight into the database, every copy goes
through the API.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient, Response
from sqlalchemy import select

from lorenzo_api.models import Entity, Tenant

SECRET_ENTRY = "The Hidden Vault Of Mazes"

_KEYS = {"id", "name", "slug", "invited", "copied", "published"}


async def _author(tenant_id: uuid.UUID, *names: str) -> None:
    async with admin_session_factory() as session:
        session.add_all([Entity(tenant_id=tenant_id, name=name) for name in names])
        await session.commit()


async def _invite(owner: Actor, repository: uuid.UUID, *libraries: uuid.UUID) -> None:
    for library in libraries:
        response = await owner.put(f"/tenants/{repository}/subscribers/{library}")
        assert response.status_code in (200, 201), response.text


async def _publish(owner: Actor, repository: uuid.UUID) -> None:
    assert (await owner.put(f"/tenants/{repository}/published")).status_code == 200


async def _copy(actor: Actor, library: uuid.UUID, repository: uuid.UUID) -> None:
    response = await actor.post(f"/tenants/{library}/repositories/{repository}/copy")
    assert response.status_code == 201, response.text


async def _slug(tenant_id: uuid.UUID) -> str:
    async with admin_session_factory() as session:
        return (await session.scalars(select(Tenant.slug).where(Tenant.id == tenant_id))).one()


async def _dependencies(actor: Actor, library: uuid.UUID, repository: uuid.UUID) -> Response:
    return await actor.get(f"/tenants/{library}/repositories/{repository}/dependencies")


def _by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in items}


class _World:
    """Two repositories, "Zeta rules" and "Alpha setting", the second one
    built on the first, and a bridge built on both. Each has its own author;
    the bridge is published and nobody is invited to anything yet."""

    def __init__(self) -> None:
        self.actors: list[Actor] = []
        self.tenants: list[uuid.UUID] = []

    async def build(self, raw_client: AsyncClient, jwks: FakeJwksServer) -> None:
        self.zeta_author = await make_actor(raw_client, jwks, "zeta")
        self.alpha_author = await make_actor(raw_client, jwks, "alpha")
        self.bridger = await make_actor(raw_client, jwks, "bridger")
        self.gm = await make_actor(raw_client, jwks, "gm")
        self.actors = [self.zeta_author, self.alpha_author, self.bridger, self.gm]
        self.zeta = await self.zeta_author.create_tenant("Zeta rules", kind="repository")
        self.alpha = await self.alpha_author.create_tenant("Alpha setting", kind="repository")
        self.bridge = await self.bridger.create_tenant("Zeta Alpha bridge", kind="repository")
        self.table = await self.gm.create_tenant("My Table")
        self.tenants = [self.table, self.bridge, self.alpha, self.zeta]
        await _author(self.zeta, "Rulebook", SECRET_ENTRY)
        await _author(self.alpha, "City")
        # Alpha is built on Zeta ...
        await _invite(self.zeta_author, self.zeta, self.alpha)
        await _publish(self.zeta_author, self.zeta)
        await _copy(self.alpha_author, self.alpha, self.zeta)
        await _publish(self.alpha_author, self.alpha)
        # ... and the bridge on Alpha, which brings Zeta with it (ADR 0120).
        await _invite(self.alpha_author, self.alpha, self.bridge)
        await _invite(self.zeta_author, self.zeta, self.bridge)
        await _copy(self.bridger, self.bridge, self.alpha)
        await _publish(self.bridger, self.bridge)

    async def close(self) -> None:
        await cleanup(self.tenants, self.actors)


async def test_a_library_invited_only_to_the_bridge_learns_whom_to_ask(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.bridger, world.bridge, world.table)

        response = await _dependencies(world.gm, world.table, world.bridge)
        assert response.status_code == 200, response.text
        items = response.json()
        # Dependencies first: Zeta before Alpha, though Alpha sorts first by
        # name. The library is invited to neither.
        assert [item["name"] for item in items] == ["Alpha setting", "Zeta rules"]
        by_name = _by_name(items)
        assert by_name["Zeta rules"] == {
            "id": str(world.zeta),
            "name": "Zeta rules",
            "slug": await _slug(world.zeta),
            "invited": False,
            "copied": False,
            "published": True,
        }
        assert by_name["Alpha setting"]["slug"] == await _slug(world.alpha)
        assert all(set(item) == _KEYS for item in items)
        assert not any(item["invited"] or item["copied"] for item in items)
    finally:
        await world.close()


async def test_the_order_is_the_plans_order_dependencies_first(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.bridger, world.bridge, world.table)
        # Invited to Alpha, the library can read what Alpha is built on, so
        # Zeta comes before it: the order copy-plan gives.
        await _invite(world.alpha_author, world.alpha, world.table)
        items = (await _dependencies(world.gm, world.table, world.bridge)).json()
        assert [item["name"] for item in items] == ["Zeta rules", "Alpha setting"]
        plan = (
            await world.gm.get(f"/tenants/{world.table}/repositories/{world.bridge}/copy-plan")
        ).json()
        assert [step["name"] for step in plan["steps"][:-1]] == [item["name"] for item in items]
    finally:
        await world.close()


async def test_invited_and_copied_are_the_asking_librarys_own_state(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    other = await make_actor(raw_client, fake_jwks_server, "other")
    elsewhere = await other.create_tenant("Elsewhere")
    world.actors.append(other)
    world.tenants.append(elsewhere)
    try:
        await _invite(world.bridger, world.bridge, world.table, elsewhere)
        await _invite(world.zeta_author, world.zeta, world.table)

        items = _by_name((await _dependencies(world.gm, world.table, world.bridge)).json())
        assert (items["Zeta rules"]["invited"], items["Zeta rules"]["copied"]) == (True, False)
        assert (items["Alpha setting"]["invited"], items["Alpha setting"]["copied"]) == (
            False,
            False,
        )

        await _copy(world.gm, world.table, world.zeta)
        items = _by_name((await _dependencies(world.gm, world.table, world.bridge)).json())
        assert (items["Zeta rules"]["invited"], items["Zeta rules"]["copied"]) == (True, True)

        # The invitation withdrawn: the copy stays, and the library is no
        # longer invited. Another library's state is its own.
        revoked = await world.zeta_author.delete(f"/tenants/{world.zeta}/subscribers/{world.table}")
        assert revoked.status_code == 204, revoked.text
        items = _by_name((await _dependencies(world.gm, world.table, world.bridge)).json())
        assert (items["Zeta rules"]["invited"], items["Zeta rules"]["copied"]) == (False, True)
        other_items = _by_name((await _dependencies(other, elsewhere, world.bridge)).json())
        assert not any(i["invited"] or i["copied"] for i in other_items.values())
    finally:
        await world.close()


async def test_an_unpublished_dependency_is_listed_as_unpublished(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.bridger, world.bridge, world.table)
        withdrawn = await world.zeta_author.delete(f"/tenants/{world.zeta}/published")
        assert withdrawn.status_code == 200, withdrawn.text

        items = _by_name((await _dependencies(world.gm, world.table, world.bridge)).json())
        assert items["Zeta rules"]["published"] is False
        assert items["Zeta rules"]["slug"] == await _slug(world.zeta)
        assert items["Alpha setting"]["published"] is True
        # Still no word of its date: a flag, not published_at.
        assert set(items["Zeta rules"]) == _KEYS
    finally:
        await world.close()


async def test_a_repository_built_on_nothing_has_no_dependencies(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.zeta_author, world.zeta, world.table)
        response = await _dependencies(world.gm, world.table, world.zeta)
        assert response.status_code == 200, response.text
        assert response.json() == []
    finally:
        await world.close()


async def test_a_library_learns_nothing_where_the_gate_is_closed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    strangers = await stranger.create_tenant("Strangers")
    world.actors.append(stranger)
    world.tenants.append(strangers)
    try:
        # Not invited: the same answer as for an id that is nothing at all,
        # and for a library that is not a repository.
        unknown = await _dependencies(world.gm, world.table, uuid.uuid4())
        not_invited = await _dependencies(world.gm, world.table, world.bridge)
        a_library = await _dependencies(world.gm, world.table, strangers)
        for refused in (unknown, not_invited, a_library):
            assert refused.status_code == 404
            assert refused.json()["type"] == "repository-not-found"
        assert unknown.json()["title"] == not_invited.json()["title"]
        assert "slug" not in not_invited.text
        assert "Zeta" not in not_invited.text

        # Invited to the bridge, but another library's invitation does not
        # count, and a draft is invisible whatever invitations exist.
        await _invite(world.bridger, world.bridge, strangers)
        assert (await _dependencies(world.gm, world.table, world.bridge)).status_code == 404
        await _invite(world.bridger, world.bridge, world.table)
        assert (await _dependencies(world.gm, world.table, world.bridge)).status_code == 200
        withdrawn = await world.bridger.delete(f"/tenants/{world.bridge}/published")
        assert withdrawn.status_code == 200, withdrawn.text
        draft = await _dependencies(world.gm, world.table, world.bridge)
        assert draft.status_code == 404
        assert draft.json()["type"] == "repository-not-found"
        # The invitation withdrawn from a published repository ends it too.
        await _publish(world.bridger, world.bridge)
        await world.bridger.delete(f"/tenants/{world.bridge}/subscribers/{world.table}")
        assert (await _dependencies(world.gm, world.table, world.bridge)).status_code == 404
    finally:
        await world.close()


async def test_a_caller_who_is_not_a_member_of_the_library_gets_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.bridger, world.bridge, world.table)
        # The library is invited, but the caller is not one of its members.
        refused = await _dependencies(world.alpha_author, world.table, world.bridge)
        assert refused.status_code == 404
        assert refused.json()["type"] == "tenant-not-found"
        # Nor is the bridge's own author a member of the library.
        assert (await _dependencies(world.bridger, world.table, world.bridge)).status_code == 404
        # No token at all.
        anonymous = await raw_client.get(
            f"/tenants/{world.table}/repositories/{world.bridge}/dependencies"
        )
        assert anonymous.status_code in (401, 403)
    finally:
        await world.close()


async def test_nothing_of_a_dependencys_content_or_counts_comes_back(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.bridger, world.bridge, world.table)
        response = await _dependencies(world.gm, world.table, world.bridge)
        assert response.status_code == 200
        for item in response.json():
            assert set(item) == _KEYS
            assert not any(
                isinstance(value, int) and not isinstance(value, bool) for value in item.values()
            )
        for text in (SECRET_ENTRY, "Rulebook", "City", "description", "entities"):
            assert text not in response.text

        # Asking widens nothing: the library is still not invited to Zeta, so
        # its content, and its browse routes, stay shut afterwards.
        assert (
            await world.gm.get(f"/tenants/{world.table}/repositories/{world.zeta}/entities")
        ).status_code == 404
        assert (
            await world.gm.get(f"/tenants/{world.table}/repositories/{world.zeta}/dependencies")
        ).status_code == 404
    finally:
        await world.close()


async def test_it_loads_no_content(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: Any
) -> None:
    """The endpoint never plans a copy: planning loads content, and this must
    not."""
    import lorenzo_api.repository_copying as copying

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the dependencies endpoint loaded content")

    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.bridger, world.bridge, world.table)
        monkeypatch.setattr(copying, "load_content", refuse)
        monkeypatch.setattr(copying, "load_links", refuse)
        assert (await _dependencies(world.gm, world.table, world.bridge)).status_code == 200
    finally:
        await world.close()


async def test_a_dependency_that_no_longer_exists_is_left_out(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = _World()
    await world.build(raw_client, fake_jwks_server)
    try:
        await _invite(world.bridger, world.bridge, world.table)
        async with admin_session_factory() as session:
            gone = await session.get_one(Tenant, world.zeta)
            await session.delete(gone)
            await session.commit()
        items = (await _dependencies(world.gm, world.table, world.bridge)).json()
        assert [item["name"] for item in items] == ["Alpha setting"]
    finally:
        await world.close()
