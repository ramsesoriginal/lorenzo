"""ADR 0462: the dice notation and its canonical form, with nothing but the parser; the value in
the release document (format 46), and what an older document says of it.
"""

import time
import uuid

import pytest
from _content_compare import differences
from _content_fixtures import full_content

from lorenzo_api import dice
from lorenzo_api import release_document as rd
from lorenzo_api.models import StatValueType
from lorenzo_api.repository_content import Content, StatValue


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
    assert rd.FORMAT == 46

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


@pytest.mark.parametrize(
    "written", ["0" * 5000, "2d" + "6" * 5000, "d" + "0" * 40, "2d6dl" + "1" * 6, "9" * 6 + "d6"]
)
def test_a_long_or_odd_input_is_refused_at_once(written: str) -> None:
    started = time.perf_counter()
    with pytest.raises(dice.InvalidDice):
        dice.parse(written)
    assert time.perf_counter() - started < 0.5
