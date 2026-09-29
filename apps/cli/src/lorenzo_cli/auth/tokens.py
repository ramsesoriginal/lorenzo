"""Where the access token comes from (ADR 0137).

In order: `--token-stdin`, then `LORENZO_TOKEN`, then the stored login. The first two are plain
tokens the CLI can't renew; the stored login renews itself with its refresh token.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import TextIO

import httpx

from lorenzo_cli.auth import oidc
from lorenzo_cli.auth.store import CredentialsFile, StoredLogin

# Renew a little early, so a request doesn't leave with a token that dies on the way.
_EXPIRY_MARGIN_SECONDS = 60.0


class NotLoggedInError(Exception):
    """There is no token to use."""


class StaticToken:
    def __init__(self, value: str) -> None:
        self._value = value

    def token(self) -> str:
        return self._value

    def refresh(self) -> str | None:
        return None


class StoredToken:
    def __init__(
        self,
        login: StoredLogin,
        store: CredentialsFile,
        http: httpx.Client,
        *,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._login = login
        self._store = store
        self._http = http
        self._now = now

    def token(self) -> str:
        expires_at = self._login.expires_at
        if expires_at is not None and self._now() >= expires_at - _EXPIRY_MARGIN_SECONDS:
            # If renewing fails, send the old one anyway: the API decides, and a 401 says so.
            self.refresh()
        return self._login.access_token

    def refresh(self) -> str | None:
        if self._login.refresh_token is None:
            return None
        try:
            endpoints = oidc.discover(self._login.issuer, self._http)
            renewed = oidc.refresh(
                self._http,
                endpoints,
                client_id=self._login.client_id,
                refresh_token=self._login.refresh_token,
                now=self._now(),
            )
        except oidc.OidcError, httpx.HTTPError, KeyError:
            return None
        self._login = StoredLogin(
            issuer=self._login.issuer,
            client_id=self._login.client_id,
            access_token=renewed.access_token,
            # Some issuers rotate the refresh token, some keep the old one.
            refresh_token=renewed.refresh_token or self._login.refresh_token,
            expires_at=renewed.expires_at,
        )
        self._store.save(self._login)
        return self._login.access_token


def read_token_stdin(stdin: TextIO) -> str:
    value = stdin.readline().strip()
    if not value:
        raise NotLoggedInError("--token-stdin was given but nothing was piped in.")
    return value


def resolve_token_source(
    *,
    token_stdin: bool,
    stdin: TextIO,
    env: Mapping[str, str],
    store: CredentialsFile,
    http: httpx.Client,
) -> StaticToken | StoredToken:
    if token_stdin:
        return StaticToken(read_token_stdin(stdin))
    from_env = env.get("LORENZO_TOKEN")
    if from_env:
        return StaticToken(from_env.strip())
    login = store.load()
    if login is not None:
        return StoredToken(login, store, http)
    raise NotLoggedInError(
        "Not logged in. Run `lorenzo login`, set LORENZO_TOKEN, or pipe a token in with "
        "--token-stdin."
    )
