import pytest

from lorenzo_calendar import CalendarDefinition
from lorenzo_calendar.references import parse_reference, resolve_reference

DEFINITION = CalendarDefinition(
    segments=[
        {"key": "first", "name": "März / Spring", "days": 27},
        {
            "key": "leap",
            "name": "Festival",
            "kind": "festival",
            "days": 1,
            "when": {"every": 4, "offset": 0},
        },
        {"key": "last", "name": "123", "days": 20},
    ]
)


@pytest.mark.parametrize(
    "text,key,label",
    [
        ("example -1", None, "-1"),
        ("example 3286/3/16", "last", "16 123 3286"),
        ("example 3286/name:123", "last", "123 3286"),
        ("example 3286/key:last/20", "last", "20 123 3286"),
        ("example 3286/märz %2F spring/1", "first", "1 März / Spring 3286"),
        ("example 3288/2/1", "leap", "1 Festival 3288"),
    ],
)
def test_named_numbered_and_partial_references(text, key, label):
    assert resolve_reference(DEFINITION, parse_reference(text)) == (key, label)


@pytest.mark.parametrize(
    "text",
    [
        "example",
        "example 1000001",
        "example 0/0",
        "example 3286/2",
        "example 0/3/21",
        "example 0//1",
        "example 0/1/0",
        "example 0/first/1/2",
    ],
)
def test_invalid_and_absent_dates_stay_unresolved(text):
    with pytest.raises(ValueError):
        resolve_reference(DEFINITION, parse_reference(text))


def test_ambiguous_normalized_names_need_keys():
    definition = CalendarDefinition(
        segments=[{"key": "a", "name": "Ｍoon", "days": 1}, {"key": "b", "name": "moon", "days": 1}]
    )
    with pytest.raises(ValueError):
        resolve_reference(definition, parse_reference("example 0/MOON"))
    assert resolve_reference(definition, parse_reference("example 0/key:a"))[0] == "a"
