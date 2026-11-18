"""Formulas as a document writes them (ADR 0500): stats by name, the API's fields otherwise, every
kind checked against the API's own model before anything is sent."""

from __future__ import annotations

import uuid

import pytest

from lorenzo_cli.library.formulas import (
    FormulaError,
    body,
    canonical,
    check,
    from_api,
    stats_named,
    to_api,
)

IDS = {name: uuid.uuid5(uuid.NAMESPACE_DNS, name) for name in ("a", "b", "c", "level", "size")}
NAMES = {v: k for k, v in IDS.items()}

EVERY_KIND = [
    ("linear", {"source": "a", "multiplier": 0.5, "offset": -5, "round": "floor"}),
    ("comparison", {"left": "a", "comparator": "ge", "right_constant": 10, "true_value": "yes"}),
    ("sum", {"terms": ["a", {"stat": "b", "coefficient": 2}], "offset": 1}),
    ("contents", {"source": "a", "aggregate": "max", "only_active": True}),
    ("min", {"inputs": ["a", 2]}),
    ("max", {"inputs": ["a", "b", 0]}),
    ("product", {"factors": ["a", "b"], "multiplier": 2}),
    ("ratio", {"numerator": "a", "denominator_constant": 2, "round": "ceil"}),
    (
        "select",
        {
            "source": "level",
            "mode": "threshold",
            "steps": [{"from": 1, "result": {"number": 2}}, {"from": 5, "result": {"number": 3}}],
        },
    ),
    ("dice_value", {"source": "a", "as": "average", "round": "floor"}),
    ("dice", {"count": "level", "sides_constant": 6}),
]


@pytest.mark.parametrize(("kind", "fields"), EVERY_KIND, ids=[k for k, _ in EVERY_KIND])
def test_every_kind_goes_to_the_api_and_back_unchanged(kind: str, fields: dict) -> None:
    check(kind, fields)
    sent = body(kind, fields, IDS.__getitem__).model_dump(
        mode="json", by_alias=True, warnings=False
    )
    assert sent["kind"] == kind
    assert all(name not in str(sent) for name in ("'a'", "'b'"))  # ids, not names, are sent
    back = from_api({k: v for k, v in sent.items() if k != "kind"}, NAMES.__getitem__)
    assert canonical(kind, back) == canonical(kind, fields)


def test_a_decimal_the_api_writes_as_text_reads_back_as_a_number() -> None:
    api = {"source_stat_definition_id": str(IDS["a"]), "multiplier": "0.5", "offset": "0"}
    assert from_api(api, NAMES.__getitem__) == {"source": "a", "multiplier": 0.5}


@pytest.mark.parametrize(
    ("kind", "fields", "said"),
    [
        ("min", {"inputs": ["a"]}, "inputs"),
        ("max", {"inputs": ["a", "b", "c", "a", "b", "c"]}, "inputs"),
        ("product", {"factors": ["a"]}, "factors"),
        ("sum", {"terms": []}, "terms"),
        ("select", {"source": "a", "mode": "threshold", "steps": []}, "steps"),
        ("linear", {"multiplier": 2}, "source"),
        ("comparison", {"left": "a", "comparator": "about"}, "comparator"),
        ("cube", {}, "No formula kind"),
    ],
)
def test_a_limit_is_said_before_the_api_says_it(kind: str, fields: dict, said: str) -> None:
    with pytest.raises(FormulaError) as raised:
        check(kind, fields)
    assert said in str(raised.value)


def test_the_stats_a_formula_reads_are_named_once_in_order() -> None:
    fields = {"terms": ["a", {"stat": "b", "coefficient": 2}, "a"], "offset": 1}
    assert stats_named(fields) == ["a", "b"]
    assert stats_named(dict(EVERY_KIND[8][1])) == ["level"]


def test_to_api_names_every_stat_field_by_id() -> None:
    sent = to_api({"left": "a", "right": "b", "comparator": "lt"}, IDS.__getitem__)
    assert sent == {
        "left_stat_definition_id": str(IDS["a"]),
        "right_stat_definition_id": str(IDS["b"]),
        "comparator": "lt",
    }


def test_a_required_field_is_kept_even_at_its_usual_default() -> None:
    api = {"source_stat_definition_id": str(IDS["a"]), "multiplier": "1", "offset": "-1"}
    back = from_api(api, NAMES.__getitem__, "linear")
    assert back == {
        "source": "a",
        "multiplier": 1,
        "offset": -1,
    }  # linear has no default multiplier
    check("linear", back)
    product = {"factors": [str(IDS["a"]), str(IDS["b"])], "multiplier": "1"}
    assert "multiplier" not in from_api(product, NAMES.__getitem__, "product")  # product has one
