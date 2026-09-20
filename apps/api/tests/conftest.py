import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from jwt import PyJWKClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.dependencies import (
    SessionDep,
    get_current_user,
    get_jwks_client,
    get_userinfo_url,
)
from lorenzo_api.main import app
from lorenzo_api.models import (
    Being,
    Campaign,
    Character,
    Entity,
    Membership,
    MembershipRole,
    Player,
    Tenant,
    TenantAdminCampaignOptOut,
    User,
)


@pytest.fixture(scope="session", autouse=True)
def _migrate_database() -> None:
    """Applies every migration to date (see migrations/versions/ and the
    corresponding ADRs) against the test database before any test runs.
    """
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


@pytest.fixture(scope="session", autouse=True)
async def _app_lifespan() -> AsyncGenerator[None]:
    """Actually runs main.py's lifespan (startup/shutdown) once for the whole
    session - a bare ASGITransport(app=app) (used by client/raw_client below)
    never triggers it on its own (confirmed via FastAPI's own docs), so this
    is what stands between shutdown-only logic (engine.dispose()) and
    silently never being exercised by the test suite.
    """
    async with LifespanManager(app):
        yield


@pytest.fixture(scope="session")
def fake_jwks_server() -> Generator[FakeJwksServer]:
    """A real local JWKS endpoint for real_client's token-verification
    tests (ADR 0023) - see tests/_fake_jwks.py.
    """
    server = FakeJwksServer()
    yield server
    server.shutdown()


