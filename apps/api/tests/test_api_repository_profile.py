"""ADR 0213 through the real HTTP API: what a repository says about itself. An Owner
edits the profile and its cover, every member reads it, a library the repository is
granted to (and published to) reads it through the gated read, and `public` is
refused until the gates that come before it are built.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import func, select, text

from lorenzo_api.config import get_settings
from lorenzo_api.models import (
    AuditLog,
    Membership,
    MembershipRole,
    ProfilePicture,
    RepositoryProfile,
    Tenant,
    TenantKind,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
_JPEG = b"\xff\xd8\xff" + b"1" * 64

_DEFAULTS = {
    "visibility": "private",
    "preview": "showcase",
    "summary": "",
    "licence": None,
    "credits": [],
    "tags": [],
    "system": None,
    "languages": [],
    "has_cover": False,
}


async def _add_orga(tenant: uuid.UUID, actor: Actor) -> None:
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=tenant, user_id=actor.user_id, role=MembershipRole.ORGA))
        await session.commit()


async def _profile(actor: Actor, repository: uuid.UUID) -> dict[str, object]:
    response = await actor.get(f"/tenants/{repository}/profile")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def _without_stamp(profile: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in profile.items() if k != "updated_at"}


async def _grant_and_publish(
    owner: Actor, repository: uuid.UUID, library: uuid.UUID, *, publish: bool = True
) -> None:
    granted = await owner.put(f"/tenants/{repository}/subscribers/{library}")
    assert granted.status_code == 201, granted.text
    if publish:
        published = await owner.put(f"/tenants/{repository}/published")
        assert published.status_code == 200, published.text


# --- Reading ------------------------------------------------------------------------------


async def test_a_new_repository_is_private_with_an_empty_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    await _add_orga(faerun, orga)
    try:
        # Any member reads it, and what they read is the same.
        assert _without_stamp(await _profile(owner, faerun)) == _DEFAULTS
        assert _without_stamp(await _profile(orga, faerun)) == _DEFAULTS
        # It was made with the repository: one row, and nothing about it lives on `tenant`.
        async with admin_session_factory() as session:
            rows = await session.scalar(
                select(func.count()).where(RepositoryProfile.tenant_id == faerun)
            )
        assert rows == 1
    finally:
        await cleanup([faerun], [owner, orga])


async def test_a_play_tenant_has_no_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    table = await owner.create_tenant("My Table")
    try:
        for response in (
            await owner.get(f"/tenants/{table}/profile"),
            await owner.patch(f"/tenants/{table}/profile", json={"summary": "x"}),
            await owner.put(
                f"/tenants/{table}/profile/cover", files={"file": ("c.png", _PNG, "image/png")}
            ),
        ):
            assert response.status_code == 409, response.text
            assert response.json()["type"] == "not-a-repository"
        async with admin_session_factory() as session:
            rows = await session.scalar(
                select(func.count()).where(RepositoryProfile.tenant_id == table)
            )
        assert rows == 0
    finally:
        await cleanup([table], [owner])


async def test_somebody_who_is_not_a_member_finds_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        assert (
            await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        ).status_code == 204
        for response in (
            await stranger.get(f"/tenants/{faerun}/profile"),
            await stranger.patch(f"/tenants/{faerun}/profile", json={"summary": "mine now"}),
            await stranger.get(f"/tenants/{faerun}/profile/cover"),
            await stranger.put(f"/tenants/{faerun}/profile/cover", files=_png()),
            await stranger.delete(f"/tenants/{faerun}/profile/cover"),
        ):
            assert response.status_code == 404, response.text
            assert response.json()["type"] == "tenant-not-found"
        assert (await _profile(owner, faerun))["summary"] == ""
        assert (await _profile(owner, faerun))["has_cover"] is True
    finally:
        await cleanup([faerun], [owner, stranger])


async def test_a_repository_made_without_a_profile_gets_one_on_first_use(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Repositories that exist already, or are made some other way than `POST /tenants`,
    have no row until somebody asks: it is made then, private."""
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    async with admin_session_factory() as session:
        tenant = Tenant(name="Old Faerûn", kind=TenantKind.REPOSITORY)
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=owner.user_id, role=MembershipRole.OWNER)
        )
        await session.commit()
        faerun = tenant.id
    try:
        assert _without_stamp(await _profile(owner, faerun)) == _DEFAULTS
        patched = await owner.patch(f"/tenants/{faerun}/profile", json={"summary": "Back then."})
        assert patched.status_code == 200, patched.text
        assert (await _profile(owner, faerun))["summary"] == "Back then."
    finally:
        await cleanup([faerun], [owner])


