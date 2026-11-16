"""ADR 0437, RFC 0051 H4: what a library holds of a source it hides, and how that follows what it
copies and updates. The world is the one of `_hidden_world`; every flip, release, copy and update
goes through the HTTP API, and what a library holds is read from the database where the test says
so.
"""

import json
import uuid

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _hidden_world import carries, choose, hidden_names, names_of, world
from httpx import AsyncClient
from sqlalchemy import delete, select, update
from test_repository_include import _bridge, _copy, _library, _make_public

from lorenzo_api.config import get_settings
from lorenzo_api.models import (
    Entity,
    EntityPrototype,
    EntityStat,
    Item,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    Tenant,
)
from lorenzo_api.repository_content import Content
from lorenzo_api.repository_hiding import (
    HIDDEN_ENTRY,
    carries_of,
    hidden_label,
    hidden_sources,
)


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


# --- The derivation, as a function ----------------------------------------------------------


def test_what_a_library_hides_is_what_every_repository_it_holds_hides() -> None:
    a, b, c = (str(uuid.uuid4()) for _ in range(3))
    # B hides A and brings itself; nothing brings A otherwise: A is hidden.
    assert hidden_sources([{a: "hide", b: "show"}, {}]) == {uuid.UUID(a)}
    # Show wins: another repository the library holds shows A, or A was copied for itself.
    assert hidden_sources([{a: "hide", b: "show"}, {a: "show", c: "show"}]) == set()
    assert hidden_sources([{a: "hide", b: "show"}, {a: "show"}]) == set()
    # Nothing is hidden for a library that holds nothing that says so (the migration's records
    # bring themselves, `show`).
    assert hidden_sources([{a: "show"}, {b: "show"}]) == set()
    assert hidden_sources([]) == set()
    # Two that hide it keep it hidden; a third that shows another source changes nothing for A.
    assert hidden_sources([{a: "hide"}, {a: "hide", c: "show"}]) == {uuid.UUID(a)}


def test_a_release_is_read_into_what_a_repository_brings_separate() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    content = Content(tenant_id=uuid.uuid4())
    content.sources = {
        a: {"inclusion": "hide", "name": "A", "licence": None},
        b: {"inclusion": "show", "name": "B", "licence": None},
        c: {"inclusion": "include", "name": "C", "licence": None},
    }
    head = uuid.uuid4()
    # An included source is the repository's own rows: it brings nothing separate.
    assert carries_of(content, head, for_itself=False) == {str(a): "hide", str(b): "show"}
    assert carries_of(content, head, for_itself=True) == {
        str(a): "hide",
        str(b): "show",
        str(head): "show",
    }
    assert carries_of(Content(tenant_id=head), head, for_itself=False) == {}


def test_the_words_for_what_an_update_does_to_hidden_entries() -> None:
    assert hidden_label(1) == "1 change to a hidden entry"
    assert hidden_label(3) == "3 changes to hidden entries"
    assert HIDDEN_ENTRY == "a hidden entry"


# --- Show wins ------------------------------------------------------------------------------


async def test_a_library_that_also_holds_a_repository_that_shows_the_source_sees_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        assert await hidden_names(h.library) == ["Dagger", "Longsword", "Orc"]
        # C is another repository built on A that shows it: copying it brings A's rows into view.
        c, _ = await _bridge(h.w.base, "Shower", own="Shower Blade")
        h.w.tenants.append(c)
        assert (await _make_public(h.w.author, c)).status_code == 200
        copied = await _copy(h.reader, h.library, c)
        assert copied.status_code == 201, copied.text
        assert await hidden_names(h.library) == []
        names = [
            e["name"] for e in (await h.get("/entities", params={"size": 100})).json()["items"]
        ]
        assert sorted(names) == [
            "Bridge Blade",
            "Dagger",
            "Longsword",
            "Orc",
            "Shower Blade",
        ]
        held = await carries(h.library)
        assert held[h.b][str(h.a)] == "hide" and held[c][str(h.a)] == "show"
        assert (await h.get(f"/entities/{h.ids['Longsword']}")).status_code == 200

        # The other way round: a library that copies the one that shows it first and the one that
        # hides it second hides nothing either.
        reader, library = await _library(raw_client, fake_jwks_server, h.w, "Second")
        assert (await _copy(reader, library, c)).status_code == 201
        assert (await _copy(reader, library, h.b)).status_code == 201
        assert await hidden_names(library) == []
        # And one that copies only the one that hides it, hides.
        reader3, library3 = await _library(raw_client, fake_jwks_server, h.w, "Third")
        assert (await _copy(reader3, library3, h.b)).status_code == 201
        assert await hidden_names(library3) == ["Dagger", "Longsword", "Orc"]
    finally:
        await h.done()


