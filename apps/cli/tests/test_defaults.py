"""The official Lorenzo as the default, as a set and only when nothing else is named (ADR 0164)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from lorenzo_cli import main as main_module
from lorenzo_cli.auth.login import LoginError
from lorenzo_cli.auth.store import CredentialsFile, StoredLogin
from lorenzo_cli.config import ConfigError, Settings, SettingsFile, load_settings
from lorenzo_cli.defaults import OFFICIAL_API_URL, OFFICIAL_CLIENT_ID, OFFICIAL_ISSUER
from lorenzo_cli.main import Runtime, app

runner = CliRunner()

OFFICIAL = (OFFICIAL_API_URL, OFFICIAL_ISSUER, OFFICIAL_CLIENT_ID)
OFFICIAL_HOST = "lorenzo-api-100817212329.europe-west1.run.app"
NOTE = f"Using the official Lorenzo at {OFFICIAL_API_URL}."
LOCAL = "http://localhost:8000"
MINE = "https://mine.example"
OTHER_ISSUER = "https://other.authgear.cloud"


def triple(settings: Settings) -> tuple[str | None, str | None, str | None]:
    return (settings.api_url, settings.issuer, settings.client_id)


# --- the rule ---------------------------------------------------------------------------------


def test_the_defaults_are_the_official_instance() -> None:
    assert OFFICIAL_API_URL.startswith("https://")
    assert OFFICIAL_ISSUER == "https://lorenzo.authgear.cloud"
    assert OFFICIAL_CLIENT_ID == "745e5fa9ac3cd9a1"


def test_with_nothing_named_the_three_official_values_are_the_settings() -> None:
    settings = load_settings({})

    assert triple(settings) == OFFICIAL
    assert settings.defaulted
    assert settings.named_elsewhere == ()


def test_naming_another_api_url_names_nothing_else_for_it() -> None:
    settings = load_settings({}, api_url=LOCAL)

    assert triple(settings) == (LOCAL, None, None)
    assert not settings.defaulted
    assert settings.named_elsewhere == ("api_url",)


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"LORENZO_AUTHGEAR_ISSUER": OTHER_ISSUER}, (None, OTHER_ISSUER, None)),
        ({"LORENZO_AUTHGEAR_CLIENT_ID": "mine"}, (None, None, "mine")),
        ({"LORENZO_API_URL": LOCAL}, (LOCAL, None, None)),
    ],
)
def test_any_one_setting_named_otherwise_turns_the_defaults_off(
    env: dict[str, str], expected: tuple[str | None, str | None, str | None]
) -> None:
    settings = load_settings(env)

    assert triple(settings) == expected
    assert not settings.defaulted


def test_a_remembered_value_counts_as_named() -> None:
    settings = load_settings({}, remembered={"api_url": LOCAL})

    assert triple(settings) == (LOCAL, None, None)
    assert not settings.defaulted


def test_the_official_values_named_are_the_same_as_naming_nothing() -> None:
    named = load_settings(
        {"LORENZO_AUTHGEAR_ISSUER": OFFICIAL_ISSUER + "/"},
        api_url=OFFICIAL_API_URL + "/",
        client_id=OFFICIAL_CLIENT_ID,
    )

    assert triple(named) == OFFICIAL
    assert named.defaulted


def test_one_official_value_beside_another_party_is_a_mixed_pair_and_stays_as_named() -> None:
    settings = load_settings({}, api_url=OFFICIAL_API_URL, issuer=OTHER_ISSUER)

    assert triple(settings) == (OFFICIAL_API_URL, OTHER_ISSUER, None)
    assert not settings.defaulted
    assert settings.named_elsewhere == ("issuer",)


def test_the_missing_address_says_why_no_default_applies() -> None:
    settings = load_settings({"LORENZO_AUTHGEAR_ISSUER": OTHER_ISSUER})

    with pytest.raises(ConfigError, match="the issuer here names another") as raised:
        settings.require_api_url()
    assert "LORENZO_API_URL" in str(raised.value)


def test_the_file_can_be_deleted_and_a_missing_one_says_so(tmp_path: Path) -> None:
    file = SettingsFile(tmp_path / "config.toml")

    assert file.delete() is False
    file.save({"api_url": LOCAL})
    assert file.delete() is True
    assert not file.path.exists()


# --- through the commands ---------------------------------------------------------------------


def answering(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and request.url.path == "/tenants":
            return httpx.Response(
                201,
                json={
                    "id": "6f1d3c0e-5a3f-4b8e-9d1e-0b7c1c2d3e4f",
                    "slug": "core",
                    "name": "Core",
                    "description": "",
                    "kind": "repository",
                    "published_at": None,
                    "npcs_shared_with_gms": True,
                    "created_by": None,
                    "updated_by": None,
                },
            )
        return httpx.Response(
            200, json={"items": [], "total": 0, "page": 1, "size": 100, "pages": 0}
        )

    return httpx.MockTransport(handler)


def runtime(tmp_path: Path, seen: list[httpx.Request] | None = None, **env: str) -> Runtime:
    return Runtime(
        env={"LORENZO_TOKEN": "tok", **env},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        config=SettingsFile(tmp_path / "config.toml"),
        transport=answering([] if seen is None else seen),
    )


def test_a_read_goes_to_the_official_api_and_says_nothing(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(app, ["tenant", "list"], obj=runtime(tmp_path, seen))

    assert result.exit_code == 0, result.output
    assert {request.url.host for request in seen} == {OFFICIAL_HOST}
    assert "official" not in result.output


def test_a_write_says_where_it_goes_once_on_stderr(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app, ["tenant", "create", "Core", "--slug", "core", "--json"], obj=runtime(tmp_path, seen)
    )

    assert result.exit_code == 0, result.output
    assert seen[0].url.host == OFFICIAL_HOST
    assert result.stderr.count(NOTE) == 1
    assert json.loads(result.stdout)["slug"] == "core"  # stdout stays the document alone


def test_naming_the_api_silences_the_note_and_the_default(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app,
        ["--api-url", LOCAL, "tenant", "create", "Core", "--slug", "core"],
        obj=runtime(tmp_path, seen),
    )

    assert result.exit_code == 0, result.output
    assert seen[0].url.host == "localhost"
    assert "official" not in result.output


def test_the_official_address_named_is_still_the_default_and_still_says_so(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["--api-url", OFFICIAL_API_URL + "/", "tenant", "create", "Core", "--slug", "core"],
        obj=runtime(tmp_path),
    )

    assert result.exit_code == 0, result.output
    assert result.stderr.count(NOTE) == 1


def test_api_says_so_for_anything_but_a_get(tmp_path: Path) -> None:
    read = runner.invoke(app, ["api", "GET", "/tenants"], obj=runtime(tmp_path))
    write = runner.invoke(app, ["api", "POST", "/tenants", "--data", "{}"], obj=runtime(tmp_path))

    assert read.exit_code == 0 and write.exit_code == 0, (read.output, write.output)
    assert NOTE not in read.stderr
    assert write.stderr.count(NOTE) == 1


def test_a_dry_run_says_nothing_where_the_same_command_would(tmp_path: Path) -> None:
    # Neither finds the tenant (the stub lists none), but the note comes before that.
    dry = runner.invoke(app, ["seed", "--tenant", "core", "--dry-run"], obj=runtime(tmp_path))
    real = runner.invoke(app, ["seed", "--tenant", "core", "--yes"], obj=runtime(tmp_path))

    assert NOTE not in dry.output
    assert real.stderr.count(NOTE) == 1


def test_another_issuer_in_the_environment_means_no_default_api(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    rt = runtime(tmp_path, seen, LORENZO_AUTHGEAR_ISSUER=OTHER_ISSUER)
    result = runner.invoke(app, ["tenant", "list"], obj=rt)

    assert result.exit_code == 1
    assert seen == []
    assert "the issuer here names another" in " ".join(result.output.split())


def test_the_remembered_file_wins_over_the_default_and_is_not_announced(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    rt = runtime(tmp_path, seen)
    assert rt.config is not None
    rt.config.save({"api_url": "https://mine.example"})
    result = runner.invoke(app, ["tenant", "create", "Core", "--slug", "core"], obj=rt)

    assert result.exit_code == 0, result.output
    assert seen[0].url.host == "mine.example"
    assert "official" not in result.output


def api_row(output: str) -> list[str]:
    """What `whoami` printed beside "api", as words."""
    row = next(line for line in output.splitlines() if line.split()[:1] == ["api"])
    return row.split()[1:]


def test_whoami_marks_the_default(tmp_path: Path) -> None:
    me = {
        "id": "0a1b2c3d-1111-4222-8333-444455556666",
        "authgear_subject_id": "sub-1",
        "email": None,
        "nickname": None,
        "display_name": None,
        "pronouns": None,
        "bio": None,
        "locales": [],
        "user_color": None,
        "picture_url": "https://api.example/me/picture",
        "memberships": [],
        "players": [],
        "campaign_gm_grants": [],
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=me))
    by_default = runtime(tmp_path)
    by_default.transport = transport
    shown = runner.invoke(app, ["whoami"], obj=by_default)
    elsewhere = runtime(tmp_path)
    elsewhere.transport = transport
    named = runner.invoke(app, ["--api-url", MINE, "whoami"], obj=elsewhere)

    assert shown.exit_code == 0 and named.exit_code == 0, (shown.output, named.output)
    assert api_row(shown.output) == [OFFICIAL_API_URL, "(the", "default)"]
    assert api_row(named.output) == [MINE]


# --- login ------------------------------------------------------------------------------------


class FakeLogin:
    """Stands in for the OIDC flow, which test_auth.py already covers."""

    def __init__(self) -> None:
        self.seen: list[Settings] = []

    def __call__(self, settings: Settings, **kwargs: object) -> StoredLogin:
        self.seen.append(settings)
        return StoredLogin(
            issuer=settings.issuer or "", client_id=settings.client_id or "", access_token="a"
        )


@pytest.fixture
def fake_login(monkeypatch: pytest.MonkeyPatch) -> FakeLogin:
    fake = FakeLogin()
    monkeypatch.setattr(main_module, "run_login", fake)
    return fake


def test_a_plain_login_uses_the_official_set_says_so_and_remembers_nothing(
    tmp_path: Path, fake_login: FakeLogin
) -> None:
    rt = runtime(tmp_path)
    result = runner.invoke(app, ["login"], obj=rt)

    assert result.exit_code == 0, result.output
    assert [triple(seen) for seen in fake_login.seen] == [OFFICIAL]
    said = " ".join(result.output.split())
    assert f"Signing in at {OFFICIAL_ISSUER}, for the API at {OFFICIAL_API_URL}" in said
    assert "(the official Lorenzo)" in said
    assert "Remembered" not in result.output
    assert rt.config is not None
    assert not rt.config.path.exists()


def test_returning_to_the_official_set_forgets_what_was_remembered(
    tmp_path: Path, fake_login: FakeLogin
) -> None:
    rt = runtime(tmp_path)
    assert rt.config is not None
    rt.config.save({"api_url": LOCAL, "issuer": OTHER_ISSUER, "client_id": "mine"})

    result = runner.invoke(
        app,
        [
            "--api-url",
            OFFICIAL_API_URL,
            "login",
            "--issuer",
            OFFICIAL_ISSUER,
            "--client-id",
            OFFICIAL_CLIENT_ID,
        ],
        obj=rt,
    )

    assert result.exit_code == 0, result.output
    assert triple(fake_login.seen[0]) == OFFICIAL
    assert not rt.config.path.exists()
    assert "the official Lorenzo is the default again" in " ".join(result.output.split())


def test_a_login_for_another_party_is_remembered_and_not_called_official(
    tmp_path: Path, fake_login: FakeLogin
) -> None:
    rt = runtime(tmp_path)
    result = runner.invoke(
        app,
        ["--api-url", LOCAL, "login", "--issuer", OTHER_ISSUER, "--client-id", "mine"],
        obj=rt,
    )

    assert result.exit_code == 0, result.output
    assert rt.config is not None
    assert rt.config.load() == {"api_url": LOCAL, "issuer": OTHER_ISSUER, "client_id": "mine"}
    assert "official" not in result.output
    assert f"Signing in at {OTHER_ISSUER}, for the API at {LOCAL}." in " ".join(
        result.output.split()
    )


def test_login_with_only_another_issuer_asks_for_the_rest(tmp_path: Path) -> None:
    result = runner.invoke(app, ["login", "--issuer", OTHER_ISSUER], obj=runtime(tmp_path))

    assert result.exit_code == 1
    said = " ".join(result.output.split())
    assert "--client-id" in said
    assert "turns the official defaults off" in said


def test_a_failed_login_still_leaves_the_remembered_file_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(settings: Settings, **kwargs: object) -> StoredLogin:
        raise LoginError("The login was refused.")

    monkeypatch.setattr(main_module, "run_login", refuse)
    rt = runtime(tmp_path)
    assert rt.config is not None
    rt.config.save({"api_url": LOCAL})
    result = runner.invoke(
        app,
        ["--api-url", OFFICIAL_API_URL, "login", "--issuer", OFFICIAL_ISSUER, "--client-id",
         OFFICIAL_CLIENT_ID],
        obj=rt,
    )  # fmt: skip

    assert result.exit_code == 1
    assert rt.config.load() == {"api_url": LOCAL}
