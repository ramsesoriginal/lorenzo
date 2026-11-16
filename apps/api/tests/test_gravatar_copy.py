"""The one-time Gravatar copy (ADR 0439): asked once when an email is first cached, kept as the
account's own picture, never asked again, never a redirect, never a failed login."""

import hashlib
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient

from lorenzo_api import gravatar
from lorenzo_api.config import get_settings
from lorenzo_api.models import ProfilePicture, User, UserProfilePicture

_PNG = b"\x89PNG\r\n\x1a\n" + b"gravatar-bytes"


class FakeGravatar:
    """A local stand-in for www.gravatar.com: answers by path and records what was asked."""

    def __init__(self) -> None:
        self.requests: list[str] = []
        self.reply: tuple[int, str, bytes, dict[str, str]] = (200, "image/png", _PNG, {})
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib's own API
                outer.requests.append(self.path)
                status, content_type, body, headers = outer.reply
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._server = HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host!s}:{port}"

    def shutdown(self) -> None:
        self._server.shutdown()


@pytest.fixture
def fake_gravatar(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGravatar]:
    server = FakeGravatar()
    monkeypatch.setattr(get_settings(), "gravatar_lookup_enabled", True)
    monkeypatch.setattr(get_settings(), "gravatar_base_url", server.base_url)
    yield server
    server.shutdown()


async def _sign_up(raw_client: AsyncClient, jwks: FakeJwksServer, email: str) -> uuid.UUID:
    token = jwks.issue_token(f"authgear|{uuid.uuid4()}")
    jwks.register_userinfo(token, email=email, email_verified=True)
    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    return uuid.UUID(response.json()["id"])


async def _forget(user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        link = await session.get(UserProfilePicture, user_id)
        if link is not None:
            await session.delete(await session.get_one(ProfilePicture, link.profile_picture_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_a_new_account_gets_its_gravatar_once_as_its_own_picture(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, fake_gravatar: FakeGravatar
) -> None:
    email = f"Copy-{uuid.uuid4()}@Example.com "
    user_id = await _sign_up(raw_client, fake_jwks_server, email)

    digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    assert fake_gravatar.requests == [f"/avatar/{digest}?d=404&s=200"]

    picture = await raw_client.get(f"/users/{user_id}/picture", follow_redirects=False)
    assert picture.status_code == 200
    assert picture.content == _PNG
    assert picture.headers["content-type"] == "image/png"

    async with admin_session_factory() as session:
        assert (await session.get_one(User, user_id)).gravatar_checked_at is not None
    await _forget(user_id)


async def test_an_email_without_a_gravatar_leaves_no_picture_and_is_not_asked_again(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, fake_gravatar: FakeGravatar
) -> None:
    fake_gravatar.reply = (404, "text/plain", b"", {})
    user_id = await _sign_up(raw_client, fake_jwks_server, f"{uuid.uuid4()}@example.com")

    assert (await raw_client.get(f"/users/{user_id}/picture")).status_code == 404
    async with admin_session_factory() as session:
        user = await session.get_one(User, user_id)
        assert user.gravatar_checked_at is not None
        await gravatar.copy_once(session, user)
        await gravatar.copy_once(session, user)
    assert len(fake_gravatar.requests) == 1
    await _forget(user_id)


async def test_a_deleted_picture_is_not_fetched_again(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, fake_gravatar: FakeGravatar
) -> None:
    user_id = await _sign_up(raw_client, fake_jwks_server, f"{uuid.uuid4()}@example.com")
    async with admin_session_factory() as session:
        link = await session.get_one(UserProfilePicture, user_id)
        await session.delete(await session.get_one(ProfilePicture, link.profile_picture_id))
        await session.commit()

    async with admin_session_factory() as session:
        await gravatar.copy_once(session, await session.get_one(User, user_id))

    assert len(fake_gravatar.requests) == 1
    assert (await raw_client.get(f"/users/{user_id}/picture")).status_code == 404
    await _forget(user_id)


@pytest.mark.parametrize(
    "reply",
    [
        (500, "text/plain", b"nope", {}),
        (302, "text/plain", b"", {"Location": "https://elsewhere.invalid/x"}),
        (200, "text/html", b"<html></html>", {}),
        (200, "image/png", b"", {}),
    ],
    ids=["server-error", "redirect-not-followed", "not-an-image", "empty"],
)
async def test_an_unusable_answer_stores_nothing_and_does_not_fail_the_login(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    fake_gravatar: FakeGravatar,
    reply: tuple[int, str, bytes, dict[str, str]],
) -> None:
    fake_gravatar.reply = reply
    user_id = await _sign_up(raw_client, fake_jwks_server, f"{uuid.uuid4()}@example.com")

    assert (await raw_client.get(f"/users/{user_id}/picture")).status_code == 404
    async with admin_session_factory() as session:
        assert (await session.get_one(User, user_id)).gravatar_checked_at is None
    await _forget(user_id)


async def test_an_oversized_answer_is_not_kept(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    fake_gravatar: FakeGravatar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "profile_picture_max_bytes", len(_PNG) - 1)
    user_id = await _sign_up(raw_client, fake_jwks_server, f"{uuid.uuid4()}@example.com")

    assert (await raw_client.get(f"/users/{user_id}/picture")).status_code == 404
    await _forget(user_id)


async def test_nothing_is_asked_when_the_deployment_turns_the_lookup_off(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    fake_gravatar: FakeGravatar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "gravatar_lookup_enabled", False)
    user_id = await _sign_up(raw_client, fake_jwks_server, f"{uuid.uuid4()}@example.com")

    assert fake_gravatar.requests == []
    assert (await raw_client.get(f"/users/{user_id}/picture")).status_code == 404
    await _forget(user_id)


async def test_an_account_that_existed_before_is_never_asked(fake_gravatar: FakeGravatar) -> None:
    """The migration marks every existing account as answered (ADR 0439: no backfill)."""
    async with admin_session_factory() as session:
        user = User(
            authgear_subject_id=f"authgear|old-{uuid.uuid4()}", email=f"{uuid.uuid4()}@e.co"
        )
        session.add(user)
        await session.commit()
        user_id = user.id
        # What the migration did to a row that existed when it ran.
        from datetime import UTC, datetime

        user.gravatar_checked_at = datetime.now(UTC)
        await session.commit()
        await gravatar.copy_once(session, user)

    assert fake_gravatar.requests == []
    await _forget(user_id)


async def test_an_account_with_its_own_picture_keeps_it(fake_gravatar: FakeGravatar) -> None:
    async with admin_session_factory() as session:
        user = User(
            authgear_subject_id=f"authgear|own-{uuid.uuid4()}", email=f"{uuid.uuid4()}@e.co"
        )
        session.add(user)
        await session.flush()
        picture = ProfilePicture(data=b"mine", file_type="image/png")
        session.add(picture)
        await session.flush()
        session.add(UserProfilePicture(user_id=user.id, profile_picture_id=picture.id))
        await session.commit()
        user_id = user.id

        await gravatar.copy_once(session, user)

        assert fake_gravatar.requests == []
        assert (await session.get_one(ProfilePicture, picture.id)).data == b"mine"
        assert user.gravatar_checked_at is not None
    await _forget(user_id)
