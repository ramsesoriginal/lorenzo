"""The inventory file, format v1 (ADR 0191), read and written without an API."""

from __future__ import annotations

import json

import pytest

from lorenzo_cli.inventory.format import (
    MAX_LINES,
    Inventory,
    Line,
    parse,
    render_json,
    render_markdown,
    walk,
)

SHORTEST = """\
format: lorenzo-inventory/1
owner: Mira

## Equipped
- Dagger
- Backpack
  - 9 x Rations
  - Waterskin | note: filled with water

## Not carried
- Chest | place: the inn at Pal Vaz
  - Spare cloak
"""


def messages(remarks: list) -> list[str]:  # type: ignore[type-arg]
    return [str(r) for r in remarks]


def test_the_shortest_useful_file() -> None:
    inventory = parse(SHORTEST)

    assert inventory.problems == [] and inventory.warnings == []
    assert inventory.owner == "Mira"
    assert [line.name for line in inventory.equipped] == ["Dagger", "Backpack"]
    backpack = inventory.equipped[1]
    assert [(c.name, c.quantity) for c in backpack.contents] == [("Rations", 9), ("Waterskin", 1)]
    assert backpack.contents[1].note == "filled with water"
    chest = inventory.not_carried[0]
    assert chest.place == "the inn at Pal Vaz" and chest.is_container
    assert [c.name for c in chest.contents] == ["Spare cloak"]


def test_aliases_name_the_two_sections_without_case() -> None:
    inventory = parse(
        "format: lorenzo-inventory/1\n\n## HOLDING\n- Sword\n\n## At home:\n- Trophy\n"
    )

    assert inventory.problems == []
    assert [line.name for line in inventory.equipped] == ["Sword"]
    assert [line.name for line in inventory.not_carried] == ["Trophy"]


def test_a_count_a_link_and_the_fields_of_a_line() -> None:
    inventory = parse(
        "format: lorenzo-inventory/1\n\n## Equipped\n- Quiver\n"
        "  - 22 × [Crossbow bolts](crossbow-bolts) | weight: 0,04 lb | value: 5 Cp | kind: ammo"
        " | note: silvered\n"
    )

    bolts = inventory.equipped[0].contents[0]
    assert inventory.problems == []
    assert (bolts.name, bolts.quantity, bolts.ref) == ("Crossbow bolts", 22, "crossbow-bolts")
    assert (bolts.weight, bolts.value, bolts.kind, bolts.note) == (0.04, "5 Cp", "ammo", "silvered")


def test_a_number_that_is_not_a_count_stays_in_the_name() -> None:
    inventory = parse(
        "format: lorenzo-inventory/1\n\n## Equipped\n- 20x20 lumberjack plot | note: 5 g per week\n"
    )

    assert [(line.name, line.quantity) for line in inventory.equipped] == [
        ("20x20 lumberjack plot", 1)
    ]


def test_an_escaped_bar_stays_in_the_text_and_unknown_fields_are_warned_about() -> None:
    inventory = parse(
        "format: lorenzo-inventory/1\n\n## Equipped\n"
        "- Tally \\| stick | colour: red | note: a \\| b\n"
    )

    line = inventory.equipped[0]
    assert (line.name, line.note) == ("Tally | stick", "a | b")
    assert messages(inventory.warnings) == [
        "line 4: “colour: red” is not a field this version knows, and is ignored"
    ]


def test_a_weight_that_is_not_pounds_is_ignored_with_a_warning() -> None:
    inventory = parse("format: lorenzo-inventory/1\n\n## Equipped\n- Rope | weight: heavy\n")

    assert inventory.equipped[0].weight is None
    assert "not a number of pounds" in str(inventory.warnings[0])


def test_prose_and_other_headings_are_ignored_with_what_is_under_them() -> None:
    inventory = parse(
        "# Mira's things\n\nSome notes to myself.\nformat: lorenzo-inventory/1\nowner: Mira\n\n"
        "## Equipped\nCarried at all times.\n- Dagger\n\n## Spells\n- Fireball\n  - 3 x Scroll\n\n"
        "## Not carried\n- Trophy\n"
    )

    assert inventory.problems == []
    assert [line.name for line in inventory.equipped] == ["Dagger"]
    assert [line.name for line in inventory.not_carried] == ["Trophy"]
    assert messages(inventory.warnings) == [
        "line 11: the heading “Spells” is ignored, and what is under it"
    ]


