"""A description is titled with its item's name, so an item shows its name (ADR 0165)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from e2e.helpers import FIXTURES, by_slug, make_tenant, run_cli, tenant_id
from e2e.stack import Stack


def shown_title(api: httpx.Client, tid: str, slug: str) -> str:
    """What a client displays for an item: `ItemOut.title`, its description's title (ADR 0019)."""
    entity = by_slug(api, tid, slug)
    response = api.get(f"/tenants/{tid}/items/{entity['id']}")
    assert response.status_code == 200, response.text
    return str(response.json()["title"])


def description_titles(detail: dict[str, Any]) -> list[str]:
    return [i["title"] for i in detail["information"] if i["type"] == "description"]


def seeded(stack: Stack, token: str, tmp_path: Path) -> str:
    tenant = make_tenant(stack, token)
    result = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--yes")
    assert result.exit_code == 0, result.output
    return tenant


def import_weapons(stack: Stack, token: str, tmp_path: Path, tenant: str) -> Any:
    return run_cli(
        stack,
        token,
        tmp_path,
        "apply",
        "--tenant",
        tenant,
        "--review-queue",
        str(tmp_path / "review-queue.json"),
        "--proposed-map",
        str(tmp_path / "proposed.map.toml"),
        str(FIXTURES / "weapons.js"),
        "--yes",
    )


def test_a_seeded_node_shows_its_name_where_a_client_shows_the_title(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        assert shown_title(api, tid, "firearm") == "Firearm"
        focus = by_slug(api, tid, "dnd5e-spellcasting-focus")
        assert description_titles(focus) == [focus["name"]]
        assert shown_title(api, tid, "dnd5e-spellcasting-focus") == focus["name"]


def test_an_imported_item_shows_its_name_where_a_client_shows_the_title(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)
    imported = import_weapons(stack, token, tmp_path, tenant)
    assert imported.exit_code == 1, imported.output  # the moon whip is held for review

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        sword = by_slug(api, tid, "basic-weapons-purple-sword")
        assert description_titles(sword) == [sword["name"]]
        assert shown_title(api, tid, "basic-weapons-purple-sword") == sword["name"]


def set_description_title(api: httpx.Client, tid: str, slug: str, title: str) -> None:
    """What the CLI used to do to every description, or what a person might choose instead."""
    [row] = [i for i in by_slug(api, tid, slug)["information"] if i["type"] == "description"]
    path = f"/tenants/{tid}/information/{row['id']}"
    etag = api.get(path).headers["ETag"]
    response = api.patch(path, json={"title": title}, headers={"If-Match": etag})
    assert response.status_code == 200, response.text


def plan_weapons(stack: Stack, token: str, tmp_path: Path, tenant: str) -> Any:
    return run_cli(
        stack,
        token,
        tmp_path,
        "plan",
        "--tenant",
        tenant,
        "--review-queue",
        str(tmp_path / "review-queue.json"),
        "--proposed-map",
        str(tmp_path / "proposed.map.toml"),
        str(FIXTURES / "weapons.js"),
        "--json",
    )


def test_seed_retitles_a_description_the_old_seed_titled_description(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        set_description_title(api, tid, "firearm", "Description")
        set_description_title(api, tid, "dnd5e-spellcasting-focus", "A focus, my way")

    dry = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--dry-run", "--json")

    assert dry.exit_code == 2, dry.output
    actions = json.loads(dry.stdout)["actions"]
    assert [(a["kind"], a["name"], a["detail"]) for a in actions] == [
        ("retitle", "firearm", "Firearm")
    ]
    with stack.api(token) as api:
        assert shown_title(api, tid, "firearm") == "Description"  # a dry run writes nothing

    applied = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--yes")

    assert applied.exit_code == 0, applied.output
    with stack.api(token) as api:
        assert shown_title(api, tid, "firearm") == "Firearm"
        # A title somebody chose is theirs.
        assert shown_title(api, tid, "dnd5e-spellcasting-focus") == "A focus, my way"
    again = run_cli(stack, token, tmp_path, "seed", "--tenant", tenant, "--dry-run")
    assert again.exit_code == 0, again.output


def test_apply_retitles_an_imported_item_and_a_second_run_finds_nothing(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)
    assert import_weapons(stack, token, tmp_path, tenant).exit_code == 1  # the moon whip is held
    slug = "basic-weapons-purple-sword"
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        set_description_title(api, tid, slug, "Description")

    planned = json.loads(plan_weapons(stack, token, tmp_path, tenant).stdout)

    assert planned["header"]["counts"]["retitle"] == 1
    assert {i["slug"]: i["status"] for i in planned["items"] if i["slug"]}[slug] == "retitle"

    applied = import_weapons(stack, token, tmp_path, tenant)

    assert "retitled 1" in " ".join(applied.output.split())
    with stack.api(token) as api:
        assert shown_title(api, tid, slug) == by_slug(api, tid, slug)["name"]
    after = json.loads(plan_weapons(stack, token, tmp_path, tenant).stdout)
    assert after["header"]["counts"]["retitle"] == 0
    assert {i["slug"]: i["status"] for i in after["items"] if i["slug"]}[slug] == "exists"


def test_apply_leaves_a_title_somebody_chose_alone(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = seeded(stack, token, tmp_path)
    import_weapons(stack, token, tmp_path, tenant)
    slug = "basic-weapons-purple-sword"
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        set_description_title(api, tid, slug, "The Purple Blade")

    planned = json.loads(plan_weapons(stack, token, tmp_path, tenant).stdout)
    import_weapons(stack, token, tmp_path, tenant)

    assert planned["header"]["counts"]["retitle"] == 0
    with stack.api(token) as api:
        assert shown_title(api, tid, slug) == "The Purple Blade"
