"""A library or a repository with one person in each role (RFC 0040), for the tests of what an
Author may and may not do. Every one is a real, verified JWT through `raw_client`, like the
repository tests.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient

_NO_PLATFORM_ROLES: tuple[str, ...] = ()


@dataclass
class World:
    tenant_id: uuid.UUID
    owner: Actor
    orga: Actor
    author: Actor
    outsider: Actor

    @property
    def actors(self) -> list[Actor]:
        return [self.owner, self.orga, self.author, self.outsider]

    async def clean_up(self) -> None:
        await cleanup([self.tenant_id], self.actors)


async def add_member(owner: Actor, tenant_id: uuid.UUID, person: Actor, role: str) -> None:
    response = await owner.post(
        f"/tenants/{tenant_id}/memberships", json={"user_id": str(person.user_id), "role": role}
    )
    assert response.status_code == 201, response.text


async def make_world(
    raw_client: AsyncClient, jwks: FakeJwksServer, *, kind: str = "play", name: str = "World"
) -> World:
    """The Owner makes the tenant and adds an Organizer and an Author; the outsider has nothing."""
    owner = await make_actor(raw_client, jwks, "owner")
    orga = await make_actor(raw_client, jwks, "orga", roles=_NO_PLATFORM_ROLES)
    author = await make_actor(raw_client, jwks, "author", roles=_NO_PLATFORM_ROLES)
    outsider = await make_actor(raw_client, jwks, "outsider", roles=_NO_PLATFORM_ROLES)
    tenant_id = await owner.create_tenant(name, kind=kind)
    await add_member(owner, tenant_id, orga, "orga")
    await add_member(owner, tenant_id, author, "author")
    return World(tenant_id, owner, orga, author, outsider)


async def make_item(actor: Actor, tenant_id: uuid.UUID, name: str = "Sword") -> uuid.UUID:
    response = await actor.post(f"/tenants/{tenant_id}/items", json={"name": name})
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["entity_id"])
