"""`lorenzo seed` against the real API (ADR 0143, 0181)."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import httpx
from plain import plain
from typer.testing import CliRunner

from e2e.helpers import tenant_id
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
    + sum(len(n.stats) for n in SPEC.nodes)
    + len(SPEC.attachments)
    + len(SPEC.recipes)
)
LAYER_ORDER = ("core", "equipment", "dnd5e", "dnd5e-equipment")


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
        # Only the placeholder is in the public catalog, so a player may make one (ADR 0192).
        public = {
            r["slug"]
            for r in resolved
            if api.get(f"/tenants/{tid}/items/{r['entity_id']}").json()["in_public_catalog"]
        }
        assert public == {"unsorted"}
        groups = api.get(f"/tenants/{tid}/stat-groups").json()["items"]
        assert {g["name"] for g in groups} == {g.name for g in SPEC.groups}
        definitions = api.get(f"/tenants/{tid}/stat-definitions").json()["items"]
        assert {d["name"]: d["value_type"] for d in definitions} == {
            d.name: d.value_type for d in SPEC.definitions
        }


def entity(api: httpx.Client, tid: str, slug: str) -> dict[str, Any]:
    found = api.get(f"/tenants/{tid}/entities/resolve", params={"slug": [slug]}).json()
    assert len(found) == 1, slug
    return api.get(f"/tenants/{tid}/entities/{found[0]['entity_id']}").json()


def test_the_system_root_the_price_it_carries_and_the_attachments_are_in_the_tenant(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    assert seed(stack, token, tmp_path, tenant, "--yes").exit_code == 0

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        economic = entity(api, tid, "dnd5e-economic-object")
        assert [p["name"] for p in economic["prototypes"]] == ["D&D 5e"]
        price = next(s for s in economic["stats"] if s["name"] == "price")
        assert price["value"] == 0 and price["own"] is True
        assert "economic" in {g["name"] for g in economic["stat_groups"]}
        # Every axis root is under the system root, and the root is under nothing.
        assert entity(api, tid, "dnd5e-system")["prototypes"] == []
        for slug in ("dnd5e-weapon-proficiency", "dnd5e-armor-tier", "dnd5e-weapon-property"):
            assert [p["name"] for p in entity(api, tid, slug)["prototypes"]] == ["D&D 5e"]
        # The six forms have the economic object as a second parent, and keep their first.
        weapon = entity(api, tid, "weapon")
        assert {p["name"] for p in weapon["prototypes"]} == {
            "Physical object",
            "Economic object (D&D 5e)",
        }
        for spec in SPEC.attachments:
            parents = {p["id"] for p in entity(api, tid, spec.child)["prototypes"]}
            assert economic["id"] in parents, spec.child
        # What a weapon has from it, it has in turn: a price of 0 it doesn't hold itself.
        inherited = next(s for s in weapon["stats"] if s["name"] == "price")
        assert inherited["value"] == 0 and inherited["own"] is False
        # Not on `physical-object`, which is also a mountain.
        assert "price" not in {s["name"] for s in entity(api, tid, "physical-object")["stats"]}


def test_seeding_again_finds_the_forms_with_their_attached_parents_in_place(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    assert seed(stack, token, tmp_path, tenant, "--yes").exit_code == 0

    for layer in LAYER_ORDER:
        again = seed(stack, token, tmp_path, tenant, "--layer", layer, "--dry-run", "--json")
        assert again.exit_code == 0, (layer, again.output)
        plan = json.loads(again.output)
        # The forms have a parent the equipment layer doesn't name, and that is no warning.
        assert plan["actions"] == [] and plan["warnings"] == [], layer


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
        assert weighed["price"] == 0  # and the price from the economic object attached to it
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


def test_layers_can_be_seeded_apart_in_dependency_order(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)

    too_early = seed(stack, token, tmp_path, tenant, "--layer", "dnd5e", "--yes")
    attachments_too_early = seed(
        stack, token, tmp_path, tenant, "--layer", "dnd5e-equipment", "--yes"
    )
    done = {
        layer: seed(stack, token, tmp_path, tenant, "--layer", layer, "--yes")
        for layer in LAYER_ORDER
    }
    complete = seed(stack, token, tmp_path, tenant, "--dry-run")

    assert too_early.exit_code == 1  # its definitions need core's group, and nothing was written
    assert "Seed that layer first" in too_early.output.replace("\n", " ")
    assert attachments_too_early.exit_code == 1
    assert "The attachments of the dnd5e-equipment layer need categories" in (
        attachments_too_early.output.replace("\n", " ")
    )
    assert {layer: run.exit_code for layer, run in done.items()} == dict.fromkeys(LAYER_ORDER, 0)
    assert complete.exit_code == 0  # nothing left: the four layers made the whole seed


def test_the_attachments_keep_the_parents_a_form_already_has(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = make_tenant(stack, token)
    for layer in LAYER_ORDER[:3]:
        assert seed(stack, token, tmp_path, tenant, "--layer", layer, "--yes").exit_code == 0

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        base = f"/tenants/{tid}"
        armor = entity(api, tid, "armor")
        house = api.post(f"{base}/items", json={"name": "House rule"}).json()["entity_id"]
        current = api.get(f"{base}/items/{armor['id']}")
        put = api.put(
            f"{base}/items/{armor['id']}/prototypes",
            json={"prototype_ids": [p["id"] for p in armor["prototypes"]] + [house]},
            headers={"If-Match": current.headers["ETag"]},
        )
        assert put.status_code == 200, put.text

    attached = seed(stack, token, tmp_path, tenant, "--layer", "dnd5e-equipment", "--yes")

    assert attached.exit_code == 0, attached.output
    with stack.api(token) as api:
        names = {p["name"] for p in entity(api, tid, "armor")["prototypes"]}
    assert names == {"Physical object", "House rule", "Economic object (D&D 5e)"}


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

    result = seed(stack, token, tmp_path, tenant, "--layer", "core", "--yes")

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
    assert "core, equipment, dnd5e, dnd5e-equipment" in plain(result.output)
