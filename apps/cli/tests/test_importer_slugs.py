from __future__ import annotations

import re

from lorenzo_cli.importer.slugs import (
    LIST_TOKENS,
    assign_slugs,
    base_slug,
    collision_suffix,
    slugify,
)

SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


def test_slugify_makes_lower_case_words_joined_by_single_hyphens() -> None:
    assert slugify("Hempen rope, feet of") == "hempen-rope-feet-of"
    assert slugify("  Rope,  hempen (50 feet) ") == "rope-hempen-50-feet"
    assert slugify("Purplemancer's tools") == "purplemancer-s-tools"


def test_slugify_transliterates_and_never_returns_nothing() -> None:
    assert slugify("Éclair d'Épée") == "eclair-d-epee"
    assert slugify("剣") == "item"
    assert slugify("---") == "item"


def test_the_slug_is_namespace_list_and_key() -> None:
    assert base_slug("basic", "weapons", "longsword") == "basic-weapons-longsword"
    assert base_slug("hb-alice", "gear", "Rations, days of") == "hb-alice-gear-rations-days-of"


def test_a_long_key_is_cut_so_that_a_suffix_always_fits() -> None:
    slug = base_slug("basic", "gear", "x" * 500)

    assert len(slug) <= 100 - 7
    assert SLUG.match(slug + "-abcdef")
    assert not slug.endswith("-")


def test_the_same_key_always_gets_the_same_slug() -> None:
    assert base_slug("basic", "weapons", "Long Sword") == base_slug(
        "basic", "weapons", "Long Sword"
    )
    assert collision_suffix("weapons", "long sword") == collision_suffix("weapons", "long sword")
    assert len(collision_suffix("weapons", "x")) == 6


def test_only_the_members_of_a_collision_take_a_suffix_and_all_of_them_do() -> None:
    slugs = assign_slugs(
        [
            ("basic", "weapons", "long sword"),
            ("basic", "weapons", "long-sword"),
            ("basic", "weapons", "axe"),
        ]
    )

    assert slugs[("weapons", "axe")] == "basic-weapons-axe"
    a, b = slugs[("weapons", "long sword")], slugs[("weapons", "long-sword")]
    assert a != b
    assert a.startswith("basic-weapons-long-sword-") and b.startswith("basic-weapons-long-sword-")
    assert SLUG.match(a) and SLUG.match(b)


def test_which_key_came_first_cannot_change_the_slugs() -> None:
    forward = assign_slugs([("basic", "gear", "a b"), ("basic", "gear", "a-b")])
    backward = assign_slugs([("basic", "gear", "a-b"), ("basic", "gear", "a b")])

    assert forward == backward


def test_the_same_key_in_two_lists_is_not_a_collision() -> None:
    slugs = assign_slugs([("basic", "gear", "arrows"), ("basic", "ammo", "arrows")])

    assert slugs[("gear", "arrows")] == "basic-gear-arrows"
    assert slugs[("ammo", "arrows")] == "basic-ammo-arrows"


def test_a_slug_someone_else_holds_makes_ours_take_a_suffix() -> None:
    slugs = assign_slugs([("basic", "gear", "rope")], taken={"basic-gear-rope"})

    assert slugs[("gear", "rope")].startswith("basic-gear-rope-")
    assert len(slugs[("gear", "rope")]) == len("basic-gear-rope") + 7


def test_every_standard_list_has_a_token() -> None:
    assert LIST_TOKENS == {
        "WeaponsList": "weapons",
        "ArmourList": "armour",
        "GearList": "gear",
        "PacksList": "packs",
        "ToolsList": "tools",
        "AmmoList": "ammo",
    }
