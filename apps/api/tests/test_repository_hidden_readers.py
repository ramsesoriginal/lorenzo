"""ADR 0435: every read a library has leaves a hidden entry out, whoever asks.

The sweep asks every `GET` route under `/tenants/{tenant_id}` of a library that hides the entries
of A, once as itself, once with each id in the path being a hidden entry and once with each being
the visible one that inherits from it, as the library's Owner (an administrator, who is let past
every other gate). A route that answers must name no hidden entry: not its name and not its id.
Reads that need more than ids (a body, a query) answer `422` and say nothing.

Two worlds: the Armoury of the release tests (items, a being, stats and a formula), and a
repository with a row in every content table (every kind of entry there is).
"""

import re
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from _fake_jwks import FakeJwksServer
from _hidden_world import H, Rich, rich_world, world
from fastapi.routing import APIRoute
from httpx import AsyncClient

from lorenzo_api.config import get_settings
from lorenzo_api.main import app

# Routes that name a person or a repository, not an entry.
SKIPPED_PREFIXES = ("/tenants/{tenant_id}/activity-log",)


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


def _routes(router: object) -> Iterator[APIRoute]:
    for route in router.routes:  # type: ignore[attr-defined]
        if hasattr(route, "original_router"):
            yield from _routes(route.original_router)
        elif isinstance(route, APIRoute):
            yield route


def _get_routes() -> list[str]:
    paths = {
        route.path
        for route in _routes(app)
        if "GET" in route.methods
        and route.path.startswith("/tenants/{tenant_id}/")
        and not route.path.startswith(SKIPPED_PREFIXES)
    }
    return sorted(paths)


def _fill(path: str, library: uuid.UUID, entry: uuid.UUID) -> str | None:
    """The path with the tenant and every other parameter filled: an id for each `*_id` (an
    entry's, whatever the route calls it), the slug of Longsword for a slug. A parameter of
    another kind has no value here and the route is left to its own tests."""
    url = path.replace("{tenant_id}", str(library))
    for param in re.findall(r"\{(\w+)\}", url):
        if param == "slug":
            url = url.replace("{slug}", "longsword")
        elif param.endswith("_id"):
            url = url.replace("{" + param + "}", str(entry))
        else:
            return None
    return url


def _leaks(text: str, hidden: dict[str, uuid.UUID]) -> list[str]:
    found = [name for name in hidden if re.search(rf"\b{re.escape(name)}\b", text)]
    return found + [name for name, entity_id in hidden.items() if str(entity_id) in text]


async def _sweep(h: H | Rich, entry: uuid.UUID, label: str) -> dict[str, Any]:
    leaks: dict[str, Any] = {}
    asked = 0
    for path in _get_routes():
        url = _fill(path, h.library, entry)
        if url is None:
            continue
        response = await h.reader.get(url, params={"size": 100})
        asked += 1
        if response.status_code == 200:
            found = _leaks(response.text, h.hidden)
            if found:
                leaks[path] = sorted(set(found))
    assert asked > 50, f"{label}: only {asked} routes asked"
    return leaks


async def _all(h: H | Rich) -> None:
    assert await _sweep(h, uuid.uuid4(), "nothing") == {}
    for name, entity_id in sorted(h.hidden.items()):
        assert await _sweep(h, entity_id, name) == {}, name
    assert await _sweep(h, h.visible, "the visible one") == {}


async def test_no_read_of_a_library_names_a_hidden_entry_or_answers_for_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        await _all(h)
    finally:
        await h.done()


async def test_the_same_holds_for_every_kind_of_entry(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    r = await rich_world(raw_client, fake_jwks_server)
    try:
        assert len(r.hidden) > 20
        # The sweep asks with one hidden entry and with the visible one, not with each of the
        # twenty: the path guard is one function, and the lists are asked once.
        hidden = dict(list(sorted(r.hidden.items()))[:3])
        assert await _sweep(r, uuid.uuid4(), "nothing") == {}
        for name, entity_id in hidden.items():
            assert await _sweep(r, entity_id, name) == {}, name
        assert await _sweep(r, r.visible, "the visible one") == {}
    finally:
        await r.done()
