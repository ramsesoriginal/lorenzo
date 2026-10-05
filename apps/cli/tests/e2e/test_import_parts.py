"""The importer's two passes against the real API (ADR 0182): the neutral half into the equipment
repository, the system's half into the bridge that attaches it, and a table that takes the
equipment first and the bridge after.

The stack is RFC 0033's: core, an equipment repository and a rules repository over it, and a
bridge over both. It is built once for the file, since every test only reads it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from e2e.helpers import FIXTURES, by_slug, make_tenant, own_stats, parent_names, run_cli, tenant_id
from e2e.stack import Stack
from lorenzo_cli.seed import load_builtin

SEED = load_builtin()
MARTIAL = SEED.node("dnd5e-martial").name
VERSATILE = SEED.node("dnd5e-versatile").name
FILES = [str(FIXTURES / "weapons.js"), str(FIXTURES / "packs.js")]
MAP = ["--map", str(FIXTURES / "legendary-form.map.toml")]


def said(result: Any) -> str:
    return " ".join(result.output.split())


class Parted:
    """Core, the equipment (neutral pass) and the rules, and the bridge (system pass) over both."""

    def __init__(self, stack: Stack, work: Path) -> None:
        self.stack = stack
        self.work = work
        self.token = stack.creator_token("parts-owner")
        self.core = make_tenant(stack, self.token, "repository")
        self.equipment = make_tenant(stack, self.token, "repository")
        self.rules = make_tenant(stack, self.token, "repository")
        self.bridge = make_tenant(stack, self.token, "repository")
        self.ok("seed", "--tenant", self.core, "--layer", "core", "--yes")
        self.ok("repo", "publish", "--tenant", self.core)
        for repository, layer in ((self.equipment, "equipment"), (self.rules, "dnd5e")):
            self.ok("repo", "grant", repository, "--tenant", self.core)
            self.ok("repo", "copy", self.core, "--tenant", repository, "--yes")
            self.ok("seed", "--tenant", repository, "--layer", layer, "--yes")
        self.ok(*self.importing(self.equipment, "neutral", "--public-catalog", "--yes"))
        self.ok("repo", "publish", "--tenant", self.equipment)
        self.ok("repo", "publish", "--tenant", self.rules)
        self.bridge_over(self.bridge, self.equipment)
        self.ok(*self.importing(self.bridge, "system", "--yes"))
        self.ok("repo", "publish", "--tenant", self.bridge)

    def bridge_over(self, bridge: str, equipment: str) -> None:
        self.ok("repo", "offer", bridge, "--tenant", equipment, "--yes")
        self.ok("repo", "offer", bridge, "--tenant", self.rules, "--yes")
        self.ok("seed", "--tenant", bridge, "--layer", "dnd5e-equipment", "--yes")

    def importing(self, tenant: str, part: str, *flags: str) -> tuple[str, ...]:
        return (
            "apply", "--tenant", tenant, "--part", part, *flags, *MAP,
            "--review-queue", str(self.work / "review-queue.json"),
            "--proposed-map", str(self.work / "proposed.map.toml"),
            *FILES,
        )  # fmt: skip

    def planning(self, tenant: str, part: str | None, *flags: str) -> tuple[str, ...]:
        chosen = ("--part", part) if part else ()
        return (
            "plan", "--tenant", tenant, *chosen, *flags, *MAP,
            "--review-queue", str(self.work / "review-queue.json"),
            "--proposed-map", str(self.work / "proposed.map.toml"),
            *FILES,
        )  # fmt: skip

    def cli(self, *args: str) -> Any:
        return run_cli(self.stack, self.token, self.work, *args)

    def ok(self, *args: str) -> Any:
        result = self.cli(*args)
        assert result.exit_code == 0, f"{' '.join(args)}\n{result.output}"
        return result

    def json(self, *args: str) -> tuple[int, Any]:
        result = self.cli(*args, "--json")
        return result.exit_code, json.loads(result.stdout) if result.stdout.strip() else None

    def entity(self, tenant: str, slug: str) -> dict[str, Any]:
        with self.stack.api(self.token) as api:
            return by_slug(api, tenant_id(api, tenant), slug)

    def has(self, tenant: str, slug: str) -> bool:
        with self.stack.api(self.token) as api:
            response = api.get(f"/tenants/{tenant_id(api, tenant)}/entities/by-slug/{slug}")
        return response.status_code == 200

    def public(self, tenant: str, slug: str) -> bool:
        with self.stack.api(self.token) as api:
            return in_public_catalog(api, tenant_id(api, tenant), self.entity(tenant, slug)["id"])


def in_public_catalog(api: httpx.Client, tid: str, entity_id: str) -> bool:
    shown = api.get(f"/tenants/{tid}/items/{entity_id}")
    assert shown.status_code == 200, shown.text
    return bool(shown.json()["in_public_catalog"])


@pytest.fixture(scope="module")
def parted(stack: Stack, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Parted]:
    yield Parted(stack, tmp_path_factory.mktemp("parted"))


def test_the_neutral_pass_writes_the_item_under_its_forms_public_and_with_nothing_of_the_system(
    parted: Parted,
) -> None:
    sword = parted.entity(parted.equipment, "basic-weapons-purple-sword")

    assert parent_names(sword) == ["Blade", "Melee weapon"]
    assert own_stats(sword) == {"sourcebook": "T:W 4, P 149", "own_weight": 3.0}
    assert parted.public(parted.equipment, "basic-weapons-purple-sword") is True
    assert not parted.has(parted.equipment, "srd5e-weapons-purple-sword")
    # A form a map row mints under a neutral axis is the neutral pass's, in the equipment.
    assert parent_names(parted.entity(parted.equipment, "basic-weapons-moon-whip")) == [
        "Legendary weapon",
        "Melee weapon",
        "Whip",
    ]
    assert parted.has(parted.equipment, "hb-legendary-form")


def test_the_system_pass_attaches_a_prototype_to_the_equipments_item_in_the_bridge(
    parted: Parted,
) -> None:
    sword = parted.entity(parted.bridge, "basic-weapons-purple-sword")
    prototype = parted.entity(parted.bridge, "srd5e-weapons-purple-sword")

    assert parent_names(sword) == ["Blade", "Melee weapon", "Purple sword (D&D 5e)"]
    assert prototype["name"] == "Purple sword (D&D 5e)"
    assert parent_names(prototype) == sorted([MARTIAL, VERSATILE])
    assert own_stats(prototype) == {
        "damage_dice_count": 1,
        "damage_die": 8,
        "damage_type": "slashing",
        "damage_versatile_die": 10,
        "attack_ability": "Strength",
        "ability_to_damage": True,
    }
    # The sword has its dice from the prototype and the price of 0 from the Economic object that
    # the bridge's seed attached to Weapon: neither is its own.
    inherited = {s["name"]: s for s in sword["stats"]}
    assert inherited["damage_die"]["value"] == 8 and inherited["damage_die"]["own"] is False
    assert inherited["price"]["value"] == 0 and inherited["price"]["own"] is False
    assert inherited["own_weight"]["own"] is True
    # The prototype is for the GM's whole catalog; the neutral item stays public.
    assert parted.public(parted.bridge, "srd5e-weapons-purple-sword") is False
    assert parted.public(parted.bridge, "basic-weapons-purple-sword") is True
    # Nothing of the neutral half was written on it, and the bridge's own item list has both.
    assert "own_weight" not in {s["name"] for s in prototype["stats"] if s["own"]}


def test_a_weapon_with_no_proficiency_still_gets_its_prototype_for_its_dice(
    parted: Parted,
) -> None:
    whip = parted.entity(parted.bridge, "basic-weapons-moon-whip")
    prototype = parted.entity(parted.bridge, "srd5e-weapons-moon-whip")

    assert "Moon whip (D&D 5e)" in parent_names(whip)
    assert parent_names(prototype) == []
    assert own_stats(prototype)["damage_die"] == 6


def test_a_pack_keeps_its_contents_in_the_equipment_and_gets_its_price_from_the_bridge(
    parted: Parted,
) -> None:
    contents = [
        p["content"]
        for i in parted.entity(parted.equipment, "basic-packs-camper")["information"]
        if i["type"] == "description"
        for p in i["payloads"]
    ]
    pack = parted.entity(parted.bridge, "basic-packs-camper")
    prototype = parted.entity(parted.bridge, "srd5e-packs-camper")

    assert len(contents) == 1 and contents[0].startswith("This pack contains:")
    assert "price" not in own_stats(parted.entity(parted.equipment, "basic-packs-camper"))
    assert "Camper's pack (D&D 5e)" in parent_names(pack)
    assert own_stats(prototype) == {"price": 700}
    # Every item of the pack is the equipment's, with its own price in the bridge.
    assert own_stats(parted.entity(parted.bridge, "srd5e-gear-backpack")) == {"price": 200}
    assert "price" not in own_stats(parted.entity(parted.equipment, "basic-gear-backpack"))
    # A plain item made for an entry of the pack has nothing of the system's, so no prototype.
    assert parted.has(parted.bridge, "basic-gear-alms-box")
    assert not parted.has(parted.bridge, "srd5e-gear-alms-box")


def test_a_second_run_of_each_pass_finds_what_the_first_made_and_attaches_nothing_twice(
    parted: Parted,
) -> None:
    before = parent_names(parted.entity(parted.bridge, "basic-weapons-purple-sword"))

    neutral_code, neutral = parted.json(*parted.planning(parted.equipment, "neutral"))
    system_code, system = parted.json(*parted.planning(parted.bridge, "system"))
    parted.ok(*parted.importing(parted.bridge, "system", "--yes"))

    assert neutral_code == 0 and system_code == 0
    assert {i["status"] for i in neutral["items"]} == {"exists", "skipped"}
    assert {i["status"] for i in system["items"]} == {"exists", "skipped"}
    assert neutral["header"]["part"] == "neutral" and system["header"]["part"] == "system"
    assert parent_names(parted.entity(parted.bridge, "basic-weapons-purple-sword")) == before


def test_a_table_that_took_the_equipment_first_gets_the_prototype_when_it_takes_the_bridge(
    parted: Parted,
) -> None:
    table = make_tenant(parted.stack, parted.token, "play")
    parted.ok("repo", "offer", table, "--tenant", parted.equipment, "--yes")
    before = parted.entity(table, "basic-weapons-purple-sword")
    assert parent_names(before) == ["Blade", "Melee weapon"]
    assert "damage_die" not in {s["name"] for s in before["stats"]}

    code, offered = parted.json("repo", "offer", table, "--tenant", parted.bridge, "--yes")

    assert code == 0, offered
    after = parted.entity(table, "basic-weapons-purple-sword")
    # The one sword the table had has the prototype as a parent now, and its dice by inheritance.
    assert parent_names(after) == ["Blade", "Melee weapon", "Purple sword (D&D 5e)"]
    dice = next(s for s in after["stats"] if s["name"] == "damage_die")
    assert dice["value"] == 8 and dice["own"] is False
    assert parted.public(table, "basic-weapons-purple-sword") is True
    assert parted.public(table, "srd5e-weapons-purple-sword") is False
    with parted.stack.api(parted.token) as api:
        swords = api.get(
            f"/tenants/{tenant_id(api, table)}/entities/resolve",
            params={"slug": ["basic-weapons-purple-sword"]},
        ).json()
    assert len(swords) == 1


def test_the_system_pass_before_the_neutral_one_holds_every_item_and_writes_nothing(
    parted: Parted,
) -> None:
    equipment = make_tenant(parted.stack, parted.token, "repository")
    bridge = make_tenant(parted.stack, parted.token, "repository")
    parted.ok("repo", "grant", equipment, "--tenant", parted.core)
    parted.ok("repo", "copy", parted.core, "--tenant", equipment, "--yes")
    parted.ok("seed", "--tenant", equipment, "--layer", "equipment", "--yes")
    parted.ok("repo", "publish", "--tenant", equipment)
    parted.bridge_over(bridge, equipment)

    code, document = parted.json(*parted.planning(bridge, "system"))
    refused = parted.cli(*parted.importing(bridge, "system", "--yes"))

    assert code == 1
    held = [i for i in document["items"] if i["status"] == "held"]
    assert held and {i["status"] for i in document["items"]} <= {"held", "skipped"}
    assert {issue["kind"] for i in held for issue in i["issues"]} == {"neutral-item"}
    assert refused.exit_code == 1
    queue = json.loads((parted.work / "review-queue.json").read_text())
    assert any("lorenzo apply --part neutral" in entry["suggestion"] for entry in queue)
    assert not parted.has(bridge, "srd5e-weapons-purple-sword")


def test_a_prototype_is_never_public_so_the_flag_is_refused_with_the_system_pass(
    parted: Parted,
) -> None:
    refused = parted.cli(*parted.importing(parted.bridge, "system", "--public-catalog", "--yes"))

    assert refused.exit_code == 2
    assert "--public-catalog is for the neutral pass" in said(refused)


def test_without_a_part_one_tenant_gets_the_one_item_with_both_halves_as_before(
    parted: Parted,
) -> None:
    tenant = make_tenant(parted.stack, parted.token, "repository")
    parted.ok("seed", "--tenant", tenant, "--yes")

    code, document = parted.json(*parted.planning(tenant, None))
    parted.ok(
        "apply", "--tenant", tenant, *MAP, "--review-queue", str(parted.work / "rq.json"),
        "--proposed-map", str(parted.work / "pm.toml"), *FILES, "--yes",
    )  # fmt: skip

    assert code == 2 and document["header"]["part"] == "all"
    sword = parted.entity(tenant, "basic-weapons-purple-sword")
    assert parent_names(sword) == ["Blade", MARTIAL, "Melee weapon", VERSATILE]
    assert own_stats(sword)["damage_die"] == 8
    assert not parted.has(tenant, "srd5e-weapons-purple-sword")
