from __future__ import annotations

import io
import json
import stat
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from lorenzo_cli.auth import login as login_module
from lorenzo_cli.auth.login import (
    LoginError,
    LoopbackReceiver,
    authorization_url,
    code_from_redirect,
    make_pkce_pair,
    run_login,
)
from lorenzo_cli.auth.oidc import Endpoints
from lorenzo_cli.auth.store import CredentialsFile, StoredLogin, default_path
from lorenzo_cli.auth.tokens import (
    NotLoggedInError,
    StaticToken,
    StoredToken,
    resolve_token_source,
)
from lorenzo_cli.config import Settings

ISSUER = "https://auth.example"
ENDPOINTS = Endpoints(f"{ISSUER}/authorize", f"{ISSUER}/token")


def issuer_transport(seen: list[httpx.Request] | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": ENDPOINTS.authorization_endpoint,
                    "token_endpoint": ENDPOINTS.token_endpoint,
                },
            )
        if request.url.path == "/token":
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["refresh_token"]:
                return httpx.Response(
                    200, json={"access_token": "renewed", "refresh_token": "r2", "expires_in": 3600}
                )
            return httpx.Response(
                200, json={"access_token": "a1", "refresh_token": "r1", "expires_in": 3600}
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_the_pkce_challenge_is_the_s256_of_the_verifier() -> None:
    # RFC 7636, appendix B.
    import base64
    import hashlib

    verifier, challenge = make_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert challenge == expected.decode()
    assert 43 <= len(verifier) <= 128


def test_the_authorization_url_carries_pkce_state_and_the_offline_scope() -> None:
    url = authorization_url(
        ENDPOINTS,
        client_id="cli",
        redirect_uri="http://127.0.0.1:8766/callback",
        challenge="C",
        state="S",
    )
    query = parse_qs(urlparse(url).query)
    assert url.startswith(ENDPOINTS.authorization_endpoint + "?")
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid offline_access"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == ["C"]
    assert query["state"] == ["S"]


def test_the_code_is_read_from_a_whole_redirect_or_just_its_query() -> None:
    assert code_from_redirect("http://127.0.0.1:8766/callback?code=abc&state=S", "S") == "abc"
    assert code_from_redirect("code=abc&state=S", "S") == "abc"
    assert code_from_redirect("  ?code=abc&state=S\n", "S") == "abc"


def test_a_redirect_for_another_login_or_with_an_error_is_refused() -> None:
    with pytest.raises(LoginError, match="state"):
        code_from_redirect("http://x/callback?code=abc&state=OTHER", "S")
    with pytest.raises(LoginError, match="access_denied"):
        code_from_redirect("http://x/callback?error=access_denied&state=S", "S")
    with pytest.raises(LoginError, match="no code"):
        code_from_redirect("http://x/callback?state=S", "S")


def test_the_loopback_receiver_catches_the_redirect() -> None:
    receiver = LoopbackReceiver.bind(ports=(0,))
    result: list[str] = []
    thread = threading.Thread(target=lambda: result.append(receiver.wait(timeout=10)))
    thread.start()
    response = httpx.get(f"{receiver.redirect_uri}?code=abc&state=S")
    thread.join(timeout=10)

    assert response.status_code == 200
    assert code_from_redirect(result[0], "S") == "abc"


def test_the_loopback_receiver_ignores_stray_requests_and_times_out() -> None:
    receiver = LoopbackReceiver.bind(ports=(0,))
    thread = threading.Thread(
        target=lambda: httpx.get(f"http://127.0.0.1:{receiver.port}/favicon.ico")
    )
    thread.start()
    with pytest.raises(LoginError, match="Timed out"):
        receiver.wait(timeout=1.5)
    thread.join()


def test_a_busy_port_falls_back_to_the_next() -> None:
    first = LoopbackReceiver.bind(ports=(0,))
    try:
        second = LoopbackReceiver.bind(ports=(first.port, 0))
        second.close()
        assert second.port != first.port
    finally:
        first.close()


def test_the_credentials_file_is_private_and_round_trips(tmp_path: Path) -> None:
    store = CredentialsFile(tmp_path / "config" / "lorenzo" / "credentials.json")
    login = StoredLogin(ISSUER, "cli", "a1", "r1", 123.0)

    store.save(login)

    assert store.load() == login
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700
    store.save(StoredLogin(ISSUER, "cli", "a2"))  # overwriting keeps it private
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert store.delete() is True
    assert store.delete() is False
    assert store.load() is None


def test_a_garbled_credentials_file_reads_as_logged_out(tmp_path: Path) -> None:
    path = tmp_path / "credentials.json"
    path.write_text("{not json")
    assert CredentialsFile(path).load() is None
    path.write_text(json.dumps({"unexpected": 1}))
    assert CredentialsFile(path).load() is None


def test_the_default_path_follows_xdg() -> None:
    assert default_path({"XDG_CONFIG_HOME": "/x"}) == Path("/x/lorenzo/credentials.json")
    assert default_path({}).parts[-3:] == (".config", "lorenzo", "credentials.json")


def test_token_sources_are_tried_stdin_then_env_then_the_stored_login(tmp_path: Path) -> None:
    store = CredentialsFile(tmp_path / "credentials.json")
    store.save(StoredLogin(ISSUER, "cli", "stored"))
    with httpx.Client(transport=issuer_transport()) as http:

        def pick(token_stdin: bool, env: dict[str, str]) -> str:
            return resolve_token_source(
                token_stdin=token_stdin,
                stdin=io.StringIO("piped\n"),
                env=env,
                store=store,
                http=http,
            ).token()

        assert pick(True, {"LORENZO_TOKEN": "from-env"}) == "piped"
        assert pick(False, {"LORENZO_TOKEN": " from-env "}) == "from-env"
        assert pick(False, {}) == "stored"


def test_no_token_anywhere_says_how_to_get_one(tmp_path: Path) -> None:
    with (
        httpx.Client(transport=issuer_transport()) as http,
        pytest.raises(NotLoggedInError, match="lorenzo login"),
    ):
        resolve_token_source(
            token_stdin=False,
            stdin=io.StringIO(""),
            env={},
            store=CredentialsFile(tmp_path / "credentials.json"),
            http=http,
        )


def test_an_empty_stdin_is_an_error(tmp_path: Path) -> None:
    with (
        httpx.Client(transport=issuer_transport()) as http,
        pytest.raises(NotLoggedInError, match="piped"),
    ):
        resolve_token_source(
            token_stdin=True,
            stdin=io.StringIO("\n"),
            env={},
            store=CredentialsFile(tmp_path / "credentials.json"),
            http=http,
        )


def test_a_plain_token_cannot_refresh() -> None:
    assert StaticToken("t").refresh() is None


def test_an_expired_stored_token_is_renewed_and_saved(tmp_path: Path) -> None:
    store = CredentialsFile(tmp_path / "credentials.json")
    login = StoredLogin(ISSUER, "cli", "stale", "r1", expires_at=1000.0)
    store.save(login)

    with httpx.Client(transport=issuer_transport()) as http:
        token = StoredToken(login, store, http, now=lambda: 2000.0)
        assert token.token() == "renewed"

    saved = store.load()
    assert saved is not None
    assert (saved.access_token, saved.refresh_token) == ("renewed", "r2")


def test_a_token_that_is_still_good_is_left_alone(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    login = StoredLogin(ISSUER, "cli", "fine", "r1", expires_at=10_000.0)
    with httpx.Client(transport=issuer_transport(seen)) as http:
        assert (
            StoredToken(login, CredentialsFile(tmp_path / "c.json"), http, now=lambda: 1.0).token()
            == "fine"
        )
    assert seen == []


def test_a_failed_renewal_falls_back_to_the_old_token(tmp_path: Path) -> None:
    login = StoredLogin(ISSUER, "cli", "old", "r1", expires_at=1.0)
    down = httpx.MockTransport(lambda request: httpx.Response(500))
    with httpx.Client(transport=down) as http:
        token = StoredToken(login, CredentialsFile(tmp_path / "c.json"), http, now=lambda: 2000.0)
        assert token.token() == "old"
        assert token.refresh() is None


def test_a_login_without_a_refresh_token_cannot_refresh(tmp_path: Path) -> None:
    login = StoredLogin(ISSUER, "cli", "old")
    with httpx.Client(transport=issuer_transport()) as http:
        assert StoredToken(login, CredentialsFile(tmp_path / "c.json"), http).refresh() is None


def test_login_without_a_configured_client_says_what_to_do(tmp_path: Path) -> None:
    with (
        httpx.Client(transport=issuer_transport()) as http,
        pytest.raises(LoginError, match="issuer and the client id"),
    ):
        run_login(
            Settings(None, None, None),
            no_browser=True,
            http_client=http,
            store=CredentialsFile(tmp_path / "c.json"),
            echo=lambda _: None,
            read_line=lambda _: "",
        )


def test_login_with_no_browser_prints_the_url_and_takes_the_pasted_redirect(tmp_path: Path) -> None:
    store = CredentialsFile(tmp_path / "c.json")
    printed: list[str] = []
    settings = Settings("https://api.example", ISSUER, "cli")

    def paste(_: str) -> str:
        url = next(line for line in printed if line.startswith(ENDPOINTS.authorization_endpoint))
        state = parse_qs(urlparse(url.strip()).query)["state"][0]
        return f"http://127.0.0.1:{login_module.CALLBACK_PORTS[0]}/callback?code=abc&state={state}"

    with httpx.Client(transport=issuer_transport()) as http:
        login = run_login(
            settings,
            no_browser=True,
            http_client=http,
            store=store,
            echo=printed.append,
            read_line=paste,
        )

    assert login.access_token == "a1"
    assert store.load() == login


def test_login_with_a_browser_catches_the_redirect_on_the_loopback(tmp_path: Path) -> None:
    settings = Settings("https://api.example", ISSUER, "cli")
    store = CredentialsFile(tmp_path / "c.json")

    def open_browser(url: str) -> None:
        query = parse_qs(urlparse(url).query)
        redirect = query["redirect_uri"][0]
        state = query["state"][0]
        threading.Thread(target=lambda: httpx.get(f"{redirect}?code=abc&state={state}")).start()

    with httpx.Client(transport=issuer_transport()) as http:
        login = run_login(
            settings,
            no_browser=False,
            http_client=http,
            store=store,
            echo=lambda _: None,
            read_line=lambda _: "",
            open_browser=open_browser,
            timeout=10,
            ports=(0,),
        )

    assert login.access_token == "a1"
