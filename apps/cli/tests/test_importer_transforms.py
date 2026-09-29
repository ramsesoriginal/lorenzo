from __future__ import annotations

from typing import Any

import pytest

from lorenzo_cli.importer.mapping import Rule
from lorenzo_cli.importer.transforms import (
    Context,
    apply_rule,
    find_price,
    format_citation,
)

CURRENCIES = {"cp": 1, "sp": 10, "ep": 50, "gp": 100, "pp": 1000}


def run(transform: str, value: Any, entry: dict[str, Any] | None = None, **params: Any):
    context = Context("weapons", CURRENCIES, entry or {})
    return apply_rule(Rule(transform=transform, **params), "attr", value, context)


@pytest.mark.parametrize(
    ("text", "copper"),
    [
        ("Acid (vial) [25 gp]", 2500),
        ("Burglar's pack (16 gp)", 1600),
        ("Bullets, Violet (10) [5 sp]", 50),
        ("Lamp [2 gp 5 sp]", 250),
        ("Tools [1,500 gp]", 150_000),
        ("Feed (1 day) [5 cp]", 5),
        ("Ring [1.5 gp]", 150),
        ("Coin [3 pp]", 3000),
        ("Trinket [2 EP]", 100),
    ],
)
def test_a_price_is_read_from_the_group_that_is_made_of_known_currencies(
    text: str, copper: int
) -> None:
    assert find_price(text, CURRENCIES).copper == copper


@pytest.mark.parametrize(
    "text",
    ["Chain (10 feet)", "Arrows (20)", "Thing", "Thing [3 marks]", "Thing [a gp]", "[gp]"],
)
def test_a_string_without_a_price_in_a_known_currency_has_none(text: str) -> None:
    assert find_price(text, CURRENCIES).copper is None


def test_the_last_price_group_wins_and_sizes_do_not_count() -> None:
    price = find_price("Chain (10 feet) [5 gp]", CURRENCIES)

    assert price.copper == 500
    assert price.seen == ["(10 feet)", "[5 gp]"]


def test_a_new_currency_is_only_a_row() -> None:
    assert find_price("Thing [3 marks]", {**CURRENCIES, "mark": 250}).copper == 750


def test_name_and_price_splits_a_display_string() -> None:
    effect = run("name_and_price", "Bullets, Violet (10) [5 sp]")

    assert effect.name == "Bullets, Violet (10)"
    assert effect.stats == {"price": 50}
    assert effect.issues == []


def test_a_display_string_without_a_price_keeps_its_name_and_asks() -> None:
    effect = run("name_and_price", "Chain (10 feet) [3 marks]")

    assert effect.name == "Chain (10 feet) [3 marks]"
    assert "price" not in effect.stats
    issue = effect.issues[0]
    assert issue.kind == "price"
    assert "[3 marks]" in issue.reason and "[currencies]" in issue.suggestion


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([["SRD", 66], ["P", 149]], "SRD 66, P 149"),
        (["SRD", 204], "SRD 204"),
        ([["HB", 0]], "HB"),
        (["HB", 0], "HB"),
        ([["E", 7], ["S", 115]], "E 7, S 115"),
        ([["T:W", 4]], "T:W 4"),
    ],
)
def test_a_citation_is_book_and_page(value: Any, expected: str) -> None:
    assert format_citation(value) == expected


@pytest.mark.parametrize("value", [None, "SRD", [], [[]], [[1, 2]], 5])
def test_something_that_is_not_a_citation_is_not_one(value: Any) -> None:
    assert format_citation(value) is None


def test_the_sourcebook_transform_reports_a_source_it_cannot_read() -> None:
    assert run("sourcebook", [["SRD", 66]]).stats == {"sourcebook": "SRD 66"}
    assert run("sourcebook", "nonsense").issues[0].kind == "sourcebook"


def test_weight_is_per_unit_times_how_many_the_entry_is() -> None:
    assert run("own_weight", 0.05, {"amount": 20}).stats == {"own_weight": 1.0}
    assert run("own_weight", 3, {"amount": ""}).stats == {"own_weight": 3.0}
    assert run("own_weight", 2, {}).stats == {"own_weight": 2.0}
    assert run("own_weight", 0.2, {"amount": 50}).stats == {"own_weight": 10.0}
    assert isinstance(run("own_weight", 3).stats["own_weight"], float)


def test_a_missing_weight_is_nothing_and_a_wrong_one_is_an_issue() -> None:
    assert run("own_weight", "").stats == {}
    assert run("own_weight", "heavy").issues[0].kind == "weight"
    assert run("own_weight", -1).issues[0].kind == "weight"
    assert run("own_weight", True).issues[0].kind == "weight"


def test_damage_dice_and_type() -> None:
    assert run("damage", [1, 8, "Slashing"]).stats == {
        "damage_dice_count": 1,
        "damage_die": 8,
        "damage_type": "slashing",
    }


def test_damage_that_is_not_dice_keeps_its_type_and_says_so() -> None:
    effect = run("damage", [1, "", "fire"])

    assert effect.stats == {"damage_type": "fire"}
    assert "isn't a dice roll" in effect.notes[0]
    assert run("damage", "1d6").issues[0].kind == "damage"


