import uuid
from datetime import timedelta

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient

from lorenzo_api.models import Membership, MembershipRole, Tenant, User


async def test_valid_token_grants_access_and_auto_provisions_user(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)

    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["authgear_subject_id"] == subject
    assert body["memberships"] == []
    user_id = uuid.UUID(body["id"])

    # Same subject again - must resolve to the SAME user, not create a
    # second row (the atomic-upsert path, ADR 0023).
    token2 = fake_jwks_server.issue_token(subject)
    response2 = await raw_client.get("/me", headers={"Authorization": f"Bearer {token2}"})
    assert response2.status_code == 200
    assert response2.json()["id"] == str(user_id)

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_missing_token_is_rejected(raw_client: AsyncClient) -> None:
    response = await raw_client.get("/me")
    assert response.status_code == 401


async def test_bad_signature_is_rejected(raw_client: AsyncClient) -> None:
    response = await raw_client.get("/me", headers={"Authorization": "Bearer not.a.validtoken"})
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


async def test_expired_token_is_rejected(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    token = fake_jwks_server.issue_token(
        f"authgear|{uuid.uuid4()}", expires_delta=timedelta(seconds=-10)
    )
    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


async def test_wrong_audience_is_rejected(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    token = fake_jwks_server.issue_token(f"authgear|{uuid.uuid4()}", audience="wrong-audience")
    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_wrong_issuer_is_rejected(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    token = fake_jwks_server.issue_token(f"authgear|{uuid.uuid4()}", issuer="wrong-issuer")
    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_me_reports_tenant_memberships(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)
    headers = {"Authorization": f"Bearer {token}"}

    # First request auto-provisions the user - need its id before creating
    # a Membership row for it.
    response = await raw_client.get("/me", headers=headers)
    user_id = uuid.UUID(response.json()["id"])

    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()
        tenant_id = tenant.id

    response2 = await raw_client.get("/me", headers=headers)
    assert response2.status_code == 200
    assert response2.json()["memberships"] == [{"tenant_id": str(tenant_id), "role": "owner"}]

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_tenant_scoped_route_requires_real_membership(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Proves get_tenant_context's new membership check end to end through
    a real existing tenant-scoped route (entities), not just /me.
    """
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)
    headers = {"Authorization": f"Bearer {token}"}

    me_response = await raw_client.get("/me", headers=headers)
    user_id = uuid.UUID(me_response.json()["id"])

    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    # No Membership yet - must 404, identical in shape to a genuinely
    # unknown tenant (ADR 0023) - a non-member can't distinguish the two.
    no_membership_response = await raw_client.get(f"/tenants/{tenant_id}/entities", headers=headers)
    assert no_membership_response.status_code == 404
    unknown_tenant_response = await raw_client.get(
        f"/tenants/{uuid.uuid4()}/entities", headers=headers
    )
    assert unknown_tenant_response.status_code == 404
    assert no_membership_response.json()["type"] == unknown_tenant_response.json()["type"]
    assert no_membership_response.json()["title"] == unknown_tenant_response.json()["title"]

    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()

    with_membership_response = await raw_client.get(
        f"/tenants/{tenant_id}/entities", headers=headers
    )
    assert with_membership_response.status_code == 200

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()
