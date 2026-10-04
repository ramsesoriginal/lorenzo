"""`--json` on `apply` and `pack give` against the real API (ADR 0156)."""

from __future__ import annotations

import json
from pathlib import Path

from e2e.helpers import FIXTURES, make_tenant, run_cli, tenant_id
from e2e.stack import Stack
from e2e.test_import_packs import a_party


def test_apply_json_is_one_document_and_never_asks(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    assert run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--yes").exit_code == 0
    apply = [
        "apply", "--tenant", tenant, str(FIXTURES / "gear.js"),
        "--review-queue", str(tmp_path / "review-queue.json"),
        "--proposed-map", str(tmp_path / "proposed.map.toml"),
        "--json",
    ]  # fmt: skip

    refused = run_cli(stack, token, tmp_path, *apply)
    assert refused.exit_code == 1  # it never asks, and was not told to write
    unwritten = json.loads(refused.stdout)
    assert unwritten["applied"] is None
    assert unwritten["plan"]["header"]["counts"]["create"] > 0
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        missing = api.get(f"/tenants/{tid}/entities/by-slug/basic-armour-purple-plate")
        assert missing.status_code == 404

    written = run_cli(stack, token, tmp_path, *apply, "--yes")
    assert written.exit_code == 0, written.output
    document = json.loads(written.stdout)  # nothing but the document
    assert document["applied"]["created"] > 0
    assert document["failures"] == []
    assert document["unresolved"] is False
    with stack.api(token) as api:
        found = api.get(f"/tenants/{tid}/entities/by-slug/basic-armour-purple-plate")
        assert found.status_code == 200

    again = run_cli(stack, token, tmp_path, *apply, "--yes")
    assert again.exit_code == 0, again.output
    assert json.loads(again.stdout)["applied"] is None  # nothing left to write


def test_pack_give_json_is_what_the_api_made(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant, _, who = a_party(stack, token, tmp_path)
    give = ["pack", "give", "basic-packs-camper", "--tenant", tenant, "--owner", who["alice"]]

    dry = run_cli(stack, token, tmp_path, *give, "--dry-run", "--json")
    given = run_cli(stack, token, tmp_path, *give, "--json")

    assert dry.exit_code == 0, dry.output
    assert json.loads(dry.stdout)["dry_run"] is True
    assert given.exit_code == 0, given.output
    document = json.loads(given.stdout)
    assert document["dry_run"] is False
    assert document["created"][0]["item_instance"]["title"] == "Backpack"
    assert len(document["created"][0]["children"]) == 5
