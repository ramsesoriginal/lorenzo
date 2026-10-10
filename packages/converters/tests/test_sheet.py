from __future__ import annotations

import itertools
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lorenzo_converters import ledger
from lorenzo_converters.cli import app
from lorenzo_converters.sheet import ConversionError, Table, _tables, convert

GOLDEN = Path(__file__).parent / "golden"


def test_the_sheet_becomes_the_ledger_in_the_golden_file(make_book: Callable[..., Path]) -> None:
    result = convert(make_book(), "Mira")

    assert ledger.render(result.ledger) == (GOLDEN / "sheet-de.ledger").read_text("utf-8")


def test_holding_is_equipped_and_a_row_without_a_container_is_not_carried(
    make_book: Callable[..., Path],
) -> None:
    result = convert(make_book(), "Mira")

    assert [line.name for line in result.ledger.equipped] == [
        "Dolch",
        "Köcher",
        "Rucksack",
        "Schleuder",
    ]
    assert "Glücksbringer" in [line.name for line in result.ledger.not_carried]


def test_a_container_spelled_two_ways_is_one_and_the_bag_in_the_bag_nests(
    make_book: Callable[..., Path],
) -> None:
    result = convert(make_book(), "Mira")
    rucksack = next(line for line in result.ledger.equipped if line.name == "Rucksack")

    assert [line.name for line in rucksack.contents] == [
        "Seil 50 ft",
        "Zunderkasten",
        "Tragetasche",
    ]
    assert [line.name for line in rucksack.contents[2].contents] == ["Edelsteine", "Brief"]


def test_a_container_kept_elsewhere_is_in_not_carried_with_its_place(
    make_book: Callable[..., Path],
) -> None:
    result = convert(make_book(), "Mira")
    kiste = next(line for line in result.ledger.not_carried if line.name == "Kiste")

    assert kiste.place == "Hafenstadt"
    assert [line.name for line in kiste.contents] == ["Ersatzumhang"]
    assert any("'Burg' is taken as where the character is" in note for note in result.notes)


def test_home_can_be_given_and_then_the_other_places_are_elsewhere(
    make_book: Callable[..., Path],
) -> None:
    result = convert(make_book(), "Mira", home="Hafenstadt")

    kinds = {line.name: line.place for line in result.ledger.not_carried}
    assert kinds["Kiste"] is None
    assert kinds["Rucksack"] == "Burg"
    assert not any("taken as where" in note for note in result.notes)


def test_what_is_odd_is_said_and_left_out(make_book: Callable[..., Path]) -> None:
    result = convert(make_book(), "Mira")
    said = "\n".join(result.warnings)

    assert "Schleuder" in said and "formula" in said
    assert "'Korb' is named as a container" in said
    zunder = next(
        line for line in result.ledger.equipped[2].contents if line.name == "Zunderkasten"
    )
    assert zunder.weight is None
    schleuder = next(line for line in result.ledger.equipped if line.name == "Schleuder")
    assert schleuder.weight is None


def test_a_note_of_several_lines_is_a_quoted_block_and_a_bar_is_escaped(
    make_book: Callable[..., Path],
) -> None:
    text = ledger.render(convert(make_book(), "Mira").ledger)

    assert "      > Zeile eins\n      > Zeile zwei\n" in text
    assert "note: mit \\| Strich" in text


def test_english_headers_and_a_semicolon_csv(tmp_path: Path) -> None:
    path = tmp_path / "things.csv"
    path.write_text(
        "Name;Count;Weight;Value;Container;Kind;Description\n"
        "Lantern;1;2,5;5 G;holding;gear;hooded\n"
        "Oil;3;1;1 Sb;Lantern;consumable;\n"
        "Cloak;1;1;;;gear;\n",
        encoding="utf-8",
    )

    text = ledger.render(convert(path, "Mira").ledger)

    assert text == (GOLDEN / "sheet-en.ledger").read_text("utf-8")


def test_a_stack_at_the_top_level_is_written_as_lines_when_few_and_warned_when_many(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stacks.csv"
    path.write_text(
        "Name,Count,Container\nDagger,3,holding\nArrows,98,\nPack,2,\nRation,4,Pack\n",
        encoding="utf-8",
    )

    result = convert(path, "Mira")
    said = "\n".join(result.warnings)

    assert [line.name for line in result.ledger.equipped] == ["Dagger"] * 3
    assert all(line.quantity == 1 for line in result.ledger.equipped)
    assert "3 x 'Dagger' is at the top level" in said and "written as 3 lines" in said
    assert "98 x 'Arrows' is at the top level" in said and "put it in a container" in said
    assert "'Pack': 2 of a thing that holds things" in said


def test_a_loop_of_containers_is_cut(tmp_path: Path) -> None:
    path = tmp_path / "loop.csv"
    path.write_text("Name,Count,Container\nA,1,B\nB,1,A\nC,1,B\n", encoding="utf-8")

    result = convert(path, "Mira")

    assert any("inside itself" in warning for warning in result.warnings)
    assert ledger.count(result.ledger.not_carried) == 3


def test_a_file_without_a_table_of_items_says_what_it_found(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    path.write_text("Foo,Bar\n1,2\n", encoding="utf-8")

    with pytest.raises(ConversionError, match="no table of items found"):
        convert(path, "Mira")


def test_other_files_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "things.docx"
    path.write_text("x")

    with pytest.raises(ConversionError, match=r"expected an \.xlsx or \.csv"):
        convert(path, "Mira")


def test_the_importers_limits_are_said_before_importing() -> None:
    result = ledger.Ledger(owner="Mira", not_carried=[ledger.Line(name="x")] * 2)

    assert ledger.count(result.not_carried) == 2


def test_a_million_blank_rows_are_not_read(tmp_path: Path) -> None:
    rows = itertools.chain([("Name", "Count"), ("Torch", 2)], itertools.repeat((None, None), 5_000))

    table = _tables(iter(rows))

    assert isinstance(table, Table)
    assert [raw[0] for _, raw in table.rows] == ["Torch"]


def test_the_command_writes_the_ledger_and_says_what_to_do_next(
    make_book: Callable[..., Path], tmp_path: Path
) -> None:
    out = tmp_path / "mira.md"

    result = CliRunner().invoke(app, ["sheet", str(make_book()), "--owner", "Mira", "-O", str(out)])

    assert result.exit_code == 0, result.output
    assert out.read_text("utf-8") == (GOLDEN / "sheet-de.ledger").read_text("utf-8")
    assert "lorenzo inventory import" in result.output


def test_the_command_prints_to_the_screen_by_default(make_book: Callable[..., Path]) -> None:
    result = CliRunner().invoke(app, ["sheet", str(make_book()), "--owner", "Mira"])

    assert result.exit_code == 0
    assert result.stdout.startswith("format: lorenzo-ledger/1\nowner: Mira\n")


def test_the_command_fails_clearly(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    path.write_text("Foo,Bar\n1,2\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["sheet", str(path), "--owner", "Mira"])

    assert result.exit_code == 1
    assert "no table of items found" in result.output
