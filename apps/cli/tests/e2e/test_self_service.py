"""`item list|add` and `character list` for a player, against the real API (ADR 0190)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from e2e.helpers import run_cli
from e2e.stack import Stack


def _table(stack: Stack) -> dict[str, Any]:
    """A play tenant run by a GM, with a public Rope and a private Vault key, one campaign, and a
    player with a character, Ashfang."""
    gm = stack.creator_token(f"gm-{uuid.uuid4().hex[:8]}")
    player = stack.authgear.token(f"player-{uuid.uuid4().hex[:8]}")
    slug = f"e2e-{uuid.uuid4().hex[:10]}"
    with stack.api(gm) as api, stack.api(player) as theirs:
        tenant = api.post("/tenants", json={"name": slug, "slug": slug, "kind": "play"}).json()
        t = f"/tenants/{tenant['id']}"
        campaign = api.post(
            f"{t}/campaigns",
            json={
                "name": "Table",
                "game_system": "D&D 5e",
                "slug": "table",
                "description": "",
                "secret": False,
            },
        ).json()
        me = theirs.get("/me").json()["id"]
        seat = api.post(f"{t}/campaigns/{campaign['id']}/players", json={"user_id": me}).json()
        character = api.post(
            f"{t}/characters",
            json={"name": "Ashfang", "owner_player_id": seat["id"], "player_ids": [seat["id"]]},
        ).json()
        for name, public in (("Rope", True), ("Vault key", False)):
            api.post(
                f"{t}/items", json={"name": name, "prototype_ids": [], "in_public_catalog": public}
            )
    return {
        "slug": slug,
        "gm": gm,
        "player": player,
        "tenant_id": tenant["id"],
        "campaign_id": campaign["id"],
        "seat_id": seat["id"],
        "character_id": character["entity_id"],
    }


def _owned(stack: Stack, table: dict[str, Any]) -> list[tuple[str, int | None]]:
    with stack.api(table["player"]) as api:
        owned = api.get(
            f"/tenants/{table['tenant_id']}/item-instances/owned-by/{table['character_id']}"
        ).json()
    return sorted((i["title"], i["quantity"]) for g in owned["groups"] for i in g["item_instances"])


def test_a_player_finds_their_character_and_the_public_catalog_and_adds_to_it(
    stack: Stack, tmp_path: Path
) -> None:
    table = _table(stack)
    player, slug = table["player"], table["slug"]

    characters = json.loads(
        run_cli(stack, player, tmp_path, "character", "list", "-t", slug, "--json").stdout
    )
    catalog = json.loads(
        run_cli(stack, player, tmp_path, "item", "list", "-t", slug, "--json").stdout
    )

    assert [c["name"] for c in characters] == ["Ashfang"]
    assert [i["title"] for i in catalog] == ["Rope"]

    added = run_cli(
        stack, player, tmp_path, "item", "add", "rope", "-t", slug, "--name", "Old rope"
    )

    assert added.exit_code == 0, added.output
    assert "Added Old rope to Ashfang." in " ".join(added.output.split())
    assert _owned(stack, table) == [("Old rope", None)]


def test_a_stack_goes_into_a_container_the_character_already_holds(
    stack: Stack, tmp_path: Path
) -> None:
    table = _table(stack)
    player, slug = table["player"], table["slug"]
    with stack.api(table["gm"]) as api:
        api.post(
            f"/tenants/{table['tenant_id']}/items",
            json={"name": "Backpack", "prototype_ids": [], "in_public_catalog": True},
        )

    backpack = json.loads(
        run_cli(stack, player, tmp_path, "item", "add", "backpack", "-t", slug, "--json").stdout
    )
    stacked = run_cli(
        stack,
        player,
        tmp_path,
        "item",
        "add",
        "rope",
        "-t",
        slug,
        "-n",
        "5",
        "--into",
        backpack["entity_id"],
    )

    assert stacked.exit_code == 0, stacked.output
    assert _owned(stack, table) == [("Backpack", None), ("Rope", 5)]


def test_what_the_api_refuses_is_said_in_its_own_words(stack: Stack, tmp_path: Path) -> None:
    table = _table(stack)
    player, slug = table["player"], table["slug"]

    private = run_cli(stack, player, tmp_path, "item", "add", "Vault key", "-t", slug)
    assert private.exit_code == 1
    assert "There's no item" in " ".join(private.output.split())

    with stack.api(table["gm"]) as api:
        api.patch(
            f"/tenants/{table['tenant_id']}/campaigns/{table['campaign_id']}",
            json={"player_self_service": False},
        )
    off = run_cli(stack, player, tmp_path, "item", "add", "rope", "-t", slug)

    assert off.exit_code == 1
    assert "switched off" in " ".join(off.output.split())
    assert _owned(stack, table) == []
