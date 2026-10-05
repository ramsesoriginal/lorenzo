from __future__ import annotations

import pytest

from lorenzo_cli.importer.mapping import (
    MappingError,
    Row,
    load_mapping,
)


def test_the_builtin_map_loads_and_says_what_a_martial_weapon_is() -> None:
    loaded = load_mapping()
    mapping = loaded.mapping

    assert loaded.user_map_sha256 == ""
    assert loaded.builtin_version == "2"
    assert mapping.classify["weapons"]["type"]["martial"].parents == ["dnd5e-martial"]
    assert mapping.classify["weapons"]["type"]["natural"].disposition == "skip"
    assert mapping.classify["gear"]["type"]["ammunition"].replace_form is True
    assert mapping.classify["gear"]["type"]["*"].disposition == "attach-form-only"
    assert mapping.lists["weapons"].reach_required is True
    assert mapping.currencies == {"cp": 1, "sp": 10, "ep": 50, "gp": 100, "pp": 1000}
    assert [r.transform for r in mapping.attributes["weapons"]["damage"]] == ["damage"]
    assert [r.transform for r in mapping.attributes["weapons"]["description"]] == [
        "description",
        "regex_extract",
    ]  # an attribute can feed more than one stat
    assert "property" in mapping.lists["weapons"].roots


def test_a_project_map_overlays_the_builtin_one_row_by_row() -> None:
    loaded = load_mapping(
        """
schema = 1
[currencies]
mark = 250
gp = 120
[classify.weapons.type]
Martial = ["hb-heavy"]
Exotic = "attach-form-only"
[attributes.weapons]
flavour = "drop"
[namespaces]
"my.js" = "hb-alice"
"""
    )
    mapping = loaded.mapping

    assert mapping.currencies["mark"] == 250 and mapping.currencies["gp"] == 120
    assert mapping.currencies["sp"] == 10  # the rest of the built-in row set is still there
    assert mapping.classify["weapons"]["type"]["martial"].parents == ["hb-heavy"]  # replaced
    assert mapping.classify["weapons"]["type"]["simple"].parents == ["dnd5e-simple"]  # kept
    assert mapping.classify["weapons"]["type"]["exotic"].disposition == "attach-form-only"
    assert [r.transform for r in mapping.attributes["weapons"]["flavour"]] == ["drop"]
    assert [r.transform for r in mapping.attributes["weapons"]["damage"]] == ["damage"]
    assert len(loaded.user_map_sha256) == 64


def test_the_namespace_is_declared_per_file_and_defaults_to_basic() -> None:
    mapping = load_mapping('schema = 1\n[namespaces]\n"my.js" = "hb-alice"\n').mapping

    assert mapping.namespace_for("my.js") == "hb-alice"
    assert mapping.namespace_for("ListsGear.js") == "basic"


def test_a_row_can_be_a_list_a_disposition_or_a_table() -> None:
    loaded = load_mapping(
        """
schema = 1
[classify.weapons.type]
a = ["x", "y"]
b = "skip"
c = { disposition = "map", parents = ["z"], replace_form = true }
d = { disposition = "create-under", axis = "proficiency", slug = "hb-d", name = "D" }
"""
    )
    rows = loaded.mapping.classify["weapons"]["type"]

    assert rows["a"] == Row(parents=["x", "y"])
    assert rows["b"].disposition == "skip"
    assert rows["c"].replace_form is True
    assert (rows["d"].axis, rows["d"].slug) == ("proficiency", "hb-d")


def test_the_same_map_always_hashes_the_same() -> None:
    text = "schema = 1\n[currencies]\nmark = 250\n"

    assert load_mapping(text).user_map_sha256 == load_mapping(text).user_map_sha256
    assert load_mapping(text + "\n").user_map_sha256 != load_mapping(text).user_map_sha256


def test_the_name_rules_of_a_project_come_before_the_builtin_ones() -> None:
    mapping = load_mapping(
        'schema = 1\n[[name_rule]]\nin_list = "gear"\nstarts_with = ["crate"]\nparents = ["container"]\n'
    ).mapping

    assert mapping.name_rules[0].starts_with == ["crate"]
    assert any("backpack" in rule.starts_with for rule in mapping.name_rules[1:])


