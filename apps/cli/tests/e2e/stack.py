"""The real apps/api, on a fresh database, trusting a fake Authgear (ADR 0137; the counterpart of
inventory-web's Playwright stack, ADR 0114).

Only the identity provider is fake: a real RSA key served as a real JWKS document, so the API's
own token verification runs. Postgres, the migrations, and the API are the real ones.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

API_DIR = Path(__file__).resolve().parents[3] / "api"
DATABASE = "lorenzo_cli_e2e"
_ROLES_CLAIM = "https://authgear.com/claims/user/roles"
_KEY_ID = "e2e-key"


def _userinfo(authorization: str) -> tuple[int, bytes]:
    """What Authgear's UserInfo endpoint says about the token's subject: a verified email of its own.

    The API asks for an email on every request until it has one for the user, and a request that
    asks builds an HTTP client first (about 70 ms on a slow machine, against under 1 ms to answer).
    A fake that has no email to give leaves every request of every test paying that, which was most
    of an end-to-end run. A real user has one, and the API keeps it after the first request.
    """
    try:
        claims = jwt.decode(
            authorization.removeprefix("Bearer "), options={"verify_signature": False}
        )
    except jwt.InvalidTokenError:
        return 401, b'{"error": "invalid_token"}'
    subject = str(claims.get("sub", "unknown"))
    return 200, json.dumps(
        {"sub": subject, "email": f"{subject}@e2e.test", "email_verified": True}
    ).encode()


class FakeAuthgear:
    """Serves a JWKS and a UserInfo endpoint, and signs tokens with its key."""

    def __init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = RSAAlgorithm.to_jwk(self._key.public_key(), as_dict=True)
        jwk.update({"kid": _KEY_ID, "use": "sig", "alg": "RS256"})
        body = json.dumps({"keys": [jwk]}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib's own naming
                if self.path.startswith("/oauth2/jwks"):
                    status, payload = 200, body
                elif self.path.startswith("/oauth2/userinfo"):
                    status, payload = _userinfo(self.headers.get("Authorization", ""))
                else:
                    status, payload = 404, b"{}"
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def token(self, subject: str, *, roles: tuple[str, ...] = ()) -> str:
        now = datetime.now(tz=UTC)
        claims: dict[str, Any] = {
            "sub": subject,
            "iss": self.url,
            "aud": self.url,
            "iat": now,
            "exp": now + timedelta(hours=1),
        }
        if roles:
            claims[_ROLES_CLAIM] = list(roles)
        return jwt.encode(claims, self._key, algorithm="RS256", headers={"kid": _KEY_ID})

    def shutdown(self) -> None:
        self._server.shutdown()


@dataclass(frozen=True)
class Stack:
    api_url: str
    authgear: FakeAuthgear

    def creator_token(self, subject: str = "creator") -> str:
        """A user allowed to create tenants (Authgear's `tenant_creator` role)."""
        return self.authgear.token(subject, roles=("tenant_creator",))

    def api(self, token: str) -> httpx.Client:
        return httpx.Client(
            base_url=self.api_url, headers={"Authorization": f"Bearer {token}"}, timeout=30
        )


class StackUnavailableError(Exception):
    """Postgres or the API tooling isn't there; the end-to-end tests skip."""


def _postgres_parts() -> tuple[str, int]:
    """Host and port of the Postgres to use: CI's service (via MIGRATIONS_DATABASE_URL), else the
    docker-compose one (infra/docker-compose.yml, port 55432)."""
    configured = os.environ.get("MIGRATIONS_DATABASE_URL")
    if configured:
        parts = urlsplit(configured.replace("+asyncpg", ""))
        return parts.hostname or "127.0.0.1", parts.port or 5432
    return "127.0.0.1", int(os.environ.get("E2E_POSTGRES_PORT", "55432"))


# Held on the server while the template is made and while a database is cloned from it, so that
# parallel workers (pytest-xdist, one stack each) migrate once and clone one at a time.
_LOCK = 727401


def _migrations_fingerprint() -> str:
    """Names the template: it changes when a migration is added or edited, so a template made by
    an earlier run of other migrations is never cloned."""
    digest = hashlib.sha1(usedforsecurity=False)
    for path in sorted((API_DIR / "migrations" / "versions").glob("*.py")):
        digest.update(f"{path.name}:{path.stat().st_size};".encode())
    return digest.hexdigest()[:10]


def _migrate(env: dict[str, str]) -> None:
    try:
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],  # noqa: S607 - uv on PATH
            cwd=API_DIR,
            env=env,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"")[-400:].decode(errors="replace")
        raise StackUnavailableError(f"couldn't migrate the API's database: {exc} {detail}") from exc


