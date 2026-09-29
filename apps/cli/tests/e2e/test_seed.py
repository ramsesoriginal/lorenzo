"""`lorenzo seed` against the real API (ADR 0143)."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import httpx
from typer.testing import CliRunner

from e2e.stack import Stack
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.main import Runtime, app
from lorenzo_cli.seed import load_builtin

runner = CliRunner()
SPEC = load_builtin()
EVERYTHING = (
    len(SPEC.groups)
    + len(SPEC.definitions)
    + len(SPEC.nodes)
    + sum(len(n.tags) for n in SPEC.nodes)
    + sum(1 for n in SPEC.nodes if n.description)
    + len(SPEC.recipes)
)


def make_tenant(stack: Stack, token: str, kind: str = "repository") -> str:
    slug = f"e2e-{uuid.uuid4().hex[:10]}"
    with stack.api(token) as api:
        response = api.post("/tenants", json={"name": slug, "slug": slug, "kind": kind})
    assert response.status_code == 201, response.text
    return slug


def seed(stack: Stack, token: str, tmp_path: Path, tenant: str, *args: str) -> Any:
    runtime = Runtime(
        env={"LORENZO_API_URL": stack.api_url, "LORENZO_TOKEN": token},
        stdin=io.StringIO(),
        store=CredentialsFile(tmp_path / "credentials.json"),
    )
    return runner.invoke(app, ["seed", "--tenant", tenant, *args], obj=runtime)


def tenant_id(api: httpx.Client, slug: str) -> str:
    listed = api.get("/tenants").json()["items"]
    return next(t["id"] for t in listed if t["slug"] == slug)


def test_a_fresh_repository_tenant_is_seeded_and_a_second_run_finds_nothing(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)

    dry = seed(stack, token, tmp_path, tenant, "--dry-run", "--json")
    assert dry.exit_code == 2, dry.output
    plan = json.loads(dry.output)
    assert len(plan["actions"]) == EVERYTHING
    assert plan["tenant"]["kind"] == "repository"
    assert plan["tenant"]["published"] is False
    assert plan["problems"] == []

    applied = seed(stack, token, tmp_path, tenant, "--yes")
    assert applied.exit_code == 0, applied.output

    again = seed(stack, token, tmp_path, tenant, "--dry-run", "--json")
    assert again.exit_code == 0, again.output
    assert json.loads(again.output)["actions"] == []
    written = seed(stack, token, tmp_path, tenant, "--yes")
    assert written.exit_code == 0
    assert "Created" not in written.output  # nothing to do is not "created 0"

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        slugs = [n.slug for n in SPEC.nodes]
        resolved = api.get(f"/tenants/{tid}/entities/resolve", params={"slug": slugs}).json()
        assert sorted(r["slug"] for r in resolved) == sorted(slugs)
        assert {tuple(r["kinds"]) for r in resolved} == {("item",)}
        groups = api.get(f"/tenants/{tid}/stat-groups").json()["items"]
        assert {g["name"] for g in groups} == {g.name for g in SPEC.groups}
        definitions = api.get(f"/tenants/{tid}/stat-definitions").json()["items"]
        assert {d["name"]: d["value_type"] for d in definitions} == {
            d.name: d.value_type for d in SPEC.definitions
        }


def test_the_seeded_taxonomy_works_a_backpack_weighs_what_is_in_it(
    stack: Stack, tmp_path: Path
) -> None:
    """The point of the recipe and the tag: build on the seed, the way the importer will."""
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    assert seed(stack, token, tmp_path, tenant, "--yes").exit_code == 0

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        base = f"/tenants/{tid}"
        prototypes = {
            r["slug"]: r["entity_id"]
            for r in api.get(
                f"{base}/entities/resolve", params={"slug": ["container", "gear"]}
            ).json()
        }
        own_weight = next(
            d["id"]
            for d in api.get(f"{base}/stat-definitions").json()["items"]
            if d["name"] == "own_weight"
        )

        def item(name: str, parent: str, weight: float) -> str:
            created = api.post(
                f"{base}/items", json={"name": name, "prototype_ids": [prototypes[parent]]}
            )
            assert created.status_code == 201, created.text
            entity = created.json()["entity_id"]
            put = api.put(
                f"{base}/entities/{entity}/stats/{own_weight}",
                json={"value": weight, "acquire_group": True},
            )
            assert put.status_code == 200, put.text
            return str(entity)

        backpack_item = item("Backpack", "container", 2.0)
        rope_item = item("Hempen rope", "gear", 1.5)
        backpack = api.post(f"{base}/item-instances", json={"prototype_id": backpack_item}).json()
        rope = api.post(
            f"{base}/item-instances",
            json={
                "prototype_id": rope_item,
                "container_entity_id": backpack["entity_id"],
                "quantity": 2,
            },
        )
        assert rope.status_code == 201, rope.text

        weighed = api.get(f"{base}/item-instances/{backpack['entity_id']}").json()
        # 2.0 of its own, plus two lengths of 1.5 inside it.
        assert weighed["weight"] == 5.0
        assert weighed["is_container"] is True  # the tag is inherited from the `container` node
        assert {"physical"} <= {
            g["name"] for g in api.get(f"{base}/entities/{backpack_item}").json()["stat_groups"]
        }


def test_a_play_tenant_is_refused_unless_asked(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token, kind="play")

    refused = seed(stack, token, tmp_path, tenant, "--dry-run")
    allowed = seed(stack, token, tmp_path, tenant, "--dry-run", "--allow-play-tenant")

    assert refused.exit_code == 1
    assert (
        "can't be published" in refused.output.replace("\n", " ") or "published" in refused.output
    )
    assert allowed.exit_code == 2


def test_layers_can_be_seeded_apart_but_dnd5e_needs_core(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)

    too_early = seed(stack, token, tmp_path, tenant, "--layer", "dnd5e", "--yes")
    core = seed(stack, token, tmp_path, tenant, "--layer", "core", "--yes")
    then_dnd5e = seed(stack, token, tmp_path, tenant, "--layer", "dnd5e", "--yes")
    complete = seed(stack, token, tmp_path, tenant, "--dry-run")

    assert too_early.exit_code == 1  # its definitions need core's group, and nothing was written
    assert "Seed that layer first" in too_early.output.replace("\n", " ")
    assert core.exit_code == 0, core.output
    assert then_dnd5e.exit_code == 0, then_dnd5e.output
    assert complete.exit_code == 0  # nothing left: the two layers made the whole seed


def test_a_stat_of_the_wrong_type_stops_the_seed_before_it_writes_anything(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        group = api.post(f"/tenants/{tid}/stat-groups", json={"name": "physical"}).json()
        made = api.post(
            f"/tenants/{tid}/stat-definitions",
            json={"name": "weight", "stat_group_id": group["id"], "value_type": "int"},
        )
        assert made.status_code == 201

    result = seed(stack, token, tmp_path, tenant, "--yes")

    assert result.exit_code == 1
    assert "weight" in result.output
    with stack.api(token) as api:
        items = api.get(f"/tenants/{tid}/items").json()["items"]
        assert items == []  # nothing was written


def test_the_installed_command_runs_end_to_end(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    command = shutil.which("lorenzo")
    assert command, "the `lorenzo` script isn't installed in this environment"

    completed = subprocess.run(  # noqa: S603 - the script we just installed
        [command, "seed", "--tenant", tenant, "--dry-run", "--json"],
        capture_output=True,
        text=True,
        env={
            "PATH": str(Path(command).parent),
            "LORENZO_API_URL": stack.api_url,
            "LORENZO_TOKEN": token,
            "XDG_CONFIG_HOME": str(tmp_path),
        },
        check=False,
    )

    assert completed.returncode == 2, completed.stderr
    assert len(json.loads(completed.stdout)["actions"]) == EVERYTHING


def test_nothing_is_written_without_yes_when_nobody_can_be_asked(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)

    refused = seed(stack, token, tmp_path, tenant)
    still_to_do = seed(stack, token, tmp_path, tenant, "--dry-run", "--json")

    assert refused.exit_code == 1
    assert "--yes" in refused.output
    assert len(json.loads(still_to_do.output)["actions"]) == EVERYTHING  # untouched


def test_an_unknown_layer_is_a_usage_error(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)

    result = seed(stack, token, tmp_path, tenant, "--layer", "pathfinder")

    assert result.exit_code == 2
    assert "core, dnd5e" in result.output.replace("\n", " ")
