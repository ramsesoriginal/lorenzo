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
from _author_world import add_member
from _fake_jwks import FakeJwksServer
from _hidden_world import H, Rich, rich_world, world
from _repository_actors import Actor, make_actor
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


def _fill(
    path: str, library: uuid.UUID, entry: uuid.UUID, repository: uuid.UUID | None = None
) -> str | None:
    """The path with the tenant and every other parameter filled: an id for each `*_id` (an
    entry's, whatever the route calls it), the slug of Longsword for a slug. A parameter of
    another kind has no value here and the route is left to its own tests."""
    url = path.replace("{tenant_id}", str(library))
    for param in re.findall(r"\{(\w+)\}", url):
        if param == "slug":
            url = url.replace("{slug}", "longsword")
        elif param == "repository_id" and repository is not None:
            url = url.replace("{repository_id}", str(repository))
        elif param.endswith("_id"):
            url = url.replace("{" + param + "}", str(entry))
        else:
            return None
    return url


def _leaks(text: str, hidden: dict[str, uuid.UUID]) -> list[str]:
    found = [name for name in hidden if re.search(rf"\b{re.escape(name)}\b", text)]
    return found + [name for name, entity_id in hidden.items() if str(entity_id) in text]


async def _sweep(
    h: H | Rich,
    entry: uuid.UUID,
    label: str,
    reader: Actor | None = None,
    repository: uuid.UUID | None = None,
) -> dict[str, Any]:
    leaks: dict[str, Any] = {}
    asked = 0
    for path in _get_routes():
        url = _fill(path, h.library, entry, repository)
        if url is None:
            continue
        response = await (reader or h.reader).get(url, params={"size": 100})
        asked += 1
        if response.status_code == 200:
            found = _leaks(response.text, h.hidden)
            if found:
                leaks[path] = sorted(set(found))
    assert asked > 50, f"{label}: only {asked} routes asked"
    return leaks


async def _all(h: H, reader: Actor | None = None) -> None:
    assert await _sweep(h, uuid.uuid4(), "nothing", reader) == {}
    for name, entity_id in sorted(h.hidden.items()):
        assert await _sweep(h, entity_id, name, reader) == {}, name
    assert await _sweep(h, h.visible, "the visible one", reader) == {}
    # The repositories the library holds: A (which it holds through B) and B, each asked with a
    # hidden entry and the visible one, as the entry of its browse and its preview.
    for repository in (h.a, h.b):
        for entry in (h.hidden["Longsword"], h.visible):
            assert await _sweep(h, entry, "a repository", reader, repository) == {}, repository


async def test_no_read_of_a_library_names_a_hidden_entry_or_answers_for_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        await _all(h)
    finally:
        await h.done()


async def test_nor_does_a_read_of_an_author_or_an_organizer_of_the_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        for role in ("author", "orga"):
            person = await make_actor(raw_client, fake_jwks_server, role, roles=())
            h.w.actors.append(person)
            await add_member(h.reader, h.library, person, role)
            assert await _sweep(h, h.hidden["Longsword"], role, person) == {}, role
            assert await _sweep(h, h.visible, role, person) == {}, role
    finally:
        await h.done()


async def test_the_sweep_finds_what_it_looks_for_when_nothing_is_hidden(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The same world with the source shown: every read the sweep asks names its entries, so the
    sweep has the power the other tests rely on."""
    h = await world(raw_client, fake_jwks_server, choice="show")
    try:
        found = await _sweep(h, h.hidden["Longsword"], "shown")
        assert "/tenants/{tenant_id}/items" in found and "/tenants/{tenant_id}/entities" in found
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
        for repository in (r.a, r.b):
            assert await _sweep(r, r.visible, "a repository", None, repository) == {}, repository
    finally:
        await r.done()
