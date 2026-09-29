from __future__ import annotations

import pytest

from lorenzo_cli.importer.mapping import load_mapping
from lorenzo_cli.importer.packs import (
    NameIndex,
    PackLine,
    Ref,
    Target,
    build_contents,
    parse_description,
    parse_entries,
    render,
    resolve,
    resolve_refs,
)

MAPPING = load_mapping().mapping


def index() -> NameIndex:
    found = NameIndex()
    found.add("gear", "backpack", Target("basic-gear-backpack", "Backpack"), ["Backpack"])
    found.add(
        "gear",
        "rations (1 day)",
        Target("basic-gear-rations-1-day", "Rations (1 day)"),
        ["Rations, days of", "Rations (1 day)"],
    )
    found.add("gear", "torch", Target("basic-gear-torch", "Torch"), ["Torch"])
    found.add(
        "gear",
        "rope, hempen (50 feet)",
        Target("basic-gear-rope", "Rope, hempen (50 feet)", bundle=50),
        ["Hempen rope, feet of"],
    )
    return found


def test_a_container_entry_is_marked_and_its_name_cleaned() -> None:
    entries = parse_entries(
        [["Backpack, with:", "", 5], ["Rations, days of", 5, 2], ["Bell", "", ""]]
    )

    assert [(e.name, e.quantity, e.container) for e in entries] == [
        ("Backpack", 1, True),
        ("Rations, days of", 5, False),
        ("Bell", 1, False),
    ]


def test_entries_that_are_not_entries_are_ignored_and_a_bad_quantity_is_one() -> None:
    entries = parse_entries([["Ok", 0, 1], "junk", [], ["", 2], [5], ["Rope", True], ["Bag", 2.5]])

    assert [(e.name, e.quantity) for e in entries] == [("Ok", 1), ("Rope", 1), ("Bag", 1)]


def test_the_contents_nest_under_the_container_and_a_name_is_found_exactly() -> None:
    entries = parse_entries(
        [["Backpack, with:", "", 5], ["Rations, days of", 5, 2], ["Torch", 2, 1]]
    )

    contents = resolve(entries, index(), MAPPING)

    assert contents.lines == [
        PackLine(0, 1, "Backpack", "basic-gear-backpack"),
        PackLine(1, 5, "Rations (1 day)", "basic-gear-rations-1-day"),
        PackLine(1, 2, "Torch", "basic-gear-torch"),
    ]
    assert contents.unresolved == []


def test_entries_before_the_container_are_not_inside_it() -> None:
    entries = parse_entries([["Torch", 1, 1], ["Backpack, with:", "", 5], ["Torch", 1, 1]])

    depths = [line.depth for line in resolve(entries, index(), MAPPING).lines]

    assert depths == [0, 0, 1]


def test_a_second_container_starts_again_at_the_top() -> None:
    entries = parse_entries(
        [["Backpack, with:", "", 5], ["Torch", 1, 1], ["Backpack, with:", "", 5], ["Torch", 1, 1]]
    )

    assert [line.depth for line in resolve(entries, index(), MAPPING).lines] == [0, 1, 0, 1]


def test_a_quantity_is_converted_to_the_bundle_it_is_found_in() -> None:
    entries = parse_entries([["Hempen rope, feet of", 50, 0.2], ["Hempen rope, feet of", 100, 0.2]])

    lines = resolve(entries, index(), MAPPING).lines

    assert [line.quantity for line in lines] == [1, 2]
    assert lines[0].label == "Rope, hempen (50 feet)"  # named by the item, so the count reads right


def test_a_quantity_that_does_not_divide_is_rounded_up_and_says_so() -> None:
    entries = parse_entries([["Hempen rope, feet of", 60, 0.2]])

    contents = resolve(entries, index(), MAPPING)

    assert contents.lines[0].quantity == 2
    assert "rounded up to 2" in contents.notes[0]


def test_a_row_of_the_map_links_a_name_that_does_not_match() -> None:
    mapping = load_mapping('schema = 1\n[pack_items]\n"Fire sticks" = "gear:torch"\n').mapping

    contents = resolve(parse_entries([["Fire sticks", 3, 1]]), index(), mapping)

    assert contents.lines == [PackLine(0, 3, "Torch", "basic-gear-torch")]


def test_the_builtin_map_knows_the_srds_plurals_and_what_is_not_an_item() -> None:
    torches = NameIndex()
    torches.add("gear", "torch", Target("basic-gear-torch", "Torch"), ["Torch"])

    contents = resolve(parse_entries([["Torches", 10, 1], ["Alms box", "", ""]]), torches, MAPPING)

    assert contents.lines == [
        PackLine(0, 10, "Torch", "basic-gear-torch"),
        PackLine(0, 1, "Alms box", None),  # plain text, and nothing to report
    ]
    assert contents.unresolved == []


def test_a_name_nothing_finds_becomes_a_plain_item_and_is_reported_with_a_row() -> None:
    resolution = resolve_refs(parse_entries([["Mystery thing", 1, 1]]), index(), MAPPING)

    [placed] = resolution.placed
    assert placed.ref == Ref("item", "gear", "mystery thing")
    [missing] = resolution.unresolved
    assert missing.name == "Mystery thing"
    assert "a plain item is made for it" in missing.reason
    assert missing.suggestion.startswith('[pack_items]\n"mystery thing" = ')
    slugs = {"mystery thing": "basic-gear-mystery-thing"}
    lines = build_contents(resolution, index(), slugs).lines
    assert lines == [PackLine(0, 1, "Mystery thing", "basic-gear-mystery-thing")]


