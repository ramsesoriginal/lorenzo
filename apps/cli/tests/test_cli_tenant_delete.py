"""`lorenzo tenant delete` (ADR 0184): what it asks, what it sends, and how it puts the API's
refusals."""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
from plain import plain
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app

runner = CliRunner()

TENANT_ID = "6f1d3c0e-5a3f-4b8e-9d1e-0b7c1c2d3e4f"
TENANT = {
    "id": TENANT_ID,
    "slug": "sunken-vale",
    "name": "Sunken Vale",
    "description": "",
    "kind": "repository",
    "published_at": None,
    "npcs_shared_with_gms": True,
    "created_by": None,
    "updated_by": None,
}


def api(
    seen: list[httpx.Request], *, deleting: httpx.Response | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/tenants":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": TENANT_ID,
                            "slug": "sunken-vale",
                            "name": "Sunken Vale",
                            "role": "owner",
                            "kind": "repository",
                        }
                    ],
                    "total": 1,
                    "page": 1,
                    "size": 50,
                    "pages": 1,
                },
            )
        if request.method == "GET" and request.url.path == f"/tenants/{TENANT_ID}":
            return httpx.Response(200, json=TENANT)
        if request.method == "DELETE" and request.url.path == f"/tenants/{TENANT_ID}":
            return deleting or httpx.Response(204)
        return httpx.Response(404, json={"title": "Not Found", "detail": "No such thing."})

    return httpx.MockTransport(handler)


def runtime(
    tmp_path: Path, transport: httpx.MockTransport, *, interactive: bool | None = None
) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=transport,
        interactive_override=interactive,
    )


def deletes(seen: list[httpx.Request]) -> list[httpx.Request]:
    return [r for r in seen if r.method == "DELETE"]


def test_it_asks_for_the_slug_and_then_deletes(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app,
        ["tenant", "delete", "sunken-vale"],
        obj=runtime(tmp_path, api(seen), interactive=True),
        input="sunken-vale\n",
    )

    assert result.exit_code == 0, result.output
    assert [r.url.path for r in deletes(seen)] == [f"/tenants/{TENANT_ID}"]
    text = plain(result.output)
    assert "This deletes “Sunken Vale” and everything in it." in text
    assert "Deleted sunken-vale" in text


def test_a_wrong_slug_deletes_nothing(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app,
        ["tenant", "delete", "sunken-vale"],
        obj=runtime(tmp_path, api(seen), interactive=True),
        input="sunken\n",
    )

    assert result.exit_code == 1
    assert "Nothing was deleted." in plain(result.output)
    assert deletes(seen) == []


def test_yes_skips_the_question(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app, ["tenant", "delete", "sunken-vale", "--yes"], obj=runtime(tmp_path, api(seen))
    )

    assert result.exit_code == 0, result.output
    assert len(deletes(seen)) == 1


def test_where_nothing_can_be_asked_it_needs_yes_and_sends_nothing(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    asked = runner.invoke(
        app,
        ["tenant", "delete", "sunken-vale"],
        obj=runtime(tmp_path, api(seen), interactive=False),
    )
    as_json = runner.invoke(
        app,
        ["tenant", "delete", "sunken-vale", "--json"],
        obj=runtime(tmp_path, api(seen), interactive=True),
    )

    for result in (asked, as_json):
        assert result.exit_code == 1
        assert "run again with --yes" in plain(result.output)
    assert deletes(seen) == []


def test_json_prints_the_tenant_that_was_deleted(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["tenant", "delete", TENANT_ID, "--yes", "--json"],
        obj=runtime(tmp_path, api([])),
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["slug"] == "sunken-vale"


def test_a_repository_others_hold_is_refused_with_the_way_out(tmp_path: Path) -> None:
    refusing = httpx.Response(
        409,
        json={
            "type": "repository-still-granted",
            "title": "Other tenants still hold this repository",
            "detail": f"Tenant {TENANT_ID} is still granted to 2 tenant(s)",
        },
    )
    result = runner.invoke(
        app,
        ["tenant", "delete", "sunken-vale", "--yes"],
        obj=runtime(tmp_path, api([], deleting=refusing)),
    )

    assert result.exit_code == 1
    text = " ".join(plain(result.output).split())
    assert "still granted to 2 tenant(s)" in text
    assert "lorenzo repo subscribers --tenant sunken-vale" in text
    assert "lorenzo repo revoke <tenant> --tenant sunken-vale" in text
    assert "HTTP 409" in text


def test_a_refusal_for_a_missing_role_or_ownership_is_shown_as_the_api_said_it(
    tmp_path: Path,
) -> None:
    refusing = httpx.Response(
        403,
        json={
            "type": "tenant-deletion-forbidden",
            "title": "Only an owner can delete a tenant",
            "detail": f"Only an owner of tenant {TENANT_ID} can delete it",
        },
    )
    result = runner.invoke(
        app,
        ["tenant", "delete", "sunken-vale", "--yes"],
        obj=runtime(tmp_path, api([], deleting=refusing)),
    )

    assert result.exit_code == 1
    assert "Only an owner" in plain(result.output)
    assert "HTTP 403" in plain(result.output)


def test_a_tenant_that_isnt_there_is_said_plainly(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["tenant", "delete", "elsewhere", "--yes"], obj=runtime(tmp_path, api([]))
    )

    assert result.exit_code == 1
    assert "no tenant “elsewhere”" in plain(result.output)
