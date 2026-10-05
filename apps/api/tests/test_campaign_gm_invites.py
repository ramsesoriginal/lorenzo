"""A GM invite link - see ADR 0177, which amends ADR 0092's "never GM" for one narrow kind of link.

Single use, at most 7 days, minted by whoever may grant GM directly; redeeming one makes a GM, not
a player and not a tenant member. Creation goes through the management API as the tenant's owner;
redemption through the public routes, with genuine verified tokens and invites seeded under a known
token, as `test_campaign_invite_redemption.py` does.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.invites import generate_token, hash_token
from lorenzo_api.models import (
    AuditLog,
    CampaignGm,
    CampaignInvite,
    InviteRole,
    Membership,
    Notification,
    Player,
    Tenant,
    User,
)
from lorenzo_api.rate_limit import reset_invite_rate_limiter


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> None:
    reset_invite_rate_limiter()


def _in(**delta: int) -> str:
    return (datetime.now(tz=UTC) + timedelta(**delta)).isoformat()


# --- Creating a GM link (the management API) -----------------------------------------------


async def _campaign(client: AsyncClient, tenant_id: uuid.UUID) -> uuid.UUID:
    response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "Hand-over",
            "game_system": "D&D 5e",
            "slug": f"hand-over-{uuid.uuid4()}",
            "description": "",
        },
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


async def test_a_gm_link_is_created_single_use_and_says_its_role(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    for body in (
        {"expires_at": _in(days=3), "role": "gm"},
        {"expires_at": _in(days=3), "role": "gm", "max_uses": 1},
    ):
        response = await client.post(base, json=body)
        assert response.status_code == 201, response.text
        created = response.json()
        assert created["role"] == "gm"
        assert created["max_uses"] == 1  # stored as single use, however it was asked for
        assert created["token"]

    listed = (await client.get(base)).json()["items"]
    assert {item["role"] for item in listed} == {"gm"}
    assert "token" not in listed[0]

    await delete_tenant(tenant_id)


async def test_a_link_without_a_role_is_a_player_link_as_before(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    created = (await client.post(base, json={"expires_at": _in(days=29), "max_uses": 5})).json()

    assert created["role"] == "player"
    assert created["max_uses"] == 5
    await delete_tenant(tenant_id)


async def test_a_gm_link_refuses_more_than_one_use(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    refused = await client.post(base, json={"expires_at": _in(days=1), "role": "gm", "max_uses": 5})

    assert refused.status_code == 422
    await delete_tenant(tenant_id)


async def test_a_gm_link_lives_at_most_seven_days(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    too_long = await client.post(base, json={"expires_at": _in(days=8), "role": "gm"})
    assert too_long.status_code == 422
    assert "7 days" in too_long.json()["detail"]
    in_the_past = await client.post(base, json={"expires_at": _in(days=-1), "role": "gm"})
    assert in_the_past.status_code == 422
    assert (
        await client.post(base, json={"expires_at": _in(days=6, hours=23), "role": "gm"})
    ).status_code == 201
    # A player link keeps its 30 days.
    assert (await client.post(base, json={"expires_at": _in(days=29)})).status_code == 201

    await delete_tenant(tenant_id)


async def test_only_who_may_grant_gm_may_mint_a_gm_link(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A player of the campaign can see it but not manage it, so not mint a GM link either:
    403, as for any link. Someone with no standing in it gets the 404 that hides it exists."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        as_player = await make_campaign(session, tenant_id=tenant_id, name="Player Here")
        unrelated = await make_campaign(session, tenant_id=tenant_id, name="No Standing")
        session.add(Player(user_id=test_user_id, campaign_id=as_player.id, tenant_id=tenant_id))
        await session.commit()
        player_campaign_id, unrelated_campaign_id = as_player.id, unrelated.id

    body = {"expires_at": _in(days=1), "role": "gm"}
    as_a_player = await client.post(
        f"/tenants/{tenant_id}/campaigns/{player_campaign_id}/invites", json=body
    )
    as_a_stranger = await client.post(
        f"/tenants/{tenant_id}/campaigns/{unrelated_campaign_id}/invites", json=body
    )

    assert as_a_player.status_code == 403
    assert as_a_stranger.status_code == 404
    await delete_tenant(tenant_id)


async def test_creating_a_gm_link_is_logged_with_its_role_and_never_the_token(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _campaign(client, tenant_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}/invites"

    created = (await client.post(base, json={"expires_at": _in(days=2), "role": "gm"})).json()
    player = (await client.post(base, json={"expires_at": _in(days=2)})).json()

    async with admin_session_factory() as session:
        entries = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.tenant_id == tenant_id,
                        AuditLog.action == "campaign_invite.created",
                    )
                )
            )
            .scalars()
            .all()
        )
    by_target = {entry.target_id: entry.detail or "" for entry in entries}
    assert "role=gm" in by_target[uuid.UUID(created["id"])]
    assert "max_uses=1" in by_target[uuid.UUID(created["id"])]
    # A player link's entry reads as it always did.
    assert "role=" not in by_target[uuid.UUID(player["id"])]
    assert created["token"] not in "".join(by_target.values())
    await delete_tenant(tenant_id)


# --- Redeeming one (the public routes) -------------------------------------------------------


class Table:
    def __init__(self, tenant_id: uuid.UUID, campaign_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.campaign_id = campaign_id
        self.owner_id = owner_id
        self.subjects: list[str] = []


@pytest.fixture
async def table(test_user_id: uuid.UUID) -> AsyncGenerator[Table]:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Hand-over")
        await session.commit()
        campaign_id = campaign.id
    state = Table(tenant_id, campaign_id, test_user_id)
    yield state
    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        for subject in state.subjects:
            user = (
                await session.execute(select(User).where(User.authgear_subject_id == subject))
            ).scalar_one_or_none()
            if user is not None:
                await session.delete(user)
        await session.commit()


async def _seed_gm_link(
    table: Table,
    *,
    expires_in: timedelta = timedelta(days=3),
    use_count: int = 0,
    revoked: bool = False,
) -> tuple[str, uuid.UUID]:
    token = generate_token()
    async with admin_session_factory() as session:
        invite = CampaignInvite(
            tenant_id=table.tenant_id,
            campaign_id=table.campaign_id,
            token_hash=hash_token(token),
            role=InviteRole.GM,
            created_by=table.owner_id,
            expires_at=datetime.now(tz=UTC) + expires_in,
            max_uses=1,
            use_count=use_count,
            revoked_at=datetime.now(tz=UTC) if revoked else None,
        )
        session.add(invite)
        await session.commit()
        return token, invite.id


def _auth(table: Table, fake_jwks_server: FakeJwksServer, subject: str | None = None) -> dict:
    subject = subject or f"authgear|new-gm-{uuid.uuid4()}"
    table.subjects.append(subject)
    return {"Authorization": f"Bearer {fake_jwks_server.issue_token(subject)}"}


async def _add_user(table: Table, label: str) -> tuple[uuid.UUID, str]:
    subject = f"authgear|{label}-{uuid.uuid4()}"
    table.subjects.append(subject)
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=subject)
        session.add(user)
        await session.commit()
        return user.id, subject


async def _gm_user_ids(table: Table) -> set[uuid.UUID]:
    async with admin_session_factory() as session:
        return set(
            (
                await session.execute(
                    select(CampaignGm.user_id).where(CampaignGm.campaign_id == table.campaign_id)
                )
            ).scalars()
        )


async def _use_count(invite_id: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return (await session.get_one(CampaignInvite, invite_id)).use_count


async def test_the_preview_says_a_gm_link_is_one(raw_client: AsyncClient, table: Table) -> None:
    token, _ = await _seed_gm_link(table)

    response = await raw_client.get(f"/invites/{token}")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "campaign_name": "The Hand-over",
        "picture_url": None,
        "role": "gm",
    }


async def test_redeeming_a_gm_link_makes_a_gm_and_nothing_else(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, table: Table
) -> None:
    token, invite_id = await _seed_gm_link(table)
    headers = _auth(table, fake_jwks_server)

    response = await raw_client.post(f"/invites/{token}/redeem", headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "gm"
    assert body["player_id"] is None
    assert body["already_joined"] is False
    assert body["campaign_id"] == str(table.campaign_id)
    assert await _use_count(invite_id) == 1

    async with admin_session_factory() as session:
        gm = (
            await session.execute(
                select(CampaignGm).where(
                    CampaignGm.campaign_id == table.campaign_id,
                    CampaignGm.user_id != table.owner_id,
                )
            )
        ).scalar_one()
        # Attributed to whoever made the link, as PUT .../gms/{user} attributes to its granter.
        assert gm.created_by == table.owner_id
        assert (
            await session.execute(select(Player).where(Player.user_id == gm.user_id))
        ).first() is None
        assert (
            await session.execute(select(Membership).where(Membership.user_id == gm.user_id))
        ).first() is None


async def test_a_gm_link_is_single_use(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, table: Table
) -> None:
    token, _ = await _seed_gm_link(table)

    first = await raw_client.post(
        f"/invites/{token}/redeem", headers=_auth(table, fake_jwks_server)
    )
    second = await raw_client.post(
        f"/invites/{token}/redeem", headers=_auth(table, fake_jwks_server)
    )
    preview = await raw_client.get(f"/invites/{token}")

    assert first.status_code == 201
    assert second.status_code == preview.status_code == 404
    assert len(await _gm_user_ids(table)) == 1


async def test_two_people_racing_for_one_gm_link_get_one_seat(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, table: Table
) -> None:
    token, invite_id = await _seed_gm_link(table)

    responses = await asyncio.gather(
        raw_client.post(f"/invites/{token}/redeem", headers=_auth(table, fake_jwks_server)),
        raw_client.post(f"/invites/{token}/redeem", headers=_auth(table, fake_jwks_server)),
    )

    assert sorted(r.status_code for r in responses) == [201, 404]
    assert await _use_count(invite_id) == 1
    assert len(await _gm_user_ids(table)) == 1


async def test_someone_who_already_gms_gets_200_and_spends_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, table: Table
) -> None:
    token, invite_id = await _seed_gm_link(table)
    user_id, subject = await _add_user(table, "already-gm")
    async with admin_session_factory() as session:
        session.add(
            CampaignGm(user_id=user_id, campaign_id=table.campaign_id, tenant_id=table.tenant_id)
        )
        await session.commit()

    response = await raw_client.post(
        f"/invites/{token}/redeem", headers=_auth(table, fake_jwks_server, subject)
    )

    assert response.status_code == 200, response.text
    assert response.json()["already_joined"] is True
    assert response.json()["role"] == "gm"
    assert response.json()["player_id"] is None
    assert await _use_count(invite_id) == 0
    # ...and the link is still good for the person it was meant for.
    assert (await raw_client.get(f"/invites/{token}")).status_code == 200


async def test_a_player_who_redeems_a_gm_link_is_a_gm_too_and_keeps_their_seat(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, table: Table
) -> None:
    token, _ = await _seed_gm_link(table)
    user_id, subject = await _add_user(table, "player-turned-gm")
    async with admin_session_factory() as session:
        session.add(
            Player(user_id=user_id, campaign_id=table.campaign_id, tenant_id=table.tenant_id)
        )
        await session.commit()

    response = await raw_client.post(
        f"/invites/{token}/redeem", headers=_auth(table, fake_jwks_server, subject)
    )

    assert response.status_code == 201, response.text
    assert user_id in await _gm_user_ids(table)
    async with admin_session_factory() as session:
        assert (
            await session.execute(select(Player).where(Player.user_id == user_id))
        ).scalar_one_or_none() is not None


async def test_redeeming_a_gm_link_is_logged_and_tells_the_other_gms_only(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, table: Table
) -> None:
    token, invite_id = await _seed_gm_link(table)
    co_gm_id, _ = await _add_user(table, "co-gm")
    player_id, _ = await _add_user(table, "bystander")
    async with admin_session_factory() as session:
        session.add(
            CampaignGm(user_id=co_gm_id, campaign_id=table.campaign_id, tenant_id=table.tenant_id)
        )
        session.add(
            Player(user_id=player_id, campaign_id=table.campaign_id, tenant_id=table.tenant_id)
        )
        await session.commit()

    response = await raw_client.post(
        f"/invites/{token}/redeem", headers=_auth(table, fake_jwks_server)
    )

    assert response.status_code == 201, response.text
    async with admin_session_factory() as session:
        entry = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.tenant_id == table.tenant_id,
                    AuditLog.action == "campaign_invite.redeemed",
                    AuditLog.target_id == invite_id,
                )
            )
        ).scalar_one()
        assert "role=gm" in (entry.detail or "")
        redeemer = entry.actor_id

        told = {
            n.user_id
            for n in (
                await session.execute(
                    select(Notification).where(
                        Notification.tenant_id == table.tenant_id,
                        Notification.type == "campaign_invite_gm_redeemed",
                    )
                )
            ).scalars()
        }
    assert told == {co_gm_id}  # not the player, and not the one who just joined
    assert redeemer not in told


async def test_a_dead_gm_link_is_indistinguishable_from_any_other_dead_link(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, table: Table
) -> None:
    expired, _ = await _seed_gm_link(table, expires_in=timedelta(days=-1))
    revoked, _ = await _seed_gm_link(table, revoked=True)
    spent, _ = await _seed_gm_link(table, use_count=1)
    tokens = [generate_token(), expired, revoked, spent]  # the first is unknown outright
    headers = _auth(table, fake_jwks_server)

    def normalized(response: object) -> tuple[int, dict[str, object]]:
        body = dict(response.json())  # type: ignore[attr-defined]
        body.pop("instance", None)  # echoes the request path, which differs by token
        return response.status_code, body  # type: ignore[attr-defined]

    previews = [normalized(await raw_client.get(f"/invites/{t}")) for t in tokens]
    redeems = [
        normalized(await raw_client.post(f"/invites/{t}/redeem", headers=headers)) for t in tokens
    ]

    assert previews[0][0] == redeems[0][0] == 404
    assert len({repr(p) for p in previews}) == 1
    assert len({repr(r) for r in redeems}) == 1
    assert await _gm_user_ids(table) == set()