@pytest.fixture(scope="session")
async def test_user_id() -> AsyncGenerator[uuid.UUID]:
    """One real, persistent app_user row shared by the whole test session -
    what `client`'s get_current_user override resolves to. Tests that need
    it to actually access a tenant add their own Membership row linking
    this same id, rather than each needing a real signed token for a
    concern (auth itself) they aren't testing - see ADR 0023.
    """
    async with admin_session_factory() as session:
        user = User(authgear_subject_id="conftest-fixture-user")
        session.add(user)
        await session.commit()
        user_id = user.id
    yield user_id
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def make_tenant(user_id: uuid.UUID) -> uuid.UUID:
    """A tenant with a single OWNER Membership for user_id - the shape
    almost every REST-layer test needs. Promoted here after the identical
    ~10 lines were independently duplicated in test_api_items.py,
    test_api_item_instances.py, and test_api_payloads.py - a plain helper
    function, not a fixture, since tests routinely need two (tenant_a/
    tenant_b) and tear one down mid-test rather than only at test end.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()
        return tenant.id


async def delete_tenant(tenant_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def make_campaign(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str = "Campaign",
    game_system: str = "D&D 5e",
) -> Campaign:
    """A campaign with its required dedicated Entity already attached (ADR
    0030) and a valid random slug/description - promoted here since every
    existing Campaign(...) fixture call needed both the moment slug/
    description stopped being optional, the same trigger make_player was
    promoted for. Not a pytest fixture, matching make_player - some tests
    need more than one campaign per tenant.
    """
    entity = Entity(tenant_id=tenant_id, name=name)
    session.add(entity)
    await session.flush()
    campaign = Campaign(
        tenant_id=tenant_id,
        name=name,
        game_system=game_system,
        slug=f"campaign-{uuid.uuid4()}",
        description="",
        entity_id=entity.id,
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def make_player(
    session: AsyncSession, *, tenant_id: uuid.UUID, campaign_id: uuid.UUID
) -> Player:
    """A fresh User + Player for one campaign. Promoted here after the same
    helper was independently duplicated (save for an irrelevant debug-prefix
    string) in test_knowledge.py and test_being_character_ownership.py.
    Creates its own User rather than reusing test_user_id, so the caller
    is responsible for deleting it too once done - matching both original
    call sites' own existing cleanup.
    """
    user = User(authgear_subject_id=f"authgear|test-player-{uuid.uuid4()}")
    session.add(user)
    await session.flush()
    player = Player(user_id=user.id, campaign_id=campaign_id, tenant_id=tenant_id)
    session.add(player)
    await session.flush()
    return player


async def make_being(session: AsyncSession, *, tenant_id: uuid.UUID, name: str = "Being") -> Being:
    """A bare sentient entity, no Character row - an NPC/monster stub not worth
    individual tracking (ADR 0031).
    """
    entity = Entity(tenant_id=tenant_id, name=name)
    session.add(entity)
    await session.flush()
    being = Being(entity_id=entity.id, tenant_id=tenant_id)
    session.add(being)
    await session.flush()
    return being


async def make_character(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str = "Character",
    owner_player_id: uuid.UUID | None = None,
) -> Character:
    """A tracked character - a being, promoted (ADR 0031/RFC 0004)."""
    being = await make_being(session, tenant_id=tenant_id, name=name)
    character = Character(
        entity_id=being.entity_id, tenant_id=tenant_id, owner_player_id=owner_player_id
    )
    session.add(character)
    await session.flush()
    return character


async def make_plain_participant(tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Makes user_id a plain participant of tenant_id: no tenant-wide
    Membership (so no administrative bypass of any kind, ADR 0091), but a
    Player seat in a fresh campaign so tenant reads still admit them. What
    the "hides GM-only information from a plain member" tests actually need
    - they originally used an OWNER Membership as the stand-in, which was
    only "plain" while OWNER had no information bypass.
    """
    async with admin_session_factory() as session:
        membership = await session.get(Membership, (tenant_id, user_id))
        if membership is not None:
            await session.delete(membership)
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Plain Participant")
        session.add(Player(user_id=user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()


async def make_opted_out_admin(tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Keeps user_id's tenant-wide Membership but gives them a campaign
    admin opt-out, which suppresses the information bypass tenant-wide (ADR
    0034/0091). For the routes that require a Membership (the item catalog,
    payload content) and so can't be reached by a plain participant: since
    every MembershipRole is administrative, an opted-out administrator is
    the only caller there who does not get the bypass - and it exercises
    the same filtering code a "plain member" originally did.
    """
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Opted Out")
        session.add(
            TenantAdminCampaignOptOut(tenant_id=tenant_id, user_id=user_id, campaign_id=campaign.id)
        )
        await session.commit()


def _make_fake_current_user(
    test_user_id: uuid.UUID, *, authgear_roles: frozenset[str]
) -> Callable[[SessionDep], Awaitable[User]]:
    """Builds the get_current_user override both `client` fixtures below
    install - parameterized on authgear_roles (ADR 0033/RFC 0012) so the
    tenant-creation negative-case test can get one with an empty set
    without duplicating the rest of this function.
    """

    async def _fake_current_user(session: SessionDep) -> User:
        # Mirrors the real get_current_user's own set_config call -
        # membership's RLS policy needs app.user_id set to allow the
        # self-access read get_tenant_context's own membership check does,
        # or that lookup can't see even a genuinely-existing row (ADR 0023).
        await session.execute(
            text("SELECT set_config('app.user_id', :u, true)"), {"u": str(test_user_id)}
        )
        user = User(id=test_user_id, authgear_subject_id="conftest-fixture-user")
        # Not a mapped column - see models.User's own docstring on it.
        user.authgear_roles = authgear_roles
        return user

    return _fake_current_user


@pytest.fixture
async def client(test_user_id: uuid.UUID) -> AsyncGenerator[AsyncClient]:
    """get_current_user is overridden to a fixed test user - real token
    verification is its own concern, tested directly in test_auth.py via
    `raw_client` instead. Every other test uses this fixture.

    authgear_roles defaults to including "tenant_creator" (ADR 0033/RFC
    0012 - underscore, not hyphen, per that ADR's addendum) so tests
    unrelated to that role aren't newly blocked from POST /tenants - the
    specific negative-case test for its 403 uses
    `client_without_tenant_creator_role` below instead.
    """
    app.dependency_overrides[get_current_user] = _make_fake_current_user(
        test_user_id, authgear_roles=frozenset({"tenant_creator"})
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    del app.dependency_overrides[get_current_user]


@pytest.fixture
async def client_without_tenant_creator_role(
    test_user_id: uuid.UUID,
) -> AsyncGenerator[AsyncClient]:
    """Same as `client`, but with an empty authgear_roles - ADR 0033/RFC
    0012's own negative case for POST /tenants' 403.
    """
    app.dependency_overrides[get_current_user] = _make_fake_current_user(
        test_user_id, authgear_roles=frozenset()
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    del app.dependency_overrides[get_current_user]


@pytest.fixture
async def client_with_platform_operator_role(
    test_user_id: uuid.UUID,
) -> AsyncGenerator[AsyncClient]:
    """Same as `client`, plus the platform-operator role (ADR 0057) - for
    /admin/* routes' positive case. Keeps tenant-creator too, so a test
    combining both concerns doesn't need a third fixture.
    """
    app.dependency_overrides[get_current_user] = _make_fake_current_user(
        test_user_id, authgear_roles=frozenset({"tenant-creator", "platform-operator"})
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    del app.dependency_overrides[get_current_user]


@pytest.fixture
async def raw_client(fake_jwks_server: FakeJwksServer) -> AsyncGenerator[AsyncClient]:
    """Like `client`, but with real token verification (no get_current_user
    override) - get_jwks_client and get_userinfo_url are both swapped to
    point at the same fake server instead of a real Authgear instance (ADR
    0023/0075). For tests that specifically need to exercise the real
    pipeline end to end - see test_auth.py. Every other test uses `client`
    instead.
    """
    app.dependency_overrides[get_jwks_client] = lambda: PyJWKClient(fake_jwks_server.jwks_url)
    app.dependency_overrides[get_userinfo_url] = lambda: fake_jwks_server.userinfo_url
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    del app.dependency_overrides[get_jwks_client]
    del app.dependency_overrides[get_userinfo_url]
