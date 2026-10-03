"""The API URL, issuer and client id `lorenzo login` remembers (ADR 0157)."""

from __future__ import annotations

import io
import stat
import tomllib
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from lorenzo_cli import main as main_module
from lorenzo_cli.auth.login import LoginError
from lorenzo_cli.auth.store import CredentialsFile, StoredLogin
from lorenzo_cli.config import Settings, SettingsFile, default_config_path, load_settings
from lorenzo_cli.main import Runtime, app

runner = CliRunner()

ISSUER = "https://example.authgear.cloud"
API = "https://api.example"


def triple(settings: Settings) -> tuple[str | None, str | None, str | None]:
    return (settings.api_url, settings.issuer, settings.client_id)


def test_the_file_round_trips_and_is_plain_toml(tmp_path: Path) -> None:
    file = SettingsFile(tmp_path / "lorenzo" / "config.toml")
    file.save({"api_url": API, "issuer": ISSUER, "client_id": "abc123"})

    assert file.load() == {"api_url": API, "issuer": ISSUER, "client_id": "abc123"}
    assert tomllib.loads(file.path.read_text()) == file.load()
    assert stat.S_IMODE(file.path.parent.stat().st_mode) == 0o700


def test_saving_keeps_what_was_remembered_and_changes_what_was_given(tmp_path: Path) -> None:
    file = SettingsFile(tmp_path / "config.toml")
    file.save({"api_url": API, "issuer": ISSUER})
    file.save({"client_id": "abc123", "api_url": "https://other.example"})

    assert file.load() == {
        "api_url": "https://other.example",
        "issuer": ISSUER,
        "client_id": "abc123",
    }


def test_a_value_with_quotes_survives(tmp_path: Path) -> None:
    file = SettingsFile(tmp_path / "config.toml")
    file.save({"client_id": 'we"ird\\id'})

    assert file.load() == {"client_id": 'we"ird\\id'}


def test_unknown_keys_and_non_strings_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('api_url = "https://api.example"\ncolour = "blue"\nissuer = 5\n')

    assert SettingsFile(path).load() == {"api_url": "https://api.example"}


def test_a_missing_file_reads_as_empty_without_a_warning(tmp_path: Path) -> None:
    warned: list[str] = []

    assert SettingsFile(tmp_path / "none.toml").load(warn=warned.append) == {}
    assert warned == []


