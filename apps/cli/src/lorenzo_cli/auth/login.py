"""`lorenzo login`: the authorization code flow with PKCE (RFC 7636, RFC 8252), ADR 0137.

Authgear has no device authorization grant, so there are two ways to receive the code:

- **Loopback** (default): listen on a fixed port on 127.0.0.1, open the browser, catch the redirect.
- **`--no-browser`**: print the URL, open it on any machine, and paste back the address the
  browser was redirected to. That covers WSL and SSH, where the browser can't reach this process.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import secrets
import time
import urllib.parse
import webbrowser
from collections.abc import Callable, Sequence
from typing import Self

import httpx

from lorenzo_cli.auth import oidc
from lorenzo_cli.auth.store import CredentialsFile, StoredLogin
from lorenzo_cli.config import Settings

# Registered on the Authgear client as redirect URIs: one fixed port and a fallback or two.
CALLBACK_PORTS: tuple[int, ...] = (8766, 8767, 8768)
SCOPE = "openid offline_access"
_PAGE = b"<html><body>Signed in to Lorenzo - you can close this tab.</body></html>"


class LoginError(Exception):
    """The login couldn't be completed."""


def redirect_uri_for(port: int) -> str:
    return f"http://127.0.0.1:{port}/callback"


def make_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    return verifier, challenge


def authorization_url(
    endpoints: oidc.Endpoints, *, client_id: str, redirect_uri: str, challenge: str, state: str
) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return f"{endpoints.authorization_endpoint}?{query}"


def code_from_redirect(redirected_to: str, state: str) -> str:
    """The `code` in the address the browser was redirected to (or in just its query string)."""
    text = redirected_to.strip()
    query = urllib.parse.urlparse(text).query if "?" in text else text.lstrip("?")
    params = dict(urllib.parse.parse_qsl(query))
    if "error" in params:
        detail = params.get("error_description", "")
        raise LoginError(f"The login was refused: {params['error']} {detail}".strip())
    if params.get("state") != state:
        raise LoginError("That redirect doesn't belong to this login (the state doesn't match).")
    code = params.get("code")
    if not code:
        raise LoginError("There is no code in that address. Paste the whole address.")
    return code


class LoopbackReceiver:
    """A one-shot listener on 127.0.0.1 for the redirect."""

    def __init__(self, server: http.server.HTTPServer) -> None:
        self._server = server
        # Read back from the socket, so binding port 0 (tests) reports the port it got.
        self.port: int = server.server_address[1]
        self.redirect_uri = redirect_uri_for(self.port)
        self._params: dict[str, str] = {}
        server.RequestHandlerClass = self._handler()

    @classmethod
    def bind(cls, ports: Sequence[int] = CALLBACK_PORTS) -> Self:
        for port in ports:
            try:
                server = http.server.HTTPServer(
                    ("127.0.0.1", port), http.server.BaseHTTPRequestHandler
                )
            except OSError:
                continue
            return cls(server)
        raise LoginError(
            f"Couldn't listen on 127.0.0.1 port {' or '.join(map(str, ports))}. "
            "Free one, or use `lorenzo login --no-browser`."
        )

    def _handler(self) -> type[http.server.BaseHTTPRequestHandler]:
        params = self._params

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib's own naming
                query = urllib.parse.urlparse(self.path).query
                found = dict(urllib.parse.parse_qsl(query))
                if "code" in found or "error" in found:
                    params.update(found)
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(_PAGE)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass  # no per-request logging on the user's terminal

        return Handler

    def wait(self, timeout: float) -> str:
        """The redirect's query string, once one arrives; raises LoginError on timeout."""
        deadline = time.monotonic() + timeout
        self._server.timeout = 1.0
        while not self._params and time.monotonic() < deadline:
            self._server.handle_request()
        self._server.server_close()
        if not self._params:
            raise LoginError("Timed out waiting for the browser. Try `lorenzo login --no-browser`.")
        return urllib.parse.urlencode(self._params)

    def close(self) -> None:
        self._server.server_close()


def run_login(
    settings: Settings,
    *,
    no_browser: bool,
    http_client: httpx.Client,
    store: CredentialsFile,
    echo: Callable[[str], None],
    read_line: Callable[[str], str],
    open_browser: Callable[[str], object] = webbrowser.open,
    timeout: float = 300.0,
    ports: Sequence[int] = CALLBACK_PORTS,
) -> StoredLogin:
    if not settings.issuer or not settings.client_id:
        raise LoginError(
            "Both the issuer and the client id of the Authgear client are needed: pass --issuer "
            "and --client-id once (login remembers them) or set LORENZO_AUTHGEAR_ISSUER and "
            "LORENZO_AUTHGEAR_CLIENT_ID. Naming one of the three settings (API URL, issuer, "
            "client id) other than the official Lorenzo's turns the official defaults off. "
            "Or use LORENZO_TOKEN or --token-stdin."
        )
    try:
        endpoints = oidc.discover(settings.issuer, http_client)
    except (oidc.OidcError, httpx.HTTPError, KeyError) as exc:
        raise LoginError(f"Couldn't reach {settings.issuer}: {exc}") from exc

    verifier, challenge = make_pkce_pair()
    state = secrets.token_urlsafe(16)

    if no_browser:
        redirect_uri = redirect_uri_for(ports[0])
        url = authorization_url(
            endpoints,
            client_id=settings.client_id,
            redirect_uri=redirect_uri,
            challenge=challenge,
            state=state,
        )
        echo("Open this address in a browser on any machine and sign in:\n")
        echo(url + "\n")
        echo(
            "The browser will then fail to load a page at 127.0.0.1. That is expected: copy the "
            "address it ended up at."
        )
        code = code_from_redirect(read_line("Paste that address here: "), state)
    else:
        receiver = LoopbackReceiver.bind(ports)
        redirect_uri = receiver.redirect_uri
        url = authorization_url(
            endpoints,
            client_id=settings.client_id,
            redirect_uri=redirect_uri,
            challenge=challenge,
            state=state,
        )
        echo("Opening your browser to sign in. If nothing opens, use this address:\n")
        echo(url + "\n")
        try:
            open_browser(url)
            code = code_from_redirect(receiver.wait(timeout), state)
        finally:
            receiver.close()

    try:
        tokens = oidc.exchange_code(
            http_client,
            endpoints,
            client_id=settings.client_id,
            code=code,
            redirect_uri=redirect_uri,
            verifier=verifier,
        )
    except (oidc.OidcError, httpx.HTTPError, KeyError) as exc:
        raise LoginError(str(exc)) from exc

    login = StoredLogin(
        issuer=settings.issuer,
        client_id=settings.client_id,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_at=tokens.expires_at,
    )
    store.save(login)
    return login
