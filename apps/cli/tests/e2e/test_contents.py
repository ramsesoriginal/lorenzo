"""`lorenzo repo contents` against the real API (ADR 0169): what a repository holds, what it is
built on, and how much of each seed layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plain import plain

from e2e.helpers import FIXTURES, by_slug, make_tenant, run_cli, tenant_id
from e2e.stack import Stack

SEED_CATEGORIES = 61  # 33 in core and 28 in dnd5e


def said(result: Any) -> str:
    return plain(result.output)


def contents(stack: Stack, token: str, tmp_path: Path, tenant: str) -> dict[str, Any]:
    result = run_cli(stack, token, tmp_path, "repo", "contents", "--tenant", tenant, "--json")
    assert result.exit_code == 0, result.output
    document: dict[str, Any] = json.loads(result.stdout)
    return document


def items_total(stack: Stack, token: str, tenant: str) -> int:
    with stack.api(token) as api:
        body = api.get(f"/tenants/{tenant_id(api, tenant)}/items", params={"size": 1}).json()
    return int(body["total"])


def test_a_core_repository_holds_core_and_nothing_beyond_it(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    seeded = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--layer", "core", "--yes")
    assert seeded.exit_code == 0, seeded.output

    document = contents(stack, token, tmp_path, tenant)

    assert document["tenant"]["slug"] == tenant and document["tenant"]["published_at"] is None
    assert document["granted_to"] == 0 and document["built_on"] == []
    assert document["holds"] == {"stat_groups": 6, "stat_definitions": 18, "items": 33}
    layers = document["seed"]["layers"]
    assert layers["core"]["holds"] == "complete"
    assert layers["dnd5e"]["holds"] == "not there"
    assert layers["dnd5e"]["stat_definitions"] == {"present": 0, "in_seed": 22}
    assert document["beyond_seed"] == {"stat_groups": 0, "stat_definitions": 0, "items": 0}

    human = run_cli(stack, token, tmp_path, "repo", "contents", "--tenant", tenant)
    assert human.exit_code == 0, human.output
    text = said(human)
    assert "is a repository, a draft, granted to 0 tenant(s)." in text
    assert "core complete 6 of 6 18 of 18 33 of 33" in text
    assert "dnd5e not there - 0 of 22 0 of 28" in text


def test_a_bridge_is_built_on_core_holds_both_layers_and_the_items_beyond_the_seed(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    core = make_tenant(stack, token)
    bridge = make_tenant(stack, token)
    for args in (
        ["seed", "--tenant", core, "--layer", "core", "--yes"],
        ["repo", "publish", "--tenant", core],
        ["repo", "grant", bridge, "--tenant", core],
        ["repo", "copy", core, "--tenant", bridge, "--yes"],
        ["seed", "--tenant", bridge, "--layer", "dnd5e", "--yes"],
    ):
        done = run_cli(stack, token, tmp_path, *args)
        assert done.exit_code == 0, f"{' '.join(args)}\n{done.output}"
    imported = run_cli(
        stack,
        token,
        tmp_path,
        *["apply", "--tenant", bridge, "--review-queue", str(tmp_path / "rq.json")],
        *["--proposed-map", str(tmp_path / "pm.toml"), str(FIXTURES / "weapons.js"), "--yes"],
    )
    assert imported.exit_code == 1, imported.output  # the moon whip is held for review

    document = contents(stack, token, tmp_path, bridge)

    total = items_total(stack, token, bridge)
    assert [row["slug"] for row in document["built_on"]] == [core]
    assert document["built_on"][0]["updated_since"] is False
    layers = document["seed"]["layers"]
    assert layers["core"]["holds"] == layers["dnd5e"]["holds"] == "complete"
    assert document["holds"]["items"] == total
    assert document["beyond_seed"]["items"] == total - SEED_CATEGORIES > 0
    assert document["beyond_seed"]["stat_groups"] == 0

    # When core publishes again, the bridge is told it has changed.
    run_cli(stack, token, tmp_path, "repo", "publish", "--tenant", core)
    human = run_cli(stack, token, tmp_path, "repo", "contents", "--tenant", bridge)
    assert f"Built on {core}, copied" in said(human)
    assert "and has published since." in said(human)


def test_a_layer_with_a_category_gone_is_partly_there(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    seeded = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--yes")
    assert seeded.exit_code == 0, seeded.output
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        for slug in ("dnd5e-holy-symbol", "dnd5e-druidic-focus"):
            gone = api.delete(f"/tenants/{tid}/items/{by_slug(api, tid, slug)['id']}")
            assert gone.status_code == 204, gone.text

    document = contents(stack, token, tmp_path, tenant)

    layers = document["seed"]["layers"]
    assert layers["core"]["holds"] == "complete"
    assert layers["dnd5e"]["holds"] == "partly"
    assert layers["dnd5e"]["categories"] == {"present": 26, "in_seed": 28}
    assert layers["dnd5e"]["stat_definitions"] == {"present": 22, "in_seed": 22}
    assert document["beyond_seed"]["items"] == 0


def test_a_play_tenant_is_refused(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    table = make_tenant(stack, token, "play")

    result = run_cli(stack, token, tmp_path, "repo", "contents", "--tenant", table)

    assert result.exit_code == 1, result.output
    assert "play tenant, not a repository" in said(result)
