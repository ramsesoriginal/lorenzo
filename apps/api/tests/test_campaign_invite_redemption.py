"""The public invite-link routes - see ADR 0092. GET /invites/{token} is
unauthenticated; POST /invites/{token}/redeem needs a verified login but no
tenant membership. Exercised with genuine verified tokens (`raw_client`), and
with invites seeded straight into the database under a known token so these
tests don't depend on the management API.
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
from sqlalchemy import func, select

from lorenzo_api.invites import generate_token, hash_token
from lorenzo_api.models import (
    AuditLog,
    Campaign,
    CampaignGm,
    CampaignInvite,
    Membership,
    Notification,
    Player,
    User,
)
from lorenzo_api.rate_limit import reset_invite_rate_limiter


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> None:
    """Every test gets a full bucket: the limiter is process-wide, and
    these tests make more requests from one address than a minute allows.
    """
    reset_invite_rate_limiter()


class Setup:
    def __init__(self, tenant_id: uuid.UUID, campaign_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.campaign_id = campaign_id
        self.owner_id = owner_id
        self.subjects: list[str] = []


@pytest.fixture
async def setup(test_user_id: uuid.UUID) -> AsyncGenerator[Setup]:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Open Table")
        await session.commit()
        campaign_id = campaign.id
    state = Setup(tenant_id, campaign_id, test_user_id)
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


async def _seed_invite(
    setup: Setup,
    *,
    max_uses: int | None = None,
    expires_in: timedelta = timedelta(days=7),
    revoked: bool = False,
    use_count: int = 0,
) -> tuple[str, uuid.UUID]:
    token = generate_token()
    async with admin_session_factory() as session:
        invite = CampaignInvite(
            tenant_id=setup.tenant_id,
            campaign_id=setup.campaign_id,
            token_hash=hash_token(token),
            expires_at=datetime.now(tz=UTC) + expires_in,
            max_uses=max_uses,
            use_count=use_count,
            revoked_at=datetime.now(tz=UTC) if revoked else None,
        )
        session.add(invite)
        await session.commit()
        return token, invite.id


def _auth(setup: Setup, fake_jwks_server: FakeJwksServer) -> dict[str, str]:
    subject = f"authgear|invitee-{uuid.uuid4()}"
    setup.subjects.append(subject)
    return {"Authorization": f"Bearer {fake_jwks_server.issue_token(subject)}"}


async def _use_count(invite_id: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return (await session.get_one(CampaignInvite, invite_id)).use_count


async def _player_count(setup: Setup) -> int:
    async with admin_session_factory() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(Player)
                .where(Player.campaign_id == setup.campaign_id)
            )
        ).scalar_one()


async def test_preview_is_unauthenticated_and_shows_only_the_campaign(
    raw_client: AsyncClient, setup: Setup
) -> None:
    token, _ = await _seed_invite(setup)

    response = await raw_client.get(f"/invites/{token}")  # no Authorization header at all

    assert response.status_code == 200, response.text
    assert response.json() == {"campaign_name": "The Open Table", "picture_url": None}


async def test_every_dead_link_gets_the_identical_response(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    """Unknown, expired, revoked and exhausted must be indistinguishable
    (ADR 0092) - a different answer tells an attacker a token was once real.
    """
    expired, _ = await _seed_invite(setup, expires_in=timedelta(days=-1))
    revoked, _ = await _seed_invite(setup, revoked=True)
    exhausted, _ = await _seed_invite(setup, max_uses=2, use_count=2)
    tokens = [generate_token(), expired, revoked, exhausted]  # first is unknown outright
    headers = _auth(setup, fake_jwks_server)

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
    assert await _player_count(setup) == 0


async def test_redeem_gives_a_player_seat_records_it_and_tells_only_the_gms(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    token, invite_id = await _seed_invite(setup)
    headers = _auth(setup, fake_jwks_server)
    async with admin_session_factory() as session:
        gm_subject = f"authgear|gm-{uuid.uuid4()}"
        bystander_subject = f"authgear|bystander-{uuid.uuid4()}"
        setup.subjects += [gm_subject, bystander_subject]  # so the fixture deletes them
        gm = User(authgear_subject_id=gm_subject)
        bystander = User(authgear_subject_id=bystander_subject)
        session.add_all([gm, bystander])
        await session.flush()
        session.add(
            CampaignGm(user_id=gm.id, campaign_id=setup.campaign_id, tenant_id=setup.tenant_id)
        )
        session.add(
            Player(user_id=bystander.id, campaign_id=setup.campaign_id, tenant_id=setup.tenant_id)
        )
        await session.commit()
        gm_id, bystander_id = gm.id, bystander.id

    response = await raw_client.post(f"/invites/{token}/redeem", headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["already_joined"] is False
    assert body["campaign_id"] == str(setup.campaign_id)
    assert await _use_count(invite_id) == 1

    async with admin_session_factory() as session:
        player = (
            await session.execute(select(Player).where(Player.id == uuid.UUID(body["player_id"])))
        ).scalar_one()
        redeemer_id = player.user_id
        # The seat is a player seat and nothing more (ADR 0092): never GM,
        # never a tenant-wide membership.
        assert (
            await session.execute(select(CampaignGm).where(CampaignGm.user_id == redeemer_id))
        ).first() is None
        assert (
            await session.execute(select(Membership).where(Membership.user_id == redeemer_id))
        ).first() is None

        entry = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.tenant_id == setup.tenant_id,
                    AuditLog.action == "campaign_invite.redeemed",
                )
            )
        ).scalar_one()
        assert entry.actor_id == redeemer_id and entry.target_id == invite_id

        told = {
            n.user_id
            for n in (
                await session.execute(
                    select(Notification).where(Notification.type == "campaign_invite_redeemed")
                )
            ).scalars()
            if n.tenant_id == setup.tenant_id
        }
    assert told == {gm_id}
    assert bystander_id not in told


async def test_redeeming_twice_is_idempotent_and_spends_no_second_use(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    token, invite_id = await _seed_invite(setup, max_uses=5)
    headers = _auth(setup, fake_jwks_server)

    first = await raw_client.post(f"/invites/{token}/redeem", headers=headers)
    second = await raw_client.post(f"/invites/{token}/redeem", headers=headers)

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["already_joined"] is True
    assert second.json()["player_id"] == first.json()["player_id"]
    assert await _use_count(invite_id) == 1
    assert await _player_count(setup) == 1


async def test_an_unlimited_link_admits_everyone_and_still_counts_uses(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    token, invite_id = await _seed_invite(setup, max_uses=None)

    statuses = [
        (
            await raw_client.post(
                f"/invites/{token}/redeem", headers=_auth(setup, fake_jwks_server)
            )
        ).status_code
        for _ in range(4)
    ]

    assert statuses == [201, 201, 201, 201]
    assert await _use_count(invite_id) == 4


async def test_a_capped_link_stops_when_it_runs_out(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    token, _ = await _seed_invite(setup, max_uses=1)

    first = await raw_client.post(
        f"/invites/{token}/redeem", headers=_auth(setup, fake_jwks_server)
    )
    second = await raw_client.post(
        f"/invites/{token}/redeem", headers=_auth(setup, fake_jwks_server)
    )

    assert (first.status_code, second.status_code) == (201, 404)


async def test_concurrent_redemptions_never_exceed_max_uses(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    """Eight distinct users race for a three-use link. The spend is one
    atomic UPDATE ... WHERE still-live RETURNING, so exactly three win.
    """
    token, invite_id = await _seed_invite(setup, max_uses=3)
    all_headers = [_auth(setup, fake_jwks_server) for _ in range(8)]
    # Provision every user first, so the race below is about the invite and
    # not about first-login upserts.
    for headers in all_headers:
        assert (await raw_client.get("/me", headers=headers)).status_code == 200

    responses = await asyncio.gather(
        *(raw_client.post(f"/invites/{token}/redeem", headers=h) for h in all_headers)
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [201, 201, 201, 404, 404, 404, 404, 404]
    assert await _use_count(invite_id) == 3
    assert await _player_count(setup) == 3


async def test_a_revoked_or_expired_link_cannot_be_redeemed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    revoked, _ = await _seed_invite(setup, revoked=True)
    expired, _ = await _seed_invite(setup, expires_in=timedelta(seconds=-1))

    for token in (revoked, expired):
        response = await raw_client.post(
            f"/invites/{token}/redeem", headers=_auth(setup, fake_jwks_server)
        )
        assert response.status_code == 404
    assert await _player_count(setup) == 0


async def test_redeeming_requires_a_login(raw_client: AsyncClient, setup: Setup) -> None:
    token, invite_id = await _seed_invite(setup)

    response = await raw_client.post(f"/invites/{token}/redeem")  # no Authorization header

    assert response.status_code in (401, 403)
    assert await _use_count(invite_id) == 0


async def test_a_suspended_account_cannot_redeem(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, setup: Setup
) -> None:
    token, invite_id = await _seed_invite(setup)
    headers = _auth(setup, fake_jwks_server)
    assert (await raw_client.get("/me", headers=headers)).status_code == 200
    subject = setup.subjects[-1]
    async with admin_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.authgear_subject_id == subject))
        ).scalar_one()
        user.suspended_at = datetime.now(tz=UTC)
        await session.commit()

    response = await raw_client.post(f"/invites/{token}/redeem", headers=headers)

    assert response.status_code == 403
    assert await _use_count(invite_id) == 0
    assert await _player_count(setup) == 0


async def test_a_deleted_campaign_takes_its_invites_with_it(
    raw_client: AsyncClient, setup: Setup
) -> None:
    token, invite_id = await _seed_invite(setup)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Campaign, setup.campaign_id))
        await session.commit()

    assert (await raw_client.get(f"/invites/{token}")).status_code == 404
    async with admin_session_factory() as session:
        assert await session.get(CampaignInvite, invite_id) is None