def test_a_file_needs_its_format_line_and_a_known_version() -> None:
    missing = parse("## Equipped\n- Dagger\n")
    other = parse("format: lorenzo-inventory/2\n\n## Equipped\n- Dagger\n")

    assert "needs a “format: lorenzo-inventory/1” line" in str(missing.problems[0])
    assert "lorenzo-inventory/2" in str(other.problems[0])


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ("- 98 x Crossbow bolts\n", "a stack needs a container"),
        ("- 2 x Backpack\n  - Rope\n", "holds things, so it is one"),
        ("- Backpack\n   - Rope\n", "indent with two spaces"),
        ("- Backpack\n\t- Rope\n", "indent with two spaces"),
        ("- Backpack\n    - Rope\n", "indented one level too far"),
        ("- 0 x Rope\n", "a count is from 1"),
        ("- | note: nothing\n", "an item with no name"),
    ],
)
def test_what_cannot_be_made_as_written_is_a_problem(body: str, problem: str) -> None:
    inventory = parse(f"format: lorenzo-inventory/1\n\n## Equipped\n{body}")

    assert any(problem in str(p) for p in inventory.problems), inventory.problems


def test_an_item_before_the_first_section_is_a_problem() -> None:
    inventory = parse("format: lorenzo-inventory/1\n- Dagger\n")

    assert "before the first section" in str(inventory.problems[0])


def test_containers_go_six_levels_deep() -> None:
    nest = "".join("  " * level + f"- Box {level}\n" for level in range(7))

    inventory = parse(f"format: lorenzo-inventory/1\n\n## Equipped\n{nest}")

    assert [str(p) for p in inventory.problems] == ["line 10: containers go 6 levels deep, no more"]
    assert len(walk(inventory.equipped)) == 6


def test_a_line_that_does_not_fit_takes_what_is_under_it_along_but_not_its_sibling() -> None:
    inventory = parse(
        "format: lorenzo-inventory/1\n\n## Equipped\n- Bag\n      - Lost\n        - Lost too\n"
        "  - Rope\n"
    )

    assert [c.name for c in inventory.equipped[0].contents] == ["Rope"]
    assert len(inventory.problems) == 1


def test_a_file_holds_at_most_1024_lines() -> None:
    body = "".join(f"- Thing {n}\n" for n in range(MAX_LINES + 5))

    inventory = parse(f"format: lorenzo-inventory/1\n\n## Equipped\n{body}")

    assert [str(p) for p in inventory.problems] == [
        f"line {MAX_LINES + 4}: a file holds at most {MAX_LINES} lines"
    ]
    assert len(inventory.equipped) == MAX_LINES


def test_windows_line_endings_are_fine() -> None:
    inventory = parse(SHORTEST.replace("\n", "\r\n"))

    assert inventory.problems == [] and inventory.owner == "Mira"
    assert inventory.equipped[1].contents[1].note == "filled with water"


def test_what_is_rendered_parses_back_to_the_same_inventory() -> None:
    inventory = parse(SHORTEST)
    inventory.equipped[0].weight = 0.5
    inventory.equipped[0].value = "2 G"
    inventory.equipped[1].contents[0].ref = "rations"

    again = parse(render_markdown(inventory))

    assert again.problems == [] and again.warnings == []
    assert _shape(again) == _shape(inventory)


def test_the_json_form_is_the_same_inventory() -> None:
    inventory = parse(SHORTEST)

    document = json.loads(render_json(inventory))
    again = parse(render_json(inventory))

    assert document["format"] == "lorenzo-inventory/1" and document["owner"] == "Mira"
    assert document["equipped"][1]["contents"][0] == {"name": "Rations", "quantity": 9}
    assert again.problems == [] and _shape(again) == _shape(inventory)


def test_json_that_is_not_an_inventory_says_so() -> None:
    assert "not JSON" in str(parse("{nope").problems[0])
    assert "lorenzo-inventory/1" in str(parse('{"owner": "Mira"}').problems[0])
    unnamed = parse('{"format": "lorenzo-inventory/1", "equipped": [{"quantity": 2}]}')
    assert "with no name" in str(unnamed.problems[0])


def test_json_keeps_unknown_keys_out_with_a_warning() -> None:
    inventory = parse(
        '{"format": "lorenzo-inventory/1", "equipped": [{"name": "Rope", "colour": "red",'
        ' "weight": "5 lb"}]}'
    )

    assert inventory.equipped[0].weight == 5.0
    assert "“colour” is not known" in str(inventory.warnings[0])


def _shape(inventory: Inventory) -> object:
    def line(item: Line) -> object:
        return (
            item.name,
            item.quantity,
            item.ref,
            item.weight,
            item.value,
            item.kind,
            item.note,
            item.place,
            [line(child) for child in item.contents],
        )

    return (
        inventory.owner,
        [line(i) for i in inventory.equipped],
        [line(i) for i in inventory.not_carried],
    )
