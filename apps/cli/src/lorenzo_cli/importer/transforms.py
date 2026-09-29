"""The transforms an attribute rule can name (RFC 0025 R5, ADR 0144).

Each takes one attribute's value (and the entry it came from) and says what it becomes: a name,
stats, a description, extra parents, notes, or a reason it can't be decided. None of them
guesses: a value they can't read is an `Issue`, which holds the item back for review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lorenzo_cli.importer.mapping import REGEX_INPUT_CAP, Rule

StatValue = int | float | str | bool


@dataclass(frozen=True)
class Issue:
    """Something a person has to decide. `suggestion` is a ready-to-paste row for the map."""

    kind: str
    attribute: str
    value: str
    reason: str
    suggestion: str = ""


@dataclass
class Effect:
    name: str | None = None
    description: str | None = None
    stats: dict[str, StatValue] = field(default_factory=dict)
    # For a stat a rule invented (not one of the seed's): its type and, to create it, its group.
    stat_types: dict[str, str] = field(default_factory=dict)
    stat_groups: dict[str, str] = field(default_factory=dict)
    parents: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    pack_items: list[Any] | None = None


@dataclass(frozen=True)
class Context:
    list_name: str
    currencies: dict[str, int]
    entry: dict[str, Any]


def apply_rule(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    handler = _HANDLERS.get(rule.transform)
    if handler is None:  # classify is decided elsewhere, by the whole entry
        return Effect()
    return handler(rule, attribute, value, ctx)


# ---- helpers ----


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value


def _text(value: Any) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) and value.strip() else None


def _bad(effect: Effect, kind: str, attribute: str, value: Any, reason: str) -> Effect:
    effect.issues.append(Issue(kind, attribute, repr(value)[:80], reason))
    return effect


# ---- the plain transforms ----


def _drop(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    return Effect()


def _name(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    text = _text(value)
    if text is None:
        return _bad(Effect(), "name", attribute, value, "the name is empty or isn't text")
    return Effect(name=text)


def format_citation(value: Any) -> str | None:
    """`["SRD", 204]` or `[["E", 7], ["S", 115]]` (or `["HB", 0]`, homebrew) as `E 7, S 115`."""
    pairs = value if value and isinstance(value, list) and isinstance(value[0], list) else [value]
    parts: list[str] = []
    for pair in pairs:
        if not (isinstance(pair, list) and pair and isinstance(pair[0], str) and pair[0]):
            return None
        page = pair[1] if len(pair) > 1 else 0
        parts.append(pair[0] if page in (0, "", None) else f"{pair[0]} {page}")
    return ", ".join(parts) or None


def _sourcebook(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    citation = format_citation(value)
    if citation is None:
        return _bad(
            Effect(), "sourcebook", attribute, value, "the source isn't a list of [book, page]"
        )
    return Effect(stats={"sourcebook": citation})


def _description(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    text = _text(value)
    return Effect(description=text) if text else Effect()


def _own_weight(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    """The weight of one, times how many the entry is (a bundle of 20 arrows at 0.05 each)."""
    if value in ("", None):
        return Effect()
    weight = _number(value)
    if weight is None or weight < 0:
        return _bad(Effect(), "weight", attribute, value, "the weight isn't a number")
    amount = _number(ctx.entry.get("amount"))
    count = amount if amount is not None and amount > 0 else 1
    return Effect(stats={"own_weight": round(float(weight) * count, 6)})


def _damage(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    effect = Effect()
    if not (isinstance(value, list) and len(value) == 3):
        return _bad(effect, "damage", attribute, value, "damage isn't [dice, die, type]")
    dice, die, kind = value
    if _number(dice) is not None and _number(die) is not None and die > 0:
        effect.stats["damage_dice_count"] = int(dice)
        effect.stats["damage_die"] = int(die)
    else:
        effect.notes.append(f"damage {value!r} isn't a dice roll, so its amount isn't stored")
    if isinstance(kind, str) and kind.strip():
        effect.stats["damage_type"] = kind.strip().lower()
    return effect


_DISTANCE = re.compile(r"(\d+)\s*(?:/\s*(\d+))?\s*ft", re.IGNORECASE)


def _range(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    """`Melee`, `Melee, 20/60 ft`, `150/600 ft`, `60 ft`: reach and distances."""
    effect = Effect()
    if not isinstance(value, str):
        return _bad(effect, "range", attribute, value, "range isn't text")
    if re.match(r"\s*melee\b", value, re.IGNORECASE):
        effect.parents.add("melee-weapon")
    distance = _DISTANCE.search(value)
    if distance:
        effect.parents.add("ranged-weapon")
        effect.stats["range_normal"] = int(distance.group(1))
        if distance.group(2):
            effect.stats["range_long"] = int(distance.group(2))
    elif value.strip() and not effect.parents:
        effect.notes.append(f"range {value!r} isn't a reach or a distance, so it isn't stored")
    return effect


def _armor(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    number = _number(value)
    if number is not None and float(number).is_integer():
        return Effect(stats={"armor": int(number)})
    return Effect(notes=[f"armour class {value!r} is a formula, so it isn't stored as a number"])


def _pack_contents(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    return Effect(pack_items=value if isinstance(value, list) else [])


# ---- prices ----

_AMOUNT_UNIT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([A-Za-z]+)")
_GROUP = re.compile(r"\[([^\]]*)\]|\(([^)]*)\)")


@dataclass(frozen=True)
class Price:
    copper: int | None
    # The text of the group it was found in, so a name can be cleaned of it.
    span: tuple[int, int] | None
    seen: list[str]


def _unit_value(unit: str, currencies: dict[str, int]) -> int | None:
    """A currency's worth in copper; `marks` is the currency `mark` (a plural needs no row)."""
    lowered = unit.lower()
    if lowered in currencies:
        return currencies[lowered]
    if lowered.endswith("s") and lowered[:-1] in currencies:
        return currencies[lowered[:-1]]
    return None