async def test_what_a_library_copied_for_itself_is_never_hidden_by_another_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A public source can be copied alone; copied first, and then a repository built on it that
    hides it, its entries stay in view: hiding it is cosmetic, and the library asked for it."""
    h = await world(raw_client, fake_jwks_server, protected=False, copy=False)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, h.w, "Alone")
        assert (await _copy(reader, library, h.a)).status_code == 201
        assert (await _copy(reader, library, h.b)).status_code == 201
        assert await hidden_names(library) == []
        listed = (await reader.get(f"/tenants/{library}/entities", params={"size": 100})).json()
        assert sorted(e["name"] for e in listed["items"]) == [
            "Bridge Blade",
            "Dagger",
            "Longsword",
            "Orc",
        ]
        held = await carries(library)
        assert held[h.a][str(h.a)] == "show" and held[h.b][str(h.a)] == "hide"
        # While the library that copies the repository alone hides the public source, as asked.
        reader2, library2 = await _library(raw_client, fake_jwks_server, h.w, "Through")
        assert (await _copy(reader2, library2, h.b)).status_code == 201
        assert await hidden_names(library2) == ["Dagger", "Longsword", "Orc"]
    finally:
        await h.done()


# --- Hidden rows are read-only --------------------------------------------------------------


async def test_a_library_cannot_change_or_delete_a_hidden_entry(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        longsword = h.ids["Longsword"]
        for method, path, body in (
            ("patch", f"/entities/{longsword}", {"name": "Sabre"}),
            ("delete", f"/entities/{longsword}", None),
            ("patch", f"/items/{longsword}", {"name": "Sabre"}),
            ("delete", f"/items/{longsword}", None),
            ("put", f"/entities/{longsword}/kinds/fact", None),
            ("delete", f"/entities/{longsword}/kinds/item", None),
            ("put", f"/entities/{longsword}/parents", {"parents": []}),
            ("put", f"/entities/{longsword}/slug", {"slug": "sabre"}),
            ("delete", f"/entities/{longsword}/slug", None),
            ("post", f"/entities/{longsword}/information", {"title": "t", "type": "notes"}),
        ):
            call = getattr(h.reader, method)
            response = await (
                call(f"/tenants/{h.library}{path}", json=body)
                if body is not None
                else call(f"/tenants/{h.library}{path}")
            )
            assert response.status_code == 404, (method, path, response.status_code)
        # It is all still there, as it was.
        assert await hidden_names(h.library) == ["Dagger", "Longsword", "Orc"]
        async with admin_session_factory() as session:
            assert (await session.get_one(Entity, longsword)).name == "Longsword"
    finally:
        await h.done()


async def test_a_hidden_entry_is_what_inheritance_resolves_through_for_every_stat_read(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        blade = h.ids["Bridge Blade"]
        strength = (await h.get("/stat-definitions", params={"size": 100})).json()["items"]
        strength_id = next(d["id"] for d in strength if d["name"] == "Strength")
        damage_id = next(d["id"] for d in strength if d["name"] == "Damage")
        # The entry's own read says the value is inherited from an entry it cannot see.
        detail = (await h.get(f"/entities/{blade}")).json()
        by_name = {s["name"]: s for s in detail["stats"]}
        assert by_name["Strength"]["from_hidden"] is True and by_name["Strength"]["own"] is False
        assert by_name["Strength"]["from_entity"] is None
        # The effective values of a page, the explanation, the item's own read and a formula over
        # the inherited stat all resolve, and none names the source.
        effective = await h.get(
            "/entities/effective-stats", params={"stat_definition_id": strength_id}
        )
        assert effective.status_code == 200, effective.text
        assert [e["id"] for e in effective.json()["items"]] == [str(blade)]
        row = effective.json()["items"][0]["stats"][0]
        assert row["value"] == 10 and row["from_entity"] is None and row["from_hidden"] is True
        explained = await h.get(f"/entities/{blade}/stats/{damage_id}/explanation")
        assert explained.status_code == 200, explained.text
        assert explained.json()["value"] == 6 and explained.json()["from_hidden"] is True
        assert explained.json()["from_entity"] is None
        item = await h.get(f"/items/{blade}")
        assert item.status_code == 200
        assert "Longsword" not in item.text and str(h.ids["Longsword"]) not in item.text
        # An entry the library made itself, with a hidden entry as its parent, reads the same.
        async with admin_session_factory() as session:
            own = Entity(tenant_id=h.library, name="Library Blade")
            session.add(own)
            await session.flush()
            session.add_all(
                [
                    Item(entity_id=own.id, tenant_id=h.library),
                    EntityPrototype(
                        entity_id=own.id, prototype_id=h.ids["Longsword"], tenant_id=h.library
                    ),
                ]
            )
            await session.commit()
            library_blade = own.id
        detail = (await h.get(f"/entities/{library_blade}")).json()
        assert {s["name"]: s["value"] for s in detail["stats"]}["Strength"] == 10
        assert detail["prototypes"] == []
        assert "Longsword" not in str(detail)
    finally:
        await h.done()


# --- Updates --------------------------------------------------------------------------------


async def _change_a(h, *, remove: tuple[str, ...] = ("Orc",), label: str = "p2") -> None:
    """A's Owner changes Longsword's Strength, adds a Pike and removes what `remove` names, and
    releases."""
    ids = h.w.base.ids
    async with admin_session_factory() as session:
        await session.execute(
            update(EntityStat)
            .where(
                EntityStat.tenant_id == h.a,
                EntityStat.entity_id == ids["Longsword"],
                EntityStat.stat_definition_id == ids["Strength"],
            )
            .values(value_int=20)
        )
        pike = Entity(tenant_id=h.a, name="Pike")
        session.add(pike)
        await session.flush()
        session.add(Item(entity_id=pike.id, tenant_id=h.a))
        for name in remove:
            await session.execute(delete(Entity).where(Entity.id == ids[name]))
        await session.commit()
    released = await h.w.author.put(
        f"/tenants/{h.a}/published", json={"label": label, "acknowledge_breaking": True}
    )
    assert released.status_code == 200, released.text


async def test_the_update_of_a_hidden_source_is_counts_and_a_label_and_is_taken_with_the_rest(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        await _change_a(h)
        updates = await h.get(f"/repositories/{h.a}/updates")
        assert updates.status_code == 200, updates.text
        body = updates.json()
        # Nothing is named: not in a list, not in the names, not in the text of the answer.
        assert (body["changed"], body["removed"], body["added"]) == ([], [], [])
        assert body["hidden"] == {
            "changed": 1,
            "added": 1,
            "removed": 1,
            "breaking": 1,
            "label": "3 changes to hidden entries",
        }
        for word in ("Longsword", "Pike", "Orc", "Dagger"):
            assert word not in updates.text, word

        # The breaking one among them is acknowledged as one line, and not before.
        url = f"/tenants/{h.library}/repositories/{h.a}/updates"
        refused = await h.reader.post(url, json={"actions": []})
        assert refused.status_code == 409, refused.text
        problem = refused.json()
        assert problem["type"] == "update-needs-confirmation"
        assert [u["kind"] for u in problem["unconfirmed"]] == ["hidden"]
        assert problem["unconfirmed"][0]["name"] == "1 change to a hidden entry"
        assert "Orc" not in refused.text
        assert (await carries(h.library))[h.a] == {}

        applied = await h.reader.post(
            url, json={"actions": [], "acknowledge_hidden_breaking": True}
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["hidden"]["label"] == "3 changes to hidden entries"
        names = await names_of(h.library)
        # The Pike is there and hidden, the Orc is gone (nothing visible uses it), the Longsword
        # has the new Strength.
        assert "Pike" in names and "Orc" not in names
        assert await hidden_names(h.library) == ["Dagger", "Longsword", "Pike"]
        async with admin_session_factory() as session:
            value = await session.scalar(
                select(EntityStat.value_int).where(
                    EntityStat.tenant_id == h.library, EntityStat.entity_id == names["Longsword"]
                )
            )
            assert value == 20
            synced = await session.scalar(
                select(RepositoryCopy.synced_release_id).where(
                    RepositoryCopy.tenant_id == h.library,
                    RepositoryCopy.repository_tenant_id == h.a,
                )
            )
            assert synced is not None
        # What is visible is what it was, and it inherits the new value.
        listed = (await h.get("/entities", params={"size": 100})).json()["items"]
        assert [e["name"] for e in listed] == ["Bridge Blade"]
        blade = (await h.get(f"/entities/{h.ids['Bridge Blade']}")).json()
        assert {s["name"]: s["value"] for s in blade["stats"]}["Strength"] == 20
        # And there is nothing left to take.
        again = (await h.get(f"/repositories/{h.a}/updates")).json()
        assert again["hidden"] is None
        # A write the library never made: the Pike is hidden, not editable.
        assert (await h.get(f"/entities/{names['Pike']}")).status_code == 404
    finally:
        await h.done()


async def test_a_hidden_entry_something_visible_uses_stays_when_the_source_drops_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        # The Longsword is the parent of the visible Bridge Blade: A dropping it does not take it
        # out of the library, which would take the blade's parent with it.
        await _change_a(h, remove=("Longsword",))
        body = (await h.get(f"/repositories/{h.a}/updates")).json()
        assert body["hidden"]["removed"] == 1 and body["hidden"]["breaking"] >= 1
        url = f"/tenants/{h.library}/repositories/{h.a}/updates"
        applied = await h.reader.post(
            url, json={"actions": [], "acknowledge_hidden_breaking": True}
        )
        assert applied.status_code == 200, applied.text
        assert "Longsword" in await names_of(h.library)
        assert "Longsword" in await hidden_names(h.library)
        blade = (await h.get(f"/entities/{h.ids['Bridge Blade']}")).json()
        assert {s["name"]: s["value"] for s in blade["stats"]}["Strength"] == 10
    finally:
        await h.done()


async def test_a_visible_row_that_mentions_a_hidden_entry_does_not_name_it_in_an_update(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        # B gives its Bridge Blade a second parent, B's copy of the Dagger, and releases again.
        blade = h.w.ids["Bridge Blade"]
        async with admin_session_factory() as session:
            session.add(
                EntityPrototype(entity_id=blade, prototype_id=h.w.ids["Dagger"], tenant_id=h.b)
            )
            await session.commit()
        released = await h.w.author.put(f"/tenants/{h.b}/published", json={"label": "2"})
        assert released.status_code == 200, released.text
        updates = await h.get(f"/repositories/{h.b}/updates")
        assert updates.status_code == 200, updates.text
        body = updates.json()
        assert [r["name"] for r in body["changed"]] == ["Bridge Blade"]
        assert "a hidden entry" in body["names"].values()
        assert "Dagger" not in updates.text and "Longsword" not in updates.text
        assert body["hidden"] is None
    finally:
        await h.done()


# --- The flag follows what the library holds --------------------------------------------------


async def test_the_flag_and_the_tenants_column_follow_the_records(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        async with admin_session_factory() as session:
            assert (await session.get_one(Tenant, h.library)).hides_entries is True
            # Every entry of A is hidden and none of B's own is.
            flags = dict(
                (name, hidden)
                for name, hidden in await session.execute(
                    select(Entity.name, RepositoryCopyLinkEntity.hidden)
                    .join(
                        RepositoryCopyLinkEntity,
                        RepositoryCopyLinkEntity.entity_id == Entity.id,
                    )
                    .where(RepositoryCopyLinkEntity.tenant_id == h.library)
                )
            )
            assert flags == {"Longsword": True, "Dagger": True, "Orc": True, "Bridge Blade": False}
        # A tenant that hides nothing says so, and its Owner's reads are unchanged by the gate.
        c, _ = await _bridge(h.w.base, "Shower", own="Shower Blade")
        h.w.tenants.append(c)
        assert (await _make_public(h.w.author, c)).status_code == 200
        assert (await _copy(h.reader, h.library, c)).status_code == 201
        async with admin_session_factory() as session:
            assert (await session.get_one(Tenant, h.library)).hides_entries is False
        # The library's records are what the flag is derived from: the choice of B can change in
        # the next release, and the library follows it once it takes the release.
        assert (await choose(h.w.author, h.b, h.a, "show")).status_code == 200
    finally:
        await h.done()


async def test_the_migration_leaves_what_a_library_holds_visible() -> None:
    """The records it wrote bring themselves, `show`: nothing a library held before hiding existed
    is hidden by a choice made later."""
    from lorenzo_api.repository_hiding import hidden_sources as derive

    repository = uuid.uuid4()
    other = uuid.uuid4()
    assert (
        derive([{str(repository): "show"}, {str(other): "show", str(repository): "hide"}]) == set()
    )
    # Dumped to the shape the update engine and the migration write.
    assert json.loads(
        json.dumps(carries_of(Content(tenant_id=repository), repository, for_itself=True))
    ) == {str(repository): "show"}


async def test_a_release_that_stops_hiding_shows_the_entries_once_the_library_takes_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        assert await hidden_names(h.library) == ["Dagger", "Longsword", "Orc"]
        # B's Owner keeps A separate and visible from now on: a breaking release, which the library
        # learns of by taking it. Until then it holds what it held.
        assert (await choose(h.w.author, h.b, h.a, "show")).status_code == 200
        released = await h.w.author.put(
            f"/tenants/{h.b}/published", json={"label": "2", "acknowledge_breaking": True}
        )
        assert released.status_code == 200, released.text
        assert await hidden_names(h.library) == ["Dagger", "Longsword", "Orc"]
        taken = await h.reader.post(
            f"/tenants/{h.library}/repositories/{h.b}/updates", json={"actions": []}
        )
        assert taken.status_code == 200, taken.text
        assert await hidden_names(h.library) == []
        assert (await carries(h.library))[h.b] == {str(h.a): "show", str(h.b): "show"}
        names = [
            e["name"] for e in (await h.get("/entities", params={"size": 100})).json()["items"]
        ]
        assert sorted(names) == ["Bridge Blade", "Dagger", "Longsword", "Orc"]
        # And hidden again by the next release: the entries go out of sight again.
        assert (await choose(h.w.author, h.b, h.a, "hide")).status_code == 200
        released = await h.w.author.put(
            f"/tenants/{h.b}/published", json={"label": "3", "acknowledge_breaking": True}
        )
        assert released.status_code == 200, released.text
        taken = await h.reader.post(
            f"/tenants/{h.library}/repositories/{h.b}/updates", json={"actions": []}
        )
        assert taken.status_code == 200, taken.text
        assert await hidden_names(h.library) == ["Dagger", "Longsword", "Orc"]
    finally:
        await h.done()
