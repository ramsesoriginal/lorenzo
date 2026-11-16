"""`lorenzo legal` (ADR 0439): the legal notice and privacy policy of the Lorenzo you use."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import httpx
from plain import plain
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

runner = CliRunner()

REGISTRY: dict[str, Any] = {
    "apps": {"legal": {"url": "https://legal.example.org"}},
    "links": {
        "legal_notice_en": "https://legal.example.org/en/legal-notice/",
        "legal_notice_de": "https://legal.example.org/de/impressum/",
        "legal_privacy_en": "https://legal.example.org/en/privacy-policy/",
        "legal_privacy_de": "https://legal.example.org/de/datenschutz/",
    },
    "support_url": "https://support.example.org/x",
}


def run(tmp_path: Path, handler: Any, *args: str):
    runtime = Runtime(
        env={"LORENZO_API_URL": "https://api.example"},  # no token: the registry is public
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=httpx.MockTransport(handler),
    )
    return runner.invoke(app, list(args), obj=runtime)


def test_legal_prints_the_addresses_without_a_login(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=REGISTRY)

    result = run(tmp_path, handler, "legal")

    assert result.exit_code == 0, result.output
    text = plain(result.output)
    assert "https://legal.example.org/en/legal-notice/" in text
    assert "https://legal.example.org/de/datenschutz/" in text
    assert "https://support.example.org/x" in text
    assert [r.url.path for r in seen] == ["/app-links"]
    assert "authorization" not in seen[0].headers


def test_legal_can_print_json(tmp_path: Path) -> None:
    result = run(tmp_path, lambda r: httpx.Response(200, json=REGISTRY), "legal", "--json")

    assert (
        json.loads(result.stdout)["privacy policy"]
        == "https://legal.example.org/en/privacy-policy/"
    )


def test_a_deployment_with_no_legal_pages_says_so_and_exits_1(tmp_path: Path) -> None:
    bare = {"apps": {}, "links": {"item": "https://x/item"}}

    result = run(tmp_path, lambda r: httpx.Response(200, json=bare), "legal")

    assert result.exit_code == 1
    assert "has not published a legal notice or a privacy policy" in plain(result.output)


def test_an_unreachable_api_is_one_line_not_a_traceback(tmp_path: Path) -> None:
    result = run(tmp_path, lambda r: httpx.Response(500, text="no"), "legal")

    assert result.exit_code == 1
    assert "Could not read https://api.example/app-links" in plain(result.output)


def test_the_help_points_to_it(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--help"])

    assert "lorenzo legal" in plain(result.output)
