"""Making and reading invite links of every kind through the real API, for the tests of ADR 0220."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from _admin_db import admin_session_factory
from _repository_actors import Actor
from httpx import AsyncClient

from lorenzo_api.models import Invite
from lorenzo_api.rate_limit import reset_invite_rate_limiter


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> None:
    """Every test gets a full bucket: the limiter is process-wide and these tests make more
    requests from one address than a minute allows."""
    reset_invite_rate_limiter()


def in_days(days: float) -> str:
    return (datetime.now(tz=UTC) + timedelta(days=days)).isoformat()


async def mint(owner: Actor, tenant_id: uuid.UUID, **body: object) -> dict[str, object]:
    response = await owner.post(f"/tenants/{tenant_id}/invites", json=body)
    assert response.status_code == 201, response.text
    created: dict[str, object] = response.json()
    return created


async def mint_role(
    owner: Actor, tenant_id: uuid.UUID, role: str = "author", **body: object
) -> str:
    """The token of a new role link."""
    created = await mint(owner, tenant_id, kind="tenant_role", role=role, **body)
    token = created["token"]
    assert isinstance(token, str)
    return token


async def mint_library(owner: Actor, repository_id: uuid.UUID, **body: object) -> str:
    """The token of a new library-access link."""
    created = await mint(owner, repository_id, kind="library_access", **body)
    token = created["token"]
    assert isinstance(token, str)
    return token


async def preview(raw_client: AsyncClient, token: str) -> tuple[int, dict[str, object]]:
    """Unauthenticated, as a visitor with a link is."""
    response = await raw_client.get(f"/invites/{token}")
    return response.status_code, response.json()


async def redeem(
    actor: Actor, token: str, library_id: uuid.UUID | None = None
) -> tuple[int, dict[str, object]]:
    kwargs: dict[str, object] = {}
    if library_id is not None:
        kwargs["json"] = {"library_id": str(library_id)}
    response = await actor.post(f"/invites/{token}/redeem", **kwargs)
    return response.status_code, response.json()


async def use_count(invite_id: str) -> int:
    async with admin_session_factory() as session:
        return (await session.get_one(Invite, uuid.UUID(invite_id))).use_count


async def end(invite_id: str, how: str) -> None:
    """Ends a link behind the API's back: `expired` or `used up` (a revoke goes through it)."""
    async with admin_session_factory() as session:
        invite = await session.get_one(Invite, uuid.UUID(invite_id))
        if how == "expired":
            invite.expires_at = datetime.now(tz=UTC) - timedelta(minutes=1)
        else:
            assert invite.max_uses is not None
            invite.use_count = invite.max_uses
        await session.commit()
