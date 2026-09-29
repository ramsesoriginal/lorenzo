"""The real apps/api, on a fresh database, trusting a fake Authgear (ADR 0137; the counterpart of
inventory-web's Playwright stack, ADR 0114).

Only the identity provider is fake: a real RSA key served as a real JWKS document, so the API's
own token verification runs. Postgres, the migrations, and the API are the real ones.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
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


class FakeAuthgear:
    """Serves a JWKS and signs tokens with its key."""

    def __init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = RSAAlgorithm.to_jwk(self._key.public_key(), as_dict=True)
        jwk.update({"kid": _KEY_ID, "use": "sig", "alg": "RS256"})
        body = json.dumps({"keys": [jwk]}).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib's own naming
                # /userinfo is only asked for an email; a 404 is "no email", which the API allows.
                status = 200 if self.path.startswith("/oauth2/jwks") else 404
                payload = body if status == 200 else b"{}"
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


def _recreate_database(host: str, port: int) -> None:
    dsn = f"postgresql://lorenzo:lorenzo@{host}:{port}/postgres"
    try:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as connection:
            connection.execute(f'DROP DATABASE IF EXISTS "{DATABASE}" WITH (FORCE)')
            connection.execute(f'CREATE DATABASE "{DATABASE}"')
    except psycopg.OperationalError as exc:
        raise StackUnavailableError(f"no Postgres at {host}:{port} ({exc})") from exc


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@contextmanager
def running_stack() -> Iterator[Stack]:
    host, port = _postgres_parts()
    _recreate_database(host, port)
    authgear = FakeAuthgear()
    env = {
        **os.environ,
        "DATABASE_URL": f"postgresql+asyncpg://lorenzo_app:lorenzo_app@{host}:{port}/{DATABASE}",
        "MIGRATIONS_DATABASE_URL": f"postgresql+asyncpg://lorenzo:lorenzo@{host}:{port}/{DATABASE}",
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
            raise StackUnavailableError(
                f"couldn't migrate the API's database: {exc} {detail}"
            ) from exc
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
