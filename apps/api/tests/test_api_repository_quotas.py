"""ADR 0298: quotas on a repository - how many entries, how many picture bytes in all, how large
one picture - through the real HTTP API, and never on a play library."""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from conftest import delete_tenant
from httpx import AsyncClient
from sqlalchemy import func, select

from lorenzo_api.config import get_settings
from lorenzo_api.exceptions import RepositoryEntryLimitError
from lorenzo_api.models import (
    Entity,
    Information,
    Item,
    Payload,
    PayloadPicture,
    ProfilePicture,
    RepositoryProfile,
    Tenant,
)
from lorenzo_api.repository_quotas import entries_held, picture_bytes_held, shown_size

_PNG = b"\x89PNG\r\n\x1a\n"


def _picture(size: int) -> bytes:
    return _PNG + b"0" * (size - len(_PNG))


def _limits(
    monkeypatch: pytest.MonkeyPatch,
    *,
    entries: int = 0,
    total: int = 0,
    single: int = 0,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "repository_max_entries", entries)
    monkeypatch.setattr(settings, "repository_max_picture_bytes", total)
    monkeypatch.setattr(settings, "repository_picture_max_bytes", single)


async def _entries(tenant_id: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(Entity).where(Entity.tenant_id == tenant_id)
            )
            or 0
        )


async def _pictures(tenant_id: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(PayloadPicture)
                .where(PayloadPicture.tenant_id == tenant_id)
            )
            or 0
        )


async def _entry(owner: Actor, tenant_id: uuid.UUID, name: str = "Entry", **body: Any) -> Any:
    return await owner.post(
        f"/tenants/{tenant_id}/entities", json={"name": name, "kinds": ["item"], **body}
    )


async def _made(owner: Actor, tenant_id: uuid.UUID, name: str = "Entry") -> uuid.UUID:
    response = await _entry(owner, tenant_id, name)
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _set_picture(
    owner: Actor, tenant_id: uuid.UUID, entity_id: uuid.UUID, data: bytes
) -> Any:
    return await owner.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/picture",
        files={"file": ("p.png", data, "image/png")},
    )


# --- Entries ------------------------------------------------------------------------------