def _prepare_database(
    host: str, port: int, database: str, env_for: Callable[[str], dict[str, str]]
) -> None:
    """A fresh, migrated database of this name, cloned from a template that is migrated once.

    Migrating takes seconds and creates the restricted role, which belongs to the whole server, so
    workers running it side by side would race. One migrates a template while the rest wait on an
    advisory lock; each then clones its own database from it in a fraction of a second."""
    template = f"{DATABASE}_tpl_{_migrations_fingerprint()}"
    dsn = f"postgresql://lorenzo:lorenzo@{host}:{port}/postgres"
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as connection:
            connection.execute("SELECT pg_advisory_lock(%s)", (_LOCK,))
            try:
                found = connection.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (template,)
                ).fetchone()
                if found is None:
                    connection.execute(f'CREATE DATABASE "{template}"')
                    try:
                        _migrate(env_for(template))
                    except BaseException:
                        connection.execute(f'DROP DATABASE IF EXISTS "{template}" WITH (FORCE)')
                        raise
                connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
                connection.execute(f'CREATE DATABASE "{database}" TEMPLATE "{template}"')
            finally:
                connection.execute("SELECT pg_advisory_unlock(%s)", (_LOCK,))
    except psycopg.OperationalError as exc:
        raise StackUnavailableError(f"no Postgres at {host}:{port} ({exc})") from exc


def _drop_database(host: str, port: int, database: str) -> None:
    """Best effort: a database left behind by a run that was killed is only clutter."""
    dsn = f"postgresql://lorenzo:lorenzo@{host}:{port}/postgres"
    with (
        suppress(psycopg.Error),
        psycopg.connect(dsn, autocommit=True, connect_timeout=3) as connection,
    ):
        connection.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def running_stack() -> Iterator[Stack]:
    host, port = _postgres_parts()
    # A database of its own for each pytest-xdist worker and each run, so neither a run's workers
    # nor two runs at once (another worktree, another session on the same Postgres) ever share a
    # row. It is dropped when the stack stops.
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    run = (os.environ.get("PYTEST_XDIST_TESTRUNUID") or uuid.uuid4().hex)[:8]
    database = f"{DATABASE}_{run}_{worker}"
    authgear = FakeAuthgear()

    def env_for(name: str) -> dict[str, str]:
        return {
            **os.environ,
            "DATABASE_URL": f"postgresql+asyncpg://lorenzo_app:lorenzo_app@{host}:{port}/{name}",
            "MIGRATIONS_DATABASE_URL": f"postgresql+asyncpg://lorenzo:lorenzo@{host}:{port}/{name}",
            "AUTHGEAR_ISSUER": authgear.url,
            "AUTHGEAR_AUDIENCE": authgear.url,
            "AUTHGEAR_JWKS_URL": f"{authgear.url}/oauth2/jwks",
            "AUTHGEAR_USERINFO_URL": f"{authgear.url}/oauth2/userinfo",
            # The API prints every trace span to the console, which would bury the test output.
            "OTEL_SDK_DISABLED": "true",
        }

    api_port = _free_port()
    server: subprocess.Popen[bytes] | None = None
    try:
        _prepare_database(host, port, database, env_for)
        env = env_for(database)
        server = subprocess.Popen(  # noqa: S603 - our own tooling
            [
                "uv",
                "run",
                "uvicorn",
                "lorenzo_api.main:app",  # noqa: S607
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
            ],
            cwd=API_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        api_url = f"http://127.0.0.1:{api_port}"
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise StackUnavailableError("the API exited while starting")
            with suppress(httpx.HTTPError):
                if httpx.get(f"{api_url}/healthz", timeout=2).status_code == 200:
                    break
            time.sleep(0.5)
        else:
            raise StackUnavailableError("the API didn't answer /healthz in time")
        yield Stack(api_url=api_url, authgear=authgear)
    finally:
        if server is not None:
            server.terminate()
            with suppress(subprocess.TimeoutExpired):
                server.wait(timeout=10)
            if server.poll() is None:
                server.kill()
        authgear.shutdown()
        _drop_database(host, port, database)
