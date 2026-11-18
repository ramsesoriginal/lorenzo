"""The output, machine and write contracts every command shares (ADR 0495, ADR 0496)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from lorenzo_cli import console
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

runner = CliRunner()


def runtime(tmp_path: Path, handler, *, interactive: bool = False) -> Runtime:  # noqa: ANN001
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(handler),
        interactive_override=interactive,
    )


def missing(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        404,
        json={
            "type": "tenant-not-found",
            "title": "Not found",
            "status": 404,
            "detail": "No such.",
        },
    )


def created(request: httpx.Request) -> httpx.Response:
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
            "weapon_stat_group_id": None,
            "ability_information_type": None,
            "created_by": None,
            "updated_by": None,
        },
    )


def test_a_failure_under_json_is_one_error_document_on_stdout(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["tenant", "show", "nope", "--json"], obj=runtime(tmp_path, missing)
    )

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["format"] == 1
    assert document["error"]["status"] == 404
    assert document["error"]["code"] == "tenant-not-found"
    assert "✗ error" in result.stderr


def test_a_failure_without_json_leaves_stdout_empty(tmp_path: Path) -> None:
    result = runner.invoke(app, ["tenant", "show", "nope"], obj=runtime(tmp_path, missing))

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "✗ error" in result.stderr


def test_every_json_report_carries_its_format(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["tenant", "create", "Core", "--slug", "core", "--yes", "--json"],
        obj=runtime(tmp_path, created),
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["format"] == console.JSON_FORMAT


def test_a_write_with_nobody_to_ask_writes_nothing_and_exits_2(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return created(request)

    result = runner.invoke(app, ["tenant", "create", "Core"], obj=runtime(tmp_path, handler))

    assert result.exit_code == 2
    assert "--yes" in result.stderr
    assert [r for r in seen if r.method == "POST"] == []


def test_a_write_at_a_terminal_asks_once_on_stderr_and_a_no_writes_nothing(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return created(request)

    result = runner.invoke(
        app, ["tenant", "create", "Core"], obj=runtime(tmp_path, handler, interactive=True),
        input="n\n",
    )  # fmt: skip

    assert result.exit_code == 2
    assert "Create the repository tenant Core?" in result.stderr
    assert result.stdout.strip() in ("", "n")  # the runner echoes what was typed
    assert seen == []


def test_quiet_keeps_the_result_and_drops_the_notices(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["--quiet", "tenant", "create", "Core", "--yes"], obj=runtime(tmp_path, created)
    )

    assert result.exit_code == 0, result.output
    assert "core" in result.stdout  # the result stays
    assert result.stderr == ""  # no notice, no progress


def test_a_status_is_a_symbol_and_a_word_without_colour() -> None:
    for kind, (symbol, word, _style) in console.STATUS.items():
        assert console.status(kind, "x").plain == f"{symbol} {word}: x"


@pytest.mark.parametrize("flag", ["quiet", "no_progress", "json"])
def test_nothing_animates_when_asked_for_quiet(flag: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console

    monkeypatch.setattr(console, "err", Console(file=io.StringIO(), force_terminal=True))
    console.reset()
    assert console.animated()
    console.configure(**{flag: True})
    assert not console.animated()
    console.reset()


def test_nothing_animates_on_a_pipe_or_with_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console

    console.reset()
    monkeypatch.setattr(console, "err", Console(file=io.StringIO(), force_terminal=False))
    assert not console.animated()
    monkeypatch.setattr(console, "err", Console(file=io.StringIO(), force_terminal=True))
    monkeypatch.setenv("NO_COLOR", "1")
    assert not console.animated()


def test_a_wait_on_a_pipe_is_one_plain_line(monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console

    stream = io.StringIO()
    monkeypatch.setattr(console, "err", Console(file=stream, force_terminal=False))
    console.reset()
    with console.waiting("Planning"):
        pass
    with console.counting("Creating", 3) as steps:
        steps.advance()
        steps.describe("a thing")
    assert stream.getvalue().splitlines() == ["Planning…", "Creating: 3…"]
    assert "\x1b" not in stream.getvalue()
