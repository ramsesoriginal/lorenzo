from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
from typer.testing import CliRunner

from lorenzo_cli.auth.store import CredentialsFile, StoredLogin
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


def api(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/tenants":
            page = int(request.url.params["page"])
            summaries = [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "slug": "elsewhere",
                    "name": "Elsewhere",
                    "role": "participant",
                    "kind": "play",
                },
                {
                    "id": TENANT_ID,
                    "slug": "sunken-vale",
                    "name": "Sunken Vale",
                    "role": "owner",
                    "kind": "repository",
                },
            ]
            return httpx.Response(
                200,
                json={
                    "items": summaries[page - 1 : page],
                    "total": 2,
                    "page": page,
                    "size": 1,
                    "pages": 2,
                },
            )
        if request.url.path == f"/tenants/{TENANT_ID}":
            return httpx.Response(200, json=TENANT)
        return httpx.Response(404, json={"title": "Not Found", "detail": "No such thing."})

    return httpx.MockTransport(handler)


def runtime(tmp_path: Path, seen: list[httpx.Request], **env: str) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok", **env},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=api(seen),
    )


def test_tenant_show_by_id_prints_the_kind_and_published_state(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(app, ["tenant", "show", TENANT_ID], obj=runtime(tmp_path, seen))

    assert result.exit_code == 0, result.output
    assert "repository" in result.output
    assert "no" in result.output
    assert seen[0].headers["Authorization"] == "Bearer tok"


def test_tenant_show_by_slug_pages_through_the_users_tenants(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app, ["tenant", "show", "sunken-vale", "--json"], obj=runtime(tmp_path, seen)
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["id"] == TENANT_ID
    assert [r.url.path for r in seen] == ["/tenants", "/tenants", f"/tenants/{TENANT_ID}"]


def test_an_unknown_slug_is_a_clean_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["tenant", "show", "nope"], obj=runtime(tmp_path, []))

    assert result.exit_code == 1
    assert "nope" in result.output


def test_an_api_error_shows_its_detail_and_status(tmp_path: Path) -> None:
    other = "22222222-2222-2222-2222-222222222222"
    result = runner.invoke(app, ["tenant", "show", other], obj=runtime(tmp_path, []))

    assert result.exit_code == 1
    assert "No such thing." in result.output
    assert "404" in result.output


def test_no_api_url_is_refused_before_any_request(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    rt = runtime(tmp_path, seen)
    # Another issuer named: no official default is filled in around it (ADR 0164).
    rt.env = {"LORENZO_TOKEN": "tok", "LORENZO_AUTHGEAR_ISSUER": "https://other.example"}
    result = runner.invoke(app, ["tenant", "show", TENANT_ID], obj=rt)

    assert result.exit_code == 1
    assert "LORENZO_API_URL" in result.output
    assert seen == []


def test_the_api_url_can_come_from_the_option(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    rt = runtime(tmp_path, seen)
    rt.env = {"LORENZO_TOKEN": "tok"}
    result = runner.invoke(
        app, ["--api-url", "https://elsewhere.example", "tenant", "show", TENANT_ID], obj=rt
    )

    assert result.exit_code == 0, result.output
    assert seen[0].url.host == "elsewhere.example"


def test_no_token_says_how_to_log_in(tmp_path: Path) -> None:
    rt = runtime(tmp_path, [])
    rt.env = {"LORENZO_API_URL": "https://api.example"}
    result = runner.invoke(app, ["tenant", "show", TENANT_ID], obj=rt)

    assert result.exit_code == 1
    assert "lorenzo login" in result.output


def test_a_token_can_be_piped_in(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    rt = runtime(tmp_path, seen)
    rt.env = {"LORENZO_API_URL": "https://api.example"}
    rt.stdin = io.StringIO("piped-token\n")
    result = runner.invoke(app, ["--token-stdin", "tenant", "show", TENANT_ID], obj=rt)

    assert result.exit_code == 0, result.output
    assert seen[0].headers["Authorization"] == "Bearer piped-token"


def test_login_without_a_client_explains_and_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["login"], obj=runtime(tmp_path, []))

    assert result.exit_code == 1
    assert "LORENZO_AUTHGEAR_CLIENT_ID" in result.output


def test_logout_forgets_the_stored_login(tmp_path: Path) -> None:
    rt = runtime(tmp_path, [])
    rt.store.save(StoredLogin("https://auth.example", "cli", "a1"))

    first = runner.invoke(app, ["logout"], obj=rt)
    second = runner.invoke(app, ["logout"], obj=rt)

    assert "Signed out" in first.output
    assert "no stored login" in second.output
    assert rt.store.load() is None


def test_no_arguments_shows_the_help() -> None:
    result = runner.invoke(app, [])
    assert "tenant" in result.output
    assert "login" in result.output


CORPUS = Path(__file__).parent / "corpus"


def test_inspect_shows_the_files_lists_and_what_was_stubbed(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["inspect", str(CORPUS / "stubs" / "uses_sheet.js")],
        obj=runtime(tmp_path, []),
    )

    assert result.exit_code == 0, result.output
    assert "uses_sheet.js" in result.output
    assert "WeaponsList" in result.output
    assert "What (2)" in result.output
    assert "stubbed sheet call" in result.output


def test_inspect_starts_the_lists_from_the_base_files_and_names_each_entrys_file(
    tmp_path: Path,
) -> None:
    case = CORPUS / "base_and_patch"
    result = runner.invoke(
        app,
        ["inspect", "--base", str(case / "base.js"), str(case / "homebrew.js"), "--json"],
        obj=runtime(tmp_path, []),
    )

    assert result.exit_code == 0, result.output
    origins = json.loads(result.output)["origins"]["WeaponsList"]
    assert origins == {
        "longsword": "base.js",
        "dagger": "homebrew.js",
        "glass sword": "homebrew.js",
    }


def test_inspect_exits_1_when_a_file_fails_but_still_reports_the_rest(tmp_path: Path) -> None:
    errors = CORPUS / "errors"
    result = runner.invoke(
        app,
        ["inspect", str(errors / "syntax_error.js"), str(errors / "fine.js")],
        obj=runtime(tmp_path, []),
    )

    assert result.exit_code == 1
    assert "fine.js" in result.output
    assert "WeaponsList" in result.output


def test_inspect_reports_a_missing_file_as_a_usage_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["inspect", str(tmp_path / "nope.js")], obj=runtime(tmp_path, []))

    assert result.exit_code == 2


def creating(seen: list[httpx.Request], *, status: int = 201) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and request.url.path == "/tenants":
            body = json.loads(request.content)
            if status != 201:
                return httpx.Response(
                    status, json={"title": "Forbidden", "detail": "You can't create tenants."}
                )
            return httpx.Response(
                201, json={**TENANT, "name": body["name"], "slug": body["slug"] or "derived",
                           "kind": body["kind"]}
            )  # fmt: skip
        return httpx.Response(404, json={"title": "Not Found", "detail": "No such thing."})

    return httpx.MockTransport(handler)


def creator(tmp_path: Path, transport: httpx.MockTransport) -> Runtime:
    return Runtime(
        env={"LORENZO_API_URL": "https://api.example", "LORENZO_TOKEN": "tok"},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
        transport=transport,
    )


def test_tenant_create_makes_a_repository_unless_told_otherwise(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app,
        ["tenant", "create", "My Homebrew", "--slug", "my-homebrew"],
        obj=creator(tmp_path, creating(seen)),
    )

    assert result.exit_code == 0, result.output
    assert json.loads(seen[0].content) == {
        "name": "My Homebrew",
        "slug": "my-homebrew",
        "description": None,
        "kind": "repository",
    }
    assert "repository" in result.output
    assert "lorenzo seed --tenant my-homebrew" in result.output


def test_tenant_create_can_make_a_play_tenant_and_prints_json(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app,
        ["tenant", "create", "Our Table", "--kind", "play", "--description", "Fridays", "--json"],
        obj=creator(tmp_path, creating(seen)),
    )

    assert result.exit_code == 0, result.output
    assert json.loads(seen[0].content)["kind"] == "play"
    assert json.loads(seen[0].content)["description"] == "Fridays"
    assert json.loads(result.output)["kind"] == "play"


def test_tenant_create_without_the_creator_role_shows_why(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["tenant", "create", "X"], obj=creator(tmp_path, creating([], status=403))
    )

    assert result.exit_code == 1
    assert "can't create tenants" in result.output
    assert "403" in result.output


def test_a_kind_that_does_not_exist_is_refused_before_any_request(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    result = runner.invoke(
        app, ["tenant", "create", "X", "--kind", "castle"], obj=creator(tmp_path, creating(seen))
    )

    assert result.exit_code == 2
    assert seen == []