@pytest.mark.parametrize(
    ("text", "parents", "stats"),
    [
        ("Melee", {"melee-weapon"}, {}),
        (
            "Melee, 20/60 ft",
            {"melee-weapon", "ranged-weapon"},
            {"range_normal": 20, "range_long": 60},
        ),
        ("150/600 ft", {"ranged-weapon"}, {"range_normal": 150, "range_long": 600}),
        ("60 ft", {"ranged-weapon"}, {"range_normal": 60}),
        ("melee", {"melee-weapon"}, {}),
        ("", set(), {}),
    ],
)
def test_range_gives_reach_and_distances(
    text: str, parents: set[str], stats: dict[str, int]
) -> None:
    effect = run("range", text)

    assert effect.parents == parents
    assert effect.stats == stats


def test_a_range_that_says_nothing_readable_is_noted() -> None:
    assert "isn't a reach or a distance" in run("range", "Special").notes[0]
    assert run("range", 5).issues[0].kind == "range"


def test_an_armour_class_that_is_a_number_is_stored_and_a_formula_is_noted() -> None:
    assert run("armor", 16).stats == {"armor": 16}
    effect = run("armor", "10+Wis")
    assert effect.stats == {}
    assert "formula" in effect.notes[0]


def test_names_are_tidied_and_an_empty_one_is_an_issue() -> None:
    assert run("name", "  Padded   armor ").name == "Padded armor"
    assert run("name", "   ").issues[0].kind == "name"
    assert run("name", None).issues[0].kind == "name"


def test_a_description_is_kept_and_an_empty_one_is_nothing() -> None:
    assert run("description", "Versatile (1d10)").description == "Versatile (1d10)"
    assert run("description", "").description is None


def test_pack_items_are_carried_for_later() -> None:
    items = [["Backpack, with:", "", 5]]

    assert run("pack_contents", items).pack_items == items
    assert run("pack_contents", "nope").pack_items == []


def test_the_typed_transforms_write_the_stat_they_are_told_to() -> None:
    assert run("int", 5, stat="hp", group="destroyable").stats == {"hp": 5}
    assert run("int", 5, stat="hp", group="destroyable").stat_types == {"hp": "int"}
    assert run("int", 5, stat="hp", group="destroyable").stat_groups == {"hp": "destroyable"}
    assert run("float", 5, stat="w").stats == {"w": 5.0}
    assert run("text", "  hi  ", stat="t").stats == {"t": "hi"}
    assert run("bool", True, stat="b").stats == {"b": True}


def test_the_typed_transforms_refuse_what_does_not_fit() -> None:
    for transform, value in (("int", 1.5), ("int", "x"), ("bool", 1), ("text", 5), ("float", "x")):
        assert run(transform, value, stat="s").issues[0].kind == "value", (transform, value)


def test_denomination_sum_reads_a_named_attribute() -> None:
    effect = run(
        "denomination_sum", None, {"cost": "3 gp 2 sp"}, **{"from": "cost", "stat": "price"}
    )

    assert effect.stats == {"price": 320}


def test_denomination_sum_is_only_an_issue_when_a_price_is_required() -> None:
    quiet = run("denomination_sum", "free", stat="price")
    strict = run("denomination_sum", "free", stat="price", required=True)

    assert quiet.issues == []
    assert strict.issues[0].kind == "price"


def test_regex_extract_reads_a_group_and_caps_its_input() -> None:
    rule = dict(pattern=r"holds (\d+) lb", group=1, stat="capacity", **{"as": "int"})

    assert run("regex_extract", "It holds 30 lb.", **rule).stats == {"capacity": 30}
    assert run("regex_extract", "nothing", **rule).stats == {}
    assert run("regex_extract", "x" * 300 + " holds 30 lb", **rule).stats == {}  # past the cap
    assert run("regex_extract", 5, **rule).stats == {}


def test_regex_extract_can_read_a_float_or_text() -> None:
    assert run(
        "regex_extract", "w 1.5", pattern=r"w ([\d.]+)", stat="s", **{"as": "float"}
    ).stats == {"s": 1.5}
    assert run("regex_extract", "w abc", pattern=r"w (\w+)", stat="s").stats == {"s": "abc"}
    assert (
        run("regex_extract", "w x", pattern=r"w (\w+)", stat="s", **{"as": "int"}).issues[0].kind
        == "value"
    )


def test_keyword_flag_sets_a_tag_when_a_word_is_there() -> None:
    hit = run("keyword_flag", "Finesse, Light", stat="finesse", keywords=["finesse"])
    miss = run("keyword_flag", "Heavy", stat="finesse", keywords=["finesse"])

    assert hit.stats == {"finesse": True} and hit.stat_types == {"finesse": "bool"}
    assert miss.stats == {}


def test_first_of_takes_the_first_attribute_that_has_a_value() -> None:
    entry = {"a": "", "b": 7, "c": 9}

    assert run("first_of", None, entry, of=["a", "b", "c"], stat="s", **{"as": "int"}).stats == {
        "s": 7
    }
    assert run("first_of", None, entry, of=["a"], stat="s").stats == {}
    assert (
        run("first_of", None, {"b": "x"}, of=["b"], stat="s", **{"as": "int"}).issues[0].kind
        == "value"
    )


def test_drop_and_classify_have_no_effect_of_their_own() -> None:
    for transform in ("drop", "classify"):
        effect = run(transform, "anything")
        assert (effect.stats, effect.parents, effect.issues, effect.name) == ({}, set(), [], None)
