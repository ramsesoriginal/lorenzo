"""The sheet's own SRD items through the whole importer, when a local clone of the upstream
repository is given (see tests/test_evalworker_upstream.py). Upstream is GPL-3.0 and is not copied
into this repository."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from e2e.helpers import by_slug, own_stats, parent_names, run_cli, tenant_id
from e2e.stack import Stack
from e2e.test_import import apply, plan, seeded_tenant, statuses

_ROOT = os.environ.get("LORENZO_UPSTREAM_CORPUS")

pytestmark = pytest.mark.skipif(not _ROOT, reason="LORENZO_UPSTREAM_CORPUS is not set")


def srd_arguments() -> list[str]:
    variables = Path(_ROOT or "") / "_variables"
    arguments: list[str] = []
    for name in ("ListsSources.js", "Lists.js", "ListsGear.js"):
        arguments += ["--base", str(variables / name)]
    return arguments


def test_the_srd_imports_with_nothing_left_unresolved_and_a_second_run_finds_nothing(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

    dry = plan(stack, token, tmp_path, tenant, *srd_arguments(), "--json")
    document = json.loads(dry.stdout)
    by_status = Counter(i["status"] for i in document["items"])
    held = [
        (i["list"], i["key"], [x["reason"] for x in i["issues"]])
        for i in document["items"]
        if i["status"] == "held"
    ]
    assert document["problems"] == [], document["problems"]
    assert held == [], held
    assert document["unmapped_attributes"] == [], document["unmapped_attributes"]
    assert by_status["create"] >= 200 and by_status["skipped"] >= 10, by_status

    applied = apply(stack, token, tmp_path, tenant, *srd_arguments(), "--yes")
    assert applied.exit_code == 0, applied.output
    again = plan(stack, token, tmp_path, tenant, *srd_arguments(), "--json")
    assert again.exit_code == 0, again.output
    assert set(statuses(json.loads(again.stdout)).values()) == {"exists"}

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        longsword = by_slug(api, tid, "basic-weapons-longsword")
        assert parent_names(longsword) == ["Martial weapon", "Melee weapon"]
        assert own_stats(longsword)["own_weight"] == 3.0
        assert own_stats(longsword)["damage_die"] == 8
        dagger = by_slug(api, tid, "basic-weapons-dagger")
        assert parent_names(dagger) == ["Melee weapon", "Ranged weapon", "Simple weapon"]
        assert own_stats(dagger)["range_long"] == 60
        chain_mail = by_slug(api, tid, "basic-armour-chain-mail")
        assert parent_names(chain_mail) == ["Armor", "Heavy armor"]
        assert own_stats(chain_mail)["armor"] == 16
        backpack = by_slug(api, tid, "basic-gear-backpack")
        assert "Container" in parent_names(backpack)
        rope = by_slug(api, tid, "basic-gear-rope-hempen-50-feet")
        assert own_stats(rope)["own_weight"] == 10.0  # 50 feet at 0.2 each
        assert own_stats(rope)["price"] == 100
        arrows = by_slug(api, tid, "basic-gear-arrows-20")
        assert parent_names(arrows) == ["Ammunition"]


def test_the_srd_packs_link_cleanly_and_can_be_handed_out(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    assert apply(stack, token, tmp_path, tenant, *srd_arguments(), "--yes").exit_code == 0

    strict = plan(stack, token, tmp_path, tenant, *srd_arguments(), "--strict", "--json")
    assert strict.exit_code == 0, json.loads(strict.stdout)["unmapped_attributes"]
    packs = [i for i in json.loads(strict.stdout)["items"] if i["list"] == "packs"]
    assert len(packs) == 7 and all(p["pack"]["plain_text"] == [] for p in packs)

    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        explorer = by_slug(api, tid, "basic-packs-explorer")
        [text] = [
            p["content"]
            for i in explorer["information"]
            if i["type"] == "description"
            for p in i["payloads"]
        ]
    assert text.startswith("This pack contains:\n\n- 1 x [Backpack](basic-gear-backpack)\n")
    assert "  - 10 x [Rations (1 day)](basic-gear-rations-1-day)" in text
    assert "[Rope, hempen (50 feet)](basic-gear-rope-hempen-50-feet)" in text  # 50 feet, one coil

    given = run_cli(
        stack, token, tmp_path, "pack", "give", "basic-packs-explorer", "--tenant", tenant
    )
    assert given.exit_code == 0, given.output
