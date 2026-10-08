from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from e2e.helpers import SharedRepository, golden_repository
from e2e.stack import Stack, StackUnavailableError, running_stack


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """CI splits these tests over several runners, each with its own Postgres (ADR 0148): with
    TEST_SHARD=2/3 only the second of three groups of test files runs. Files go to the lightest
    group by test count, largest first, so the split is the same on every runner. (apps/api has
    the same hook.)"""
    shard = os.environ.get("TEST_SHARD")
    if not shard:
        return
    index, total = (int(part) for part in shard.split("/"))
    counts: dict[str, int] = {}
    for item in items:
        counts[str(item.path)] = counts.get(str(item.path), 0) + 1
    loads = [0] * total
    owner: dict[str, int] = {}
    for path in sorted(counts, key=lambda p: (-counts[p], p)):
        lightest = loads.index(min(loads))
        owner[path] = lightest
        loads[lightest] += counts[path]
    kept = [item for item in items if owner[str(item.path)] == index - 1]
    kept_ids = {id(item) for item in kept}
    config.hook.pytest_deselected(items=[item for item in items if id(item) not in kept_ids])
    items[:] = kept


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


@pytest.fixture(scope="session")
def shared_repository(stack: Stack) -> SharedRepository:
    """The golden repository (helpers.golden_repository): every seed layer, published. Here for the
    tests that only read it or plan against it, so each doesn't pay for its own seed (about 130
    requests). Built when the first test of the session asks, so a CI shard without one never
    makes it.

    The rules for a test that uses it:
    - Never write to it: no apply, seed, unseed, publish, rename, delete, copy or grant, not
      even a command that is expected to refuse (the grants that a copy of it
      needs are the one write it takes). A write left behind changes every other test.
    - Never assert on what is tenant-wide and another test could change, such as counts of
      every item; the seed's own entities and "nothing is imported yet" are fair to assert.
    - Keep files a command writes (review queue, proposed map) in the test's own `tmp_path`.
    - Use its token (`.token`), not the shared "creator": that subject already holds dozens
      of tenants, and `helpers.tenant_id` pages through all of them."""
    return golden_repository(stack)
