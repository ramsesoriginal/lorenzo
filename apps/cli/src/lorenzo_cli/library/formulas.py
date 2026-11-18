"""Formulas as a person writes them (ADR 0486): the API's fields for each kind, with a stat named
instead of identified. No notation: a formula is its kind and that kind's fields (RFC 0016).

A field `<x>_stat_definition_id` is written `<x>` (`source`, `left`, `right`, `numerator`,
`denominator`, `count`, `sides`, `where`), a term's, input's or result's `stat_definition_id` is
written `stat`, `factors` are names, and `round_mode` is `round`. Every other field keeps the API's
name. A formula is checked against the API's own model of its kind before it is sent, so a limit
(two to five inputs, one to sixty-four steps, dice of 1 to 100 and sides of 2 to 1000) is said
before the API says it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

KINDS = {
    "linear": "LinearFormulaBodyInput",
    "comparison": "ComparisonFormulaBodyInput",
    "sum": "SumFormulaBodyInput",
    "contents": "ContentsFormulaBodyInput",
    "min": "MinFormulaBodyInput",
    "max": "MaxFormulaBodyInput",
    "product": "ProductFormulaBodyInput",
    "ratio": "RatioFormulaBodyInput",
    "select": "SelectFormulaBodyInput",
    "dice_value": "DiceValueFormulaBody",
    "dice": "DiceFormulaBody",
}
STAT_FIELDS = ("source", "left", "right", "numerator", "denominator", "count", "sides", "where")
# What a field holds when the document leaves it out; export leaves these out too.
DEFAULTS: dict[str, Any] = {
    "round": "none",
    "offset": 0.0,
    "multiplier": 1.0,
    "coefficient": 1.0,
    "aggregate": "sum",
    "only_active": False,
}
# The fields that hold a decimal, which the API writes as text.
NUMERIC = frozenset(
    {
        "multiplier",
        "offset",
        "coefficient",
        "constant",
        "right_constant",
        "denominator_constant",
        "if_none",
        "number",
        "from",
    }
)


class FormulaError(Exception):
    """A formula its kind does not accept; the message names the field and the limit."""


def _number(value: Any) -> Any:
    """The API writes a decimal as text (`"0.5"`); a document writes it as a number."""
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return value
        return int(number) if number.is_integer() else number
    return value


def to_api(fields: dict[str, Any], stat_id: Callable[[str], uuid.UUID]) -> dict[str, Any]:
    """A formula as the document writes it, as the API's body, with stats as ids."""
    out: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if key in STAT_FIELDS:
            out[f"{key}_stat_definition_id"] = str(stat_id(value))
        elif key == "stat":
            out["stat_definition_id"] = str(stat_id(value))
        elif key == "round":
            out["round_mode"] = value
        elif key == "factors":
            out["factors"] = [str(stat_id(name)) for name in value]
        elif key == "terms":
            out["terms"] = [
                to_api(t if isinstance(t, dict) else {"stat": t}, stat_id) for t in value
            ]
        elif key == "inputs":
            out["inputs"] = [
                to_api({"stat": i}, stat_id)
                if isinstance(i, str)
                else {"constant": i}
                if isinstance(i, int | float)
                else to_api(i, stat_id)
                for i in value
            ]
        elif key == "steps":
            out["steps"] = [to_api(step, stat_id) for step in value]
        elif key in ("result", "otherwise"):
            out[key] = to_api(value, stat_id)
        else:
            out[key] = value
    return out


