"""The world of the tests of ADR 0435, RFC 0051 H4: a source whose entries a library hides.

A is the Armoury of the release tests (Longsword with Strength and the formula Damage, Dagger whose
parent is Longsword, Orc), protected by its Owner. B is a bridge built on it that carries it
hidden: it copied A, put "Bridge Blade" of its own on top of Longsword, and is public over it. A
library copies B, holds A through it and cannot see any entry of A, while Bridge Blade inherits
from Longsword all the same.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import release_world
from _repository_actors import Actor
from httpx import AsyncClient
from sqlalchemy import select
from test_repository_include import W, _bridge, _copy, _library, _make_public

from lorenzo_api.models import Entity, RepositoryCopy, RepositoryCopyLinkEntity

A_ENTRIES = ("Longsword", "Dagger", "Orc")


@dataclass
class H:
    """The world, the library that copied B and its Owner."""

    w: W
    reader: Actor
    library: uuid.UUID
    ids: dict[str, uuid.UUID]

    @property
    def a(self) -> uuid.UUID:
        return self.w.a

    @property
    def b(self) -> uuid.UUID:
        return self.w.b

    @property
    def hidden(self) -> dict[str, uuid.UUID]:
        return {name: self.ids[name] for name in A_ENTRIES}

    @property
    def visible(self) -> uuid.UUID:
        return self.ids["Bridge Blade"]

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.reader.get(f"/tenants/{self.library}{path}", **kwargs)

    async def done(self) -> None:
        await self.w.done()


async def protect(actor: Actor, repository: uuid.UUID, **body: Any) -> Any:
    return await actor.put(f"/tenants/{repository}/protected", json=body)


async def choose(actor: Actor, b: uuid.UUID, source: uuid.UUID, choice: str) -> Any:
    return await actor.put(
        f"/tenants/{b}/repositories/{source}/inclusion", json={"inclusion": choice}
    )


async def world(
    raw_client: AsyncClient,
    jwks: FakeJwksServer,
    *,
    choice: str = "hide",
    protected: bool = True,
    copy: bool = True,
) -> H:
    """A (protected unless `protected` is false, then public) and B built on it with `choice`,
    public; a library that has copied B if `copy`."""
    base = await release_world(raw_client, jwks)
    if protected:
        assert (await protect(base.author, base.repository, label="p1")).status_code == 200
    b, ids = await _bridge(base, "Bridge")
    w = W(base, b, ids)
    if not protected:
        made = await _make_public(base.author, base.repository)
        assert made.status_code == 200, made.text
    chosen = await choose(base.author, b, base.repository, choice)
    assert chosen.status_code == 200, chosen.text
    made = await _make_public(base.author, b)
    assert made.status_code == 200, made.text
    reader, library = await _library(raw_client, jwks, w)
    h = H(w, reader, library, {})
    if copy:
        copied = await _copy(reader, library, b)
        assert copied.status_code == 201, copied.text
        h.ids = await names_of(library)
    return h


async def names_of(tenant: uuid.UUID) -> dict[str, uuid.UUID]:
    """Every entry the tenant holds, by name, straight from the database: what the library has,
    whatever it can read of it."""
    async with admin_session_factory() as session:
        return {
            name: entity_id
            for entity_id, name in await session.execute(
                select(Entity.id, Entity.name).where(Entity.tenant_id == tenant)
            )
        }


async def hidden_names(tenant: uuid.UUID) -> list[str]:
    """The names of the entries whose copy link is hidden."""
    async with admin_session_factory() as session:
        return sorted(
            await session.scalars(
                select(Entity.name)
                .join(RepositoryCopyLinkEntity, RepositoryCopyLinkEntity.entity_id == Entity.id)
                .where(
                    RepositoryCopyLinkEntity.tenant_id == tenant,
                    RepositoryCopyLinkEntity.hidden.is_(True),
                )
            )
        )


async def carries(tenant: uuid.UUID) -> dict[uuid.UUID, dict[str, str]]:
    async with admin_session_factory() as session:
        return {
            repository: carried
            for repository, carried in await session.execute(
                select(RepositoryCopy.repository_tenant_id, RepositoryCopy.carries).where(
                    RepositoryCopy.tenant_id == tenant
                )
            )
        }


@dataclass
class Rich:
    """A repository `a` with a row in every content table (`seed_every_content_table`), protected;
    a repository `b` built on it that hides it and has one entry of its own on top of it, public;
    a library that copied `b`. `hidden` is the name and id of every entry of A."""

    author: Actor
    reader: Actor
    a: uuid.UUID
    b: uuid.UUID
    library: uuid.UUID
    spear: uuid.UUID
    hidden: dict[str, uuid.UUID]
    tenants: list[uuid.UUID]
    actors: list[Actor]

    @property
    def visible(self) -> uuid.UUID:
        return self.spear

    async def done(self) -> None:
        from _repository_actors import cleanup

        await cleanup(self.tenants, self.actors)


async def rich_world(raw_client: AsyncClient, jwks: FakeJwksServer) -> Rich:
    from _repository_actors import make_actor
    from _repository_fixtures import seed_every_content_table

    from lorenzo_api.models import EntityPrototype, Item

    author = await make_actor(raw_client, jwks, "author")
    reader = await make_actor(raw_client, jwks, "reader")
    a = await author.create_tenant("Fixtures", kind="repository")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, a)
        await session.commit()
    assert (await protect(author, a, label="p1")).status_code == 200
    b = await author.create_tenant("Bridge", kind="repository")
    assert (await author.put(f"/tenants/{a}/subscribers/{b}")).status_code in (200, 201)
    copied = await author.post(f"/tenants/{b}/repositories/{a}/copy", json={})
    assert copied.status_code == 201, copied.text
    ids = await names_of(b)
    async with admin_session_factory() as session:
        spear = Entity(tenant_id=b, name="Bridge Spear")
        session.add(spear)
        await session.flush()
        session.add_all(
            [
                Item(entity_id=spear.id, tenant_id=b),
                EntityPrototype(entity_id=spear.id, prototype_id=ids["Sword"], tenant_id=b),
            ]
        )
        await session.commit()
        spear_id = spear.id
    assert (await choose(author, b, a, "hide")).status_code == 200
    made = await _make_public(author, b)
    assert made.status_code == 200, made.text
    library = await reader.create_tenant("Library")
    copied = await _copy(reader, library, b)
    assert copied.status_code == 201, copied.text
    held = await names_of(library)
    hidden = {name: entity_id for name, entity_id in held.items() if name != "Bridge Spear"}
    return Rich(author, reader, a, b, library, spear_id, hidden, [a, b, library], [author, reader])
