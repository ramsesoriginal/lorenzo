"""Notifications: platform/tenant/campaign/character scope, in-app inbox.
See ADR 0054.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_player, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import CharacterPlayer, Notification, Player, Tenant, User


async def test_create_tenant_notification_single_recipient(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        recipient = User(authgear_subject_id=f"authgear|recipient-{uuid.uuid4()}")
        session.add(recipient)
        await session.commit()
        recipient_id = recipient.id

    response = await client.post(
        f"/tenants/{tenant_id}/notifications",
        json={
            "recipient_user_id": str(recipient_id),
            "type": "announcement",
            "title": "Hi",
            "body": "Hello",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body) == 1
    assert body[0]["scope"] == "tenant"
    assert body[0]["tenant_id"] == str(tenant_id)

    async with admin_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Notification).where(Notification.user_id == recipient_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        await session.delete(await session.get_one(User, recipient_id))
        await session.commit()

    await delete_tenant(tenant_id)


async def test_create_tenant_notification_broadcasts_to_full_roster(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        await session.commit()
        player_user_id = player.user_id

    response = await client.post(
        f"/tenants/{tenant_id}/notifications",
        json={"type": "announcement", "title": "Everyone", "body": "News"},
    )
    assert response.status_code == 201
    recipient_ids = {n["id"] for n in response.json()}
    assert len(recipient_ids) == 2  # test_user_id (OWNER) + the player

    async with admin_session_factory() as session:
        for uid in (test_user_id, player_user_id):
            rows = (
                (await session.execute(select(Notification).where(Notification.user_id == uid)))
                .scalars()
                .all()
            )
            assert len(rows) == 1
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()

    await delete_tenant(tenant_id)


async def test_create_tenant_notification_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.post(
        f"/tenants/{tenant_id}/notifications",
        json={"type": "x", "title": "x", "body": "x"},
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_create_membership_also_creates_an_invite_notification(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        invitee = User(authgear_subject_id=f"authgear|invitee-{uuid.uuid4()}")
        session.add(invitee)
        await session.commit()
        invitee_id = invitee.id

    response = await client.post(
        f"/tenants/{tenant_id}/memberships", json={"user_id": str(invitee_id), "role": "orga"}
    )
    assert response.status_code == 201

    async with admin_session_factory() as session:
        rows = (
            (await session.execute(select(Notification).where(Notification.user_id == invitee_id)))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].scope == "tenant"
        assert rows[0].type == "tenant_invite"
        await session.delete(await session.get_one(User, invitee_id))
        await session.commit()

    await delete_tenant(tenant_id)


async def test_create_campaign_notification_broadcasts_to_players_and_gms(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        campaign_id = campaign.id
        await session.commit()
        player_user_id = player.user_id

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/notifications",
        json={"type": "session_reminder", "title": "Session Saturday", "body": "3pm"},
    )
    assert response.status_code == 201
    assert (
        len(response.json()) == 1
    )  # only the player - test_user_id is OWNER, not a Player/GM here
    assert response.json()[0]["scope"] == "campaign"
    assert response.json()[0]["source_id"] == str(campaign_id)

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()
    await delete_tenant(tenant_id)


async def test_create_campaign_notification_403_for_a_plain_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/notifications",
        json={"type": "x", "title": "x", "body": "x"},
    )
    assert response.status_code == 403

    await delete_tenant(tenant_id)


async def test_create_character_notification_broadcasts_to_controlling_players(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
        session.add(
            CharacterPlayer(
                character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        character_id, player_user_id = character.entity_id, player.user_id

    response = await client.post(
        f"/tenants/{tenant_id}/characters/{character_id}/notifications",
        json={
            "type": "research_complete",
            "title": "Research done",
            "body": "The tome is decoded.",
        },
    )
    assert response.status_code == 201
    assert len(response.json()) == 1
    assert response.json()[0]["scope"] == "character"
    assert response.json()[0]["source_id"] == str(character_id)

    async with admin_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(Notification).where(Notification.user_id == player_user_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()
    await delete_tenant(tenant_id)


async def test_create_platform_notification_requires_a_recipient(
    client_with_platform_operator_role: AsyncClient,
) -> None:
    response = await client_with_platform_operator_role.post(
        "/admin/notifications", json={"type": "x", "title": "x", "body": "x"}
    )
    assert response.status_code == 422


async def test_create_platform_notification_single_recipient(
    client_with_platform_operator_role: AsyncClient,
) -> None:
    async with admin_session_factory() as session:
        recipient = User(authgear_subject_id=f"authgear|platform-recipient-{uuid.uuid4()}")
        session.add(recipient)
        await session.commit()
        recipient_id = recipient.id

    response = await client_with_platform_operator_role.post(
        "/admin/notifications",
        json={
            "recipient_user_id": str(recipient_id),
            "type": "system",
            "title": "Welcome",
            "body": "Hi there",
        },
    )
    assert response.status_code == 201
    assert response.json()["scope"] == "platform"
    assert response.json()["tenant_id"] is None

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, recipient_id))
        await session.commit()


async def test_list_my_notifications_across_multiple_tenants(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The actual proof of the RLS design (ADR 0054): one call, no
    explicit tenant context, returns notifications from every tenant.
    """
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)

    await client.post(
        f"/tenants/{tenant_a}/notifications", json={"type": "a", "title": "A", "body": "a"}
    )
    await client.post(
        f"/tenants/{tenant_b}/notifications", json={"type": "b", "title": "B", "body": "b"}
    )

    response = await client.get("/me/notifications")
    assert response.status_code == 200
    tenant_ids = {item["tenant_id"] for item in response.json()["items"]}
    assert {str(tenant_a), str(tenant_b)} <= tenant_ids

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_list_my_notifications_unread_only_filter(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    create_response = await client.post(
        f"/tenants/{tenant_id}/notifications", json={"type": "x", "title": "x", "body": "x"}
    )
    notification_id = create_response.json()[0]["id"]

    await client.post(f"/me/notifications/{notification_id}/read")

    unread_response = await client.get("/me/notifications", params={"unread_only": "true"})
    assert notification_id not in {i["id"] for i in unread_response.json()["items"]}

    all_response = await client.get("/me/notifications", params={"unread_only": "false"})
    assert notification_id in {i["id"] for i in all_response.json()["items"]}

    await delete_tenant(tenant_id)


async def test_mark_notification_read_is_idempotent(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    create_response = await client.post(
        f"/tenants/{tenant_id}/notifications", json={"type": "x", "title": "x", "body": "x"}
    )
    notification_id = create_response.json()[0]["id"]

    first = await client.post(f"/me/notifications/{notification_id}/read")
    assert first.status_code == 200
    read_at_first = first.json()["read_at"]
    assert read_at_first is not None

    second = await client.post(f"/me/notifications/{notification_id}/read")
    assert second.status_code == 200
    assert second.json()["read_at"] == read_at_first

    await delete_tenant(tenant_id)


async def test_mark_notification_read_404_for_someone_elses_notification(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        other = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other)
        await session.flush()
        notification = Notification(
            user_id=other.id,
            tenant_id=tenant_id,
            scope="tenant",
            source_id=None,
            type="x",
            title="x",
            body="x",
        )
        session.add(notification)
        await session.commit()
        notification_id, other_id = notification.id, other.id

    response = await client.post(f"/me/notifications/{notification_id}/read")
    assert response.status_code == 404

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_id))
        await session.commit()
    await delete_tenant(tenant_id)
