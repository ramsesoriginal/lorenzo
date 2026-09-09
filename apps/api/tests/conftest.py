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

from lorenzo_api.dependencies import SessionDep, get_current_user, get_jwks_client
from lorenzo_api.main import app
from lorenzo_api.models import User


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