def from_api(
    body: dict[str, Any], stat_name: Callable[[uuid.UUID], str], kind: str | None = None
) -> dict[str, Any]:
    """The API's formula as the document writes it: names for stats, numbers for decimals, and the
    fields that hold their default left out."""
    out: dict[str, Any] = {}
    for key, value in body.items():
        if value is None:
            continue
        if key.endswith("_stat_definition_id"):
            out[key.removesuffix("_stat_definition_id")] = stat_name(uuid.UUID(str(value)))
        elif key == "stat_definition_id":
            out["stat"] = stat_name(uuid.UUID(str(value)))
        elif key == "round_mode":
            out["round"] = value
        elif key == "factors":
            out["factors"] = [stat_name(uuid.UUID(str(v))) for v in value]
        elif key == "inputs":
            out["inputs"] = [
                stat_name(uuid.UUID(str(i["stat_definition_id"])))
                if i.get("stat_definition_id")
                else _number(i.get("constant"))
                for i in value
            ]
        elif key == "terms":
            terms = [from_api(t, stat_name) for t in value]
            out["terms"] = [t["stat"] if set(t) == {"stat"} else t for t in terms]
        elif key in ("steps",):
            out[key] = [from_api(step, stat_name) for step in value]
        elif key in ("result", "otherwise"):
            out[key] = from_api(value, stat_name)
        else:
            out[key] = _number(value) if key in NUMERIC else value
    required = _required(kind)
    return {k: v for k, v in out.items() if k in required or DEFAULTS.get(k, object()) != v}


def _required(kind: str | None) -> set[str]:
    """The fields `kind` has no default for, as a document names them: those are always written."""
    if kind is None or kind not in KINDS:
        return set()
    fields = model(kind).model_fields
    names = {"round_mode": "round"}
    return {names.get(name, name) for name, info in fields.items() if info.is_required()}


def stats_named(fields: dict[str, Any]) -> list[str]:
    """Every stat a formula reads, in the order it names them."""
    found: list[str] = []

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for item in value:
                if key in ("factors", "terms", "inputs") and isinstance(item, str):
                    found.append(item)
                else:
                    walk(item, key)
        elif isinstance(value, str) and (key in STAT_FIELDS or key == "stat"):
            found.append(value)

    walk(fields)
    return list(dict.fromkeys(found))


def model(kind: str) -> Any:
    from lorenzo_cli.client import ops

    if kind not in KINDS:
        raise FormulaError(f"No formula kind {kind}: choose from {', '.join(KINDS)}.")
    return ops.resolve(KINDS[kind])


def check(kind: str, fields: dict[str, Any]) -> None:
    """Raise FormulaError when the API's model of `kind` would refuse these fields."""
    placeholder = uuid.UUID(int=1)
    body = {**to_api(fields, lambda _: placeholder), "kind": kind}
    try:
        model(kind).model_validate(body)
    except ValidationError as exc:
        said = "; ".join(
            f"{_field(e['loc'])}: {e['msg']}"
            for e in exc.errors()
            if e["type"] != "union_tag_invalid"
        )
        raise FormulaError(f"a {kind} formula: {said}") from exc


def _field(loc: tuple[Any, ...]) -> str:
    names = []
    for part in loc:
        text = str(part)
        if text.endswith("_stat_definition_id"):
            text = text.removesuffix("_stat_definition_id")
        names.append({"stat_definition_id": "stat", "round_mode": "round"}.get(text, text))
    return ".".join(n for n in names if not n.startswith(("float", "constrained", "function")))


def body(kind: str, fields: dict[str, Any], stat_id: Callable[[str], uuid.UUID]) -> Any:
    """The request model the API takes for this formula."""
    return model(kind).model_validate({**to_api(fields, stat_id), "kind": kind})


def canonical(kind: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Two formulas are the same when their canonical forms are: defaults filled in, decimals as
    numbers, names as written."""
    names: dict[str, uuid.UUID] = {}

    def stat_id(name: str) -> uuid.UUID:
        return names.setdefault(name, uuid.UUID(int=len(names) + 2))

    dumped = (
        model(kind)
        .model_validate({**to_api(fields, stat_id), "kind": kind})
        .model_dump(mode="json", by_alias=True, warnings=False)
    )
    by_id = {str(v): k for k, v in names.items()}
    normalised: dict[str, Any] = _normalised(dumped, by_id)
    return normalised


def _normalised(value: Any, by_id: dict[str, str], key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: _normalised(v, by_id, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalised(v, by_id, key) for v in value]
    if isinstance(value, str) and value in by_id:
        return by_id[value]
    return _number(value) if key in NUMERIC else value
