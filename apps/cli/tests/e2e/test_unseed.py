"""`lorenzo unseed`, and a bare `seed` that won't add a layer, against the real API (ADR 0166,
0167, 0168)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from e2e.helpers import FIXTURES, make_tenant, run_cli, tenant_id
from e2e.stack import Stack


def seeded(stack: Stack, token: str, tmp_path: Path, *layers: str) -> str:
    tenant = make_tenant(stack, token)
    flags = [arg for layer in layers for arg in ("--layer", layer)]
    result = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, *flags, "--yes")
    assert result.exit_code == 0, result.output
    return tenant


def definitions(api: httpx.Client, tid: str) -> list[str]:
    body = api.get(f"/tenants/{tid}/stat-definitions", params={"size": 100}).json()
    return [d["name"] for d in body["items"]]


def groups(api: httpx.Client, tid: str) -> list[str]:
    return [g["name"] for g in api.get(f"/tenants/{tid}/stat-groups").json()["items"]]


def seed_dry_run(stack: Stack, token: str, tmp_path: Path, tenant: str, *layers: str) -> Any:
    flags = [arg for layer in layers for arg in ("--layer", layer)]
    return run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, *flags, "--dry-run")


def said(result: Any) -> str:
    return " ".join(result.output.split())


def test_unseed_takes_a_layer_out_and_seed_can_put_it_back(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)  # both layers, into a tenant that holds neither
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        assert len(definitions(api, tid)) == 40

    dry = run_cli(
        stack,
        token,
        tmp_path,
        "unseed",
        "--tenant",
        tenant,
        "--layer",
        "dnd5e",
        "--dry-run",
        "--json",
    )

    assert dry.exit_code == 2, dry.output
    document = json.loads(dry.stdout)
    assert document["result"] is None
    kinds = [t["kind"] for t in document["plan"]["targets"]]
    assert (kinds.count("node"), kinds.count("definition"), kinds.count("group")) == (28, 22, 0)
    with stack.api(token) as api:
        assert len(definitions(api, tid)) == 40  # a dry run writes nothing

    declined = run_cli(
        stack,
        token,
        tmp_path,
        *["unseed", "--tenant", tenant, "--layer", "dnd5e"],
        answers="n\n",
    )
    assert declined.exit_code == 1, declined.output
    assert "Nothing was deleted" in said(declined)
    with stack.api(token) as api:
        assert len(definitions(api, tid)) == 40

    agreed = run_cli(
        stack,
        token,
        tmp_path,
        *["unseed", "--tenant", tenant, "--layer", "dnd5e"],
        answers="y\n",
    )
    assert agreed.exit_code == 0, agreed.output
    assert "Delete 28 categories, 22 stat definitions and 0 stat groups" in said(agreed)
    with stack.api(token) as api:
        left = definitions(api, tid)
        assert len(left) == 18 and "damage_die" not in left and "weight" in left
    assert seed_dry_run(stack, token, tmp_path, tenant, "core").exit_code == 0
    again = run_cli(
        stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "dnd5e", "--yes"
    )
    assert again.exit_code == 0, again.output
    assert "To remove: 0 categories, 0 stat definitions and 0 stat groups" in said(again)

    # What it took out can be put back: the tenant now holds core alone, so the layer is named.
    assert seed_dry_run(stack, token, tmp_path, tenant, "dnd5e").exit_code == 2
    back = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--layer", "dnd5e", "--yes")
    assert back.exit_code == 0, back.output
    assert seed_dry_run(stack, token, tmp_path, tenant).exit_code == 0


def test_unseed_refuses_while_imported_items_are_under_the_layer(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)
    imported = run_cli(
        stack,
        token,
        tmp_path,
        *["apply", "--tenant", tenant, "--review-queue", str(tmp_path / "rq.json")],
        *["--proposed-map", str(tmp_path / "pm.toml"), str(FIXTURES / "weapons.js"), "--yes"],
    )
    assert imported.exit_code == 1, imported.output  # the moon whip is held for review

    result = run_cli(
        stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "dnd5e", "--yes"
    )

    assert result.exit_code == 1, result.output
    assert "nothing was deleted" in said(result)
    assert "dnd5e-martial" in said(result) and "Purple sword" in said(result)
    with stack.api(token) as api:
        assert len(definitions(api, tenant_id(api, tenant))) == 40
    assert seed_dry_run(stack, token, tmp_path, tenant).exit_code == 0


def test_unseed_keeps_a_definition_that_is_still_in_use_and_finishes_once_it_is_not(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        made = api.post(f"/tenants/{tid}/items", json={"name": "My blade", "slug": "my-blade"})
        assert made.status_code == 201, made.text
        blade = made.json()["entity_id"]
        dice = next(
            d["id"]
            for d in api.get(f"/tenants/{tid}/stat-definitions", params={"size": 100}).json()[
                "items"
            ]
            if d["name"] == "damage_dice_count"
        )
        held = api.put(f"/tenants/{tid}/entities/{blade}/stats/{dice}", json={"value": 2})
        assert held.status_code == 200, held.text

    result = run_cli(
        stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "dnd5e", "--yes"
    )

    assert result.exit_code == 1, result.output
    assert "Kept definition damage_dice_count" in said(result)
    assert "1 value(s) held" in said(result)
    with stack.api(token) as api:
        left = definitions(api, tid)
        assert [name for name in left if name in ("damage_dice_count", "damage_die")] == [
            "damage_dice_count"
        ]
        assert len(left) == 19  # core's 18, and the one in use
        assert api.delete(f"/tenants/{tid}/items/{blade}").status_code == 204

    finished = run_cli(
        stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "dnd5e", "--yes"
    )

    assert finished.exit_code == 0, finished.output
    with stack.api(token) as api:
        assert len(definitions(api, tid)) == 18


def test_unseeding_core_takes_the_groups_too_and_leaves_an_empty_tenant(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path, "core")
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        assert len(groups(api, tid)) == 6

    result = run_cli(
        stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "core", "--yes"
    )

    assert result.exit_code == 0, result.output
    with stack.api(token) as api:
        assert definitions(api, tid) == [] and groups(api, tid) == []
    bare = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--dry-run")
    assert bare.exit_code == 2  # empty again, so a bare seed adds both


def test_unseed_needs_yes_without_a_terminal_and_json_never_asks(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path, "core", "dnd5e")

    quiet = run_cli(stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "dnd5e")
    as_json = run_cli(
        stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "dnd5e", "--json"
    )

    assert quiet.exit_code == as_json.exit_code == 1
    assert "run again with --yes" in said(quiet) and "run again with --yes" in said(as_json)
    with stack.api(token) as api:
        assert len(definitions(api, tenant_id(api, tenant))) == 40


def test_unseed_wants_a_layer_and_a_known_one(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)

    missing = run_cli(stack, token, tmp_path, "unseed", "--tenant", tenant)
    unknown = run_cli(stack, token, tmp_path, "unseed", "--tenant", tenant, "--layer", "warhammer")

    assert missing.exit_code == 2 and unknown.exit_code == 2


def test_a_bare_seed_will_not_add_a_layer_to_a_tenant_that_holds_another(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path, "core")

    dry = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--dry-run", "--json")
    real = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--yes")

    assert dry.exit_code == real.exit_code == 1
    [problem] = json.loads(dry.stdout)["problems"]
    assert "holds the core layer and none of dnd5e" in problem
    assert "`--layer dnd5e`" in problem
    with stack.api(token) as api:
        assert len(definitions(api, tenant_id(api, tenant))) == 18  # nothing was added
    named = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--layer", "dnd5e", "--yes")
    assert named.exit_code == 0, named.output
    with stack.api(token) as api:
        assert len(definitions(api, tenant_id(api, tenant))) == 40
