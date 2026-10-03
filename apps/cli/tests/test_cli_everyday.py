"""`--version`, shell completion, `tenant list` and `whoami` (ADR 0153, 0154, 0155, 0158)."""

from __future__ import annotations

import importlib.metadata
import io
import json
from pathlib import Path

import httpx
from plain import plain
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile, StoredLogin
from lorenzo_cli.main import Runtime, app

runner = CliRunner()

USER_ID = "0a1b2c3d-1111-4222-8333-444455556666"
ME = {
    "id": USER_ID,
    "authgear_subject_id": "sub-1",
    "email": "alice@example.com",
    "nickname": "alice",
    "display_name": "Alice Archivist",
    "pronouns": None,
    "bio": None,
    "locales": [],
    "user_color": None,
    "picture_url": "https://api.example/me/picture",
    "memberships": [
        {"tenant_id": "11111111-1111-1111-1111-111111111111", "role": "owner"},
        {"tenant_id": "22222222-2222-2222-2222-222222222222", "role": "participant"},
    ],
    "players": [],
    "campaign_gm_grants": [],
}
SUMMARIES = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "slug": "sunken-vale",
        "name": "Sunken Vale",
        "role": "owner",
        "kind": "repository",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "slug": "table-one",
        "name": "Table One",
        "role": "participant",
        "kind": "play",
    },
]


def api(seen: list[httpx.Request], *, me_status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/me":
            if me_status != 200:
                return httpx.Response(me_status, json={"title": "Unauthorized", "detail": "no"})
            return httpx.Response(200, json=ME)
        if request.url.path == "/tenants":
            kind = request.url.params.get("kind")
            rows = [row for row in SUMMARIES if kind is None or row["kind"] == kind]
            page = int(request.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "items": rows[page - 1 : page],
                    "total": len(rows),
                    "page": page,
                    "size": 1,
                    "pages": len(rows),
                },
            )
        return httpx.Response(404, json={"title": "Not Found", "detail": "No such thing."})

    return httpx.MockTransport(handler)


def runtime(tmp_path: Path, seen: list[httpx.Request], **env: str) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok", **env},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=api(seen),
    )


# --- --version ---------------------------------------------------------------------------