def find_price(text: str, currencies: dict[str, int]) -> Price:
    """The price in a display string: the last bracketed or parenthesised group made entirely of
    amounts of known currencies (`[2 gp 5 sp]`, `(16 gp)`, `[1,000 gp]`). Groups that aren't
    (`(20)`, `(10 feet)`) are not prices."""
    found: Price | None = None
    seen: list[str] = []
    for match in _GROUP.finditer(text):
        inner = match.group(1) if match.group(1) is not None else match.group(2)
        seen.append(match.group(0))
        pairs = _AMOUNT_UNIT.findall(inner)
        rest = _AMOUNT_UNIT.sub("", inner).replace(",", "").strip()
        values = [_unit_value(unit, currencies) for _, unit in pairs]
        if pairs and not rest and all(v is not None for v in values):
            total = sum(
                float(amount.replace(",", "")) * (value or 0)
                for (amount, _), value in zip(pairs, values, strict=True)
            )
            found = Price(int(total + 0.5), match.span(), seen)
    return found or Price(None, None, seen)


def _price_issue(attribute: str, value: Any, price: Price) -> Issue:
    return Issue(
        "price",
        attribute,
        repr(value)[:80],
        "no price could be read from it"
        + (f" (groups seen: {', '.join(price.seen)})" if price.seen else ""),
        "if one of those is a price in another currency, add it under [currencies]",
    )


