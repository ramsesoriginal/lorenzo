"""Deleting an account records every departure it causes - ADR 0084's
addendum. The cascade removes the user's memberships, player seats and GM
grants in every tenant; each is recorded first, in its own tenant, with the
reason `account deleted`. Exercised with a genuine verified token
(`raw_client`) and a throwaway user, since the entries are written under
per-tenant RLS contexts that only a real request sets up.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from conftest import delete_tenant, make_campaign
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import (
    AuditLog,
    CampaignGm,
    Membership,
    MembershipRole,
    Player,
    Tenant,
    User,
)


async def _provision(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> tuple[dict[str, str], uuid.UUID]:
    token = fake_jwks_server.issue_token(f"authgear|leaving-{uuid.uuid4()}")
    headers = {"Authorization": f"Bearer {token}"}
    me = await raw_client.get("/me", headers=headers)
    assert me.status_code == 200
    return headers, uuid.UUID(me.json()["id"])


async def _tenant() -> uuid.UUID:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        return tenant.id


async def _entries(tenant_id: uuid.UUID) -> list[AuditLog]:
    async with admin_session_factory() as session:
        return list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.tenant_id == tenant_id)
                    .order_by(AuditLog.action, AuditLog.detail)
                )
            )
            .scalars()
            .all()
        )


async def test_deleting_an_account_records_every_departure_in_its_own_tenant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    headers, user_id = await _provision(raw_client, fake_jwks_server)
    admin_tenant, play_tenant = await _tenant(), await _tenant()
    other_owner_id = uuid.uuid4()
    async with admin_session_factory() as session:
        # A co-owner, so the sole-owner guard doesn't refuse the deletion.
        session.add(User(id=other_owner_id, authgear_subject_id=f"authgear|co-{uuid.uuid4()}"))
        await session.flush()
        session.add_all(
            [
                Membership(tenant_id=admin_tenant, user_id=user_id, role=MembershipRole.OWNER),
                Membership(
                    tenant_id=admin_tenant, user_id=other_owner_id, role=MembershipRole.OWNER
                ),
            ]
        )
        gm_campaign = await make_campaign(session, tenant_id=admin_tenant, name="Run By Them")
        table_a = await make_campaign(session, tenant_id=play_tenant, name="Table A")
        table_b = await make_campaign(session, tenant_id=play_tenant, name="Table B")
        session.add(CampaignGm(user_id=user_id, campaign_id=gm_campaign.id, tenant_id=admin_tenant))
        seat_a = Player(user_id=user_id, campaign_id=table_a.id, tenant_id=play_tenant)
        seat_b = Player(user_id=user_id, campaign_id=table_b.id, tenant_id=play_tenant)
        session.add_all([seat_a, seat_b])
        await session.commit()
        gm_campaign_id, seat_ids = gm_campaign.id, {seat_a.id, seat_b.id}

    response = await raw_client.delete("/me", headers=headers)
    assert response.status_code == 204, response.text

    admin_entries = await _entries(admin_tenant)
    assert [(e.action, e.target_id, e.detail) for e in admin_entries] == [
        ("campaign_gm.revoked", user_id, f"account deleted, campaign_id={gm_campaign_id}"),
        ("membership.deleted", user_id, "account deleted, role=owner"),
    ]

    play_entries = await _entries(play_tenant)
    assert {e.action for e in play_entries} == {"player.removed"}
    assert {e.target_id for e in play_entries} == seat_ids
    assert {e.detail for e in play_entries} == {f"account deleted, user={user_id}"}

    # Each entry sits only in its own tenant, and the actor has been cleared
    # by ON DELETE SET NULL now that the account is gone - the departed user
    # stays identifiable by target_id / detail.
    assert all(e.actor_id is None for e in [*admin_entries, *play_entries])

    await delete_tenant(admin_tenant)
    await delete_tenant(play_tenant)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_owner_id))
        await session.commit()


async def test_a_refused_deletion_writes_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    headers, user_id = await _provision(raw_client, fake_jwks_server)
    tenant_id = await _tenant()
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.OWNER))
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(Player(user_id=user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await raw_client.delete("/me", headers=headers)
    assert response.status_code == 409  # sole owner

    assert await _entries(tenant_id) == []

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_an_account_with_no_tenant_ties_deletes_cleanly(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    headers, user_id = await _provision(raw_client, fake_jwks_server)

    assert (await raw_client.delete("/me", headers=headers)).status_code == 204

    async with admin_session_factory() as session:
        assert await session.get(User, user_id) is None
