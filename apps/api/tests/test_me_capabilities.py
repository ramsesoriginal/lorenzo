"""`GET /me`'s `capabilities` (ADR 0175): what the caller may create, from the
same check `POST /tenants` gates on - so each answer is paired with what that
route actually does for the same caller.
"""

import uuid

from conftest import delete_tenant
from httpx import AsyncClient


async def test_me_says_a_tenant_creator_may_create_and_post_tenants_agrees(
    client: AsyncClient,
) -> None:
    me = await client.get("/me")

    assert me.status_code == 200
    assert me.json()["capabilities"] == {"create_tenant": True}

    created = await client.post("/tenants", json={"name": "Capability World"})
    assert created.status_code == 201
    await delete_tenant(uuid.UUID(created.json()["id"]))


async def test_me_says_no_without_the_role_and_post_tenants_agrees(
    client_without_tenant_creator_role: AsyncClient,
) -> None:
    me = await client_without_tenant_creator_role.get("/me")

    assert me.status_code == 200
    assert me.json()["capabilities"] == {"create_tenant": False}

    refused = await client_without_tenant_creator_role.post(
        "/tenants", json={"name": "Capability World"}
    )
    assert refused.status_code == 403


async def test_patch_me_carries_the_capabilities_too(client: AsyncClient) -> None:
    """PATCH /me answers with the same MeOut, so a client that updates its
    profile and keeps the response does not lose the capability."""
    response = await client.patch("/me", json={"pronouns": "they/them"})

    assert response.status_code == 200
    assert response.json()["capabilities"] == {"create_tenant": True}


async def test_patch_me_without_the_role_says_no(
    client_without_tenant_creator_role: AsyncClient,
) -> None:
    response = await client_without_tenant_creator_role.patch("/me", json={"pronouns": "she/her"})

    assert response.status_code == 200
    assert response.json()["capabilities"] == {"create_tenant": False}
