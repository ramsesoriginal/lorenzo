"""The parts of OpenID Connect the CLI uses: discovery, the code exchange, and a refresh."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from typing import Any

import httpx


class OidcError(Exception):
    """The issuer refused, or answered with something that isn't a token."""


@dataclass(frozen=True)
class Endpoints:
    authorization_endpoint: str
    token_endpoint: str


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_at: float | None


def discover(issuer: str, http: httpx.Client) -> Endpoints:
    response = http.get(f"{issuer.rstrip('/')}/.well-known/openid-configuration")
    if response.is_error:
        raise OidcError(f"Couldn't read {issuer}'s OpenID configuration ({response.status_code}).")
    config = response.json()
    return Endpoints(config["authorization_endpoint"], config["token_endpoint"])


def _token_response(response: httpx.Response, now: float) -> TokenResponse:
    if response.is_error:
        body: dict[str, Any] = {}
        with contextlib.suppress(ValueError):
            body = response.json()
        reason = body.get("error_description") or body.get("error") or response.text[:200]
        raise OidcError(f"The token endpoint refused ({response.status_code}): {reason}")
    body = response.json()
    expires_in = body.get("expires_in")
    return TokenResponse(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        expires_at=now + float(expires_in) if expires_in is not None else None,
    )


def exchange_code(
    http: httpx.Client,
    endpoints: Endpoints,
    *,
    client_id: str,
    code: str,
    redirect_uri: str,
    verifier: str,
    now: float | None = None,
) -> TokenResponse:
    # A public client: no secret, the PKCE verifier is the proof.
    response = http.post(
        endpoints.token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    return _token_response(response, time.time() if now is None else now)


def refresh(
    http: httpx.Client,
    endpoints: Endpoints,
    *,
    client_id: str,
    refresh_token: str,
    now: float | None = None,
) -> TokenResponse:
    response = http.post(
        endpoints.token_endpoint,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )
    return _token_response(response, time.time() if now is None else now)