def test_a_row_pointing_somewhere_that_is_not_in_the_run_is_reported() -> None:
    mapping = load_mapping('schema = 1\n[pack_items]\n"bell" = "gear:bell"\n').mapping

    contents = resolve(parse_entries([["Bell", 1, 1]]), index(), mapping)

    assert "isn't in this run" in contents.unresolved[0].reason


def test_a_name_two_items_answer_to_is_reported_not_picked() -> None:
    both = index()
    both.add("tools", "bell", Target("basic-tools-bell", "Bell"), ["Bell"])
    both.add("gear", "bell", Target("basic-gear-bell", "Bell"), ["Bell"])

    contents = resolve(parse_entries([["Bell", 1, 1]]), both, MAPPING)

    assert "could be any of gear:bell, tools:bell" in contents.unresolved[0].reason
    # Neither is picked: the gear entry under the entry's own key is what is linked, in the open.
    assert contents.lines[0].slug == "basic-gear-bell"
    assert "the gear entry of that name is used instead" in contents.unresolved[0].reason


def test_a_name_two_items_answer_to_gets_a_plain_item_when_there_is_no_gear_entry() -> None:
    both = index()
    both.add("tools", "bell", Target("basic-tools-bell", "Bell"), ["Bell"])
    both.add("weapons", "bell", Target("basic-weapons-bell", "Bell"), ["Bell"])

    resolution = resolve_refs(parse_entries([["Bell", 1, 1]]), both, MAPPING)

    assert resolution.placed[0].ref == Ref("item", "gear", "bell")
    assert "a plain item is made instead" in resolution.unresolved[0].reason


def test_the_description_is_an_introduction_and_a_list() -> None:
    text = render(
        [
            PackLine(0, 1, "Backpack", "basic-gear-backpack"),
            PackLine(1, 5, "Rations (1 day)", "basic-gear-rations-1-day"),
            PackLine(0, 1, "Alms box", None),
        ]
    )

    assert text == (
        "This pack contains:\n\n"
        "- 1 x [Backpack](basic-gear-backpack)\n"
        "  - 5 x [Rations (1 day)](basic-gear-rations-1-day)\n"
        "- 1 x Alms box"
    )


def test_what_was_rendered_parses_back_to_the_same_lines() -> None:
    lines = [
        PackLine(0, 1, "Backpack", "basic-gear-backpack"),
        PackLine(1, 5, "Rations, days of", "basic-gear-rations-1-day"),
        PackLine(1, 2, "Torch (lit)", "basic-gear-torch"),
        PackLine(0, 3, "Alms box", None),
    ]

    assert parse_description(render(lines)) == lines


def test_prose_around_the_list_is_ignored() -> None:
    text = (
        "Bought at the market.\n\n"
        "This pack contains:\n\n"
        "- 1 x [Backpack](basic-gear-backpack)\n"
        "A GM note: swap the rope for silk.\n"
        "  - 5 x [Rations](basic-gear-rations)\n\n"
        "Keep it dry."
    )

    assert parse_description(text) == [
        PackLine(0, 1, "Backpack", "basic-gear-backpack"),
        PackLine(1, 5, "Rations", "basic-gear-rations"),
    ]


@pytest.mark.parametrize(
    "line",
    [
        "* 1 x [A](a)",  # not a dash
        "- 1 [A](a)",  # no "x"
        "-  1 x [A](a)",  # two spaces after the dash
        "- one x [A](a)",  # not a number
        "- 1 x [A](has space)",  # not a slug
        "- 1 x [A](-a)",  # not a slug
        "- 0 x [A](a)",  # nothing
        "   - 1 x [A](a)",  # odd indent
        "        - 1 x [A](a)",  # deeper than a pack goes
        "- 1 x [](a)",  # no label
        "- 1 x [A]()",  # no target
    ],
)
def test_only_a_line_of_the_exact_shape_counts(line: str) -> None:
    assert parse_description(line) == []


def test_windows_line_endings_are_fine() -> None:
    assert parse_description("- 1 x [A](a)\r\n  - 2 x [B](b)\r\n") == [
        PackLine(0, 1, "A", "a"),
        PackLine(1, 2, "B", "b"),
    ]


def test_a_row_saying_item_makes_a_plain_item_and_reports_nothing() -> None:
    resolution = resolve_refs(parse_entries([["Alms box", "", ""]]), index(), MAPPING)

    assert resolution.placed[0].ref == Ref("item", "gear", "alms box")
    assert resolution.unresolved == []


def test_a_row_saying_text_keeps_the_entry_as_plain_text() -> None:
    mapping = load_mapping('schema = 1\n[pack_items]\n"air" = "text"\n').mapping

    contents = resolve(parse_entries([["Air", 1, 1]]), index(), mapping)

    assert contents.lines == [PackLine(0, 1, "Air", None)]
    assert contents.unresolved == []


def test_an_entry_whose_key_a_gear_entry_already_has_links_that_entry() -> None:
    have = index()
    have.add("gear", "alms box", Target("basic-gear-alms-box", "Alms box"), ["Alms box (sheet)"])

    contents = resolve(parse_entries([["Alms box", 1, 1]]), have, MAPPING)

    assert contents.lines == [PackLine(0, 1, "Alms box", "basic-gear-alms-box")]


def test_the_weight_the_pack_gives_is_kept_for_the_plain_item() -> None:
    [entry] = parse_entries([["Censer", 1, 4]])

    assert entry.weight == 4.0
    assert parse_entries([["Censer", 1, ""]])[0].weight is None
    assert parse_entries([["Censer", 1, 0]])[0].weight is None


def test_plain_items_are_named_once_however_many_packs_mention_them() -> None:
    from lorenzo_cli.importer.packs import plain_key

    assert plain_key("  Alms   BOX ") == plain_key("alms box") == "alms box"
