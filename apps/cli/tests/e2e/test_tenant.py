"""`lorenzo tenant create` against the real API (ADR 0147)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from e2e.helpers import run_cli, tenant_id
from e2e.stack import Stack


def test_a_repository_is_created_and_seeded_from_the_command_line(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    slug = f"e2e-{uuid.uuid4().hex[:10]}"

    created = run_cli(stack, token, tmp_path, "tenant", "create", "Homebrew", "--slug", slug)
    seeded = run_cli(stack, token, tmp_path, "seed", "--tenant", slug, "--yes")

    assert created.exit_code == 0, created.output
    assert f"lorenzo seed --tenant {slug}" in created.output
    assert seeded.exit_code == 0, seeded.output  # a repository, so nothing refuses it
    with stack.api(token) as api:
        detail = api.get(f"/tenants/{tenant_id(api, slug)}").json()
    assert detail["kind"] == "repository"


def test_a_play_tenant_can_be_asked_for_and_the_importer_then_refuses_it(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    slug = f"e2e-{uuid.uuid4().hex[:10]}"

    created = run_cli(
        stack, token, tmp_path, "tenant", "create", "Table", "--slug", slug, "--kind", "play",
        "--json",
    )  # fmt: skip
    seeded = run_cli(stack, token, tmp_path, "seed", "--tenant", slug, "--yes")

    assert json.loads(created.stdout)["kind"] == "play"
    assert seeded.exit_code == 1
    assert "play tenant" in seeded.output