def test_version_prints_the_installed_package_version(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--version"], obj=runtime(tmp_path, []))

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == f"lorenzo {importlib.metadata.version('lorenzo-cli')}"


def test_version_needs_no_api_url_login_or_network(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    bare = Runtime(
        env={},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=api(seen),
    )
    result = runner.invoke(app, ["--version"], obj=bare)

    assert result.exit_code == 0, result.output
    assert seen == []


def test_version_wins_over_a_command(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--version", "whoami"], obj=runtime(tmp_path, []))

    assert result.exit_code == 0
    assert result.stdout.startswith("lorenzo ")


# --- shell completion ---------------------------------------------------------------------


def test_help_offers_install_and_show_completion(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--help"], obj=runtime(tmp_path, []))

    assert "--install-completion" in plain(result.output)
    assert "--show-completion" in plain(result.output)


def test_show_completion_prints_a_script_without_touching_any_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--show-completion", "bash"], obj=runtime(tmp_path, []))

    assert result.exit_code == 0, result.output
    assert "_lorenzo_completion" in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_tab_completes_options_and_subcommands(tmp_path: Path) -> None:
    def complete(words: str, cword: int) -> list[str]:
        result = runner.invoke(
            app,
            [],
            obj=runtime(tmp_path, []),
            env={
                "_LORENZO_COMPLETE": "complete_bash",
                "COMP_WORDS": words,
                "COMP_CWORD": str(cword),
            },
        )
        return result.stdout.split()

    assert complete("lorenzo --ver", 1) == ["--version"]
    assert {"show", "list", "create"} <= set(complete("lorenzo tenant ", 2))


# --- tenant list --------------------------------------------------------------------------


def test_tenant_list_shows_every_page_with_kind_and_role(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(app, ["tenant", "list"], obj=runtime(tmp_path, seen))

    assert result.exit_code == 0, result.output
    for expected in ("sunken-vale", "Table One", "repository", "play", "owner", "participant"):
        assert expected in result.output
    assert [r.url.params["page"] for r in seen] == ["1", "2"]
    assert seen[0].headers["Authorization"] == "Bearer tok"


def test_tenant_list_kind_is_the_apis_own_filter(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app, ["tenant", "list", "--kind", "repository"], obj=runtime(tmp_path, seen)
    )

    assert result.exit_code == 0, result.output
    assert "sunken-vale" in result.output
    assert "table-one" not in result.output
    assert {r.url.params["kind"] for r in seen} == {"repository"}


def test_tenant_list_json_is_one_array_of_what_the_api_returned(tmp_path: Path) -> None:
    result = runner.invoke(app, ["tenant", "list", "--json"], obj=runtime(tmp_path, []))

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == SUMMARIES


def test_tenant_list_with_no_tenants_says_so_and_is_not_an_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["tenant", "list", "--kind", "play", "--json"], obj=runtime(tmp_path, [])
    )
    assert json.loads(result.stdout) == [SUMMARIES[1]]

    def nothing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"items": [], "total": 0, "page": 1, "size": 100, "pages": 0}
        )

    rt = runtime(tmp_path, [])
    rt.transport = httpx.MockTransport(nothing)
    empty = runner.invoke(app, ["tenant", "list"], obj=rt)

    assert empty.exit_code == 0, empty.output
    assert "don't belong to any tenant" in empty.output


# --- whoami -------------------------------------------------------------------------------


def test_whoami_names_the_user_the_api_and_where_the_token_came_from(tmp_path: Path) -> None:
    result = runner.invoke(app, ["whoami"], obj=runtime(tmp_path, []))

    assert result.exit_code == 0, result.output
    for expected in (USER_ID, "Alice Archivist", "alice@example.com", "https://api.example"):
        assert expected in result.output
    assert "LORENZO_TOKEN" in result.output
    assert "2" in result.output


def test_whoami_json_is_what_the_api_said(tmp_path: Path) -> None:
    result = runner.invoke(app, ["whoami", "--json"], obj=runtime(tmp_path, []))

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["id"] == USER_ID


def test_whoami_says_where_a_stored_login_came_from(tmp_path: Path) -> None:
    rt = runtime(tmp_path, [])
    rt.env = {"LORENZO_API_URL": "https://api.example"}
    rt.store.save(StoredLogin(issuer="https://auth.example", client_id="cli", access_token="a1"))
    result = runner.invoke(app, ["whoami"], obj=rt)

    assert result.exit_code == 0, result.output
    assert "stored login" in result.output


def test_whoami_with_a_piped_token_says_so(tmp_path: Path) -> None:
    rt = runtime(tmp_path, [])
    rt.env = {"LORENZO_API_URL": "https://api.example"}
    rt.stdin = io.StringIO("piped-token\n")
    rt.token_stdin = True
    result = runner.invoke(app, ["whoami"], obj=rt)

    assert result.exit_code == 0, result.output
    assert "--token-stdin" in result.output


def test_a_rejected_token_is_named_with_what_to_do(tmp_path: Path) -> None:
    rt = runtime(tmp_path, [])
    rt.transport = api([], me_status=401)
    result = runner.invoke(app, ["whoami"], obj=rt)

    assert result.exit_code == 1
    assert "LORENZO_TOKEN" in result.output
    assert "lorenzo login" in result.output
    assert "401" in result.output


def test_any_other_refusal_shows_its_own_detail(tmp_path: Path) -> None:
    rt = runtime(tmp_path, [])
    rt.transport = api([], me_status=403)
    result = runner.invoke(app, ["whoami"], obj=rt)

    assert result.exit_code == 1
    assert "403" in result.output
    assert "lorenzo login" not in result.output
