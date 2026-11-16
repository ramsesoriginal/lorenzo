"""ADR 0462: the dice notation and its canonical form, with nothing but the parser; the value in
the release document (format 46), and what an older document says of it.
"""

import itertools
import time
import uuid
from fractions import Fraction

import pytest
from _content_compare import differences
from _content_fixtures import full_content

from lorenzo_api import dice
from lorenzo_api import release_document as rd
from lorenzo_api.models import StatValueType
from lorenzo_api.repository_content import Content, Formula, StatValue


@pytest.mark.parametrize(
    ("written", "canonical", "parts"),
    [
        ("d20", "d20", (1, 20, None, None)),
        ("W20", "d20", (1, 20, None, None)),
        ("1d20", "d20", (1, 20, None, None)),
        ("2d6", "2d6", (2, 6, None, None)),
        ("2W6", "2d6", (2, 6, None, None)),
        ("  2w6  ", "2d6", (2, 6, None, None)),
        ("4d6d1", "4d6dl1", (4, 6, "lowest", 1)),
        ("4d6dl1", "4d6dl1", (4, 6, "lowest", 1)),
        ("4W6DL1", "4d6dl1", (4, 6, "lowest", 1)),
        ("4d6dh1", "4d6dh1", (4, 6, "highest", 1)),
        ("4W6DH1", "4d6dh1", (4, 6, "highest", 1)),
        ("100d1000d99", "100d1000dl99", (100, 1000, "lowest", 99)),
        ("2d2", "2d2", (2, 2, None, None)),
    ],
)
def test_every_accepted_form_reads_back_in_the_canonical_one(
    written: str, canonical: str, parts: tuple[int, int, str | None, int | None]
) -> None:
    value = dice.parse(written)
    assert value.notation == canonical
    assert (value.count, value.sides, value.drop_mode, value.drop_count) == parts
    # The canonical form is its own reading.
    assert dice.parse(canonical) == value


@pytest.mark.parametrize(
    ("written", "part"),
    [
        ("", "notation"),
        ("2", "notation"),
        ("6d", "notation"),
        ("2x6", "notation"),
        ("2d6+3", "notation"),
        ("2d6 + 1d4", "notation"),
        ("d%", "notation"),
        ("2d6kh1", "notation"),
        ("4d6wl1", "notation"),
        ("4d6dx1", "notation"),
        ("4d6dl", "notation"),
        ("-2d6", "notation"),
        ("0d6", "count"),
        ("101d6", "count"),
        ("2d1", "sides"),
        ("2d0", "sides"),
        ("2d1001", "sides"),
        ("4d6dl0", "drop"),
        ("4d6dl4", "drop"),
        ("1d6dl1", "drop"),
        ("4d6dh9", "drop"),
    ],
)
def test_what_is_not_dice_names_the_part_that_failed(written: str, part: str) -> None:
    with pytest.raises(dice.InvalidDice) as raised:
        dice.parse(written)
    assert raised.value.part == part


def test_parts_are_held_to_the_same_limits_and_a_drop_names_its_mode() -> None:
    assert dice.from_parts(4, 6, "highest", 2).notation == "4d6dh2"
    for args, part in [
        ((0, 6), "count"),
        ((True, 6), "count"),
        ((2.0, 6), "count"),
        ((2, "6"), "sides"),
        ((2, 1001), "sides"),
        ((4, 6, "middle", 1), "drop"),
        ((4, 6, "lowest", None), "drop"),
        ((4, 6, None, 1), "drop"),
        ((4, 6, "lowest", 4), "drop"),
        ((4, 6, "lowest", True), "drop"),
    ]:
        with pytest.raises(dice.InvalidDice) as raised:
            dice.from_parts(*args)
        assert raised.value.part == part, args


def test_the_parts_are_what_the_api_shows() -> None:
    assert dice.parse("4W6DL1").parts() == {
        "count": 4,
        "sides": 6,
        "drop": {"mode": "lowest", "count": 1},
    }
    assert dice.parse("d20").parts() == {"count": 1, "sides": 20, "drop": None}
    assert dice.columns(dice.parse("4d6dh1")) == {
        "dice_count": 4,
        "dice_sides": 6,
        "dice_drop_mode": "highest",
        "dice_drop_count": 1,
    }
    assert set(dice.columns(None).values()) == {None}


def _with_dice() -> tuple[Content, uuid.UUID, uuid.UUID]:
    """The fixture's content and a dice stat held by one of its entries (4d6, lowest dropped)."""
    content = full_content()
    holder = next(iter(content.stats))[0]
    definition = uuid.UUID(int=900)
    content.definitions[definition] = {
        **next(iter(content.definitions.values())),
        "name": "Hit dice",
        "value_type": StatValueType.DICE,
    }
    content.stats[(holder, definition)] = StatValue(None, None, None, None, 4, 6, "lowest", 1)
    return content, holder, definition


def test_a_dice_value_is_written_as_its_parts_and_reads_back_exactly() -> None:
    content, holder, definition = _with_dice()
    document, files = rd.encode(content)
    held = {(a, b): v for a, b, v in document["stats"]}
    assert held[(str(holder), str(definition))]["dice_count"] == 4
    back = rd.decode(rd.loads(rd.dumps(document)), files)
    assert differences(content, back) == []
    assert back.stats[(holder, definition)].as_json() == "4d6dl1"