def _name_and_price(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    effect = Effect()
    text = _text(value)
    if text is None:
        return _bad(effect, "name", attribute, value, "the name is empty or isn't text")
    price = find_price(value, ctx.currencies)
    if price.copper is None or price.span is None:
        effect.name = text
        effect.issues.append(_price_issue(attribute, value, price))
        return effect
    effect.name = _text(value[: price.span[0]] + value[price.span[1] :]) or text
    effect.stats["price"] = price.copper
    return effect


# ---- the parameterised transforms ----


def _declare(effect: Effect, rule: Rule, stat: str, value_type: str) -> None:
    effect.stat_types[stat] = value_type
    group = rule.params.get("group")
    if isinstance(group, str):
        effect.stat_groups[stat] = group


def _typed(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    effect = Effect()
    stat = str(rule.params["stat"])
    kind = rule.transform
    coerced: StatValue | None
    if kind == "text":
        coerced = _text(value)
    elif kind == "bool":
        coerced = value if isinstance(value, bool) else None
    else:
        number = _number(value)
        coerced = None if number is None else (int(number) if kind == "int" else float(number))
        if kind == "int" and number is not None and not float(number).is_integer():
            coerced = None
    if coerced is None:
        return _bad(effect, "value", attribute, value, f"can't be read as {kind}")
    effect.stats[stat] = coerced
    _declare(effect, rule, stat, kind)
    return effect


def _denomination_sum(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    effect = Effect()
    source = rule.params.get("from")
    text = ctx.entry.get(str(source)) if source else value
    stat = str(rule.params["stat"])
    _declare(effect, rule, stat, "int")
    if not isinstance(text, str):
        if rule.params.get("required"):
            effect.issues.append(_price_issue(attribute, text, Price(None, None, [])))
        return effect
    # A bare cost (`cost: "3 gp 2 sp"`) has no brackets; read it as if it had.
    price = find_price(f"[{text}]", ctx.currencies)
    if price.copper is None:
        if rule.params.get("required", False):
            effect.issues.append(_price_issue(attribute, text, price))
        return effect
    effect.stats[stat] = price.copper
    return effect


def _regex_extract(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    effect = Effect()
    stat = str(rule.params["stat"])
    kind = str(rule.params.get("as", "text"))
    _declare(effect, rule, stat, kind)
    if not isinstance(value, str):
        return effect
    match = re.search(str(rule.params["pattern"]), value[:REGEX_INPUT_CAP])
    if not match:
        return effect
    raw = match.group(int(rule.params.get("group", 1)))
    try:
        effect.stats[stat] = int(raw) if kind == "int" else float(raw) if kind == "float" else raw
    except ValueError:
        return _bad(effect, "value", attribute, value, f"{raw!r} can't be read as {kind}")
    return effect


def _keyword_flag(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    effect = Effect()
    stat = str(rule.params["stat"])
    _declare(effect, rule, stat, "bool")
    if isinstance(value, str):
        lowered = value.lower()
        if any(str(keyword).lower() in lowered for keyword in rule.params["keywords"]):
            effect.stats[stat] = True
    return effect


def _first_of(rule: Rule, attribute: str, value: Any, ctx: Context) -> Effect:
    effect = Effect()
    stat = str(rule.params["stat"])
    kind = str(rule.params.get("as", "text"))
    _declare(effect, rule, stat, kind)
    for name in rule.params["of"]:
        candidate = ctx.entry.get(str(name))
        if candidate in ("", None):
            continue
        if kind in ("int", "float"):
            number = _number(candidate)
            if number is None:
                return _bad(effect, "value", str(name), candidate, f"can't be read as {kind}")
            effect.stats[stat] = int(number) if kind == "int" else float(number)
        else:
            effect.stats[stat] = str(candidate)
        break
    return effect


_HANDLERS = {
    "drop": _drop,
    "name": _name,
    "sourcebook": _sourcebook,
    "description": _description,
    "own_weight": _own_weight,
    "damage": _damage,
    "range": _range,
    "armor": _armor,
    "name_and_price": _name_and_price,
    "pack_contents": _pack_contents,
    "int": _typed,
    "float": _typed,
    "text": _typed,
    "bool": _typed,
    "denomination_sum": _denomination_sum,
    "regex_extract": _regex_extract,
    "keyword_flag": _keyword_flag,
    "first_of": _first_of,
}
