"""One database per pytest-xdist worker, cloned from a migrated template (ADR 0148).

Importing this module, before anything reads the settings, points `DATABASE_URL` and
`MIGRATIONS_DATABASE_URL` at the worker's own database; a run without workers does nothing and keeps
the database it was given. That is why `conftest.py` imports it first.

The migrations create a role that belongs to the whole server, so workers migrating side by side
would race. One migrates a template while the rest wait on an advisory lock, and each then clones
a database of its own from it, which takes a fraction of a second. The template is named after the
migrations, so a changed one makes a new template; a worker's database is named after the run and
the worker and dropped when the worker finishes, so two runs on one Postgres never share one.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import subprocess
import sys
import threading
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from lorenzo_api.config import Settings

API_DIR = Path(__file__).resolve().parents[1]
_LOCK = 727402
_DATABASE: str | None = None


def _with_database(url: str, database: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{database}"))


def _maintenance_dsn(url: str) -> str:
    """The server's `postgres` database, as a plain DSN asyncpg reads."""
    return _with_database(url, "postgres").replace("postgresql+asyncpg://", "postgresql://")


def _fingerprint() -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    for path in sorted((API_DIR / "migrations" / "versions").glob("*.py")):
        digest.update(f"{path.name}:{path.stat().st_size};".encode())
    return digest.hexdigest()[:10]


def _run[T](work: Callable[[], Awaitable[T]]) -> T:
    """Runs a coroutine to the end on a loop of its own, in a thread of its own, so that no event
    loop is left behind on the importing thread for the tests' own to trip over."""
    box: list[T] = []
    failure: list[BaseException] = []

    def target() -> None:
        try:
            box.append(asyncio.run(work()))
        except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread
            failure.append(exc)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    if failure:
        raise failure[0]
    return box[0]


def _migrate(admin_url: str, app_url: str, database: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env={
            **os.environ,
            "DATABASE_URL": _with_database(app_url, database),
            "MIGRATIONS_DATABASE_URL": _with_database(admin_url, database),
        },
        check=True,
    )


async def _clone(admin_url: str, app_url: str, template: str, database: str) -> None:
    connection = await asyncpg.connect(_maintenance_dsn(admin_url), timeout=10)
    try:
        await connection.execute("SELECT pg_advisory_lock($1)", _LOCK)
        try:
            found = await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", template
            )
            if found is None:
                await connection.execute(f'CREATE DATABASE "{template}"')
                try:
                    await asyncio.to_thread(_migrate, admin_url, app_url, template)
                except BaseException:
                    await connection.execute(f'DROP DATABASE IF EXISTS "{template}" WITH (FORCE)')
                    raise
            await connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
            await connection.execute(f'CREATE DATABASE "{database}" TEMPLATE "{template}"')
        finally:
            await connection.execute("SELECT pg_advisory_unlock($1)", _LOCK)
    finally:
        await connection.close()


async def _drop(admin_url: str, database: str) -> None:
    connection = await asyncpg.connect(_maintenance_dsn(admin_url), timeout=10)
    try:
        await connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
    finally:
        await connection.close()


def point_at_worker_database() -> None:
    global _DATABASE  # noqa: PLW0603 - one per process, set once
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker is None or _DATABASE is not None:
        return
    settings = Settings()
    admin_url, app_url = settings.migrations_database_url, settings.database_url
    base = urlsplit(admin_url).path.lstrip("/")
    run = (os.environ.get("PYTEST_XDIST_TESTRUNUID") or uuid.uuid4().hex)[:8]
    database = f"{base}_{run}_{worker}"
    _run(lambda: _clone(admin_url, app_url, f"{base}_tpl_{_fingerprint()}", database))
    os.environ["DATABASE_URL"] = _with_database(app_url, database)
    os.environ["MIGRATIONS_DATABASE_URL"] = _with_database(admin_url, database)
    _DATABASE = database


def drop_worker_database() -> None:
    """Best effort, when the worker is done: a database left by a killed run is only clutter."""
    if _DATABASE is None:
        return
    admin_url = os.environ["MIGRATIONS_DATABASE_URL"]
    with contextlib.suppress(OSError, asyncpg.PostgresError):
        _run(lambda: _drop(admin_url, _DATABASE))


point_at_worker_database()
