"""ADR 0436, RFC 0051 H4: a repository built on another hides its entries from the libraries that
copy it. The world is the one of `_hidden_world`; every flip, release, copy and update goes through
the HTTP API, and what a library holds is read from the database where the test says so.
"""

import pytest
from _fake_jwks import FakeJwksServer
from _hidden_world import carries, hidden_names, protect, world
from httpx import AsyncClient

from lorenzo_api.config import get_settings


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def test_a_library_that_copies_a_repository_hiding_its_source_holds_and_cannot_see_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        # The library holds every entry of A and B (the Orc of A comes from A, not from B).
        assert sorted(h.ids) == ["Bridge Blade", "Dagger", "Longsword", "Orc"]
        assert await hidden_names(h.library) == ["Dagger", "Longsword", "Orc"]
        listed = await h.get("/entities", params={"size": 100})
        assert [e["name"] for e in listed.json()["items"]] == ["Bridge Blade"]
        # An entry it cannot see is not there by its address either, for its Owner too.
        for name in ("Longsword", "Dagger", "Orc"):
            assert (await h.get(f"/entities/{h.ids[name]}")).status_code == 404
        assert (await h.get(f"/entities/{h.ids['Bridge Blade']}")).status_code == 200
    finally:
        await h.done()


async def test_inheritance_values_formulas_and_provenance_resolve_through_a_hidden_entry(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The spike of RFC 0051 H4: a hidden entry is still what inheritance resolves through."""
    h = await world(raw_client, fake_jwks_server)
    try:
        blade = (await h.get(f"/entities/{h.ids['Bridge Blade']}")).json()
        stats = {s["name"]: s for s in blade["stats"]}
        # Strength is Longsword's (10: B's own edit of it does not travel, A's row does), Damage is
        # the formula Longsword holds, evaluated for the blade: both inherited from the hidden one.
        assert stats["Strength"]["value"] == 10 and stats["Strength"]["own"] is False
        assert stats["Damage"]["value"] == 6 and stats["Damage"]["computed"] is True
        # The source is not named, and nothing of the hidden entry is: not its name, not its id.
        assert stats["Strength"]["from_entity"] is None and stats["Damage"]["from_entity"] is None
        assert "Longsword" not in str(blade) and str(h.ids["Longsword"]) not in str(blade)
        # The parent it has is not listed either.
        assert blade["prototypes"] == []
    finally:
        await h.done()


async def test_what_is_hidden_is_derived_from_what_the_library_holds(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        # B brings A hidden and brings itself for the library's sake only as the head it copied.
        held = await carries(h.library)
        assert held[h.b] == {str(h.a): "hide", str(h.b): "show"}
        assert held[h.a] == {}
        # The Owner of A, who does not hide it, reads it as ever.
        assert (await protect(h.w.author, h.a)).json()["type"] == "repository-already-protected"
    finally:
        await h.done()
