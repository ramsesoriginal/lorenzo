"""Packs against the real API (RFC 0025 R7, ADR 0145): their contents in the description, and
handing them out."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx

from e2e.helpers import (
    FIXTURES,
    SharedRepository,
    by_slug,
    copy_of_seeded,
    run_cli,
    tenant_id,
)
from e2e.stack import Stack
from e2e.test_import import apply, plan, seeded_tenant, statuses

PACKS = str(FIXTURES / "packs.js")

# The rope entry counts 50 feet; the item is a coil of 50 feet, so it is one.
# Everything after "Backpack, with:" goes inside it. An entry the sheet has no gear entry for
# (an alms box) is a plain item of its own, so every line links.
CONTENTS = (
    "This pack contains:\n\n"
    "- 1 x [Backpack](basic-gear-backpack)\n"
    "  - 5 x [Rations (1 day)](basic-gear-rations-1-day)\n"
    "  - 2 x [Torch](basic-gear-torch)\n"
    "  - 1 x [Rope, hempen (50 feet)](basic-gear-rope-hempen-50-feet)\n"
    "  - 1 x [Alms box](basic-gear-alms-box)\n"
    "  - 1 x [Mystery thing](basic-gear-mystery-thing)"
)


def description(detail: dict[str, Any]) -> list[str]:
    return [
        p["content"]
        for i in detail["information"]
        if i["type"] == "description"
        for p in i["payloads"]
    ]


def imported(stack: Stack, token: str, tmp_path: Path) -> str:
    tenant = seeded_tenant(stack, token, tmp_path)
    result = apply(stack, token, tmp_path, tenant, PACKS, "--yes")
    assert result.exit_code == 0, result.output
    return tenant


def test_the_server_leaves_the_contents_list_exactly_as_it_was_written(
    stack: Stack, tmp_path: Path
) -> None:
    """R7's open question: nothing is done to a description's text on the way in or out."""
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    with stack.api(token) as api:
        pack = by_slug(api, tenant_id(api, tenant), "basic-packs-camper")

    assert description(pack) == [CONTENTS]
    assert pack["name"] == "Camper's pack"


def test_a_pack_is_planned_with_its_contents_and_what_could_not_be_linked(
    stack: Stack, tmp_path: Path, shared_repository: SharedRepository
) -> None:
    token, tenant = shared_repository.token, shared_repository.slug

    result = plan(stack, token, tmp_path, tenant, PACKS, "--json")

    document = json.loads(result.stdout)
    [pack] = [i for i in document["items"] if i["list"] == "packs"]
    assert pack["pack"] == {"lines": 6, "unresolved": ["Mystery thing"]}
    assert pack["description"] is True
    assert result.exit_code == 2  # something to create; an unlinked entry doesn't block


def test_an_entry_nothing_could_be_linked_to_is_reported_and_strict_makes_it_matter(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    lenient = plan(stack, token, tmp_path, tenant, PACKS)
    strict = plan(stack, token, tmp_path, tenant, PACKS, "--strict")

    assert lenient.exit_code == 0
    assert strict.exit_code == 1
    queue = json.loads((tmp_path / "review-queue.json").read_text())
    [entry] = [q for q in queue if q["kind"] == "pack"]
    assert (entry["key"], entry["value"]) == ("camper", "'Mystery thing'")
    assert '[pack_items]\n"mystery thing" = ' in entry["suggestion"]
    assert "[pack_items]" in (tmp_path / "proposed.map.toml").read_text()


def test_a_row_in_the_map_links_the_entry_and_the_description_follows_on_a_new_tenant(
    stack: Stack, tmp_path: Path, shared_repository: SharedRepository
) -> None:
    token, tenant = shared_repository.token, shared_repository.slug
    map_file = tmp_path / "packs.map.toml"
    map_file.write_text('schema = 1\n[pack_items]\n"Mystery thing" = "item"\n')

    result = plan(
        stack, token, tmp_path, tenant, PACKS, "--map", str(map_file), "--strict", "--json"
    )

    [pack] = [i for i in json.loads(result.stdout)["items"] if i["list"] == "packs"]
    assert pack["pack"]["unresolved"] == []
    assert result.exit_code == 2  # strict and nothing unresolved: only work to do


def test_a_row_saying_text_is_refused_since_every_line_of_a_pack_links(
    stack: Stack, tmp_path: Path, shared_repository: SharedRepository
) -> None:
    token, tenant = shared_repository.token, shared_repository.slug
    map_file = tmp_path / "packs.map.toml"
    map_file.write_text('schema = 1\n[pack_items]\n"Mystery thing" = "text"\n')

    result = plan(stack, token, tmp_path, tenant, PACKS, "--map", str(map_file))

    assert result.exit_code == 1
    assert "no longer a choice" in said(result)
    assert "Say 'item'" in said(result)


def test_a_pack_imported_without_its_contents_is_finished_by_the_next_run(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        pack = by_slug(api, tid, "basic-packs-camper")
        for info in pack["information"]:
            if info["type"] == "description":
                deleted = api.delete(f"/tenants/{tid}/information/{info['id']}")
                assert deleted.status_code == 204, deleted.text

    half = plan(stack, token, tmp_path, tenant, PACKS, "--json")
    finished = apply(stack, token, tmp_path, tenant, PACKS, "--yes")

    assert statuses(json.loads(half.stdout))["basic-packs-camper"] == "complete"
    assert finished.exit_code == 0, finished.output
    with stack.api(token) as api:
        assert description(by_slug(api, tid, "basic-packs-camper")) == [CONTENTS]


def a_party(stack: Stack, token: str, tmp_path: Path) -> tuple[str, str, dict[str, str]]:
    """A play tenant with the packs imported, and someone to give them to: a campaign, the caller's
    seat in it, their character Alice, and The Company, a group Alice is the one member of.
    (A repository holds no campaigns, so nothing in it can be handed a pack.)"""
    tenant = copy_of_seeded(stack, token, tmp_path, kind="play")
    applied = apply(stack, token, tmp_path, tenant, PACKS, "--yes", "--allow-play-tenant")
    assert applied.exit_code == 0, applied.output
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        me = api.get("/me").json()
        campaign = api.post(
            f"/tenants/{tid}/campaigns",
            json={"name": "Table", "game_system": "dnd5e", "slug": "table", "description": "x"},
        )
        assert campaign.status_code == 201, campaign.text
        player = api.post(
            f"/tenants/{tid}/campaigns/{campaign.json()['id']}/players",
            json={"user_id": me["id"]},
        )
        assert player.status_code == 201, player.text
        alice = api.post(
            f"/tenants/{tid}/characters",
            json={"name": "Alice", "owner_player_id": player.json()["id"]},
        )
        assert alice.status_code == 201, alice.text
        company = api.post(
            f"/tenants/{tid}/groups",
            json={"name": "The Company", "member_character_ids": [alice.json()["entity_id"]]},
        )
        assert company.status_code == 201, company.text
    return tenant, tid, {"alice": alice.json()["entity_id"], "company": company.json()["id"]}


def instances_of(api: httpx.Client, tid: str) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = api.get(
        f"/tenants/{tid}/item-instances", params={"size": 100}
    ).json()["items"]
    return listed


def said(result: Any) -> str:
    """The output as one line: the terminal wraps it where it likes."""
    return " ".join(result.output.split())


def test_a_pack_is_handed_to_a_being_into_its_hands(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant, tid, who = a_party(stack, token, tmp_path)
    give = ["pack", "give", "basic-packs-camper", "--tenant", tenant, "--owner", who["alice"]]

    dry = run_cli(stack, token, tmp_path, *give, "--dry-run")
    with stack.api(token) as api:
        assert instances_of(api, tid) == []
    given = run_cli(stack, token, tmp_path, *give)

    assert dry.exit_code == 0, dry.output
    assert "Would give 6 item(s)." in dry.output
    assert "  5 x Rations (1 day)" in dry.output
    assert given.exit_code == 0, given.output
    assert "Gave 6 item(s)." in given.output  # a backpack and five stacks in it
    assert "1 x Backpack" in given.output
    with stack.api(token) as api:
        [backpack] = [i for i in instances_of(api, tid) if i["title"] == "Backpack"]
        assert backpack["owner_entity_id"] == who["alice"]
        # In Alice's hands: contained directly in her.
        hands = api.get(f"/tenants/{tid}/entities/{who['alice']}").json()["children"]
        assert [c["name"] for c in hands] == ["Backpack"]
        detail = api.get(f"/tenants/{tid}/entities/{backpack['entity_id']}").json()
        held = {c["name"]: c["quantity"] for c in detail["children"]}
        assert held == {
            "Rations (1 day)": 5,
            "Torch": 2,
            "Rope, hempen (50 feet)": 1,
            "Alms box": 1,
            "Mystery thing": 1,
        }
        # 5 of its own, 5 x 2 of rations, 2 x 1 of torches, and a coil of 50 feet at 0.2 each.
        assert backpack["is_container"] is True
        assert (
            api.get(f"/tenants/{tid}/item-instances/{backpack['entity_id']}").json()["weight"]
            == 27.0
        )


def test_a_pack_is_handed_to_a_group_which_owns_it_and_holds_nothing(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant, tid, who = a_party(stack, token, tmp_path)

    given = run_cli(
        stack,
        token,
        tmp_path,
        *["pack", "give", "basic-packs-camper", "--tenant", tenant, "--owner", who["company"]],
    )

    assert given.exit_code == 0, given.output
    assert "Gave 6 item(s)." in given.output
    # A group has no container for a count, so its top level shows none: "Backpack", not "1 x".
    assert any(line == "Backpack" for line in given.output.splitlines())
    with stack.api(token) as api:
        made = instances_of(api, tid)
        assert {i["owner_entity_id"] for i in made} == {who["company"]}
        # Nothing is in the group's hands: a group carries nothing.
        assert api.get(f"/tenants/{tid}/entities/{who['company']}").json()["children"] == []
        [backpack] = [i for i in made if i["title"] == "Backpack"]
        assert backpack["quantity"] is None


def test_a_pack_with_a_line_that_does_not_link_is_refused_and_says_which(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant, tid, who = a_party(stack, token, tmp_path)
    with stack.api(token) as api:
        item = api.post(f"/tenants/{tid}/items", json={"name": "Broken pack", "slug": "broken"})
        assert item.status_code == 201, item.text
        written = api.post(
            f"/tenants/{tid}/entities/{item.json()['entity_id']}/information",
            json={
                "title": "Description",
                "type": "description",
                "content": "- 1 x [Backpack](basic-gear-backpack)\n- 1 x Alms box",
                "is_public": True,
            },
        )
        assert written.status_code == 201, written.text

    result = run_cli(
        stack,
        token,
        tmp_path,
        *["pack", "give", "broken", "--tenant", tenant, "--owner", who["alice"]],
    )

    assert result.exit_code == 1
    assert "can't be handed out as it is" in said(result)
    assert "“Alms box” has no link to an item" in said(result)
    with stack.api(token) as api:
        assert instances_of(api, tid) == []


def test_something_that_is_not_a_pack_is_not_handed_out(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant, tid, who = a_party(stack, token, tmp_path)

    result = run_cli(
        stack,
        token,
        tmp_path,
        *["pack", "give", "basic-gear-backpack", "--tenant", tenant, "--owner", who["alice"]],
    )

    assert result.exit_code == 1
    assert "isn't a pack" in said(result)
    with stack.api(token) as api:
        assert instances_of(api, tid) == []


def test_a_pack_that_is_not_there_is_reported(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    result = run_cli(
        stack,
        token,
        tmp_path,
        *["pack", "give", "no-such-pack", "--tenant", tenant, "--owner", str(uuid.uuid4())],
    )

    assert result.exit_code == 1
    assert "no pack “no-such-pack”" in said(result)


def test_which_packs_contain_an_item_is_answered_by_the_backlinks(
    stack: Stack, tmp_path: Path
) -> None:
    """R7: the links in a pack's description are references, so the tenant can say where an item is
    used without a table of its own."""
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        rations = by_slug(api, tid, "basic-gear-rations-1-day")
        response = api.get(f"/tenants/{tid}/entities/{rations['id']}/backlinks")

    assert response.status_code == 200, response.text
    assert [b["name"] for b in response.json()["items"]] == ["Camper's pack"]


def test_an_entry_the_sheet_has_no_gear_entry_for_becomes_a_plain_item(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        alms = by_slug(api, tid, "basic-gear-alms-box")
        mystery = by_slug(api, tid, "basic-gear-mystery-thing")
        backlinks = api.get(f"/tenants/{tid}/entities/{alms['id']}/backlinks").json()["items"]

    assert alms["name"] == "Alms box"
    assert [p["name"] for p in alms["prototypes"]] == ["Gear"]
    assert mystery["name"] == "Mystery thing"
    assert [b["name"] for b in backlinks] == ["Camper's pack"]
