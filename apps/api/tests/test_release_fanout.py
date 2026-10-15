"""ADR 0301: the announcement of a release is a row with a cursor, drained a chunk a transaction by
whoever comes next. What the spike of RFC 0038 section 6 proved, held in the codebase: written with
the release and gone with it, exactly one notice a person however often it is stopped, drains side
by side, a sweep that finishes what stopped and costs one query when nothing did, and a release
that costs the snapshot and not the loop.
"""

import asyncio
import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _fanout_world import Libraries, add_libraries, fanouts_of, notices_of
from _repository_actors import Actor, cleanup, make_actor
from fastapi import BackgroundTasks
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_item_read_statements import _statements

import lorenzo_api.release_fanout as release_fanout
from lorenzo_api.config import Settings, get_settings
from lorenzo_api.db import async_session_factory
from lorenzo_api.dependencies import set_tenant_rls_context
from lorenzo_api.models import Tenant
from lorenzo_api.release_fanout import Outcome, announce, drain, drain_chunk, sweep
from lorenzo_api.repository_publishing import publish_release
from lorenzo_api.schemas.repositories import PublishRequest


@pytest.fixture
def held_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is drained after a response: an announcement waits for what the test does."""
    for module in ("repositories", "repository_flips"):
        monkeypatch.setattr(
            f"lorenzo_api.routers.{module}.drain_after_response", lambda *args, **kwargs: None
        )


@pytest.fixture
def small_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "release_fanout_chunk_size", 3)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _repository(
    raw_client: AsyncClient, jwks: FakeJwksServer, libraries: int, *, source: str = "invited"
) -> tuple[Actor, uuid.UUID, Libraries]:
    author = await make_actor(raw_client, jwks, "author")
    repository = await author.create_tenant("Armoury", kind="repository")
    return author, repository, await add_libraries(repository, libraries, source=source)


async def _publish(author: Actor, repository: uuid.UUID, **body: Any) -> dict[str, Any]:
    response = await author.put(f"/tenants/{repository}/published", json=body)
    assert response.status_code == 200, response.text
    return response.json()["release"]  # type: ignore[no-any-return]


def _once(people: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    return dict.fromkeys(people, 1)


# --- Written with the release -----------------------------------------------------------------


async def test_a_release_writes_one_row_and_the_drain_tells_each_person_once(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None, small_chunks: None
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 10)
    try:
        await _publish(author, repository, label="1.0", notes="The first")

        # The request wrote the announcement and told nobody.
        assert await fanouts_of(repository) == [(10, 0, False, "repository_published")]
        assert set((await notices_of(libraries.people)).values()) == {0}

        # Ten libraries in chunks of three: four chunks, and nothing left for a fifth.
        assert await drain() == 4
        assert await fanouts_of(repository) == [(10, 10, True, "repository_published")]
        assert await notices_of(libraries.people) == _once(libraries.people)
        # Not the Authors of the libraries: today's loop does not tell them either.
        assert set((await notices_of(libraries.authors)).values()) == {0}
        assert await drain() == 0
        assert await notices_of(libraries.people) == _once(libraries.people)

        async with admin_session_factory() as session:
            sample = (
                await session.execute(
                    text(
                        "SELECT type, title, body, scope, tenant_id, created_by FROM notification "
                        "WHERE user_id = :u"
                    ),
                    {"u": libraries.items[0].owner},
                )
            ).one()
        assert sample.type == "repository_published"
        assert sample.title == "Armoury is published"
        assert "The first" in sample.body
        assert (sample.scope, sample.tenant_id) == ("tenant", libraries.items[0].id)
        assert sample.created_by == author.user_id
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_a_release_with_nobody_to_tell_writes_no_row(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 0)
    try:
        await _publish(author, repository, label="1.0")
        assert await fanouts_of(repository) == []
    finally:
        await cleanup([repository], [author])


async def test_what_is_sent_is_what_the_release_said_when_it_was_made(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None
) -> None:
    """The words are written with the announcement: editing the release's notes or label after
    it, before the drain, changes nothing that is sent."""
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 2)
    try:
        release = await _publish(author, repository, label="1.0", notes="As first written")
        edited = await author.patch(
            f"/tenants/{repository}/releases/{release['id']}",
            json={"label": "Renamed", "notes": "Edited since"},
        )
        assert edited.status_code == 200, edited.text
        await drain()
        async with admin_session_factory() as session:
            body = (
                await session.execute(
                    text("SELECT title, body FROM notification WHERE user_id = :u"),
                    {"u": libraries.items[0].owner},
                )
            ).one()
        assert body.title == "Armoury is published"
        assert "As first written" in body.body and "Edited since" not in body.body
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_an_announcement_is_rolled_back_with_the_release_it_announces(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 3)
    try:
        async with async_session_factory() as session:
            await set_tenant_rls_context(session, repository)
            tenant = await session.get_one(Tenant, repository)
            await publish_release(
                session, repository=tenant, user_id=author.user_id, body=PublishRequest()
            )
            assert await session.scalar(text("SELECT count(*) FROM release_fanout")) == 1
            await session.rollback()
        assert await fanouts_of(repository) == []
        async with admin_session_factory() as session:
            assert (
                await session.scalar(
                    text("SELECT count(*) FROM repository_release WHERE tenant_id = :t"),
                    {"t": repository},
                )
                == 0
            )
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_a_delisted_repository_announces_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 2)
    try:
        async with admin_session_factory() as session:
            await session.execute(
                text("UPDATE tenant SET delisted_at = now(), delist_reason = 'Spam' WHERE id = :t"),
                {"t": repository},
            )
            await session.commit()
        await _publish(author, repository, label="1.0")
        assert await fanouts_of(repository) == []
    finally:
        await cleanup([repository], [author])
        await libraries.done()


# --- Stopped, resumed, side by side ------------------------------------------------------------


async def test_a_drain_stopped_in_a_chunk_resumes_and_tells_each_person_exactly_once(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    held_back: None,
    small_chunks: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 10)
    try:
        await _publish(author, repository, label="1.0")

        # Stopped after one whole chunk, as a process killed between two: the cursor says where.
        assert await drain(chunks=1) == 1
        assert await fanouts_of(repository) == [(10, 3, False, "repository_published")]
        told = await notices_of(libraries.people)
        assert sum(told.values()) == 6

        # Stopped in the middle of the next one, the second library of it: nothing of that chunk
        # was committed, and the cursor did not move.
        real = release_fanout.create_tenant_admins_notification
        calls = 0

        async def dying(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("the process was stopped")
            return await real(*args, **kwargs)

        monkeypatch.setattr(release_fanout, "create_tenant_admins_notification", dying)
        assert await drain() == 0
        monkeypatch.setattr(release_fanout, "create_tenant_admins_notification", real)
        assert await fanouts_of(repository) == [(10, 3, False, "repository_published")]
        assert await notices_of(libraries.people) == told

        # The next drain finishes it: everybody once, nobody twice.
        assert await drain() == 3
        assert await fanouts_of(repository) == [(10, 10, True, "repository_published")]
        assert await notices_of(libraries.people) == _once(libraries.people)
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_drains_at_once_take_turns_and_the_row_they_skip_is_the_one_held(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None, small_chunks: None
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 10)
    try:
        await _publish(author, repository, label="1.0")
        [(_, _, _, _)] = await fanouts_of(repository)
        async with admin_session_factory() as session:
            fanout_id = await session.scalar(
                text("SELECT id FROM release_fanout WHERE tenant_id = :t"), {"t": repository}
            )

        # A drain that holds the row: another finds nothing it can take, and does not wait.
        async with async_session_factory() as holder, async_session_factory() as other:
            await holder.execute(text("SELECT set_config('app.fanout_sweep', 'on', true)"))
            await holder.execute(
                text("SELECT id FROM release_fanout WHERE id = :i FOR UPDATE"), {"i": fanout_id}
            )
            assert await drain_chunk(other, fanout_id) is Outcome.IDLE
            assert await drain_chunk(other) is Outcome.IDLE
            await holder.rollback()
        assert await fanouts_of(repository) == [(10, 0, False, "repository_published")]

        # Three drains started together: the chunks are written once each, whoever takes them.
        written = await asyncio.gather(*(drain(fanout_id) for _ in range(3)))
        assert sum(written) == 4
        assert await fanouts_of(repository) == [(10, 10, True, "repository_published")]
        assert await notices_of(libraries.people) == _once(libraries.people)
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_two_announcements_of_one_repository_are_each_drained_once(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None, small_chunks: None
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 4)
    try:
        await _publish(author, repository, label="1.0")
        await _publish(author, repository, label="2.0")
        assert [f[3] for f in await fanouts_of(repository)] == [
            "repository_published",
            "repository_updated",
        ]
        await asyncio.gather(drain(), drain())
        assert [(f[1], f[2]) for f in await fanouts_of(repository)] == [(4, True), (4, True)]
        # One notice of each, to each person: two in all.
        assert set((await notices_of(libraries.people)).values()) == {2}
        assert set((await notices_of(libraries.people, "repository_updated")).values()) == {1}
    finally:
        await cleanup([repository], [author])
        await libraries.done()


# --- The other two announcements ---------------------------------------------------------------


async def test_making_an_earlier_release_current_is_announced_through_the_table(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None, enabled: None
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 3)
    try:
        # A public repository keeps the content of its releases, which a rollback reads.
        made = await author.put(
            f"/tenants/{repository}/public", json={"summary": "Every blade", "label": "1.0"}
        )
        assert made.status_code == 200, made.text
        first = made.json()["release"]
        await _publish(author, repository, label="2.0")
        await drain()
        moved = await author.put(f"/tenants/{repository}/releases/{first['id']}/current")
        assert moved.status_code == 200, moved.text
        fanouts = await fanouts_of(repository)
        assert fanouts[-1] == (3, 0, False, "repository_updated")
        assert await drain() == 1
        assert set((await notices_of(libraries.people, "repository_updated")).values()) == {2}
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_the_revoke_notice_of_going_private_reaches_the_libraries_whose_grants_it_deleted(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    held_back: None,
    enabled: None,
) -> None:
    author, repository, _ = await _repository(raw_client, fake_jwks_server, 0)
    copying = invited = Libraries()
    try:
        made = await author.put(f"/tenants/{repository}/public", json={"summary": "Every blade"})
        assert made.status_code == 200, made.text
        copying = await add_libraries(repository, 4, source="public")
        invited = await add_libraries(repository, 2)
        await drain()
        before = await notices_of(copying.people + invited.people, "repository_revoked")
        assert set(before.values()) == {0}

        private = await author.delete(
            f"/tenants/{repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert private.status_code == 200, private.text
        # The grants are gone by now, and the snapshot is what says who to tell.
        async with admin_session_factory() as session:
            assert (
                await session.scalar(
                    text(
                        "SELECT count(*) FROM repository_subscription "
                        "WHERE repository_tenant_id = :t AND source = 'public'"
                    ),
                    {"t": repository},
                )
                == 0
            )
        assert (await fanouts_of(repository))[-1] == (4, 0, False, "repository_revoked")

        await drain()
        assert await notices_of(copying.people, "repository_revoked") == _once(copying.people)
        # The libraries it invited keep their grant and are told nothing.
        assert set((await notices_of(invited.people, "repository_revoked")).values()) == {0}
    finally:
        await cleanup([repository], [author])
        await copying.done()
        await invited.done()


# --- The sweep ---------------------------------------------------------------------------------


@pytest.fixture
def fresh_gate() -> Any:
    release_fanout.reset_sweep_gate()
    yield
    release_fanout.reset_sweep_gate()


async def test_the_sweep_finishes_a_stranded_announcement_and_only_so_much_at_once(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    held_back: None,
    small_chunks: None,
    fresh_gate: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 10)
    try:
        await _publish(author, repository, label="1.0")
        monkeypatch.setattr(get_settings(), "release_fanout_sweep_chunks", 2)

        # Bounded: two chunks of the four, and the rest left for the next.
        assert await sweep() == 2
        assert await fanouts_of(repository) == [(10, 6, False, "repository_published")]
        assert await sweep() == 2
        assert await fanouts_of(repository) == [(10, 10, True, "repository_published")]
        assert await notices_of(libraries.people) == _once(libraries.people)
        assert await sweep() == 0
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_a_sweep_starts_on_an_authenticated_request_at_most_once_a_minute(
    fresh_gate: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "release_fanout_sweep_interval_seconds", 60)

    def scheduled() -> int:
        tasks = BackgroundTasks()
        release_fanout.schedule_sweep(tasks)
        return len(tasks.tasks)

    assert scheduled() == 1  # the first request of a process
    assert scheduled() == 0  # a burst of requests starts one sweep, not one each
    release_fanout._last_sweep -= 59  # type: ignore[operator]
    assert scheduled() == 0
    release_fanout._last_sweep -= 2  # type: ignore[operator]
    assert scheduled() == 1  # a minute has passed
    # One that is running is not started again.
    release_fanout._last_sweep -= 120  # type: ignore[operator]
    release_fanout._sweeping = True
    assert scheduled() == 0


async def test_an_authenticated_request_sweeps_after_its_response_and_an_open_one_does_not(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    held_back: None,
    small_chunks: None,
    fresh_gate: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 4)
    try:
        await _publish(author, repository, label="1.0")
        assert (await fanouts_of(repository))[0][1] == 0
        # Setting the scene was done by authenticated requests: this process has not swept since.
        release_fanout.reset_sweep_gate()
        monkeypatch.setattr(get_settings(), "release_fanout_sweep_interval_seconds", 60)

        # Health checks and the open routes never start one.
        assert (await raw_client.get("/healthz")).status_code == 200
        assert (await raw_client.get("/readyz")).status_code == 200
        assert release_fanout._last_sweep is None
        assert await fanouts_of(repository) == [(4, 0, False, "repository_published")]

        # An authenticated request does, once its response is out: the announcement is finished.
        assert (await author.get("/me")).status_code == 200
        assert release_fanout._last_sweep is not None
        assert await fanouts_of(repository) == [(4, 4, True, "repository_published")]
        assert await notices_of(libraries.people) == _once(libraries.people)

        # And not again inside the minute: a second stranded announcement waits.
        await _publish(author, repository, label="2.0")
        assert (await author.get("/me")).status_code == 200
        assert (await fanouts_of(repository))[-1] == (4, 0, False, "repository_updated")
    finally:
        await cleanup([repository], [author])
        await libraries.done()


async def test_the_start_up_sweep_finishes_what_the_last_process_left_and_removes_old_rows(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    held_back: None,
    fresh_gate: None,
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 3)
    try:
        await _publish(author, repository, label="1.0")
        await _publish(author, repository, label="2.0")
        async with admin_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE release_fanout SET cursor = 3, done_at = now() - interval '8 days' "
                    "WHERE tenant_id = :t AND type = 'repository_published'"
                ),
                {"t": repository},
            )
            await session.commit()
        release_fanout.start_sweeping()
        task = release_fanout._startup_sweep
        assert task is not None
        assert await task == 1
        await release_fanout.stop_sweeping()
        assert await fanouts_of(repository) == [(3, 3, True, "repository_updated")]
        assert set((await notices_of(libraries.people, "repository_updated")).values()) == {1}
    finally:
        await cleanup([repository], [author])
        await libraries.done()


# --- The cost of a release ---------------------------------------------------------------------


async def test_a_release_at_five_thousand_libraries_costs_the_snapshot_and_not_the_loop(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None
) -> None:
    author, repository, _ = await _repository(raw_client, fake_jwks_server, 0)
    try:
        async with admin_session_factory() as session:
            await session.execute(
                text(
                    "WITH made AS (INSERT INTO tenant (id, name) "
                    "SELECT gen_random_uuid(), 'Held ' || n FROM generate_series(1, 5000) n "
                    "RETURNING id) "
                    "INSERT INTO repository_subscription (repository_tenant_id, "
                    "subscriber_tenant_id) SELECT :r, id FROM made"
                ),
                {"r": repository},
            )
            await session.commit()
        started = time.perf_counter()
        with _statements() as seen:
            await _publish(author, repository, label="1.0")
        elapsed = time.perf_counter() - started

        inserts = [s for s in seen if s.lstrip().upper().startswith("INSERT INTO RELEASE_FANOUT")]
        assert len(inserts) == 1
        # Not a notice and not a switch of the tenant for any of them: the loop is not in the
        # request.
        assert [s for s in seen if "insert into notification" in s.lower()] == []
        assert len([s for s in seen if "set_config('app.tenant_id'" in s]) < 5
        # The release's own, fixed number of statements (54 before this change at no libraries,
        # and 20,054 at 5,000 libraries); the snapshot adds one.
        assert len(seen) < 120, len(seen)
        # And the time of it, which was 21 s: the machine this runs on is not the one that measured.
        assert elapsed < 10, elapsed
        assert await fanouts_of(repository) == [(5000, 0, False, "repository_published")]
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text(
                    "DELETE FROM tenant WHERE id IN (SELECT subscriber_tenant_id FROM "
                    "repository_subscription WHERE repository_tenant_id = :r)"
                ),
                {"r": repository},
            )
            await session.commit()
        await cleanup([repository], [author])


# --- The table's own wall ----------------------------------------------------------------------


def _insert(repository: uuid.UUID) -> Callable[[], Any]:
    async def run(session: Any) -> None:
        await session.execute(
            text(
                "INSERT INTO release_fanout (tenant_id, type, title, body, recipients) "
                "VALUES (:t, 'repository_updated', 'T', 'B', ARRAY[]::uuid[])"
            ),
            {"t": repository},
        )

    return run


async def test_the_table_is_the_repositorys_own_and_opens_to_the_sweep_only_for_reading_and_moving(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, held_back: None
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 2)
    other = await make_actor(raw_client, fake_jwks_server, "other")
    elsewhere = await other.create_tenant("Elsewhere", kind="repository")
    try:
        await _publish(author, repository, label="1.0")
        async with async_session_factory() as session:
            # Another tenant's context reads none of it, and the repository's own reads it.
            await set_tenant_rls_context(session, elsewhere)
            assert await session.scalar(text("SELECT count(*) FROM release_fanout")) == 0
            await set_tenant_rls_context(session, repository)
            assert await session.scalar(text("SELECT count(*) FROM release_fanout")) == 1
            await session.rollback()

            # With no tenant at all it reads nothing, until the sweep's setting is on.
            assert await session.scalar(text("SELECT count(*) FROM release_fanout")) == 0
            await session.execute(text("SELECT set_config('app.fanout_sweep', 'on', true)"))
            assert await session.scalar(text("SELECT count(*) FROM release_fanout")) == 1
            await session.rollback()

        # The sweep's setting opens no write of a new row, for anyone's repository: only the
        # transaction of a release writes one, under its own repository's context.
        async with async_session_factory() as session:
            await session.execute(text("SELECT set_config('app.fanout_sweep', 'on', true)"))
            await set_tenant_rls_context(session, elsewhere)
            with pytest.raises(DBAPIError):
                await _insert(repository)(session)
            await session.rollback()
    finally:
        await cleanup([repository, elsewhere], [author, other])
        await libraries.done()


async def test_an_announcement_tells_each_library_once_however_often_it_is_named(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author, repository, libraries = await _repository(raw_client, fake_jwks_server, 2)
    try:
        async with async_session_factory() as session:
            await set_tenant_rls_context(session, repository)
            nobody = await announce(
                session,
                repository_id=repository,
                release_id=None,
                type="repository_updated",
                title="T",
                body="B",
                created_by=author.user_id,
                recipients=[],
            )
            assert nobody is None
            await announce(
                session,
                repository_id=repository,
                release_id=None,
                type="repository_updated",
                title="T",
                body="B",
                created_by=author.user_id,
                recipients=[*libraries.ids, *libraries.ids],
            )
            await session.commit()
        assert await fanouts_of(repository) == [(2, 0, False, "repository_updated")]
    finally:
        await cleanup([repository], [author])
        await libraries.done()


def test_the_settings_default_to_what_the_spike_measured() -> None:
    fields = Settings.model_fields
    assert fields["release_cooldown_seconds"].default == 300
    assert fields["release_fanout_chunk_size"].default == 250
    assert fields["release_fanout_sweep_chunks"].default == 20
    assert fields["release_fanout_sweep_interval_seconds"].default == 60
