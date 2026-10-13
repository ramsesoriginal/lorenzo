"""`lorenzo login --token`: the device flow from the CLI's side (ADR 0269), against a fake API."""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from lorenzo_cli.auth.device import DeviceLoginError, run_device_login
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

runner = CliRunner()
FLOW = {
    "device_code": "dev-code",
    "user_code": "BCDF-GHJK",
    "verification_uri": "https://hub.example/device",
    "verification_uri_complete": "https://hub.example/device?code=BCDF-GHJK",
    "interval": 5,
    "expires_in": 600,
}


def problem(kind: str, status: int = 400) -> httpx.Response:
    return httpx.Response(status, json={"type": f"https://api.example/problems/{kind}"})


def fake_api(answers: list[httpx.Response], seen: list[httpx.Request]) -> httpx.MockTransport:
    remaining = list(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/device-codes":
            return httpx.Response(201, json=FLOW)
        if request.url.path == "/device-codes/token":
            return remaining.pop(0)
        if request.url.path == "/me":
            return httpx.Response(
                200,
                json={
                    "id": "00000000-0000-0000-0000-000000000001",
                    "authgear_subject_id": "x",
                    "memberships": [],
                    "players": [],
                    "campaign_gm_grants": [],
                    "email": None,
                    "nickname": None,
                    "display_name": None,
                    "pronouns": None,
                    "bio": None,
                    "locales": [],
                    "user_color": None,
                    "picture_url": "https://api.example/me/picture",
                    "capabilities": {"create_tenant": True},
                },
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


ISSUED = httpx.Response(
    200,
    json={
        "access_token": "lor_pat_secret",
        "token_type": "Bearer",
        "id": "00000000-0000-0000-0000-0000000000aa",
        "name": "Laptop",
        "expires_at": None,
    },
)


def run(
    answers: list[httpx.Response], tmp_path: Path, sleeps: list[float]
) -> tuple[list[str], list[httpx.Request], CredentialsFile]:
    seen: list[httpx.Request] = []
    store = CredentialsFile(tmp_path / "credentials.json")
    lines: list[str] = []
    with httpx.Client(transport=fake_api(answers, seen)) as http:
        run_device_login(
            "https://api.example",
            http_client=http,
            store=store,
            echo=lines.append,
            sleep=sleeps.append,
            client_name="test",
        )
    return lines, seen, store


def test_it_prints_the_code_and_the_address_polls_and_stores_the_token(tmp_path: Path) -> None:
    sleeps: list[float] = []
    lines, seen, store = run([problem("authorization-pending"), ISSUED], tmp_path, sleeps)
    text = "\n".join(lines)
    assert "https://hub.example/device?code=BCDF-GHJK" in text and "BCDF-GHJK" in text
    assert sleeps == [5.0, 5.0]
    assert json.loads(seen[0].content) == {"client_name": "test"}
    login = store.load()
    assert login is not None
    assert (login.access_token, login.token_name) == ("lor_pat_secret", "Laptop")
    assert oct(store.path.stat().st_mode & 0o777) == "0o600"


def test_slow_down_makes_it_wait_longer(tmp_path: Path) -> None:
    sleeps: list[float] = []
    run([problem("slow-down"), ISSUED], tmp_path, sleeps)
    assert sleeps == [5.0, 10.0]


@pytest.mark.parametrize(
    ("answer", "message"),
    [(problem("access-denied"), "denied"), (problem("device-code-expired"), "expired")],
)
def test_a_denied_or_expired_request_stops_with_a_message(
    answer: httpx.Response, message: str, tmp_path: Path
) -> None:
    with pytest.raises(DeviceLoginError, match=message):
        run([answer], tmp_path, [])
    assert not (tmp_path / "credentials.json").exists()


def test_it_gives_up_when_the_time_is_up(tmp_path: Path) -> None:
    clock = iter([0.0, 601.0])
    store = CredentialsFile(tmp_path / "credentials.json")
    with httpx.Client(transport=fake_api([], [])) as http, pytest.raises(DeviceLoginError):
        run_device_login(
            "https://api.example",
            http_client=http,
            store=store,
            echo=lambda _: None,
            sleep=lambda _: None,
            now=lambda: next(clock),
        )


def runtime(tmp_path: Path, answers: list[httpx.Response], seen: list[httpx.Request]) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=fake_api(answers, seen),
        sleep=lambda _: None,
    )


def test_login_token_then_requests_use_it_whoami_names_it_and_logout_forgets_it(
    tmp_path: Path,
) -> None:
    seen: list[httpx.Request] = []
    rt = runtime(tmp_path, [ISSUED], seen)
    login = runner.invoke(app, ["login", "--token"], obj=rt)
    assert login.exit_code == 0, login.output
    assert "Connected" in login.output

    who = runner.invoke(app, ["whoami"], obj=rt)
    assert who.exit_code == 0, who.output
    assert "personal access token" in who.output and "Laptop" in who.output
    assert seen[-1].headers["Authorization"] == "Bearer lor_pat_secret"

    out = runner.invoke(app, ["logout"], obj=rt)
    assert out.exit_code == 0
    assert "revoke" in out.output
    assert not (tmp_path / "credentials.json").exists()
