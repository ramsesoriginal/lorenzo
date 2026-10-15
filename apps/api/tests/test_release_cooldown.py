"""ADR 0301: releases of a public repository are held apart. A release inside the interval after the
repository's newest is refused with `429 release-cooldown`, a `Retry-After` and the time it is
allowed; it applies to public repositories only, never to the release made by the flip to public,
to editing a release's label or notes, or to making an earlier release current; 0 turns it off.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _fanout_world import fanouts_of
from _repository_actors import Actor, cleanup, make_actor
from _upstream_documents import set_visibility
from httpx import AsyncClient, Response
from sqlalchemy import text

from lorenzo_api.config import get_settings
from lorenzo_api.repository_publishing import interval_in_words


@pytest.fixture
def cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    """The five minutes the deployment has by default; the tests' own setting is off."""
    monkeypatch.setattr(get_settings(), "release_cooldown_seconds", 300)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _repository(
    raw_client: AsyncClient, jwks: FakeJwksServer, *, public: bool
) -> tuple[Actor, uuid.UUID]:
    author = await make_actor(raw_client, jwks, "author")
    repository = await author.create_tenant("Armoury", kind="repository")
    if public:
        await set_visibility([repository], "public")
    return author, repository


async def _publish(author: Actor, repository: uuid.UUID, **body: Any) -> Response:
    return await author.put(f"/tenants/{repository}/published", json=body)


async def _newest_release(repository: uuid.UUID) -> datetime:
    async with admin_session_factory() as session:
        found = await session.scalar(
            text(
                "SELECT created_at FROM repository_release WHERE tenant_id = :t "
                "ORDER BY number DESC LIMIT 1"
            ),
            {"t": repository},
        )
    assert isinstance(found, datetime)
    return found


async def _age_releases(repository: uuid.UUID, seconds: int) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            text(
                "UPDATE repository_release SET created_at = created_at - make_interval(secs => :s) "
                "WHERE tenant_id = :t"
            ),
            {"t": repository, "s": seconds},
        )
        await session.commit()


async def _release_count(repository: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return int(
            await session.scalar(
                text("SELECT count(*) FROM repository_release WHERE tenant_id = :t"),
                {"t": repository},
            )
            or 0
        )


async def test_a_public_repository_cannot_release_again_inside_the_interval(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, cooldown: None
) -> None:
    author, repository = await _repository(raw_client, fake_jwks_server, public=True)
    try:
        assert (await _publish(author, repository, label="1.0")).status_code == 200
        first = await _newest_release(repository)

        refused = await _publish(author, repository, label="1.1")
        assert refused.status_code == 429, refused.text
        problem = refused.json()
        assert problem["type"] == "release-cooldown"
        assert problem["title"] == "This repository released a moment ago"
        allowed_at = datetime.fromisoformat(problem["allowed_at"])
        assert (allowed_at - first).total_seconds() == 300
        assert problem["interval_seconds"] == 300
        assert problem["detail"] == (
            f"This repository can make its next release at {allowed_at:%H:%M} UTC. "
            "Releases of a public repository are at least 5 minutes apart."
        )
        retry_after = int(refused.headers["Retry-After"])
        assert 1 <= retry_after <= 300
        assert abs(retry_after - (allowed_at - datetime.now(UTC)).total_seconds()) < 3
        assert "tenant" not in (problem["title"] + problem["detail"]).lower()

        # Refused whole: no release, no announcement.
        assert await _release_count(repository) == 1

        # After the interval it is made.
        await _age_releases(repository, 301)
        assert (await _publish(author, repository, label="1.1")).status_code == 200
        assert await _release_count(repository) == 2
        # And the interval runs from that one.
        assert (await _publish(author, repository, label="1.2")).status_code == 429
    finally:
        await cleanup([repository], [author])


async def test_the_refusal_comes_before_the_work_of_a_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, cooldown: None
) -> None:
    """Refused in the interval whatever else is wrong with the release: the label is taken
    here, and the answer is still the cooldown, not the label."""
    author, repository = await _repository(raw_client, fake_jwks_server, public=True)
    try:
        assert (await _publish(author, repository, label="1.0")).status_code == 200
        again = await _publish(author, repository, label="1.0")
        assert again.status_code == 429
    finally:
        await cleanup([repository], [author])


