import subprocess
import sys
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from lorenzo_api.main import app


@pytest.fixture(scope="session", autouse=True)
def _migrate_database() -> None:
    """Applies all migrations (currently ADR 0013's tenant bootstrap, ADR
    0012's entity table, ADR 0014's stat tables, ADR 0015's entity_prototype
    table, and ADR 0016's containment table) against the test database
    before any test runs.
    """
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
