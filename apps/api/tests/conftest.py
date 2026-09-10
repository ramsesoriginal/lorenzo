import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from jwt import PyJWKClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.dependencies import SessionDep, get_current_user, get_jwks_client
from lorenzo_api.main import app
from lorenzo_api.models import Campaign, Entity, Membership, MembershipRole, Player, Tenant, User


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


@pytest.fixture
async def client(test_user_id: uuid.UUID) -> AsyncGenerator[AsyncClient]:
    """get_current_user is overridden to a fixed test user - real token
    verification is its own concern, tested directly in test_auth.py via
    `raw_client` instead. Every other test uses this fixture.
    """

    async def _fake_current_user(session: SessionDep) -> User:
        # Mirrors the real get_current_user's own set_config call -
        # membership's RLS policy needs app.user_id set to allow the
        # self-access read get_tenant_context's own membership check does,
        # or that lookup can't see even a genuinely-existing row (ADR 0023).
        await session.execute(
            text("SELECT set_config('app.user_id', :u, true)"), {"u": str(test_user_id)}
        )
        return User(id=test_user_id, authgear_subject_id="conftest-fixture-user")

    app.dependency_overrides[get_current_user] = _fake_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    del app.dependency_overrides[get_current_user]


@pytest.fixture
async def raw_client(fake_jwks_server: FakeJwksServer) -> AsyncGenerator[AsyncClient]:
    """Like `client`, but with real token verification (no get_current_user
    override) - only get_jwks_client is swapped, to point at the real
    fake-JWKS server instead of a real Authgear instance. For tests that
    specifically need to exercise the real pipeline end to end - see
    test_auth.py. Every other test uses `client` instead.
    """
    app.dependency_overrides[get_jwks_client] = lambda: PyJWKClient(fake_jwks_server.jwks_url)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    del app.dependency_overrides[get_jwks_client]