async def test_two_releases_at_once_are_taken_one_after_the_other(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, cooldown: None
) -> None:
    author, repository = await _repository(raw_client, fake_jwks_server, public=True)
    try:
        first, second = await asyncio.gather(
            _publish(author, repository, label="A"), _publish(author, repository, label="B")
        )
        assert sorted([first.status_code, second.status_code]) == [200, 429]
        assert await _release_count(repository) == 1
    finally:
        await cleanup([repository], [author])


async def test_a_private_repository_is_never_held_back(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, cooldown: None
) -> None:
    author, repository = await _repository(raw_client, fake_jwks_server, public=False)
    try:
        for label in ("1.0", "1.1", "1.2"):
            assert (await _publish(author, repository, label=label)).status_code == 200
        assert await _release_count(repository) == 3
    finally:
        await cleanup([repository], [author])


async def test_the_release_made_by_the_flip_to_public_is_not_held_back_and_the_next_one_is(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, cooldown: None, enabled: None
) -> None:
    author, repository = await _repository(raw_client, fake_jwks_server, public=False)
    try:
        assert (await _publish(author, repository, label="1.0")).status_code == 200
        flipped = await author.put(
            f"/tenants/{repository}/public", json={"summary": "Every blade", "label": "2.0"}
        )
        assert flipped.status_code == 200, flipped.text
        assert await _release_count(repository) == 2
        # It is public now, and its newest release is the flip's.
        assert (await _publish(author, repository, label="2.1")).status_code == 429
    finally:
        await cleanup([repository], [author])


async def test_editing_a_release_and_making_an_earlier_one_current_are_never_refused(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    author, repository = await _repository(raw_client, fake_jwks_server, public=True)
    try:
        first = (await _publish(author, repository, label="1.0")).json()["release"]
        second = (await _publish(author, repository, label="2.0")).json()["release"]
        monkeypatch.setattr(get_settings(), "release_cooldown_seconds", 300)

        edited = await author.patch(
            f"/tenants/{repository}/releases/{second['id']}",
            json={"label": "Two", "notes": "Now with notes"},
        )
        assert edited.status_code == 200, edited.text
        rolled = await author.put(f"/tenants/{repository}/releases/{first['id']}/current")
        assert rolled.status_code == 200, rolled.text
        # A rollback is announced and is not a release: the next release is still held.
        assert (await _publish(author, repository, label="3.0")).status_code == 429
        assert await _release_count(repository) == 2
    finally:
        await cleanup([repository], [author])


async def test_a_cooldown_of_zero_turns_it_off(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "release_cooldown_seconds", 0)
    author, repository = await _repository(raw_client, fake_jwks_server, public=True)
    try:
        for label in ("1.0", "1.1", "1.2"):
            assert (await _publish(author, repository, label=label)).status_code == 200
    finally:
        await cleanup([repository], [author])


async def test_a_refused_release_announces_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, cooldown: None
) -> None:
    author, repository = await _repository(raw_client, fake_jwks_server, public=True)
    try:
        assert (await _publish(author, repository, label="1.0")).status_code == 200
        before = await fanouts_of(repository)
        assert (await _publish(author, repository, label="1.1")).status_code == 429
        assert await fanouts_of(repository) == before
    finally:
        await cleanup([repository], [author])


def test_the_interval_is_said_in_the_words_a_person_uses() -> None:
    assert interval_in_words(300) == "5 minutes"
    assert interval_in_words(60) == "1 minute"
    assert interval_in_words(120) == "2 minutes"
    assert interval_in_words(90) == "90 seconds"
    assert interval_in_words(1) == "1 second"
