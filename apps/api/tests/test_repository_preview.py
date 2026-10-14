"""ADR 0293: what a reader may look at of a repository before copying it, by the Owner's preview
switch and by whether the reader holds access, the showcase the Owner chooses, and that nothing
that is not Everyone's can come out of any of it.
"""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import Actor, make_actor
from _upstream_documents import set_visibility
from httpx import AsyncClient
from sqlalchemy import update

import lorenzo_api.repository_preview as preview_module
from lorenzo_api.config import get_settings
from lorenzo_api.models import (
    Information,
    Payload,
    PayloadDescription,
    PayloadPicture,
    RepositoryProfile,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"public-picture"
SECRET_PNG = b"\x89PNG\r\n\x1a\n" + b"secret-picture"
SECRET = "The pommel hides a gem"


async def _text(
    repository: uuid.UUID,
    entity: uuid.UUID,
    title: str,
    description: str,
    *,
    public: bool,
    picture: bytes | None = None,
) -> tuple[uuid.UUID, uuid.UUID | None]:
    """A row of text on an entry, with a description and a picture if given: the ids of the row and
    of its picture's payload."""
    async with admin_session_factory() as session:
        row = Information(
            tenant_id=repository, entity_id=entity, title=title, type="note", is_public=public
        )
        session.add(row)
        await session.flush()
        body = Payload(tenant_id=repository, information_id=row.id, order=0)
        session.add(body)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=body.id, tenant_id=repository, locale="en", content=description
            )
        )
        picture_id = None
        if picture is not None:
            shot = Payload(tenant_id=repository, information_id=row.id, order=1)
            session.add(shot)
            await session.flush()
            session.add(
                PayloadPicture(
                    payload_id=shot.id, tenant_id=repository, data=picture, file_type="image/png"
                )
            )
            picture_id = shot.id
        await session.commit()
        return row.id, picture_id


class _Case:
    world: ReleaseWorld
    visitor: Actor
    stranger: Actor
    stranger_library: uuid.UUID
    secret_picture: uuid.UUID
    public_picture: uuid.UUID

    async def build(self, raw_client: AsyncClient, jwks: FakeJwksServer) -> _Case:
        w = self.world = await release_world(raw_client, jwks, published=False)
        longsword, dagger = w.ids["Longsword"], w.ids["Dagger"]
        _, shown = await _text(
            w.repository, longsword, "Blade", "A long blade.", public=True, picture=PNG
        )
        _, hidden = await _text(
            w.repository, longsword, "Secret", SECRET, public=False, picture=SECRET_PNG
        )
        await _text(w.repository, dagger, "Edge", "A short edge.", public=True)
        assert shown is not None and hidden is not None
        self.public_picture, self.secret_picture = shown, hidden
        await set_visibility([w.repository], "public")
        await w.publish(label="1.0")
        featured = await w.author.put(
            f"/tenants/{w.repository}/showcase", json={"entity_ids": [str(longsword), str(dagger)]}
        )
        assert featured.status_code == 200, featured.text
        self.visitor = await make_actor(raw_client, jwks, "visitor", roles=())
        self.stranger = await make_actor(raw_client, jwks, "stranger")
        self.stranger_library = await self.stranger.create_tenant("A table with no access")
        w.tenants.append(self.stranger_library)
        w.actors.extend([self.visitor, self.stranger])
        return self

    async def switch(self, preview: str) -> None:
        async with admin_session_factory() as session:
            await session.execute(
                update(RepositoryProfile)
                .where(RepositoryProfile.tenant_id == self.world.repository)
                .values(preview=preview)
            )
            await session.commit()

    def reader(self, who: str) -> tuple[Actor, str]:
        """The actor and the prefix of the routes for a visitor with no library, a library with no
        access, and a holder."""
        w, base = self.world, f"/repositories/{self.world.repository}"
        if who == "visitor":
            return self.visitor, base
        if who == "stranger":
            return self.stranger, f"/tenants/{self.stranger_library}{base}"
        return w.gm, f"/tenants/{w.table}{base}"

    async def get(self, who: str, path: str) -> Any:
        actor, prefix = self.reader(who)
        return await actor.get(prefix + path)


READERS = ("visitor", "stranger", "holder")


async def _case(raw_client: AsyncClient, jwks: FakeJwksServer) -> _Case:
    return await _Case().build(raw_client, jwks)


def _names(response: Any) -> list[str]:
    assert response.status_code == 200, response.text
    return sorted(e["name"] for e in response.json()["items"])


# --- The table ---------------------------------------


