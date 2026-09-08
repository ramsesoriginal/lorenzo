import subprocess
import sys
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from lorenzo_api.main import app


@pytest.fixture(scope="session", autouse=True)
def _migrate_database() -> None:
    """Applies all migrations (currently just ADR 0012's entity table)
    against the test database before any test runs.
    """
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