def test_regex_extract_checks_its_examples_when_the_map_loads() -> None:
    good = """
schema = 1
[attributes.gear]
capacity = { transform = "regex_extract", pattern = "(\\\\d+) lb", group = 1, stat = "carry_capacity", as = "int", group_name = "x", examples = [{ input = "holds 30 lb", output = "30" }] }
"""
    # (the example passes: this loads without complaint)
    assert load_mapping(good.replace(', group_name = "x"', "")).mapping.attributes["gear"][
        "capacity"
    ]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not toml = =", "isn't valid TOML"),
        ("[currencies]\nmark = 1\n", "schema = 1"),
        ("schema = 1\nsurprise = 1\n", "Unknown top-level keys"),
        ('schema = 1\n[attributes.weapons]\nx = "shout"\n', "unknown transform 'shout'"),
        ('schema = 1\n[attributes.spells]\nx = "drop"\n', "is not a list"),
        (
            'schema = 1\n[attributes.weapons]\nx = "classify"\n',
            "is `classify`, but there is no",
        ),
        (
            'schema = 1\n[attributes.weapons]\nx = { transform = "drop", extra = 1 }\n',
            "takes no parameters",
        ),
        ('schema = 1\n[attributes.weapons]\nx = { transform = "int" }\n', "needs `stat`"),
        (
            'schema = 1\n[attributes.weapons]\nx = { transform = "keyword_flag", stat = "s" }\n',
            "needs `keywords`",
        ),
        (
            'schema = 1\n[attributes.weapons]\nx = { transform = "first_of", stat = "s" }\n',
            "needs `of`",
        ),
        (
            'schema = 1\n[attributes.gear]\nx = { transform = "regex_extract", stat = "s", pattern = "(a)" }\n',
            "needs `examples`",
        ),
        (
            'schema = 1\n[attributes.gear]\nx = { transform = "regex_extract", stat = "s", pattern = "(a", examples = [{input = "a", output = "a"}] }\n',
            "doesn't compile",
        ),
        (
            'schema = 1\n[attributes.gear]\nx = { transform = "regex_extract", stat = "s", pattern = "(\\\\d+)", examples = [{input = "5", output = "6"}] }\n',
            "should give '6', and gives '5'",
        ),
        (
            'schema = 1\n[attributes.gear]\nx = { transform = "regex_extract", stat = "s", pattern = "a", group = 1, examples = [{input = "a", output = "a"}] }\n',
            "has no group 1",
        ),
        ('schema = 1\n[namespaces]\n"a.js" = "Bad Name"\n', "lower-case letters"),
        ("schema = 1\n[currencies]\nmark = 0\n", "at least 1"),
        ('schema = 1\n[classify.weapons.type]\nx = "explode"\n', "explode"),
        (
            'schema = 1\n[classify.weapons.type]\nx = { disposition = "skip", parents = ["a"] }\n',
            "takes no parents",
        ),
        (
            'schema = 1\n[classify.weapons.type]\nx = { disposition = "create-under" }\n',
            "needs axis, slug and name",
        ),
        (
            'schema = 1\n[classify.weapons.type]\nx = { disposition = "create-under", axis = "tier", slug = "hb-x", name = "X" }\n',
            "no tier axis",
        ),
        (
            'schema = 1\n[classify.weapons.type]\nx = { disposition = "create-under", axis = "proficiency", slug = "exotic", name = "X" }\n',
            "needs a prefix that says whose it is",
        ),
        (
            'schema = 1\n[classify.weapons.type]\nx = { disposition = "create-under", axis = "form", slug = "dnd5e-x", name = "X" }\n',
            "can't go under the form axis",
        ),
        (
            'schema = 1\n[classify.weapons.type]\nx = { disposition = "create-under", axis = "proficiency", slug = "gear", name = "X" }\n',
            "already one of the seed's own categories",
        ),
        (
            'schema = 1\n[classify.weapons.type]\nx = { disposition = "create-under", axis = "proficiency", slug = "has space", name = "X" }\n',
            "not a valid slug",
        ),
        (
            'schema = 1\n[[name_rule]]\nin_list = "spells"\nstarts_with = ["a"]\nparents = ["b"]\n',
            "doesn't exist",
        ),
    ],
)
def test_a_wrong_map_is_refused_with_a_reason(text: str, message: str) -> None:
    with pytest.raises(MappingError, match=message):
        load_mapping(text)


def test_an_attribute_takes_one_rule_or_a_list_of_them() -> None:
    mapping = load_mapping(
        """
schema = 1
[attributes.gear]
one = "drop"
two = ["drop", { transform = "int", stat = "s" }]
"""
    ).mapping

    assert [r.transform for r in mapping.attributes["gear"]["one"]] == ["drop"]
    assert [r.transform for r in mapping.attributes["gear"]["two"]] == ["drop", "int"]


def test_a_name_rule_can_read_another_attribute_and_share_an_exclusive_group() -> None:
    mapping = load_mapping(
        """
schema = 1
[[name_rule]]
in_list = "weapons"
attribute = "description"
words = ["two-handed"]
group = "g"
parents = ["dnd5e-two-handed"]
"""
    ).mapping

    rule = mapping.name_rules[0]
    assert (rule.attribute, rule.words, rule.group) == ("description", ["two-handed"], "g")


def test_the_builtin_map_knows_the_families_the_properties_and_the_materials() -> None:
    mapping = load_mapping().mapping

    parents = {p for rule in mapping.name_rules for p in rule.parents}
    assert {
        "blade",
        "axe",
        "hammer",
        "bow",
        "crossbow",
        "sling",
        "silvered",
        "consumable",
    } <= parents
    assert {"dnd5e-finesse", "dnd5e-throwable", "dnd5e-two-handed", "dnd5e-versatile"} <= parents
    assert mapping.classify["weapons"]["type"]["exotic"].parents == ["dnd5e-exotic"]
    assert mapping.classify["weapons"]["list"]["firearm"].parents == ["firearm"]


def test_a_pack_entry_can_be_named_a_plain_item() -> None:
    mapping = load_mapping().mapping

    assert mapping.pack_items["alms box"] == "item"
    assert mapping.pack_items["candles"] == "gear:candle"
