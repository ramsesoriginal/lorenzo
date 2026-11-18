"""Completing names from the private cache (ADR 0507): what the client's replies write to it, how
it is keyed and kept private, and what Tab offers from it."""

from __future__ import annotations

import base64
import json
import os
import stat
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.main import get_command

from lorenzo_cli import completion
from lorenzo_cli.main import app

LIBRARY = str(uuid.UUID(int=1))
API = "https://api.example.test"


def row(name: str, n: int, **more: Any) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.UUID(int=n), name=name, slug=name, **more)


def page(*rows: SimpleNamespace, total: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(items=list(rows), page=1, total=len(rows) if total is None else total)


def jwt(claims: dict[str, str]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"e30.{body}.signature"


def recorded(tmp_path: Path, *calls: tuple[str, dict[str, object], Any, Any]) -> dict[str, Any]:
    recorder = completion.Recorder(tmp_path / "names.json")
    for operation_id, path, query, value in calls:
        recorder.saw(operation_id, path, query, value)
    recorder.flush()
    return completion.load(tmp_path / "names.json")


def test_a_complete_list_replaces_the_names_and_a_filtered_one_only_adds(tmp_path: Path) -> None:
    library = {"tenant_id": LIBRARY}
    data = recorded(
        tmp_path,
        ("list_stat_definitions", library, {"page": 1}, page(row("old", 1), row("strength", 2))),
        ("list_stat_definitions", library, {"page": 1}, page(row("strength", 2), row("dex", 3))),
        ("list_stat_definitions", library, {"system": "x"}, page(row("wis", 4))),
        ("list_stat_definitions", library, {"page": 1}, page(row("cha", 5), total=40)),
    )

    assert sorted(data["names"][LIBRARY]["stats"].values()) == ["cha", "dex", "strength", "wis"]


def test_a_write_adds_its_row_and_a_delete_takes_it_out(tmp_path: Path) -> None:
    library = {"tenant_id": LIBRARY}
    data = recorded(
        tmp_path,
        ("create_system", library, None, row("dnd5e", 7)),
        ("create_system", library, None, row("wg", 8)),
        ("delete_system", {**library, "system_id": uuid.UUID(int=8)}, None, None),
        ("create_tenant", {}, None, SimpleNamespace(id=uuid.UUID(int=1), slug="my-library")),
    )

    assert list(data["names"][LIBRARY]["systems"].values()) == ["dnd5e"]
    assert data["libraries"] == {LIBRARY: "my-library"}


def test_only_features_are_kept_from_the_entries_a_command_reads(tmp_path: Path) -> None:
    data = recorded(
        tmp_path,
        (
            "export_entities",
            {"tenant_id": LIBRARY},
            None,
            page(row("second-wind", 1, kinds=["feature"]), row("longsword", 2, kinds=["item"])),
        ),
    )

    assert list(data["names"][LIBRARY]["features"].values()) == ["second-wind"]


def test_the_cache_is_private_and_nothing_is_written_when_nothing_changed(tmp_path: Path) -> None:
    path = tmp_path / "lorenzo" / "names.json"
    recorder = completion.Recorder(path)
    recorder.saw("get_stat_group", {"tenant_id": LIBRARY}, None, row("physical", 1))
    recorder.flush()
    written = path.stat().st_mtime_ns
    again = completion.Recorder(path)
    again.saw("get_stat_group", {"tenant_id": LIBRARY}, None, row("physical", 1))
    again.flush()

    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert path.stat().st_mtime_ns == written
    assert again.changed is False


def test_a_file_is_kept_per_api_and_account() -> None:
    env = {"XDG_CACHE_HOME": "/cache"}
    alice = completion.account_of(jwt({"iss": "https://auth", "sub": "alice"}))
    bob = completion.account_of(jwt({"iss": "https://auth", "sub": "bob"}))

    assert alice == "https://auth alice"
    assert completion.cache_path(env, API, alice) != completion.cache_path(env, API, bob)
    assert completion.cache_path(env, API, alice) != completion.cache_path(env, API + "2", alice)
    assert completion.cache_path(env, API + "/", alice) == completion.cache_path(env, API, alice)
    assert completion.account_of("lzp_personal").startswith("token ")  # type: ignore[union-attr]
    assert completion.account_of(None) is None


def test_a_broken_or_foreign_file_completes_nothing(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("{not json")
    (tmp_path / "b.json").write_text(json.dumps({"format": 99, "libraries": {"x": "y"}}))

    assert completion.load(tmp_path / "a.json")["libraries"] == {}
    assert completion.load(tmp_path / "b.json")["libraries"] == {}
    assert completion.load(tmp_path / "missing.json")["names"] == {}


def complete(words: str, env: dict[str, str]) -> list[str]:
    """What Tab offers at the end of `words`, through the real command tree."""
    import contextlib
    import io
    from contextlib import redirect_stdout

    os_env = {
        "_LORENZO_COMPLETE": "complete_bash",
        "COMP_WORDS": words,
        "COMP_CWORD": str(len(words.split(" ")) - 1),
        **env,
    }
    old = {key: os.environ.get(key) for key in os_env}
    os.environ.update(os_env)
    out = io.StringIO()
    try:
        with redirect_stdout(out), contextlib.suppress(SystemExit):
            get_command(app).main([], prog_name="lorenzo", standalone_mode=False)
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return [line.split(",", 1)[-1] for line in out.getvalue().splitlines() if line]


@pytest.fixture
def cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    token = jwt({"iss": "https://auth", "sub": "alice"})
    env = {"XDG_CACHE_HOME": str(tmp_path), "LORENZO_TOKEN": token, "LORENZO_API_URL": API}
    path = completion.cache_path(env, API, completion.account_of(token) or "")
    recorder = completion.Recorder(path)
    recorder.saw("list_tenants", {}, {"page": 1}, page(SimpleNamespace(id=LIBRARY, slug="vale")))
    recorder.saw("list_systems", {"tenant_id": LIBRARY}, None, page(row("dnd5e", 1), row("wg", 2)))
    recorder.saw(
        "list_stat_definitions",
        {"tenant_id": LIBRARY},
        None,
        page(row("dnd5e_strength", 3), row("wg_strength", 4)),
    )
    recorder.flush()
    for key in ("LORENZO_TENANT", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return env


def test_tab_completes_a_library_and_then_its_names(cached: dict[str, str]) -> None:
    assert complete("lorenzo system list -t v", cached) == ["vale"]
    assert complete("lorenzo system show -t vale ", cached) == ["dnd5e", "wg"]
    assert complete("lorenzo formula show -t vale dnd", cached) == ["dnd5e_strength"]
    assert complete("lorenzo system show ", {**cached, "LORENZO_TENANT": "vale"}) == [
        "dnd5e",
        "wg",
    ]
    assert complete("lorenzo system show -t elsewhere ", cached) == []


def test_tab_with_another_account_completes_nothing(cached: dict[str, str]) -> None:
    other = {**cached, "LORENZO_TOKEN": jwt({"iss": "https://auth", "sub": "bob"})}

    assert complete("lorenzo system list -t v", other) == []


def test_logout_forgets_the_names_cached_for_that_login(tmp_path: Path) -> None:
    import io

    from typer.testing import CliRunner

    from lorenzo_cli.auth.store import CredentialsFile, StoredLogin
    from lorenzo_cli.runtime import Runtime

    token = jwt({"iss": "https://auth", "sub": "alice"})
    store = CredentialsFile(tmp_path / "credentials.json")
    store.save(StoredLogin(issuer="https://auth", client_id="cli", access_token=token))
    env = {"XDG_CACHE_HOME": str(tmp_path / "cache"), "LORENZO_API_URL": API}
    path = completion.cache_path(env, API, completion.account_of(token) or "")
    completion.save(path, {"format": 1, "libraries": {LIBRARY: "vale"}, "names": {}})
    runtime = Runtime(env=env, stdin=io.StringIO(), store=store)

    result = CliRunner().invoke(app, ["logout"], obj=runtime)

    assert result.exit_code == 0, result.output
    assert not path.exists()