# --- Writing ------------------------------------------------------------------------------


async def test_an_owner_sets_the_whole_profile_and_it_is_kept_tidy(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        patched = await owner.patch(
            f"/tenants/{faerun}/profile",
            json={
                "summary": "  The Forgotten\n  Realms,   statted.  ",
                "licence": {"label": " CC BY 4.0 ", "url": "https://creativecommons.org/by/4.0/"},
                "credits": [
                    {"name": " Ed Greenwood ", "role": "Setting", "url": "https://example.com/ed"},
                    {"name": "Mapmaker"},
                ],
                "tags": [" Forgotten Realms ", "SETTING", "setting", "d&d  5e"],
                "system": "  D&D   5e ",
                "languages": ["EN", "de", "en", "pt-BR"],
                "preview": "off",
            },
        )
        assert patched.status_code == 200, patched.text
        expected = {
            "visibility": "private",
            "preview": "off",
            "summary": "The Forgotten Realms, statted.",
            "licence": {"label": "CC BY 4.0", "url": "https://creativecommons.org/by/4.0/"},
            "credits": [
                {"name": "Ed Greenwood", "role": "Setting", "url": "https://example.com/ed"},
                {"name": "Mapmaker", "role": None, "url": None},
            ],
            "tags": ["forgotten realms", "setting", "d&d 5e"],
            "system": "D&D 5e",
            "languages": ["en", "de", "pt-br"],
            "has_cover": False,
        }
        assert _without_stamp(patched.json()) == expected
        assert _without_stamp(await _profile(owner, faerun)) == expected
    finally:
        await cleanup([faerun], [owner])


async def test_a_patch_changes_only_what_it_names_and_null_or_empty_clears(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        await owner.patch(
            f"/tenants/{faerun}/profile",
            json={
                "summary": "A summary.",
                "licence": {"label": "OGL"},
                "tags": ["one"],
                "system": "5e",
                "languages": ["en"],
                "credits": [{"name": "Me"}],
            },
        )
        # Only the summary named: everything else stays.
        again = await owner.patch(f"/tenants/{faerun}/profile", json={"summary": "Another."})
        assert again.status_code == 200
        body = again.json()
        assert body["summary"] == "Another."
        assert body["licence"] == {"label": "OGL", "url": None}
        assert (body["tags"], body["system"], body["languages"]) == (["one"], "5e", ["en"])
        assert body["credits"] == [{"name": "Me", "role": None, "url": None}]
        # Cleared: null for the single values, an empty list for the lists, an empty summary.
        cleared = await owner.patch(
            f"/tenants/{faerun}/profile",
            json={
                "licence": None,
                "system": None,
                "tags": [],
                "languages": [],
                "credits": [],
                "summary": "",
            },
        )
        assert cleared.status_code == 200, cleared.text
        assert _without_stamp(cleared.json()) == _DEFAULTS
        # A blank system is no system.
        await owner.patch(f"/tenants/{faerun}/profile", json={"system": "5e"})
        blank = await owner.patch(f"/tenants/{faerun}/profile", json={"system": "   "})
        assert blank.json()["system"] is None
        # An empty request changes nothing and is not an error.
        assert (await owner.patch(f"/tenants/{faerun}/profile", json={})).status_code == 200
    finally:
        await cleanup([faerun], [owner])


async def test_only_an_owner_edits_the_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    await _add_orga(faerun, orga)
    try:
        refused = await orga.patch(f"/tenants/{faerun}/profile", json={"summary": "Mine."})
        assert refused.status_code == 403
        assert refused.json()["type"] == "repository-management-forbidden"
        assert (await orga.put(f"/tenants/{faerun}/profile/cover", files=_png())).status_code == 403
        assert (
            await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        ).status_code == 204
        assert (await orga.delete(f"/tenants/{faerun}/profile/cover")).status_code == 403
        profile = await _profile(owner, faerun)
        assert (profile["summary"], profile["has_cover"]) == ("", True)
    finally:
        await cleanup([faerun], [owner, orga])


async def test_editing_the_profile_is_logged_by_field_name_not_by_text(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        await owner.patch(
            f"/tenants/{faerun}/profile", json={"summary": "Secret plans.", "tags": ["x"]}
        )
        await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        await owner.delete(f"/tenants/{faerun}/profile/cover")
        async with admin_session_factory() as session:
            entries = (
                await session.scalars(
                    select(AuditLog)
                    .where(
                        AuditLog.tenant_id == faerun, AuditLog.action.like("repository.profile%")
                    )
                    .order_by(AuditLog.created_at)
                )
            ).all()
        assert [(e.action, e.detail) for e in entries] == [
            ("repository.profile_updated", "fields=summary,tags"),
            ("repository.profile_cover_set", None),
            ("repository.profile_cover_removed", None),
        ]
    finally:
        await cleanup([faerun], [owner])


# --- The visibility is changed through its own route --------------------------------------


async def test_the_visibility_is_not_changed_through_the_profile_and_changes_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        await owner.put(f"/tenants/{faerun}/published")
        refused = await owner.patch(
            f"/tenants/{faerun}/profile", json={"visibility": "public", "summary": "Open to all."}
        )
        assert refused.status_code == 422
        problem = refused.json()
        assert problem["type"] == "visibility-has-its-own-route"
        assert "PUT or DELETE on /public" in problem["detail"]
        assert "tenant" not in (problem["title"] + problem["detail"]).lower()
        # Nothing of the request was kept, not even the summary beside it.
        assert _without_stamp(await _profile(owner, faerun)) == _DEFAULTS
        # Saying private, which it is, is fine, and so is every value of the preview switch.
        for body in (
            {"visibility": "private"},
            {"preview": "public"},
            {"preview": "showcase"},
            {"preview": "off"},
        ):
            assert (await owner.patch(f"/tenants/{faerun}/profile", json=body)).status_code == 200
        async with admin_session_factory() as session:
            visibility = await session.scalar(
                select(RepositoryProfile.visibility).where(RepositoryProfile.tenant_id == faerun)
            )
        assert visibility == "private"
    finally:
        await cleanup([faerun], [owner])


# --- Limits and the https rule ------------------------------------------------------------


async def _refused(owner: Actor, repository: uuid.UUID, body: dict[str, object]) -> None:
    response = await owner.patch(f"/tenants/{repository}/profile", json=body)
    assert response.status_code == 422, (body, response.text)
    assert response.headers["content-type"] == "application/problem+json"
    assert _without_stamp(await _profile(owner, repository)) == _DEFAULTS, body


async def test_values_over_the_limits_or_of_the_wrong_shape_are_refused(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        for body in (
            {"summary": "x" * 281},
            {"summary": None},
            {"visibility": None},
            {"visibility": "hidden"},
            {"preview": None},
            {"preview": "everything"},
            {"tags": [f"tag{i}" for i in range(13)]},
            {"tags": ["x" * 33]},
            {"tags": ["   "]},
            {"tags": None},
            {"system": "x" * 41},
            {"languages": ["english"]},
            {"languages": ["e"]},
            {"languages": ["en", "de", "fr", "es", "it", "pt", "nl", "pl", "sv"]},
            {"licence": {"label": ""}},
            {"licence": {"label": "x" * 81}},
            {"licence": {"url": "https://example.com"}},
            {"credits": [{"name": ""}]},
            {"credits": [{"name": "x" * 81}]},
            {"credits": [{"name": "Me", "role": "x" * 61}]},
            {"credits": [{"name": "Me"}] * 21},
            {"name": "Renamed"},
            {"published_at": "2026-01-01T00:00:00Z"},
        ):
            await _refused(owner, faerun, body)
        # The limits themselves are allowed.
        ok = await owner.patch(
            f"/tenants/{faerun}/profile",
            json={
                "summary": "x" * 280,
                "tags": [f"{i:02}" + "x" * 30 for i in range(12)],
                "system": "x" * 40,
                "languages": ["en", "de", "fr", "es", "it", "pt", "nl", "pl"],
                "licence": {"label": "x" * 80},
                "credits": [{"name": f"p{i}"} for i in range(20)],
            },
        )
        assert ok.status_code == 200, ok.text
    finally:
        await cleanup([faerun], [owner])


async def test_links_are_https_only(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        for bad in (
            "http://example.com/licence",
            "javascript:alert(1)",
            "data:text/html,<b>x</b>",
            "ftp://example.com/x",
            "mailto:me@example.com",
            "//example.com/x",
            "example.com/x",
            "https://",
            "https:///path",
            "https://user:secret@example.com/x",
            "https://exa mple.com/x",
            "https://example.com/" + "x" * 500,
            " ",
            "",
        ):
            await _refused(owner, faerun, {"licence": {"label": "L", "url": bad}})
            await _refused(owner, faerun, {"credits": [{"name": "Me", "url": bad}]})
        good = await owner.patch(
            f"/tenants/{faerun}/profile",
            json={
                "licence": {"label": "L", "url": "https://example.com/licence?v=1#top"},
                "credits": [{"name": "Me", "url": "https://example.org"}],
            },
        )
        assert good.status_code == 200, good.text
        assert good.json()["licence"]["url"] == "https://example.com/licence?v=1#top"
    finally:
        await cleanup([faerun], [owner])


# --- The cover ----------------------------------------------------------------------------


def _png() -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("cover.png", _PNG, "image/png")}


async def test_an_owner_sets_replaces_and_removes_the_cover(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    await _add_orga(faerun, orga)
    before = await _blob_total()
    try:
        nothing = await orga.get(f"/tenants/{faerun}/profile/cover")
        assert nothing.status_code == 404
        assert nothing.json()["type"] == "profile-picture-not-found"

        assert (
            await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        ).status_code == 204
        assert (await _profile(orga, faerun))["has_cover"] is True
        got = await orga.get(f"/tenants/{faerun}/profile/cover")
        assert (got.status_code, got.content, got.headers["content-type"]) == (
            200,
            _PNG,
            "image/png",
        )

        replaced = await owner.put(
            f"/tenants/{faerun}/profile/cover", files={"file": ("c.jpg", _JPEG, "image/jpeg")}
        )
        assert replaced.status_code == 204
        got = await orga.get(f"/tenants/{faerun}/profile/cover")
        assert (got.content, got.headers["content-type"]) == (_JPEG, "image/jpeg")

        assert (await owner.delete(f"/tenants/{faerun}/profile/cover")).status_code == 204
        assert (await _profile(owner, faerun))["has_cover"] is False
        assert (await owner.get(f"/tenants/{faerun}/profile/cover")).status_code == 404
        # Removing what is not there is not an error.
        assert (await owner.delete(f"/tenants/{faerun}/profile/cover")).status_code == 204
        assert await _blob_total() == before
    finally:
        await cleanup([faerun], [owner, orga])


async def test_the_cover_takes_the_pictures_types_and_cap_and_one_blob_is_kept(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        before = await _blob_total()
        wrong_type = await owner.put(
            f"/tenants/{faerun}/profile/cover", files={"file": ("a.txt", b"hello", "text/plain")}
        )
        assert wrong_type.status_code == 422
        assert wrong_type.json()["type"] == "invalid-profile-picture"
        too_big = await owner.put(
            f"/tenants/{faerun}/profile/cover",
            files={
                "file": (
                    "a.png",
                    b"0" * (get_settings().profile_picture_max_bytes + 1),
                    "image/png",
                )
            },
        )
        assert too_big.status_code == 422
        assert (await _profile(owner, faerun))["has_cover"] is False
        await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        assert await _blob_total() == before + 1
        await owner.delete(f"/tenants/{faerun}/profile/cover")
        assert await _blob_total() == before
    finally:
        await cleanup([faerun], [owner])


async def _blob_total() -> int:
    async with admin_session_factory() as session:
        return await session.scalar(select(func.count()).select_from(ProfilePicture)) or 0


async def test_deleting_a_repository_takes_its_cover_with_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    try:
        before = await _blob_total()
        await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        assert await _blob_total() == before + 1
        assert (await owner.delete(f"/tenants/{faerun}")).status_code == 204
        assert await _blob_total() == before
    finally:
        await cleanup([faerun], [owner])


# --- What a library that holds the repository reads ---------------------------------------


async def test_a_library_the_repository_is_granted_to_reads_its_profile_once_published(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        await owner.patch(
            f"/tenants/{faerun}/profile",
            json={"summary": "Realms.", "tags": ["setting"], "system": "5e"},
        )
        await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        path = f"/tenants/{table}/repositories/{faerun}"

        # Nothing is granted: it is not theirs to read, and it does not say whether it exists.
        for response in (await gm.get(f"{path}/profile"), await gm.get(f"{path}/profile/cover")):
            assert response.status_code == 404
            assert response.json()["type"] == "repository-not-found"

        # Granted but still a draft: invisible, as every read of it is.
        await _grant_and_publish(owner, faerun, table, publish=False)
        assert (await gm.get(f"{path}/profile")).status_code == 404

        await owner.put(f"/tenants/{faerun}/published")
        seen = await gm.get(f"{path}/profile")
        assert seen.status_code == 200, seen.text
        assert _without_stamp(seen.json()) == {
            **_DEFAULTS,
            "summary": "Realms.",
            "tags": ["setting"],
            "system": "5e",
            "has_cover": True,
        }
        cover = await gm.get(f"{path}/profile/cover")
        assert (cover.status_code, cover.content) == (200, _PNG)

        # Withdrawn again, it is gone for them.
        await owner.delete(f"/tenants/{faerun}/published")
        assert (await gm.get(f"{path}/profile")).status_code == 404
        assert (await gm.get(f"{path}/profile/cover")).status_code == 404
    finally:
        await cleanup([faerun, table], [owner, gm])


async def test_a_library_it_is_not_granted_to_and_a_stranger_read_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    other = await make_actor(raw_client, fake_jwks_server, "other")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    elsewhere = await other.create_tenant("Elsewhere")
    try:
        await _grant_and_publish(owner, faerun, table)
        # Another library, not granted, and somebody else's library id.
        not_granted = await other.get(f"/tenants/{elsewhere}/repositories/{faerun}/profile")
        assert not_granted.status_code == 404
        assert not_granted.json()["type"] == "repository-not-found"
        into_theirs = await other.get(f"/tenants/{table}/repositories/{faerun}/profile")
        assert into_theirs.status_code == 404
        assert into_theirs.json()["type"] == "tenant-not-found"
        # And the holder cannot write it, whatever the path says.
        for response in (
            await gm.patch(f"/tenants/{faerun}/profile", json={"summary": "Mine."}),
            await gm.patch(f"/tenants/{table}/repositories/{faerun}/profile", json={}),
            await gm.put(f"/tenants/{table}/repositories/{faerun}/profile/cover", files=_png()),
        ):
            assert response.status_code in (404, 405), response.text
        assert (await _profile(owner, faerun))["summary"] == ""
    finally:
        await cleanup([faerun, table, elsewhere], [owner, gm, other])


async def test_a_copy_does_not_carry_the_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await owner.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        created = await owner.post(
            f"/tenants/{faerun}/items",
            json={"name": "Longsword", "prototype_ids": [], "in_public_catalog": False},
        )
        assert created.status_code == 201, created.text
        await owner.patch(f"/tenants/{faerun}/profile", json={"summary": "Realms."})
        await owner.put(f"/tenants/{faerun}/profile/cover", files=_png())
        await _grant_and_publish(owner, faerun, table)
        copied = await gm.post(f"/tenants/{table}/repositories/{faerun}/copy", json={})
        assert copied.status_code == 201, copied.text
        async with admin_session_factory() as session:
            rows = await session.scalar(
                text("SELECT count(*) FROM repository_profile WHERE tenant_id = :t").bindparams(
                    t=table
                )
            )
        assert rows == 0
        # A play tenant has no profile to read, so its own routes say what they say of any.
        assert (await gm.get(f"/tenants/{table}/profile")).status_code == 409
    finally:
        await cleanup([faerun, table], [owner, gm])