async def test_a_repository_takes_entries_up_to_its_limit_and_refuses_one_over(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        _limits(monkeypatch, entries=3)
        for name in ("One", "Two", "Three"):
            await _made(owner, repository, name)

        refused = await _entry(owner, repository, "Four")

        assert refused.status_code == 422, refused.text
        body = refused.json()
        assert body["type"] == "repository-entry-limit"
        assert body["detail"] == (
            "This repository holds 3 entries, which is the most a repository can have."
        )
        assert (body["quota"], body["limit"], body["holds"]) == ("entries", 3, 3)
        # Nothing of the refused write is kept: no entry, no link name.
        assert await _entries(repository) == 3
        refused_with_slug = await _entry(owner, repository, "Five", slug="five")
        assert refused_with_slug.status_code == 422
        assert await _entries(repository) == 3
    finally:
        await cleanup([repository], [owner])


async def test_every_way_of_making_an_entry_is_held_to_the_limit(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        await _made(owner, repository)
        _limits(monkeypatch, entries=1)

        # The entries route with other kinds, the item route the importer used before it, a
        # group, and a row an ORM session adds by itself.
        being = await owner.post(
            f"/tenants/{repository}/entities", json={"name": "Orc", "kinds": ["being"]}
        )
        item = await owner.post(f"/tenants/{repository}/items", json={"name": "Sword"})
        group = await owner.post(f"/tenants/{repository}/groups", json={"name": "Harpers"})
        for response in (being, item, group):
            assert response.status_code == 422, response.text
            assert response.json()["type"] == "repository-entry-limit"
        async with admin_session_factory() as session:
            session.add(Entity(tenant_id=repository, name="Direct"))
            with pytest.raises(RepositoryEntryLimitError):
                await session.flush()
            await session.rollback()
        assert await _entries(repository) == 1
    finally:
        await cleanup([repository], [owner])


async def test_a_client_made_id_replayed_at_the_limit_is_not_a_new_entry(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        _limits(monkeypatch, entries=1)
        entry_id = str(uuid.uuid4())
        first = await _entry(owner, repository, "Once", id=entry_id)
        again = await _entry(owner, repository, "Once", id=entry_id)
        other = await _entry(owner, repository, "Twice", id=str(uuid.uuid4()))

        assert first.status_code == 201, first.text
        assert again.status_code == 200, again.text
        assert other.status_code == 422
    finally:
        await cleanup([repository], [owner])


async def test_deleting_an_entry_frees_room(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        _limits(monkeypatch, entries=2)
        first = await _made(owner, repository, "One")
        await _made(owner, repository, "Two")
        assert (await _entry(owner, repository, "Three")).status_code == 422

        deleted = await owner.delete(f"/tenants/{repository}/entities/{first}")
        assert deleted.status_code == 204, deleted.text

        assert (await _entry(owner, repository, "Three")).status_code == 201
    finally:
        await cleanup([repository], [owner])


async def test_a_repository_over_a_lowered_limit_can_still_be_changed_and_shrunk(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        ids = [await _made(owner, repository, f"Entry {i}") for i in range(4)]
        _limits(monkeypatch, entries=2, total=1, single=1_000_000)

        slug = await owner.put(
            f"/tenants/{repository}/entities/{ids[0]}/slug", json={"slug": "kept"}
        )
        assert slug.status_code in (200, 201), slug.text
        note = await owner.post(
            f"/tenants/{repository}/entities/{ids[0]}/information",
            json={"title": "Note", "type": "note", "is_public": False, "content": "Text."},
        )
        assert note.status_code == 201, note.text
        assert (await _entry(owner, repository, "More")).status_code == 422

        for entry_id in ids[:3]:
            deleted = await owner.delete(f"/tenants/{repository}/entities/{entry_id}")
            assert deleted.status_code == 204, deleted.text
        # One entry is under the limit of two, so there is room for one more, and no more.
        assert (await _entry(owner, repository, "Back")).status_code == 201
        assert (await _entry(owner, repository, "Over")).status_code == 422
    finally:
        await cleanup([repository], [owner])


async def test_a_play_library_is_never_limited(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    table = await owner.create_tenant("My Table")
    try:
        _limits(monkeypatch, entries=1, total=10, single=10)
        entry = await _made(owner, table, "One")
        await _made(owner, table, "Two")
        await _made(owner, table, "Three")
        picture = await _set_picture(owner, table, entry, _picture(400))
        another = await _set_picture(owner, table, await _made(owner, table, "Four"), _picture(400))

        assert picture.status_code == 201, picture.text
        assert another.status_code == 201, another.text
        assert await _entries(table) == 4
    finally:
        await cleanup([table], [owner])


async def test_a_limit_of_zero_takes_it_off(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        _limits(monkeypatch, entries=0, total=0, single=0)
        entry = await _made(owner, repository)
        await _made(owner, repository, "Two")
        assert (
            await _set_picture(owner, repository, entry, _picture(1_500_000))
        ).status_code == 201
    finally:
        await cleanup([repository], [owner])


# --- Pictures -----------------------------------------------------------------------------


async def test_one_picture_over_the_single_limit_is_a_413_and_writes_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        entry = await _made(owner, repository)
        _limits(monkeypatch, single=1_000)

        ok = await _set_picture(owner, repository, entry, _picture(1_000))
        too_large = await _set_picture(
            owner, repository, await _made(owner, repository, "B"), _picture(1_001)
        )
        note = await owner.post(
            f"/tenants/{repository}/entities/{entry}/information",
            json={"title": "Note", "type": "note", "is_public": False, "content": "Text."},
        )
        as_payload = await owner.post(
            f"/tenants/{repository}/information/{note.json()['id']}/payloads",
            files={"file": ("p.png", _picture(2_000), "image/png")},
        )

        assert ok.status_code == 201, ok.text
        assert too_large.status_code == 413, too_large.text
        body = too_large.json()
        assert body["type"] == "repository-picture-too-large"
        assert body["detail"] == (
            "This picture is 1 kB, and a picture in a repository can be 1 kB at most."
        )
        assert (body["quota"], body["limit"], body["size"]) == ("picture_size", 1_000, 1_001)
        assert as_payload.status_code == 413, as_payload.text
        assert await _pictures(repository) == 1
        async with admin_session_factory() as session:
            main_pictures = await session.scalar(
                select(func.count())
                .select_from(Information)
                .where(Information.tenant_id == repository, Information.type == "main_picture")
            )
            payloads = await session.scalar(
                select(func.count())
                .select_from(Payload)
                .where(
                    Payload.tenant_id == repository,
                    Payload.information_id == uuid.UUID(note.json()["id"]),
                )
            )
        assert main_pictures == 1
        assert payloads == 1  # the note's own text, and no picture beside it
    finally:
        await cleanup([repository], [owner])


async def test_the_pictures_of_a_repository_are_held_to_their_total(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        a, b, c = [await _made(owner, repository, n) for n in "ABC"]
        _limits(monkeypatch, total=1_000)

        first = await _set_picture(owner, repository, a, _picture(600))
        second = await _set_picture(owner, repository, b, _picture(400))
        refused = await _set_picture(owner, repository, c, _picture(100))

        assert (first.status_code, second.status_code) == (201, 201)
        assert refused.status_code == 422, refused.text
        body = refused.json()
        assert body["type"] == "repository-picture-total-limit"
        assert body["detail"] == (
            "The pictures in this repository take up 1 kB, and this one would take them past "
            "1 kB, the most a repository can hold."
        )
        assert (body["quota"], body["limit"], body["holds"], body["adding"]) == (
            "picture_total",
            1_000,
            1_000,
            100,
        )
        assert await _pictures(repository) == 2
        async with admin_session_factory() as session:
            assert await session.run_sync(lambda s: picture_bytes_held(s, repository)) == 1_000
    finally:
        await cleanup([repository], [owner])


async def test_replacing_and_removing_pictures_move_the_total_only_by_what_they_change(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        a, b = [await _made(owner, repository, n) for n in "AB"]
        _limits(monkeypatch, total=1_000)
        assert (await _set_picture(owner, repository, a, _picture(600))).status_code == 201
        assert (await _set_picture(owner, repository, b, _picture(400))).status_code == 201

        # Replacing one with a smaller one, or one of the same size, is room it already had.
        assert (await _set_picture(owner, repository, a, _picture(500))).status_code == 200
        assert (await _set_picture(owner, repository, a, _picture(500))).status_code == 200
        # One larger that goes past the total is refused, and the old one is kept.
        grown = await _set_picture(owner, repository, a, _picture(700))
        assert grown.status_code == 422, grown.text
        # Over a lowered limit, replacing with a smaller one is still allowed.
        _limits(monkeypatch, total=500)
        assert (await _set_picture(owner, repository, a, _picture(300))).status_code == 200
        assert (await _set_picture(owner, repository, a, _picture(301))).status_code == 422

        # Removing a picture gives its bytes back.
        cleared = await owner.delete(f"/tenants/{repository}/entities/{b}/picture")
        assert cleared.status_code == 204, cleared.text
        assert (await _set_picture(owner, repository, b, _picture(200))).status_code == 201
        async with admin_session_factory() as session:
            assert await session.run_sync(lambda s: picture_bytes_held(s, repository)) == 500
    finally:
        await cleanup([repository], [owner])


async def test_a_repositorys_cover_is_not_one_of_its_entries_pictures(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        _limits(monkeypatch, total=10, single=10)

        cover = await owner.put(
            f"/tenants/{repository}/profile/cover",
            files={"file": ("c.png", _picture(5_000), "image/png")},
        )

        # The cover is bounded by the limit of every profile picture, and counted nowhere else.
        assert cover.status_code == 204, cover.text
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, repository)
            assert profile.cover_picture_id is not None
            picture = await session.get_one(ProfilePicture, profile.cover_picture_id)
            assert len(picture.data) == 5_000
            assert await session.run_sync(lambda s: picture_bytes_held(s, repository)) == 0
        too_large = await owner.put(
            f"/tenants/{repository}/profile/cover",
            files={
                "file": (
                    "c.png",
                    _picture(get_settings().profile_picture_max_bytes + 1),
                    "image/png",
                )
            },
        )
        assert too_large.status_code == 422
    finally:
        await cleanup([repository], [owner])


# --- Copies and updates into a repository -------------------------------------------------


async def _source(owner: Actor, repository: uuid.UUID, entries: int, picture: int = 0) -> None:
    async with admin_session_factory() as session:
        for i in range(entries):
            entity = Entity(tenant_id=repository, name=f"Source {i}")
            session.add(entity)
            await session.flush()
            session.add(Item(entity_id=entity.id, tenant_id=repository))
            if picture and i == 0:
                information = Information(
                    tenant_id=repository,
                    entity_id=entity.id,
                    title="Picture",
                    type="note",
                    is_public=False,
                )
                session.add(information)
                await session.flush()
                payload = Payload(tenant_id=repository, information_id=information.id)
                session.add(payload)
                await session.flush()
                session.add(
                    PayloadPicture(
                        payload_id=payload.id,
                        tenant_id=repository,
                        data=_picture(picture),
                        file_type="image/png",
                    )
                )
        await session.commit()


async def _share(owner: Actor, repository: uuid.UUID, *subscribers: uuid.UUID) -> None:
    for subscriber in subscribers:
        response = await owner.put(f"/tenants/{repository}/subscribers/{subscriber}")
        assert response.status_code in (200, 201), response.text
    assert (await owner.put(f"/tenants/{repository}/published")).status_code == 200


async def test_a_copy_that_would_go_past_a_repositorys_entry_limit_is_refused_whole(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    builder = await make_actor(raw_client, fake_jwks_server, "builder")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    source = await author.create_tenant("Armoury", kind="repository")
    bridge = await builder.create_tenant("Bridge", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        await _source(author, source, 5)
        await _share(author, source, bridge, table)
        await _made(builder, bridge, "Own")

        _limits(monkeypatch, entries=5)
        refused = await builder.post(f"/tenants/{bridge}/repositories/{source}/copy")

        assert refused.status_code == 422, refused.text
        assert refused.json()["type"] == "repository-entry-limit"
        assert refused.json()["detail"] == (
            "This would make 6 entries in this repository, and a repository can have 5 at "
            "most. It holds 1."
        )
        assert await _entries(bridge) == 1

        # The same copy into a play library is not limited, and a roomier repository takes it.
        assert (await gm.post(f"/tenants/{table}/repositories/{source}/copy")).status_code == 201
        _limits(monkeypatch, entries=6)
        copied = await builder.post(f"/tenants/{bridge}/repositories/{source}/copy")
        assert copied.status_code == 201, copied.text
        assert await _entries(bridge) == 6
    finally:
        await cleanup([source, bridge, table], [author, builder, gm])


async def test_a_copy_that_would_go_past_the_picture_limits_is_refused_whole(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    builder = await make_actor(raw_client, fake_jwks_server, "builder")
    source = await author.create_tenant("Armoury", kind="repository")
    bridge = await builder.create_tenant("Bridge", kind="repository")
    try:
        await _source(author, source, 2, picture=800)
        await _share(author, source, bridge)

        _limits(monkeypatch, single=500)
        too_large = await builder.post(f"/tenants/{bridge}/repositories/{source}/copy")
        _limits(monkeypatch, total=700)
        past_total = await builder.post(f"/tenants/{bridge}/repositories/{source}/copy")

        assert too_large.status_code == 413, too_large.text
        assert past_total.status_code == 422, past_total.text
        assert past_total.json()["type"] == "repository-picture-total-limit"
        assert await _entries(bridge) == 0
        assert await _pictures(bridge) == 0

        _limits(monkeypatch, total=800, single=800)
        assert (
            await builder.post(f"/tenants/{bridge}/repositories/{source}/copy")
        ).status_code == 201
        assert await _pictures(bridge) == 1
    finally:
        await cleanup([source, bridge], [author, builder])


async def test_an_update_that_adds_entries_is_held_to_a_repositorys_limit(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    builder = await make_actor(raw_client, fake_jwks_server, "builder")
    source = await author.create_tenant("Armoury", kind="repository")
    bridge = await builder.create_tenant("Bridge", kind="repository")
    try:
        await _source(author, source, 2)
        await _share(author, source, bridge)
        assert (
            await builder.post(f"/tenants/{bridge}/repositories/{source}/copy")
        ).status_code == 201
        await _source(author, source, 1)
        url = f"/tenants/{bridge}/repositories/{source}/updates"
        added = (await builder.get(url)).json()["added"]
        assert len(added) == 1
        action = {"kind": "entity", "source_id": added[0]["source_id"], "action": "add"}

        _limits(monkeypatch, entries=2)
        refused = await builder.post(url, json={"actions": [action]})
        _limits(monkeypatch, entries=3)
        taken = await builder.post(url, json={"actions": [action]})

        assert refused.status_code == 422, refused.text
        assert refused.json()["type"] == "repository-entry-limit"
        assert taken.status_code == 200, taken.text
        assert await _entries(bridge) == 3
    finally:
        await cleanup([source, bridge], [author, builder])


# --- A play library's own checks stay as they were ----------------------------------------


async def test_the_existing_picture_cap_still_answers_422_for_every_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    from conftest import make_tenant

    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Sword")
        session.add(entity)
        await session.flush()
        entity_id = entity.id
        await session.commit()
    try:
        response = await client.put(
            f"/tenants/{tenant_id}/entities/{entity_id}/picture",
            files={"file": ("a.png", _picture(get_settings().picture_max_bytes + 1), "image/png")},
        )
        assert response.status_code == 422
        assert response.json()["type"] == "invalid-picture"
    finally:
        await delete_tenant(tenant_id)


# --- The words and the cost ----------------------------------------------------------------


def test_sizes_are_read_in_words_people_use() -> None:
    assert shown_size(12) == "12 bytes"
    assert shown_size(1_000) == "1 kB"
    assert shown_size(250_400) == "250 kB"
    assert shown_size(1_000_000) == "1 MB"
    assert shown_size(1_400_000) == "1.4 MB"
    assert shown_size(50_000_000) == "50 MB"
    assert shown_size(999_999) == "1 MB"


async def test_the_check_counts_the_tenants_entries(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    repository = await owner.create_tenant("Faerûn", kind="repository")
    try:
        await _made(owner, repository)
        async with admin_session_factory() as session:
            assert await session.run_sync(lambda s: entries_held(s, repository)) == 1
            tenant = await session.get_one(Tenant, repository)
            assert tenant.name == "Faerûn"
    finally:
        await cleanup([repository], [owner])


def test_no_core_insert_of_an_entry_or_a_picture_goes_round_the_check() -> None:
    """The flush hook sees ORM rows; a Core `insert(Entity)` or `insert(PayloadPicture)` would
    not be seen, so the copy engine's `write_rows` (which calls `check_rows`) is the only place
    one may be."""
    import re
    from pathlib import Path

    import lorenzo_api

    package = Path(lorenzo_api.__file__).parent
    pattern = re.compile(r"insert\(\s*(Entity|PayloadPicture)\b|(Entity|PayloadPicture)\.__table__")
    found = {
        path.name
        for path in package.rglob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    }

    assert found == set(), found
