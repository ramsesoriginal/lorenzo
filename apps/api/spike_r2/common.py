"""Shared pieces of the R2 scale spike (RFC 0037, issue #709): connections, a probe that counts
statements and the time spent in the database, timing helpers, and the in-process HTTP client.

Run from the apps/api directory of a checkout on a native Linux filesystem (not /mnt/c), with
DATABASE_URL / MIGRATIONS_DATABASE_URL pointing at the spike database (see run.sh).
"""

from __future__ import annotations

import json
import os
import statistics
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import Request
from opentelemetry.sdk.trace import export as _otel_export


class _DiscardingExporter(_otel_export.SpanExporter):
    """The app prints every span to the console (observability/tracing.py); the spans are still
    made, so the instrumentation cost is in the numbers, but nothing is printed."""

    def export(self, spans):  # type: ignore[no-untyped-def]
        return _otel_export.SpanExportResult.SUCCESS


if not os.environ.get("R2_CONSOLE_SPANS"):
    _otel_export.ConsoleSpanExporter = _DiscardingExporter  # type: ignore[misc]

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lorenzo_api.config import get_settings
from lorenzo_api.db import async_session_factory, engine
from lorenzo_api.dependencies import SessionDep, get_current_user
from lorenzo_api.main import app
from lorenzo_api.models import User

import logging

logging.getLogger("httpx").setLevel(logging.WARNING)

HERE = Path(__file__).resolve().parent
STATE_DIR = Path(os.environ.get("R2_STATE_DIR", HERE / "state"))
RESULT_DIR = Path(os.environ.get("R2_RESULT_DIR", HERE / "results"))

admin_engine = create_async_engine(get_settings().migrations_database_url)
admin_session_factory = async_sessionmaker(admin_engine, expire_on_commit=False)


def state_path(size: int) -> Path:
    return STATE_DIR / f"state_{size}.json"


def load_state(size: int) -> dict[str, Any]:
    return json.loads(state_path(size).read_text())  # type: ignore[no-any-return]


def save_state(size: int, state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(size).write_text(json.dumps(state, indent=2))


# --- The probe: statements and database time ---------------------------------------------------


@dataclass
class Probe:
    statements: int = 0
    db_seconds: float = 0.0
    _started: float = 0.0
    by_statement: dict[str, list[float]] = field(default_factory=dict)

    def install(self) -> None:
        sync = engine.sync_engine

        @event.listens_for(sync, "before_cursor_execute")
        def _before(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
            self._started = time.perf_counter()

        @event.listens_for(sync, "after_cursor_execute")
        def _after(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
            elapsed = time.perf_counter() - self._started
            self.statements += 1
            self.db_seconds += elapsed
            key = " ".join(statement.split())[:90]
            self.by_statement.setdefault(key, []).append(elapsed)

    def reset(self) -> None:
        self.statements = 0
        self.db_seconds = 0.0
        self.by_statement = {}

    def slowest(self, count: int = 5) -> list[tuple[str, float, int]]:
        ranked = sorted(
            ((k, sum(v), len(v)) for k, v in self.by_statement.items()),
            key=lambda item: -item[1],
        )
        return ranked[:count]


probe = Probe()
probe.install()


# --- Timing ------------------------------------------------------------------------------------


@dataclass
class Timing:
    name: str
    walls: list[float]
    statements: int
    db_seconds: float
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def median(self) -> float:
        return statistics.median(self.walls)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "median_ms": round(self.median * 1000, 1),
            "min_ms": round(min(self.walls) * 1000, 1),
            "max_ms": round(max(self.walls) * 1000, 1),
            "runs": len(self.walls),
            "first_ms": round(self.walls[0] * 1000, 1),
            "statements": self.statements,
            "db_ms": round(self.db_seconds * 1000, 1),
            **self.extra,
        }


async def timed(
    name: str,
    fn: Callable[[], Awaitable[Any]],
    *,
    reps: int = 5,
    warmup: int = 1,
    extra: Callable[[Any], dict[str, Any]] | None = None,
) -> Timing:
    """`warmup` runs, then `reps` timed ones; the statements and the database time are the
    median run's. `first_ms` is the very first run, which is the cold one when `warmup` is
    zero or when nothing ran before in this process."""
    walls: list[float] = []
    statements: list[int] = []
    db: list[float] = []
    last: Any = None
    first: float | None = None
    for i in range(warmup + reps):
        probe.reset()
        started = time.perf_counter()
        last = await fn()
        wall = time.perf_counter() - started
        if first is None:
            first = wall
        if i >= warmup:
            walls.append(wall)
            statements.append(probe.statements)
            db.append(probe.db_seconds)
    timing = Timing(
        name,
        walls,
        int(statistics.median(statements)),
        statistics.median(db),
        extra(last) if extra else {},
    )
    timing.extra["first_run_ms"] = round((first or 0) * 1000, 1)
    return timing


# --- Sessions and the HTTP client ---------------------------------------------------------------


async def tenant_session(tenant_id: uuid.UUID) -> AsyncSession:
    """A session of the app role in a tenant's RLS context, as a request would have."""
    session = async_session_factory()
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )
    return session


async def _spike_user(request: Request, session: SessionDep) -> User:
    user_id = uuid.UUID(request.headers["x-spike-user"])
    await session.execute(
        text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)}
    )
    user = User(id=user_id, authgear_subject_id=f"spike|{user_id}")
    user.authgear_roles = frozenset({"tenant_creator"})
    return user


app.dependency_overrides[get_current_user] = _spike_user


class Actor:
    """Requests as one user, through the app in this process (ASGI, no network)."""

    def __init__(self, client: httpx.AsyncClient, user_id: uuid.UUID) -> None:
        self.client = client
        self.user_id = user_id
        self.headers = {"x-spike-user": str(user_id)}

    async def get(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.get(url, headers=self.headers, **kw)

    async def put(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.put(url, headers=self.headers, **kw)

    async def post(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.post(url, headers=self.headers, **kw)


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://spike", timeout=3600
    )


def write_result(name: str, payload: Any) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    (RESULT_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str))


if os.environ.get("R2_PATCH_LOCAL_OF"):
    # The fix proposed in the findings: invert a copy-link map once, not on every call
    # (repository_updates._local_entity calls Links.local_of for each end of each attachment).
    from lorenzo_api.repository_content import Links as _Links

    _real_local_of = _Links.local_of
    _memo: dict[tuple[int, str], dict[uuid.UUID, uuid.UUID]] = {}

    def _memoised_local_of(self: _Links, kind: str) -> dict[uuid.UUID, uuid.UUID]:
        key = (id(self), kind)
        if key not in _memo:
            _memo[key] = _real_local_of(self, kind)
        return _memo[key]

    _Links.local_of = _memoised_local_of  # type: ignore[method-assign]
