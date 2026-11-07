"""ADR 0437, RFC 0051 H4: a repository built on another hides its entries from the libraries that
copy it. The world is the one of `_hidden_world`; every flip, release, copy and update goes through
the HTTP API, and what a library holds is read from the database where the test says so.
"""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _hidden_world import (
    LONGSWORD_PICTURE,
    LONGSWORD_TEXT,
    H,
    carries,
    hidden_names,
    protect,
    world,
)
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.config import get_settings
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, EntityPrototype, Information, ItemInstance, Payload


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


# --- The texts of a hidden entry are inherited ---------------------------------------------------


async def _instance(h: H, name: str = "Ashfang") -> uuid.UUID:
    """An item instance the library made, whose prototype is the hidden Longsword."""
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=h.library, name=name)
        session.add(entity)
        await session.flush()
        session.add_all(
            [
                ItemInstance(entity_id=entity.id, tenant_id=h.library),
                EntityPrototype(
                    entity_id=entity.id, prototype_id=h.ids["Longsword"], tenant_id=h.library
                ),
            ]
        )
        await session.commit()
        return entity.id


def _inherited(body: dict[str, Any]) -> list[tuple[str, str | None, bool | None]]:
    return [
        (d["content"], d["from_entity"]["name"] if d["from_entity"] else None, d.get("from_hidden"))
        for d in body["descriptions"]
    ]


async def test_the_texts_of_a_hidden_entry_reach_the_entries_below_it_and_it_is_not_named(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """ADR 0437: hiding an entry hides it (list, search, address, provenance) and gives what it
    holds to the entries below it exactly as a visible prototype does: its description and its
    picture are the inherited ones of the entry that has it as a prototype, from a hidden entry."""
    h = await world(raw_client, fake_jwks_server)
    try:
        blade = h.ids["Bridge Blade"]
        expected = [(LONGSWORD_TEXT, None, True)]

        # The item read and the list of items (a hidden item is not in it).
        item = (await h.get(f"/items/{blade}")).json()
        assert _inherited(item) == expected
        [picture] = item["pictures"]
        assert (picture["from_entity"], picture["from_hidden"]) == (None, True)
        listed = (await h.get("/items", params={"size": 100})).json()["items"]
        assert [i["entity_id"] for i in listed] == [str(blade)]
        assert _inherited(next(i for i in listed if i["entity_id"] == str(blade))) == expected

        # The picture's bytes are the reader's too: they come with the entry that inherits it.
        bytes_read = await h.reader.get(picture["url"])
        assert bytes_read.status_code == 200 and bytes_read.content == LONGSWORD_PICTURE

        # An instance the library made reads the same, in its read and its lists.
        instance = await _instance(h)
        read = (await h.get(f"/item-instances/{instance}")).json()
        assert _inherited(read) == expected and read["pictures"][0]["from_hidden"] is True
        every = (await h.get("/item-instances", params={"size": 100})).json()["items"]
        found = next(i for i in every if i["entity_id"] == str(instance))
        assert _inherited(found) == expected

        # The card of an entry that has no text of its own starts with the inherited one.
        preview = (await h.get(f"/entities/{blade}/preview")).json()
        assert preview["excerpt"] == LONGSWORD_TEXT

        # Nothing of the hidden entry is named: not its name, not its id, not its slug.
        for body in (item, read, preview):
            text = str(body)
            assert "Longsword" not in text and str(h.ids["Longsword"]) not in text
            assert "longsword" not in text
    finally:
        await h.done()


async def test_a_hidden_entry_nothing_visible_inherits_from_keeps_its_texts_to_itself(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Orc has a description and a picture and no entry below it that the library can see: the
    payload is 404, as is the entry. Only what is inherited is given."""
    h = await world(raw_client, fake_jwks_server)
    try:
        async with admin_session_factory() as session:
            payloads = list(
                await session.scalars(
                    select(Payload.id)
                    .join(Information, Information.id == Payload.information_id)
                    .where(Information.entity_id == h.ids["Orc"])
                )
            )
        assert len(payloads) == 2
        for payload in payloads:
            assert (await h.get(f"/payloads/{payload}/content")).status_code == 404
    finally:
        await h.done()


async def test_the_same_texts_are_given_with_the_name_when_the_source_is_shown(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The control: with `show` the entry is listed and named, and gives the same text."""
    h = await world(raw_client, fake_jwks_server, choice="show")
    try:
        item = (await h.get(f"/items/{h.ids['Bridge Blade']}")).json()
        assert _inherited(item) == [(LONGSWORD_TEXT, "Longsword", None)]
        assert item["pictures"][0]["from_hidden"] is None
        assert item["pictures"][0]["from_entity"]["name"] == "Longsword"
        assert (await h.reader.get(item["pictures"][0]["url"])).status_code == 200
    finally:
        await h.done()


def _information(entity_id: uuid.UUID, *, public: bool = True) -> Information:
    return Information(
        entity_id=entity_id, tenant_id=uuid.uuid4(), title="t", type="description", is_public=public
    )


def test_what_the_audiences_hide_still_hides_a_text_that_would_be_inherited() -> None:
    """The reader's sight: an entry hidden by the repository it came with gives its text and is not
    named; one an audience hides does not give it, and one both hide does not either."""
    entity = uuid.uuid4()
    other = uuid.uuid4()

    def sight(hidden: set[uuid.UUID], audience: set[uuid.UUID] | None) -> InformationVisibility:
        return InformationVisibility(
            is_orga=False,
            is_admin=True,
            player_ids=frozenset(),
            knower_entity_ids=frozenset(),
            gm_reachable_entity_ids=frozenset(),
            hidden_entry_ids=frozenset(hidden),
            audience_hidden_entry_ids=None if audience is None else frozenset(audience),
        )

    info = _information(entity)
    # Hidden by the source only: not seen, inherited, and said to be hidden by it.
    only = sight({entity}, set())
    assert not only.can_see(info) and only.can_see_inherited(info)
    assert only.is_hidden_by_source(entity) and not only.is_hidden_by_source(other)
    # Hidden by an audience (alone, or as well): nothing is given.
    for audience in ({entity}, {entity, other}):
        both = sight({entity}, audience)
        assert not both.can_see(info) and not both.can_see_inherited(info)
        assert not both.is_hidden_by_source(entity)
    # A tenant that hides nothing says nothing about a source, and a hand-built sight is as it was.
    plain = sight({entity}, None)
    assert not plain.can_see(info) and not plain.can_see_inherited(info)
    assert not plain.is_hidden_by_source(entity)
    assert sight(set(), None).can_see_inherited(info)
