"""GET /me/managed and ?since= on GET /me/notifications - see ADR 0086.

/me/managed is exercised with a genuine verified token (`raw_client`), not
the fake-user fixture: it sets the RLS tenant context per tenant, and ADR
0038 found the hard way that only a real token catches a lost context.
"""

import uuid
from datetime import UTC, datetime, timedelta

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from conftest import delete_tenant, make_campaign
from httpx import AsyncClient
from sqlalchemy import delete

from lorenzo_api.models import (
    CampaignGm,
    Membership,
    MembershipRole,
    Notification,
    Player,
    Tenant,
    User,
)


async def _make_tenant(name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        tenant = Tenant(name=name)
        session.add(tenant)
        await session.commit()
        return tenant.id


async def test_managed_scope_lists_admin_tenants_gm_tenants_and_nothing_else(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    subject = f"authgear|managed-{uuid.uuid4()}"
    headers = {"Authorization": f"Bearer {fake_jwks_server.issue_token(subject)}"}
    me = await raw_client.get("/me", headers=headers)  # auto-provisions the user
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    owner_tenant = await _make_tenant("Owned World")
    gm_tenant = await _make_tenant("Guest World")
    player_tenant = await _make_tenant("Player World")
    orga_tenant = await _make_tenant("Orga World")
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=owner_tenant, user_id=user_id, role=MembershipRole.OWNER))
        session.add(Membership(tenant_id=orga_tenant, user_id=user_id, role=MembershipRole.ORGA))
        owned_a = await make_campaign(session, tenant_id=owner_tenant, name="Alpha")
        owned_b = await make_campaign(session, tenant_id=owner_tenant, name="Beta")
        gm_of = await make_campaign(session, tenant_id=gm_tenant, name="Gmed")
        not_gm_of = await make_campaign(session, tenant_id=gm_tenant, name="Not Gmed")
        player_in = await make_campaign(session, tenant_id=player_tenant, name="Playing")
        session.add(CampaignGm(user_id=user_id, campaign_id=gm_of.id, tenant_id=gm_tenant))
        session.add(Player(user_id=user_id, campaign_id=player_in.id, tenant_id=player_tenant))
        await session.commit()
        gm_of_id, not_gm_of_id = gm_of.id, not_gm_of.id
        owned_ids = {owned_a.id, owned_b.id}

    response = await raw_client.get("/me/managed", headers=headers)
    assert response.status_code == 200, response.text
    tenants = {t["tenant_id"]: t for t in response.json()["tenants"]}

    # A plain player manages nothing, so their tenant isn't listed at all.
    assert set(tenants) == {str(owner_tenant), str(gm_tenant), str(orga_tenant)}

    owned = tenants[str(owner_tenant)]
    assert owned["role"] == "owner"
    assert {c["campaign_id"] for c in owned["campaigns"]} == {str(i) for i in owned_ids}
    assert [c["name"] for c in owned["campaigns"]] == ["Alpha", "Beta"]
    assert all(c["is_gm"] is False for c in owned["campaigns"])

    guest = tenants[str(gm_tenant)]
    assert guest["role"] is None
    assert [c["campaign_id"] for c in guest["campaigns"]] == [str(gm_of_id)]
    assert guest["campaigns"][0]["is_gm"] is True
    assert str(not_gm_of_id) not in {c["campaign_id"] for c in guest["campaigns"]}

    assert tenants[str(orga_tenant)]["role"] == "orga"
    assert tenants[str(orga_tenant)]["campaigns"] == []

    for tenant_id in (owner_tenant, gm_tenant, player_tenant, orga_tenant):
        await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_managed_scope_is_empty_not_404_for_a_user_who_runs_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    subject = f"authgear|managed-empty-{uuid.uuid4()}"
    headers = {"Authorization": f"Bearer {fake_jwks_server.issue_token(subject)}"}

    response = await raw_client.get("/me/managed", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"tenants": []}

    async with admin_session_factory() as session:
        user = (await raw_client.get("/me", headers=headers)).json()["id"]
        await session.delete(await session.get_one(User, uuid.UUID(user)))
        await session.commit()


async def _seed_notifications(user_id: uuid.UUID, tag: str) -> list[datetime]:
    """Three notifications at fixed, far-past instants, so they can't be
    confused with rows other tests create at "now".
    """
    base = datetime(2001, 1, 1, tzinfo=UTC)
    times = [base, base + timedelta(hours=1), base + timedelta(hours=2)]
    async with admin_session_factory() as session:
        for index, created_at in enumerate(times):
            session.add(
                Notification(
                    batch_id=uuid.uuid4(),
                    user_id=user_id,
                    tenant_id=None,
                    scope="platform",
                    source_id=None,
                    type="since_test",
                    title=f"{tag}-{index}",
                    body="b",
                    created_by=None,
                    created_at=created_at,
                    read_at=created_at if index == 2 else None,
                )
            )
        await session.commit()
    return times


async def _titles(client: AsyncClient, tag: str, **params: str | bool) -> list[str]:
    response = await client.get("/me/notifications", params={"size": 100, **params})
    assert response.status_code == 200, response.text
    return [n["title"] for n in response.json()["items"] if n["title"].startswith(tag)]


async def test_notifications_since_is_inclusive_and_composes_with_unread_only(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tag = f"since-{uuid.uuid4()}"
    t0, t1, t2 = await _seed_notifications(test_user_id, tag)

    assert sorted(await _titles(client, tag)) == [f"{tag}-0", f"{tag}-1", f"{tag}-2"]

    # Inclusive: the row exactly at `since` comes back (the client dedupes by id).
    assert sorted(await _titles(client, tag, since=t1.isoformat())) == [f"{tag}-1", f"{tag}-2"]
    assert await _titles(client, tag, since=(t2 + timedelta(seconds=1)).isoformat()) == []

    # Newest first, and unread_only still applies on top (index 2 is read).
    assert await _titles(client, tag, since=t0.isoformat(), unread_only=True) == [
        f"{tag}-1",
        f"{tag}-0",
    ]

    async with admin_session_factory() as session:
        await session.execute(delete(Notification).where(Notification.type == "since_test"))
        await session.commit()


async def test_notifications_since_rejects_a_naive_datetime(client: AsyncClient) -> None:
    response = await client.get("/me/notifications", params={"since": "2001-01-01T00:00:00"})
    assert response.status_code == 422
