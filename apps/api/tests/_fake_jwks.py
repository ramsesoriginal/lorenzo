"""A real, local, fake JWKS server for testing Authgear token verification
(ADR 0023) - a real RSA keypair, served as a real JWKS document over a
real local HTTP listener (a background daemon thread - PyJWKClient itself
is synchronous, stdlib urllib, no injectable transport, so a real listener
is the only practical way to exercise its real fetch-and-verify code path).
Only the issuer is fake here, not the verification mechanism.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from lorenzo_api.config import get_settings

_KEY_ID = "fake-jwks-test-key"


class FakeJwksServer:
    def __init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        jwk = RSAAlgorithm.to_jwk(self._private_key.public_key(), as_dict=True)
        jwk["kid"] = _KEY_ID
        jwk["use"] = "sig"
        jwk["alg"] = "RS256"
        jwks_body = json.dumps({"keys": [jwk]}).encode()

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - required name, stdlib's own API
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(jwks_body)))
                self.end_headers()
                self.wfile.write(jwks_body)

            def log_message(self, format: str, *args: Any) -> None:
                pass  # keep pytest output quiet - this is a test double, not a real service

        # Threading, not plain HTTPServer - a single stuck/lingering
        # connection must not be able to block every other test's request
        # to this same server behind it.
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def jwks_url(self) -> str:
        host, port = self._server.server_address[0], self._server.server_address[1]
        return f"http://{host}:{port}/jwks"

    def issue_token(
        self,
        subject: str,
        *,
        issuer: str | None = None,
        audience: str | None = None,
        expires_delta: timedelta = timedelta(minutes=5),
        key_id: str | None = None,
        **extra_claims: object,
    ) -> str:
        """Signs a token with the fake server's private key. `issuer`/
        `audience` default to whatever the app's own Settings actually
        expect - a "valid" token needs no extra arguments; negative-path
        tests pass a deliberately wrong value for one or the other.
        """
        settings = get_settings()
        now = datetime.now(tz=UTC)
        claims: dict[str, object] = {
            "sub": subject,
            "iss": issuer if issuer is not None else settings.authgear_issuer,
            "aud": audience if audience is not None else settings.authgear_audience,
            "iat": now,
            "exp": now + expires_delta,
            **extra_claims,
        }
        return jwt.encode(
            claims, self._private_key, algorithm="RS256", headers={"kid": key_id or _KEY_ID}
        )

    def shutdown(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
