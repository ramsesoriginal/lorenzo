"""`whoami`, `tenant list` and `api` against the real API (ADR 0154, 0155, 0161)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from e2e.helpers import make_tenant, run_cli
from e2e.stack import Stack


def test_whoami_names_the_user_the_api_knows_from_the_token(stack: Stack, tmp_path: Path) -> None:
    subject = f"whoami-{uuid.uuid4().hex[:8]}"
    token = stack.creator_token(subject)

    result = run_cli(stack, token, tmp_path, "whoami", "--json")

    assert result.exit_code == 0, result.output
    me = json.loads(result.stdout)
    assert me["authgear_subject_id"] == subject
    plain = run_cli(stack, token, tmp_path, "whoami")
    assert me["id"] in plain.output
    assert "LORENZO_TOKEN" in plain.output


def test_a_token_the_api_does_not_accept_is_named(stack: Stack, tmp_path: Path) -> None:
    result = run_cli(stack, "not-a-real-token", tmp_path, "whoami")

    assert result.exit_code == 1
    assert "didn't accept the token" in " ".join(result.output.split())
    assert "401" in result.output


def test_tenant_list_shows_what_the_user_belongs_to_and_filters_by_kind(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token(f"lister-{uuid.uuid4().hex[:8]}")
    repository = make_tenant(stack, token, "repository")
    play = make_tenant(stack, token, "play")

    everything = json.loads(run_cli(stack, token, tmp_path, "tenant", "list", "--json").stdout)
    repositories = json.loads(
        run_cli(stack, token, tmp_path, "tenant", "list", "--kind", "repository", "--json").stdout
    )

    kinds = {row["slug"]: row["kind"] for row in everything}
    assert kinds == {repository: "repository", play: "play"}
    assert {row["slug"] for row in repositories} == {repository}
    assert {row["role"] for row in everything} == {"owner"}
    table = run_cli(stack, token, tmp_path, "tenant", "list")
    assert repository in table.output and play in table.output


def test_api_makes_the_request_the_cli_would_and_prints_what_came_back(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token(f"raw-{uuid.uuid4().hex[:8]}")
    slug = f"e2e-{uuid.uuid4().hex[:10]}"

    created = run_cli(
        stack, token, tmp_path, "api", "POST", "/tenants",
        "-d", json.dumps({"name": "Raw", "slug": slug, "kind": "play"}),
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    tenant = json.loads(created.stdout)
    assert tenant["slug"] == slug

    one = run_cli(stack, token, tmp_path, "api", "GET", f"/tenants/{tenant['id']}", "--include")
    assert one.exit_code == 0, one.output
    assert one.stdout.startswith("HTTP/")
    assert f'"slug": "{slug}"' in one.stdout

    paged = run_cli(stack, token, tmp_path, "api", "GET", "/tenants", "--paginate")
    assert [row["slug"] for row in json.loads(paged.stdout)] == [slug]


def test_api_prints_a_refusal_as_the_api_sent_it_and_exits_one(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token(f"raw-{uuid.uuid4().hex[:8]}")

    result = run_cli(stack, token, tmp_path, "api", "GET", f"/tenants/{uuid.uuid4()}")

    assert result.exit_code == 1
    assert json.loads(result.stdout)["status"] == 404
    assert "HTTP 404" in result.stderr


def test_api_will_not_send_the_token_to_another_host(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token(f"raw-{uuid.uuid4().hex[:8]}")

    result = run_cli(stack, token, tmp_path, "api", "GET", "https://evil.example/tenants")

    assert result.exit_code == 2
