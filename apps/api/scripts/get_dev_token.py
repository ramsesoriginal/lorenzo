"""Get a real Authgear access token for local testing, without the manual
curl dance - RFC 8252's loopback-redirect pattern (the same one `gcloud auth
login`/`gh auth login` use): opens your browser, catches the redirect
locally, exchanges the code automatically, and prints the token.

Dev-only - never shipped, never registered as a [project.scripts] entry
point. Needs a registered OIDC client on whichever Authgear project you're
testing against, with http://127.0.0.1:8765/callback as an Authorized
Redirect URI - see docs/operations/local-authgear-setup.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import os
import secrets
import sys
import urllib.parse
import webbrowser

import httpx

from lorenzo_api.config import get_settings

_REDIRECT_URI = "http://127.0.0.1:8765/callback"
_SCOPE = "openid"


def _make_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    return verifier, challenge


def _fetch_endpoints(issuer: str) -> tuple[str, str]:
    response = httpx.get(f"{issuer}/.well-known/openid-configuration")
    response.raise_for_status()
    config = response.json()
    return config["authorization_endpoint"], config["token_endpoint"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--issuer",
        default=None,
        help="Authgear project to use (defaults to this app's own AUTHGEAR_ISSUER - "
        "whatever your .env already points at). Override to test against production "
        "without touching .env.",
    )
    args = parser.parse_args()

    client_id = os.environ.get("AUTHGEAR_DEV_CLIENT_ID")
    client_secret = os.environ.get("AUTHGEAR_DEV_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit(
            "Set AUTHGEAR_DEV_CLIENT_ID and AUTHGEAR_DEV_CLIENT_SECRET first "
            "(the client registered on your Authgear project - see "
            "docs/operations/local-authgear-setup.md). Not read from .env: these "
            "identify a login-flow client, not something apps/api itself needs to run."
        )

    issuer = args.issuer or get_settings().authgear_issuer
    authorization_endpoint, token_endpoint = _fetch_endpoints(issuer)

    verifier, challenge = _make_pkce_pair()
    auth_url = f"{authorization_endpoint}?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _REDIRECT_URI,
            "response_type": "code",
            "scope": _SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    # Closes over `result` rather than a class-level attribute - HTTPServer
    # constructs the handler itself per request, so a nested class capturing
    # this function's own local is simpler than threading a mutable
    # container through some other channel.
    result: dict[str, str] = {}

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib's own naming
            query = urllib.parse.urlparse(self.path).query
            result.update(urllib.parse.parse_qsl(query))
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Signed in - you can close this tab.</body></html>")

        def log_message(self, log_format: str, *args: object) -> None:
            pass  # silence the default per-request stderr logging

    print(f"Opening your browser to log in against {issuer} ...")
    webbrowser.open(auth_url)

    # One request only, by design - a single login round-trip, not a
    # long-lived listener (unlike tests/_fake_jwks.py's ThreadingHTTPServer,
    # which serves a whole test suite's worth of concurrent requests).
    server = http.server.HTTPServer(("127.0.0.1", 8765), _CallbackHandler)
    server.handle_request()

    if "error" in result:
        sys.exit(f"Login failed: {result['error']} - {result.get('error_description', '')}")
    code = result.get("code")
    if not code:
        sys.exit(f"No code in the callback - got: {result}")

    token_response = httpx.post(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": verifier,
        },
    )
    if token_response.is_error:
        sys.exit(f"Token exchange failed ({token_response.status_code}): {token_response.text}")
    access_token: str = token_response.json()["access_token"]

    print("\nAccess token:")
    print(access_token)
    print("\nTry it:")
    print(f'curl -H "Authorization: Bearer {access_token}" http://localhost:8000/me')


if __name__ == "__main__":
    main()
