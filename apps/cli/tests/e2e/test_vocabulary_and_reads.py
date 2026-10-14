"""Author vocabulary and read a complete sheet against the real API (ADR 0295)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from e2e.helpers import run_cli
from e2e.stack import Stack


def test_vocabulary_settings_hints_and_all_three_entry_reads(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token(f"cli-sheet-{uuid.uuid4().hex[:8]}")
    slug = f"cli-sheet-{uuid.uuid4().hex[:10]}"
    with stack.api(token) as api:
        made = api.post("/tenants", json={"name": slug, "slug": slug, "kind": "play"})
        assert made.status_code == 201, made.text
        tid = made.json()["id"]

    def cli(*args: str):
        result = run_cli(stack, token, tmp_path, *args)
        assert result.exit_code == 0, result.output
        return result

    group = json.loads(
        cli("stat-group", "create", "Weapons", "-t", slug, "--priority", "2", "--json").stdout
    )
    maximum = json.loads(
        cli(
            "stat-definition",
            "create",
            "maximum",
            "-t",
            slug,
            "--group",
            "Weapons",
            "--type",
            "int",
            "--json",
        ).stdout
    )
    damage = json.loads(
        cli(
            "stat-definition",
            "create",
            "damage",
            "-t",
            slug,
            "--group",
            "Weapons",
            "--type",
            "int",
            "--unit",
            "points",
            "--signed",
            "--max-hint",
            "maximum",
            "--pin",
            "--json",
        ).stdout
    )
    assert damage["max_hint_id"] == maximum["id"]
    cli("stat-definition", "edit", "damage", "-t", slug, "--no-pin", "--clear-max-hint")
    cli("stat-group", "edit", "Weapons", "-t", slug, "--position", "3")
    settings = json.loads(
        cli(
            "tenant",
            "sheet-settings",
            slug,
            "--weapon-stat-group",
            "Weapons",
            "--ability-information-type",
            "ability",
            "--json",
        ).stdout
    )
    assert settings["weapon_stat_group_id"] == group["id"]
    base = f"/tenants/{tid}"
    with stack.api(token) as api:
        sword_response = api.post(
            base + "/items", json={"name": "Sword", "slug": "sword", "prototype_ids": []}
        )
        assert sword_response.status_code == 201, sword_response.text
        sword = sword_response.json()["entity_id"]
        written = api.put(f"{base}/entities/{sword}/stats/{damage['id']}", json={"value": 3})
        assert written.status_code == 200, written.text
        campaign = api.post(
            base + "/campaigns",
            json={
                "name": "Reading table",
                "game_system": "None",
                "slug": "reading-table",
                "description": "",
                "secret": False,
            },
        )
        assert campaign.status_code == 201, campaign.text
        user_id = api.get("/me").json()["id"]
        seat = api.post(
            f"{base}/campaigns/{campaign.json()['id']}/players", json={"user_id": user_id}
        )
        assert seat.status_code == 201, seat.text
        being_response = api.post(
            base + "/characters",
            json={
                "name": "Reader",
                "owner_player_id": seat.json()["id"],
                "player_ids": [seat.json()["id"]],
            },
        )
        assert being_response.status_code == 201, being_response.text
        being = being_response.json()["entity_id"]
        instance_response = api.post(
            base + "/item-instances",
            json={"prototype_id": sword, "owner_character_id": being, "container_entity_id": being},
        )
        assert instance_response.status_code == 201, instance_response.text
        instance = instance_response.json()["entity_id"]
        information = api.post(
            f"{base}/entities/{sword}/information",
            json={
                "title": "Sword",
                "type": "description",
                "is_public": True,
                "content": "**Sharp**. Damage: {damage}. [[Reader]].",
                "locale": "en",
            },
        )
        assert information.status_code == 201, information.text
        ability = api.post(
            f"{base}/entities/{being}/information",
            json={
                "title": "Read the room",
                "type": "ability",
                "is_public": True,
                "content": "See **clearly**.",
                "locale": "en",
            },
        )
        assert ability.status_code == 201, ability.text
    item_json = json.loads(cli("item", "show", "sword", "-t", slug, "--json").stdout)
    assert item_json["entry"]["id"] == sword
    item_text = cli("item", "show", "Sword", "-t", slug).stdout
    assert "Sharp" in item_text and "+3 points" in item_text
    instance_text = cli("item-instance", "show", instance, "-t", slug).stdout
    assert "Sharp" in instance_text and "from Sword" in instance_text
    sheet_json = json.loads(cli("being", "show", "Reader", "-t", slug, "--json").stdout)
    assert sheet_json["sheet"]["weapons"][0]["entity_id"] == instance
    assert sheet_json["sheet"]["abilities"][0]["title"] == "Read the room"
    text = cli("being", "show", being, "-t", slug).stdout
    assert "Sword" in text and "Read the room" in text and "See clearly" in text
    cleared = json.loads(
        cli(
            "tenant",
            "sheet-settings",
            slug,
            "--clear-weapon-stat-group",
            "--clear-ability-information-type",
            "--json",
        ).stdout
    )
    assert cleared == {"weapon_stat_group_id": None, "ability_information_type": None}


def test_api_rejects_invalid_hints_and_player_writes_and_hides_secret_notes(
    stack: Stack, tmp_path: Path
) -> None:
    from e2e.test_self_service import _table

    table = _table(stack)
    tenant, gm, player = table["slug"], table["gm"], table["player"]

    def cli(token: str, *args: str):
        return run_cli(stack, token, tmp_path, *args)

    group = cli(gm, "stat-group", "create", "Health", "-t", tenant, "--json")
    assert group.exit_code == 0, group.output
    text_stat = cli(
        gm,
        "stat-definition",
        "create",
        "caption",
        "-t",
        tenant,
        "--group",
        "Health",
        "--type",
        "text",
    )
    assert text_stat.exit_code == 0, text_stat.output
    invalid = cli(
        gm,
        "stat-definition",
        "create",
        "stress",
        "-t",
        tenant,
        "--group",
        "Health",
        "--type",
        "int",
        "--max-hint",
        "caption",
    )
    assert invalid.exit_code == 1 and "HTTP 422" in invalid.output
    denied = cli(player, "stat-group", "create", "Forbidden", "-t", tenant)
    assert denied.exit_code == 1, denied.output
    denied = cli(
        player, "tenant", "sheet-settings", tenant, "--ability-information-type", "ability"
    )
    assert denied.exit_code == 1, denied.output
    base = f"/tenants/{table['tenant_id']}"
    with stack.api(gm) as api:
        rope = next(i for i in api.get(base + "/items").json()["items"] if i["title"] == "Rope")
        for title, public, text in [
            ("Public note", True, "Shown in the terminal."),
            ("Secret note", False, "The secret must stay hidden."),
        ]:
            response = api.post(
                f"{base}/entities/{rope['entity_id']}/information",
                json={
                    "title": title,
                    "type": "note",
                    "is_public": public,
                    "content": text,
                    "locale": "en",
                },
            )
            assert response.status_code == 201, response.text
    visible = cli(player, "item", "show", rope["entity_id"], "-t", tenant)
    assert visible.exit_code == 0, visible.output
    assert "Shown in the terminal" in visible.stdout
    assert (
        "The secret must stay hidden" not in visible.stdout and "Secret note" not in visible.stdout
    )
    manager = cli(gm, "item", "show", rope["entity_id"], "-t", tenant)
    assert manager.exit_code == 0, manager.output
    assert "The secret must stay hidden" in manager.stdout
