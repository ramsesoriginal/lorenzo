"""`lorenzo tenant create` against the real API (ADR 0147)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from e2e.helpers import FIXTURES, run_cli, tenant_id
from e2e.stack import Stack


def test_a_repository_is_created_and_seeded_from_the_command_line(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    slug = f"e2e-{uuid.uuid4().hex[:10]}"

    created = run_cli(stack, token, tmp_path, "tenant", "create", "Homebrew", "--slug", slug)
    started = run_cli(stack, token, tmp_path, "apply", "--starter", "neutral", "-t", slug, "--yes")

    assert created.exit_code == 0, created.output
    assert f"lorenzo apply --starter neutral -t {slug}" in created.output
    assert started.exit_code == 0, started.output
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
    imported = run_cli(
        stack, token, tmp_path, "import", "mpmb", "plan", "--tenant", slug,
        str(FIXTURES / "weapons.js"),
    )  # fmt: skip

    assert json.loads(created.stdout)["kind"] == "play"
    assert imported.exit_code == 1
    assert "play tenant" in imported.output
