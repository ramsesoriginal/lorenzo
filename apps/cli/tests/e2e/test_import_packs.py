"""Packs against the real API (RFC 0025 R7, ADR 0145): their contents in the description, and
handing them out."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e.helpers import FIXTURES, by_slug, run_cli, tenant_id
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
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

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
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    map_file = tmp_path / "packs.map.toml"
    map_file.write_text('schema = 1\n[pack_items]\n"Mystery thing" = "text"\n')

    result = plan(
        stack, token, tmp_path, tenant, PACKS, "--map", str(map_file), "--strict", "--json"
    )

    [pack] = [i for i in json.loads(result.stdout)["items"] if i["list"] == "packs"]
    assert pack["pack"]["unresolved"] == []
    assert result.exit_code == 2  # strict and nothing unresolved: only work to do


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


def test_a_pack_is_handed_out_as_a_container_holding_stacks(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    dry = run_cli(
        stack,
        token,
        tmp_path,
        "pack",
        "give",
        "basic-packs-camper",
        "--tenant",
        tenant,
        "--dry-run",
    )
    given = run_cli(
        stack, token, tmp_path, "pack", "give", "basic-packs-camper", "--tenant", tenant
    )

    assert dry.exit_code == 0, dry.output
    assert "would create 5 x Rations (1 day)" in dry.output
    assert given.exit_code == 0, given.output
    assert "skipped" not in given.output  # every entry is an item
    assert "Created 11 item(s)" in given.output  # 1 + 5 + 2 + 1 + 1 + 1
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        instances = api.get(f"/tenants/{tid}/item-instances", params={"size": 100}).json()["items"]
        [backpack] = [i for i in instances if i["title"] == "Backpack"]
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


def test_something_that_is_not_a_pack_is_not_handed_out(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    result = run_cli(
        stack, token, tmp_path, "pack", "give", "basic-gear-backpack", "--tenant", tenant
    )

    assert result.exit_code == 1
    assert "no contents list" in result.output.replace("\n", " ")


def test_a_pack_that_is_not_there_is_reported(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = imported(stack, token, tmp_path)

    result = run_cli(stack, token, tmp_path, "pack", "give", "no-such-pack", "--tenant", tenant)

    assert result.exit_code == 1
    assert "no pack “no-such-pack”" in result.output.replace("\n", " ")


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
