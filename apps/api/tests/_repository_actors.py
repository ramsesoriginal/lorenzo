"""Actors for the repository tests (ADR 0118 onward): each one a real,
verified JWT through `raw_client`, like test_milestone_scenario.py, since
repositories are about two tenants run by different people.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient, Response

from lorenzo_api.models import Tenant, User

# Mirrors dependencies._AUTHGEAR_ROLES_CLAIM - see test_milestone_scenario.py.
_ROLES_CLAIM = "https://authgear.com/claims/user/roles"


@dataclass
class Actor:
    client: AsyncClient
    headers: dict[str, str]
    user_id: uuid.UUID

    async def get(self, url: str, **kwargs: object) -> Response:
        return await self.client.get(url, headers=self.headers, **kwargs)  # type: ignore[arg-type]

    async def post(self, url: str, **kwargs: object) -> Response:
        return await self.client.post(url, headers=self.headers, **kwargs)  # type: ignore[arg-type]

    async def put(self, url: str, **kwargs: object) -> Response:
        return await self.client.put(url, headers=self.headers, **kwargs)  # type: ignore[arg-type]

    async def patch(self, url: str, **kwargs: object) -> Response:
        return await self.client.patch(url, headers=self.headers, **kwargs)  # type: ignore[arg-type]

    async def delete(self, url: str, **kwargs: object) -> Response:
        return await self.client.delete(url, headers=self.headers, **kwargs)  # type: ignore[arg-type]

    async def create_tenant(self, name: str, *, kind: str = "play") -> uuid.UUID:
        response = await self.post("/tenants", json={"name": name, "kind": kind})
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["id"])


async def make_actor(raw_client: AsyncClient, jwks: FakeJwksServer, name: str) -> Actor:
    """A fresh user who may create tenants."""
    token = jwks.issue_token(
        f"authgear|{name}-{uuid.uuid4()}", **{_ROLES_CLAIM: ["tenant_creator"]}
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = await raw_client.get("/me", headers=headers)
    assert response.status_code == 200, response.text
    return Actor(raw_client, headers, uuid.UUID(response.json()["id"]))


async def cleanup(tenant_ids: list[uuid.UUID], actors: list[Actor]) -> None:
    async with admin_session_factory() as session:
        for tenant_id in tenant_ids:
            tenant = await session.get(Tenant, tenant_id)
            if tenant is not None:
                await session.delete(tenant)
        await session.commit()
        for actor in actors:
            user = await session.get(User, actor.user_id)
            if user is not None:
                await session.delete(user)
        await session.commit()