def test_a_garbled_file_reads_as_empty_with_a_warning_and_never_crashes(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("api_url = = =")
    warned: list[str] = []

    assert SettingsFile(path).load(warn=warned.append) == {}
    assert len(warned) == 1
    assert str(path) in warned[0]


def test_saving_over_a_garbled_file_replaces_it(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("api_url = = =")
    SettingsFile(path).save({"api_url": API})

    assert SettingsFile(path).load() == {"api_url": API}


def test_the_default_path_follows_xdg() -> None:
    assert default_config_path({"XDG_CONFIG_HOME": "/x"}) == Path("/x/lorenzo/config.toml")
    assert default_config_path({}).parts[-2:] == ("lorenzo", "config.toml")


def test_a_flag_beats_the_environment_beats_the_file() -> None:
    remembered = {"api_url": "file", "issuer": "file", "client_id": "file"}
    env = {"LORENZO_API_URL": "env", "LORENZO_AUTHGEAR_ISSUER": "env"}

    settings = load_settings(env, api_url="flag", remembered=remembered)

    assert triple(settings) == ("flag", "env", "file")
    assert not settings.defaulted


def test_empty_values_fall_through_to_the_next_source() -> None:
    settings = load_settings({"LORENZO_API_URL": ""}, api_url="", remembered={"api_url": "file"})

    assert settings.api_url == "file"
    # Nothing but empty values is nothing named: the official Lorenzo is the default (ADR 0164).
    assert load_settings({"LORENZO_AUTHGEAR_ISSUER": ""}, client_id="").defaulted


# --- through the commands -------------------------------------------------------------------


def runtime(tmp_path: Path, **env: str) -> Runtime:
    return Runtime(
        env=dict(env),
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        config=SettingsFile(tmp_path / "config.toml"),
    )


class FakeLogin:
    """Stands in for the OIDC flow, which test_auth.py already covers."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.seen: list[Settings] = []

    def __call__(self, settings: Settings, **kwargs: object) -> StoredLogin:
        self.seen.append(settings)
        if self.fail:
            raise LoginError("The login was refused.")
        return StoredLogin(
            issuer=settings.issuer or "", client_id=settings.client_id or "", access_token="a"
        )


@pytest.fixture
def fake_login(monkeypatch: pytest.MonkeyPatch) -> FakeLogin:
    fake = FakeLogin()
    monkeypatch.setattr(main_module, "run_login", fake)
    return fake


def test_the_first_login_remembers_all_three_and_says_so(
    tmp_path: Path, fake_login: FakeLogin
) -> None:
    rt = runtime(tmp_path)
    result = runner.invoke(
        app,
        ["--api-url", API, "login", "--issuer", ISSUER, "--client-id", "abc123"],
        obj=rt,
    )

    assert result.exit_code == 0, result.output
    assert rt.config is not None
    assert rt.config.load() == {"api_url": API, "issuer": ISSUER, "client_id": "abc123"}
    assert "Remembered the API URL, issuer, client id" in result.output
    assert "Signed in." in result.output


def test_the_next_login_needs_nothing_and_remembers_nothing_new(
    tmp_path: Path, fake_login: FakeLogin
) -> None:
    rt = runtime(tmp_path)
    assert rt.config is not None
    rt.config.save({"api_url": API, "issuer": ISSUER, "client_id": "abc123"})

    result = runner.invoke(app, ["login"], obj=rt)

    assert result.exit_code == 0, result.output
    assert [triple(seen) for seen in fake_login.seen] == [(API, ISSUER, "abc123")]
    assert "Remembered" not in result.output


def test_environment_beats_the_file_and_a_flag_beats_both_and_the_change_is_kept(
    tmp_path: Path, fake_login: FakeLogin
) -> None:
    rt = runtime(tmp_path, LORENZO_AUTHGEAR_CLIENT_ID="from-env")
    assert rt.config is not None
    rt.config.save({"api_url": API, "issuer": ISSUER, "client_id": "from-file"})

    result = runner.invoke(app, ["login", "--issuer", "https://other.authgear.cloud"], obj=rt)

    assert result.exit_code == 0, result.output
    assert triple(fake_login.seen[0]) == (API, "https://other.authgear.cloud", "from-env")
    assert rt.config.load() == {
        "api_url": API,
        "issuer": "https://other.authgear.cloud",
        "client_id": "from-env",
    }


def test_a_login_that_fails_remembers_nothing(tmp_path: Path, fake_login: FakeLogin) -> None:
    fake_login.fail = True
    rt = runtime(tmp_path)
    result = runner.invoke(
        app, ["--api-url", API, "login", "--issuer", ISSUER, "--client-id", "x"], obj=rt
    )

    assert result.exit_code == 1
    assert not (tmp_path / "config.toml").exists()


def test_something_that_is_not_an_address_is_refused_before_signing_in(
    tmp_path: Path, fake_login: FakeLogin
) -> None:
    result = runner.invoke(app, ["--api-url", "nope", "login"], obj=runtime(tmp_path))

    assert result.exit_code == 1
    assert "isn't an address" in result.output
    assert fake_login.seen == []

    other = runner.invoke(app, ["login", "--issuer", "ftp://x.example"], obj=runtime(tmp_path))
    assert other.exit_code == 1
    assert "issuer" in other.output
    assert fake_login.seen == []


def test_logout_forgets_the_tokens_and_keeps_the_settings(tmp_path: Path) -> None:
    rt = runtime(tmp_path)
    assert rt.config is not None
    rt.config.save({"api_url": API})
    rt.store.save(StoredLogin(issuer=ISSUER, client_id="c", access_token="a"))

    result = runner.invoke(app, ["logout"], obj=rt)

    assert result.exit_code == 0, result.output
    assert rt.store.load() is None
    assert rt.config.load() == {"api_url": API}


def test_other_commands_read_the_remembered_api_url_and_never_write_it(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"items": [], "total": 0, "page": 1, "size": 100, "pages": 0}
        )

    rt = runtime(tmp_path, LORENZO_TOKEN="tok")
    rt.transport = httpx.MockTransport(handler)
    assert rt.config is not None
    rt.config.save({"api_url": "https://remembered.example"})

    first = runner.invoke(app, ["tenant", "list"], obj=rt)
    second = runner.invoke(app, ["--api-url", "https://oneoff.example", "tenant", "list"], obj=rt)

    assert first.exit_code == 0 and second.exit_code == 0, (first.output, second.output)
    assert [r.url.host for r in seen] == ["remembered.example", "oneoff.example"]
    assert rt.config.load() == {"api_url": "https://remembered.example"}


def test_a_missing_api_url_says_how_to_remember_one(tmp_path: Path) -> None:
    # Naming another issuer turns the official defaults off, so the API URL is missing.
    rt = runtime(tmp_path, LORENZO_TOKEN="tok", LORENZO_AUTHGEAR_ISSUER=ISSUER)
    result = runner.invoke(app, ["tenant", "list"], obj=rt)

    assert result.exit_code == 1
    said = " ".join(result.output.split())  # the terminal wraps long lines
    assert "LORENZO_API_URL" in said
    assert "lorenzo login --api-url" in said
    assert "the issuer here names another" in said


def test_a_garbled_settings_file_warns_and_the_command_still_runs(tmp_path: Path) -> None:
    rt = runtime(tmp_path, LORENZO_TOKEN="tok", LORENZO_API_URL=API)
    assert rt.config is not None
    rt.config.path.write_text("= = =")
    rt.transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"items": [], "total": 0, "page": 1, "size": 100, "pages": 0}
        )
    )

    result = runner.invoke(app, ["tenant", "list"], obj=rt)

    assert result.exit_code == 0, result.output
    assert "Ignoring" in result.output