@pytest.mark.parametrize("who", ["visitor", "stranger"])
async def test_a_visitor_looks_at_as_much_as_the_switch_says(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, who: str
) -> None:
    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    longsword, dagger, orc = w.ids["Longsword"], w.ids["Dagger"], w.ids["Orc"]
    try:
        # off: nothing of the entries, only the profile and the counts.
        await case.switch("off")
        assert _names(await case.get(who, "/entities")) == []
        assert (await case.get(who, "/stat-groups")).json() == []
        assert (await case.get(who, "/preview")).json() == {"preview": "off", "entries": []}
        assert (await case.get(who, f"/entities/{longsword}")).status_code == 404

        # showcase: the featured entries, in the order chosen, with their text.
        await case.switch("showcase")
        assert _names(await case.get(who, "/entities")) == ["Dagger", "Longsword"]
        assert (await case.get(who, "/stat-groups")).json() == []
        shown = (await case.get(who, "/preview")).json()
        assert shown["preview"] == "showcase"
        assert [e["name"] for e in shown["entries"]] == ["Longsword", "Dagger"]
        sword = shown["entries"][0]
        assert (sword["featured"], sword["text_visible"]) == (True, True)
        assert [i["title"] for i in sword["information"]] == ["Blade"]
        assert sword["information"][0]["descriptions"] == [
            {"locale": "en", "content": "A long blade."}
        ]
        assert [s["name"] for s in sword["stats"]] == ["Strength"]
        assert sword["kinds"] == ["item"]
        assert (await case.get(who, f"/entities/{orc}")).status_code == 404

        # public: every entry, and the structure.
        await case.switch("public")
        assert _names(await case.get(who, "/entities")) == ["Dagger", "Longsword", "Orc"]
        assert (await case.get(who, "/stat-groups")).status_code == 200
        assert len((await case.get(who, "/stat-groups")).json()) == 2
        every = (await case.get(who, f"/entities/{orc}")).json()
        assert (every["featured"], every["text_visible"], every["kinds"]) == (
            False,
            True,
            ["being"],
        )
        dirk = (await case.get(who, f"/entities/{dagger}")).json()
        assert [p["name"] for p in dirk["parents"]] == ["Longsword"]
    finally:
        await case.world.done()