def test_a_document_of_format_45_has_no_dice_and_reads_with_none() -> None:
    content, _, _ = _with_dice()
    document, files = rd.encode(content)
    assert rd.FORMAT == 48

    old = dict(document)
    old["definitions"] = {
        key: definition
        for key, definition in document["definitions"].items()
        if definition["value_type"] != "dice"
    }
    old["stats"] = [
        [a, b, {k: v for k, v in value.items() if not k.startswith("dice_")}]
        for a, b, value in document["stats"]
        if not value.get("dice_count")
    ]
    back = rd.decode(old, files, format=45)
    assert all(value.dice_count is None for value in back.stats.values())
    assert back.stats  # the other stats are read as they were


def test_the_minimum_the_maximum_and_the_exact_average_of_the_rfcs_table() -> None:
    assert (dice.parse("d20").minimum, dice.parse("d20").maximum) == (1, 20)
    assert dice.parse("d20").average == Fraction(21, 2)
    assert (dice.parse("2d6").minimum, dice.parse("2d6").maximum) == (2, 12)
    assert dice.parse("2d6").average == 7
    drop = dice.parse("4d6dl1")
    assert (drop.minimum, drop.maximum) == (3, 18)
    assert drop.average == Fraction(15869, 1296)
    assert float(drop.average) == pytest.approx(12.2446, abs=1e-4)
    assert (dice.parse("4d6dh1").minimum, dice.parse("4d6dh1").maximum) == (3, 18)
    assert dice.parse("100d1000dl99").minimum == 1


@pytest.mark.parametrize(
    "written",
    ["3d4dl1", "3d4dh1", "4d3dl2", "4d3dh2", "5d2dl3", "5d2dh4", "2d5dl1", "3d6dh2", "4d6dl3"],
)
def test_the_average_of_a_drop_is_what_counting_every_roll_says(written: str) -> None:
    value = dice.parse(written)
    total = Fraction(0)
    rolls = list(itertools.product(range(1, value.sides + 1), repeat=value.count))
    for roll in rolls:
        ordered = sorted(roll)
        drop = value.drop_count or 0
        total += sum(ordered[drop:] if value.drop_mode == "lowest" else ordered[:-drop])
    assert value.average == total / len(rolls)


def test_the_average_of_a_large_drop_is_exact_and_cheap() -> None:
    started = time.perf_counter()
    value = dice.parse("100d1000dl50")
    exact = value.average
    assert time.perf_counter() - started < 5
    # Cached by value: the same dice are the same fraction, found again at no cost.
    assert dice.parse("100W1000DL50").average is exact
    assert value.minimum < float(exact) < value.maximum


def test_a_dice_value_formula_round_trips_and_a_document_of_format_46_has_none() -> None:
    content, holder, dice_stat = _with_dice()
    reading = uuid.UUID(int=901)
    content.definitions[reading] = {
        **next(iter(content.definitions.values())),
        "name": "Most damage",
        "value_type": StatValueType.INT,
    }
    content.formulas[(holder, reading)] = Formula(
        kind="dice_value", source=dice_stat, read_as="average", round_mode="ceil"
    )
    document, files = rd.encode(content)
    assert rd.FORMAT == 48
    back = rd.decode(rd.loads(rd.dumps(document)), files)
    assert differences(content, back) == []
    assert back.formulas[(holder, reading)].read_as == "average"
    assert back.formulas[(holder, reading)].inputs() == [dice_stat]

    # A document of format 46 has no `read_as` in any formula, and reads as holding none.
    old = dict(document)
    old["formulas"] = [
        [a, b, {k: v for k, v in record.items() if k != "read_as"}]
        for a, b, record in document["formulas"]
        if record["kind"] != "dice_value"
    ]
    again = rd.decode(old, files, format=46)
    assert again.formulas and all(f.read_as is None for f in again.formulas.values())


@pytest.mark.parametrize(
    "written", ["0" * 5000, "2d" + "6" * 5000, "d" + "0" * 40, "2d6dl" + "1" * 6, "9" * 6 + "d6"]
)
def test_a_long_or_odd_input_is_refused_at_once(written: str) -> None:
    started = time.perf_counter()
    with pytest.raises(dice.InvalidDice):
        dice.parse(written)
    assert time.perf_counter() - started < 0.5


def test_a_dice_formula_round_trips_and_a_document_of_format_47_has_none() -> None:
    content, holder, dice_stat = _with_dice()
    count = uuid.UUID(int=902)
    for key, name in ((count, "Level"), (uuid.UUID(int=903), "Bite")):
        content.definitions[key] = {
            **next(iter(content.definitions.values())),
            "name": name,
            "value_type": StatValueType.INT if key == count else StatValueType.DICE,
        }
    bite = uuid.UUID(int=903)
    content.formulas[(holder, bite)] = Formula(kind="dice", count=count, sides_constant=8)
    document, files = rd.encode(content)
    back = rd.decode(rd.loads(rd.dumps(document)), files)
    assert differences(content, back) == []
    built = back.formulas[(holder, bite)]
    assert (built.count, built.count_constant, built.sides, built.sides_constant) == (
        count,
        None,
        None,
        8,
    )
    assert built.inputs() == [count]

    # A document of format 47 has none of the four in any formula, and reads as holding none.
    old = dict(document)
    old["formulas"] = [
        [
            a,
            b,
            {
                k: v
                for k, v in record.items()
                if k not in ("count", "count_constant", "sides", "sides_constant")
            },
        ]
        for a, b, record in document["formulas"]
        if record["kind"] != "dice"
    ]
    again = rd.decode(old, files, format=47)
    assert all(
        (f.count, f.count_constant, f.sides, f.sides_constant) == (None,) * 4
        for f in again.formulas.values()
    )
