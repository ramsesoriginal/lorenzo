"""Member removal writes a detailed audit entry and notifies the departing
member - see ADR 0084. Removal ends only the tenant-wide Membership row, so
these also pin down what does *not* change: campaign seats survive.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import (
    AuditLog,
    Membership,
    MembershipRole,
    Notification,
    Player,
    User,
)


async def _make_user(prefix: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|{prefix}-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        return user.id


async def _delete_user(user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def _removal_notifications(tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Notification]:
    async with admin_session_factory() as session:
        return list(
            (
                await session.execute(
                    select(Notification).where(
                        Notification.tenant_id == tenant_id,
                        Notification.user_id == user_id,
                        Notification.type == "tenant_membership_removed",
                    )
                )
            )
            .scalars()
            .all()
        )


async def _deleted_entries(tenant_id: uuid.UUID, target_id: uuid.UUID) -> list[AuditLog]:
    async with admin_session_factory() as session:
        return list(
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.tenant_id == tenant_id,
                        AuditLog.target_id == target_id,
                        AuditLog.action == "membership.deleted",
                    )
                )
            )
            .scalars()
            .all()
        )


async def test_removing_a_member_notifies_them_and_records_who_and_what_role(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    member_id = await _make_user("removed-member")
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=tenant_id, user_id=member_id, role=MembershipRole.ORGA))
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(Player(user_id=member_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.delete(f"/tenants/{tenant_id}/memberships/{member_id}")
    assert response.status_code == 204

    (notice,) = await _removal_notifications(tenant_id, member_id)
    assert notice.scope == "tenant"
    assert notice.created_by == test_user_id
    assert "has ended" in notice.title
    assert "unchanged" in notice.body

    (entry,) = await _deleted_entries(tenant_id, member_id)
    assert entry.actor_id == test_user_id
    assert entry.detail == "removed, role=orga"

    # The membership is gone, but the campaign seat is not - removal is not
    # a cascade into Player/CampaignGm rows.
    async with admin_session_factory() as session:
        assert await session.get(Membership, (tenant_id, member_id)) is None
        players = (
            (await session.execute(select(Player).where(Player.user_id == member_id)))
            .scalars()
            .all()
        )
        assert len(players) == 1

    await delete_tenant(tenant_id)
    await _delete_user(member_id)


async def test_leaving_a_tenant_also_notifies_and_is_recorded_as_left(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other_owner_id = await _make_user("other-owner")
    async with admin_session_factory() as session:
        session.add(
            Membership(tenant_id=tenant_id, user_id=other_owner_id, role=MembershipRole.OWNER)
        )
        await session.commit()

    response = await client.delete(f"/tenants/{tenant_id}/memberships/{test_user_id}")
    assert response.status_code == 204

    (notice,) = await _removal_notifications(tenant_id, test_user_id)
    assert notice.title.startswith("You left ")
    assert notice.created_by == test_user_id

    (entry,) = await _deleted_entries(tenant_id, test_user_id)
    assert entry.detail == "left, role=owner"

    await delete_tenant(tenant_id)
    await _delete_user(other_owner_id)


async def test_refused_removal_of_the_sole_owner_writes_no_notice_and_no_entry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.delete(f"/tenants/{tenant_id}/memberships/{test_user_id}")
    assert response.status_code == 409

    assert await _removal_notifications(tenant_id, test_user_id) == []
    assert await _deleted_entries(tenant_id, test_user_id) == []

    await delete_tenant(tenant_id)