async def test_a_holder_always_sees_the_names_and_the_text_the_switch_says(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    longsword, orc = w.ids["Longsword"], w.ids["Orc"]
    try:
        await case.switch("off")
        assert _names(await case.get("holder", "/entities")) == ["Dagger", "Longsword", "Orc"]
        assert len((await case.get("holder", "/stat-groups")).json()) == 2
        assert (await case.get("holder", "/preview")).json()["entries"] == []
        sword = (await case.get("holder", f"/entities/{longsword}")).json()
        assert (sword["name"], sword["text_visible"], sword["information"]) == (
            "Longsword",
            False,
            [],
        )

        await case.switch("showcase")
        sword = (await case.get("holder", f"/entities/{longsword}")).json()
        assert sword["text_visible"] is True and sword["information"]
        goblin = (await case.get("holder", f"/entities/{orc}")).json()
        assert (goblin["text_visible"], goblin["stats"]) == (False, [])
        assert [e["name"] for e in (await case.get("holder", "/preview")).json()["entries"]] == [
            "Longsword",
            "Dagger",
        ]

        await case.switch("public")
        assert (await case.get("holder", f"/entities/{orc}")).json()["text_visible"] is True
    finally:
        await w.done()


# --- What is not Everyone's never comes out ---------------------------------------


async def test_no_preview_route_returns_a_row_that_is_not_everyones(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    try:
        for preview in ("off", "showcase", "public"):
            await case.switch(preview)
            for who in READERS:
                seen = [
                    (await case.get(who, "/preview")).text,
                    (await case.get(who, "/entities")).text,
                ]
                for entity in w.ids.values():
                    seen.append((await case.get(who, f"/entities/{entity}")).text)
                for text in seen:
                    assert SECRET not in text, (preview, who)
                    assert '"Secret"' not in text, (preview, who)
                # The secret row's picture is not there, nor under any other entry.
                for entity in (w.ids["Longsword"], w.ids["Dagger"], w.ids["Orc"]):
                    response = await case.get(
                        who, f"/entities/{entity}/pictures/{case.secret_picture}"
                    )
                    assert response.status_code == 404, (preview, who)
        # A row that is Everyone's can be read where text may be, and under no other entry.
        await case.switch("public")
        for who in READERS:
            ok = await case.get(
                who, f"/entities/{w.ids['Longsword']}/pictures/{case.public_picture}"
            )
            assert (ok.status_code, ok.content) == (200, PNG), who
            assert ok.headers["content-type"] == "image/png"
            other = await case.get(
                who, f"/entities/{w.ids['Dagger']}/pictures/{case.public_picture}"
            )
            assert other.status_code == 404
        # And the picture is as closed as the text: not for a visitor at `off`.
        await case.switch("off")
        closed = await case.get(
            "visitor", f"/entities/{w.ids['Longsword']}/pictures/{case.public_picture}"
        )
        assert closed.status_code == 404
    finally:
        await w.done()


async def test_what_is_looked_at_is_the_release_and_not_what_was_edited_since(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    try:
        await case.switch("showcase")
        async with admin_session_factory() as session:
            await session.execute(
                update(PayloadDescription).values(content="Rewritten after the release")
            )
            await session.commit()
        body = (await case.get("visitor", "/preview")).text
        assert "A long blade." in body and "Rewritten" not in body
    finally:
        await w.done()


# --- Access ---------------------------------------


async def test_a_private_repository_is_not_looked_at_by_anyone_but_its_holders(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    longsword = w.ids["Longsword"]
    try:
        await case.switch("showcase")
        await set_visibility([w.repository], "private")
        for who in ("visitor", "stranger"):
            for path in ("/preview", f"/entities/{longsword}", "/entities"):
                assert (await case.get(who, path)).status_code == 404, (who, path)
        # A holder reads a private repository live: names, and the featured entries' text.
        assert _names(await case.get("holder", "/entities")) == ["Dagger", "Longsword", "Orc"]
        assert [e["name"] for e in (await case.get("holder", "/preview")).json()["entries"]] == [
            "Longsword",
            "Dagger",
        ]
    finally:
        await w.done()


async def test_looking_needs_a_signed_in_user(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    case = await _case(raw_client, fake_jwks_server)
    try:
        base = f"/repositories/{case.world.repository}"
        for path in ("/preview", f"/entities/{case.world.ids['Longsword']}"):
            assert (await raw_client.get(base + path)).status_code == 401, path
    finally:
        await case.world.done()


# --- The showcase ---------------------------------------


async def test_the_owner_features_up_to_twelve_entries_in_an_order(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    url = f"/tenants/{w.repository}/showcase"
    try:
        shown = (await w.author.get(url)).json()
        assert shown["limit"] == 12
        assert [e["name"] for e in shown["entries"]] == ["Longsword", "Dagger"]

        flipped = await w.author.put(
            url, json={"entity_ids": [str(w.ids["Dagger"]), str(w.ids["Longsword"])]}
        )
        assert [e["name"] for e in flipped.json()["entries"]] == ["Dagger", "Longsword"]
        assert (await w.author.put(url, json={"entity_ids": []})).json()["entries"] == []

        again = str(w.ids["Orc"])
        refused = await w.author.put(url, json={"entity_ids": [again, again]})
        assert (refused.status_code, refused.json()["type"]) == (422, "showcase-invalid")
        stranger_entry = await w.author.put(url, json={"entity_ids": [str(uuid.uuid4())]})
        assert stranger_entry.status_code == 422
        too_many = await w.author.put(
            url, json={"entity_ids": [str(uuid.uuid4()) for _ in range(13)]}
        )
        assert too_many.status_code == 422 and "At most 12" in too_many.json()["detail"]
        # Nothing the refusals asked for was kept.
        assert (await w.author.get(url)).json()["entries"] == []
    finally:
        await w.done()


async def test_an_entry_added_after_the_release_is_featured_from_the_release_that_has_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    from lorenzo_api.models import Entity

    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    try:
        await case.switch("showcase")
        async with admin_session_factory() as session:
            spear = Entity(tenant_id=w.repository, name="Spear")
            session.add(spear)
            await session.commit()
            spear_id = spear.id
        featured = await w.author.put(
            f"/tenants/{w.repository}/showcase",
            json={"entity_ids": [str(w.ids["Longsword"]), str(spear_id)]},
        )
        assert featured.status_code == 200
        # The release does not hold it yet: the preview says nothing of it.
        names = [e["name"] for e in (await case.get("visitor", "/preview")).json()["entries"]]
        assert names == ["Longsword"]
        await w.publish(label="2.0")
        names = [e["name"] for e in (await case.get("visitor", "/preview")).json()["entries"]]
        assert names == ["Longsword", "Spear"]
    finally:
        await w.done()


# --- The cache ---------------------------------------


async def test_a_release_read_for_the_preview_is_decoded_once(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    preview_module._cache.clear()
    case = await _case(raw_client, fake_jwks_server)
    w = case.world
    reads: list[uuid.UUID] = []
    real = preview_module.read_release_content

    async def counting(*args: Any, **kwargs: Any) -> Any:
        reads.append(kwargs["release_id"])
        return await real(*args, **kwargs)

    monkeypatch.setattr(preview_module, "read_release_content", counting)
    try:
        await case.switch("public")
        for _ in range(3):
            assert (await case.get("visitor", "/preview")).status_code == 200
            assert (await case.get("visitor", f"/entities/{w.ids['Orc']}")).status_code == 200
        assert len(reads) == 1

        # A new release is another document, read once again; the setting can turn it off.
        await w.publish(label="2.0")
        assert (await case.get("visitor", "/preview")).status_code == 200
        assert len(reads) == 2
        monkeypatch.setattr(get_settings(), "release_cache_entries", 0)
        preview_module._cache.clear()
        for _ in range(2):
            assert (await case.get("visitor", "/preview")).status_code == 200
        assert len(reads) == 4
    finally:
        preview_module._cache.clear()
        await w.done()
