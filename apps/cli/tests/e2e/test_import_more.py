"""More of `plan` and `apply` against the real API: identity, recovery, and the flags (ADR 0144)."""

from __future__ import annotations

import json
from pathlib import Path

from e2e.helpers import (
    FIXTURES,
    by_slug,
    make_tenant,
    own_stats,
    parent_names,
    run_cli,
    tenant_id,
)
from e2e.stack import Stack
from e2e.test_import import apply, plan, seeded_tenant, statuses

WEAPONS = str(FIXTURES / "weapons.js")
EXOTIC = str(FIXTURES / "exotic.map.toml")


def write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_the_namespace_comes_from_the_map_and_a_change_of_it_is_a_move_not_a_duplicate(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    alice = write(
        tmp_path / "alice.map.toml",
        'schema = 1\n[namespaces]\n"weapons.js" = "hb-alice"\n'
        + Path(EXOTIC).read_text().replace("schema = 1", ""),
    )
    assert apply(stack, token, tmp_path, tenant, WEAPONS, "--map", alice, "--yes").exit_code == 0
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        assert by_slug(api, tid, "hb-alice-weapons-purple-sword")["name"] == "Purple sword"

    # The same files under the default namespace: the plan notices, and creates nothing.
    moved = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--json")
    document = json.loads(moved.stdout)
    assert moved.exit_code == 1
    assert document["header"]["counts"]["moved"] == 4
    entry = next(i for i in document["items"] if i["key"] == "purple sword")
    assert entry["status"] == "moved"
    assert entry["moved_from"] == "hb-alice-weapons-purple-sword"
    assert entry["slug"] == "basic-weapons-purple-sword"
    queue = json.loads((tmp_path / "review-queue.json").read_text())
    assert any(
        q["kind"] == "moved" and "hb-alice-weapons-purple-sword" in q["reason"] for q in queue
    )

    accepted = apply(
        stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--accept-moves", "--yes"
    )
    assert accepted.exit_code == 0, accepted.output
    with stack.api(token) as api:
        assert by_slug(api, tid, "basic-weapons-purple-sword")["name"] == "Purple sword"


def test_an_item_an_earlier_run_stopped_in_the_middle_of_is_finished_not_mistaken_for_done(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        found = api.get(
            f"/tenants/{tid}/entities/resolve",
            params={"slug": ["melee-weapon", "dnd5e-martial"]},
        ).json()
        # What a run that died right after creating the item leaves: named, parented, no stats.
        created = api.post(
            f"/tenants/{tid}/items",
            json={
                "name": "Purple sword",
                "slug": "basic-weapons-purple-sword",
                "prototype_ids": [r["entity_id"] for r in found],
            },
        )
        assert created.status_code == 201

    half = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--json")
    assert statuses(json.loads(half.stdout))["basic-weapons-purple-sword"] == "complete"
    finished = apply(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--yes")
    settled = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--json")

    assert finished.exit_code == 0, finished.output
    assert settled.exit_code == 0
    with stack.api(token) as api:
        sword = by_slug(api, tid, "basic-weapons-purple-sword")
        assert own_stats(sword)["sourcebook"] == "T:W 4, P 149"
        assert own_stats(sword)["own_weight"] == 3.0
        assert len([i for i in sword["information"] if i["type"] == "description"]) == 1


def test_changed_parents_are_reported_and_only_reconciled_when_asked(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    assert apply(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--yes").exit_code == 0
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        sword = by_slug(api, tid, "basic-weapons-purple-sword")
        ranged = api.get(
            f"/tenants/{tid}/entities/resolve", params={"slug": "ranged-weapon"}
        ).json()[0]["entity_id"]
        item = api.get(f"/tenants/{tid}/items/{sword['id']}")
        moved = api.put(
            f"/tenants/{tid}/items/{sword['id']}/prototypes",
            json={"prototype_ids": [ranged]},
            headers={"If-Match": item.headers["etag"]},
        )
        assert moved.status_code == 200, moved.text

    reported = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--json")
    counted = plan(
        stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--reconcile", "--json"
    )
    left_alone = apply(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--yes")
    with stack.api(token) as api:
        assert parent_names(by_slug(api, tid, "basic-weapons-purple-sword")) == ["Ranged weapon"]
    fixed = apply(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--reconcile", "--yes")

    assert json.loads(reported.stdout)["header"]["counts"]["would_change_parents"] == 1
    assert reported.exit_code == 0  # create-only by default: it is a report, not pending work
    assert counted.exit_code == 2
    assert left_alone.exit_code == 0
    assert fixed.exit_code == 0, fixed.output
    with stack.api(token) as api:
        assert parent_names(by_slug(api, tid, "basic-weapons-purple-sword")) == [
            "Martial weapon",
            "Melee weapon",
        ]


def test_strict_treats_an_attribute_no_rule_mentions_as_unresolved(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    only_the_category = write(
        tmp_path / "category.map.toml",
        "schema = 1\n"
        "[classify.weapons.type]\n"
        'exotic = { disposition = "create-under", axis = "proficiency", '
        'slug = "hb-exotic", name = "Exotic weapon" }\n',
    )

    lenient = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", only_the_category)
    strict = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", only_the_category, "--strict")

    assert lenient.exit_code == 2  # something to create, and flavour is only reported
    assert strict.exit_code == 1
    queue = json.loads((tmp_path / "review-queue.json").read_text())
    unmapped = next(q for q in queue if q["kind"] == "attribute")
    assert unmapped["attribute"] == "flavour"
    assert '[attributes.weapons]\nflavour = "drop"' in unmapped["suggestion"]


def test_a_rule_can_write_a_stat_the_tenant_does_not_have_yet(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    lore = write(
        tmp_path / "lore.map.toml",
        Path(EXOTIC)
        .read_text()
        .replace(
            'flavour = "drop"',
            'flavour = { transform = "text", stat = "flavour_text", group = "lore" }',
        ),
    )

    dry = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", lore, "--json")
    applied = apply(stack, token, tmp_path, tenant, WEAPONS, "--map", lore, "--yes")

    assert json.loads(dry.stdout)["new_definitions"] == [
        {"name": "flavour_text", "group": "lore", "value_type": "text"}
    ]
    assert applied.exit_code == 0, applied.output
    with stack.api(token) as api:
        tid = tenant_id(api, tenant)
        whip = by_slug(api, tid, "basic-weapons-moon-whip")
        assert own_stats(whip)["flavour_text"] == "Cracks like thunder"
        assert "lore" in {g["name"] for g in whip["stat_groups"]}


def test_two_keys_that_slugify_alike_both_take_a_suffix_and_a_later_file_wins(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)
    first = write(
        tmp_path / "first.js",
        'WeaponsList["long sword"] = {name: "Long sword", type: "Martial", list: "melee", '
        'range: "Melee", source: ["HB", 0]};\n'
        'WeaponsList["long-sword"] = {name: "Long-sword", type: "Martial", list: "melee", '
        'range: "Melee", source: ["HB", 0]};\n'
        'WeaponsList["axe"] = {name: "Axe", type: "Simple", list: "melee", range: "Melee", '
        'source: ["HB", 0]};\n',
    )
    second = write(
        tmp_path / "second.js",
        'WeaponsList["axe"] = {name: "Axe (revised)", type: "Simple", list: "melee", '
        'range: "Melee", source: ["HB", 1]};\n',
    )

    result = plan(stack, token, tmp_path, tenant, first, second, "--json")

    document = json.loads(result.stdout)
    slugs = {i["key"]: i["slug"] for i in document["items"]}
    assert slugs["axe"] == "basic-weapons-axe"  # no clash, so no suffix
    assert slugs["long sword"] != slugs["long-sword"]
    for key in ("long sword", "long-sword"):
        assert slugs[key].startswith("basic-weapons-long-sword-")
        assert len(slugs[key].rsplit("-", 1)[1]) == 6
    assert document["overrides"] == [
        {"list": "WeaponsList", "key": "axe", "replaced_file": "first.js", "by_file": "second.js"}
    ]
    axe = next(i for i in document["items"] if i["key"] == "axe")
    assert axe["name"] == "Axe (revised)" and axe["file"] == "second.js"


def test_the_imported_items_are_not_public_unless_asked(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    private = seeded_tenant(stack, token, tmp_path)
    public = seeded_tenant(stack, token, tmp_path)

    apply(stack, token, tmp_path, private, WEAPONS, "--map", EXOTIC, "--yes")
    apply(stack, token, tmp_path, public, WEAPONS, "--map", EXOTIC, "--public-catalog", "--yes")

    with stack.api(token) as api:
        for tenant, expected in ((private, False), (public, True)):
            tid = tenant_id(api, tenant)
            sword = by_slug(api, tid, "basic-weapons-purple-sword")
            assert (
                api.get(f"/tenants/{tid}/items/{sword['id']}").json()["in_public_catalog"]
                is expected
            )


def test_a_play_tenant_is_refused_and_a_bad_map_is_reported_before_anything_else(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    play = make_tenant(stack, token, kind="play")
    tenant = seeded_tenant(stack, token, tmp_path)
    broken = write(tmp_path / "broken.map.toml", 'schema = 1\n[attributes.weapons]\nx = "shout"\n')
    not_toml = write(tmp_path / "not.map.toml", "this is = = not toml")

    refused = plan(stack, token, tmp_path, play, WEAPONS)
    unknown = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", broken)
    garbled = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", not_toml)

    assert refused.exit_code == 1 and "published" in refused.output
    assert unknown.exit_code == 1 and "unknown transform 'shout'" in unknown.output
    assert garbled.exit_code == 1 and "isn't valid TOML" in garbled.output


def test_two_plans_of_the_same_inputs_are_the_same_document(stack: Stack, tmp_path: Path) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

    one = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--json")
    two = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--json")

    assert one.stdout == two.stdout


def test_nothing_is_written_without_yes_when_nobody_can_be_asked(
    stack: Stack, tmp_path: Path
) -> None:
    token = stack.creator_token()
    tenant = seeded_tenant(stack, token, tmp_path)

    refused = apply(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC)
    still = plan(stack, token, tmp_path, tenant, WEAPONS, "--map", EXOTIC, "--json")

    assert refused.exit_code == 1 and "--yes" in refused.output
    assert set(statuses(json.loads(still.stdout)).values()) == {"create"}
    assert run_cli  # (imported for the fixtures' sake)
