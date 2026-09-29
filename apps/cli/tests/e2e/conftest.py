from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from e2e.stack import Stack, StackUnavailableError, running_stack


@pytest.fixture(scope="session")
def stack() -> Iterator[Stack]:
    """The real API on a fresh database for the whole session. Skips if Postgres isn't there,
    unless LORENZO_REQUIRE_E2E is set (CI), where a missing stack is a failure."""
    try:
        with running_stack() as running:
            yield running
    except StackUnavailableError as exc:
        if os.environ.get("LORENZO_REQUIRE_E2E"):
            pytest.fail(f"The end-to-end stack is required but unavailable: {exc}")
        pytest.skip(
            f"No end-to-end stack: {exc}. `docker compose -f infra/docker-compose.yml up -d`"
        )
