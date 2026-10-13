"""The LorenzoLedger, format v1 (ADR 0191, 0226; the spec is docs/guides/inventory-file-format.md).

Pure: text or JSON in, an `Inventory` out, and back. Nothing here talks to the API. A problem stops
the import (a line that cannot be made as written); a warning does not (something was ignored).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

FORMAT = "lorenzo-ledger/1"
# The name the format had before ADR 0226: still read, and means exactly what it did.
FORMATS = (FORMAT, "lorenzo-inventory/1")
MAX_LINES = 1024
MAX_DESCRIPTION = 20_000
MAX_DEPTH = 6
MAX_QUANTITY = 1000

# Sections, by what a file may call them (compared without case and without a trailing colon).
EQUIPPED = ("equipped", "holding", "hands", "in hand", "worn")
NOT_CARRIED = ("not carried", "stored", "elsewhere", "at home", "owned")

FIELDS = ("ref", "item", "weight", "value", "kind", "note", "place")


@dataclass
class Line:
    """One thing in the file: an item, or a container when `contents` is not empty."""

    name: str
    quantity: int = 1
    ref: str | None = None
    item: str | None = None
    weight: float | None = None  # pounds, one piece
    value: str | None = None
    kind: str | None = None
    note: str | None = None
    place: str | None = None
    description: str | None = None  # LorenzoScript, from the quoted lines under the item (ADR 0226)
    contents: list[Line] = field(default_factory=list)
    number: int = 0  # the line in the file, for what is said about it; 0 when there is none

    @property
    def is_container(self) -> bool:
        return bool(self.contents)


@dataclass(frozen=True)
class Remark:
    number: int
    message: str

    def __str__(self) -> str:
        return f"line {self.number}: {self.message}" if self.number else self.message


@dataclass
class Inventory:
    owner: str | None = None
    library: str | None = None
    equipped: list[Line] = field(default_factory=list)
    not_carried: list[Line] = field(default_factory=list)
    problems: list[Remark] = field(default_factory=list)
    warnings: list[Remark] = field(default_factory=list)


def walk(lines: list[Line]) -> list[Line]:
    """Every line, a container before what is in it."""
    out: list[Line] = []
    for line in lines:
        out.append(line)
        out.extend(walk(line.contents))
    return out


def count(inventory: Inventory) -> int:
    return len(walk(inventory.equipped)) + len(walk(inventory.not_carried))


# ---- reading --------------------------------------------------------------------------------


def parse(text: str) -> Inventory:
    """A file as Markdown, or as JSON when it starts with `{`."""
    stripped = text.lstrip("﻿ \t\r\n")
    inventory = parse_json(stripped) if stripped.startswith("{") else parse_markdown(text)
    _check(inventory)
    return inventory


_QUOTE = re.compile(r"^[ \t]*>[ \t]?(?P<text>.*)$")
_ITEM = re.compile(r"^(?P<indent>[ \t]*)- (?P<rest>.*\S.*)$")
_COUNT = re.compile(r"^(?P<quantity>\d+)\s*[x×]\s+(?P<rest>.+)$")
_LINK = re.compile(r"^\[(?P<label>[^\]\n]+)\]\((?P<ref>[^)\s]+)\)$")
_HEADER = re.compile(r"^(?P<key>[A-Za-z]+):\s*(?P<value>.+?)\s*$")
_WEIGHT = re.compile(r"^(?P<number>\d+(?:[.,]\d+)?)\s*(?:lbs?\.?|pounds?)?$", re.IGNORECASE)


def _split(rest: str) -> list[str]:
    """`a | b: c`, split on a bar that is not written `\\|`."""
    parts = re.split(r"(?<!\\)\s*\|\s*", rest)
    return [part.replace("\\|", "|").strip() for part in parts]


def _section(heading: str) -> str | None:
    name = heading.strip().rstrip(":").strip().lower()
    if name in EQUIPPED:
        return "equipped"
    if name in NOT_CARRIED:
        return "not_carried"
    return None


def parse_markdown(text: str) -> Inventory:
    inventory = Inventory()
    section: str | None = None  # None before the first section; "ignored" under an unknown one
    stack: list[Line] = []  # the lines being built, one per level
    skip_below: int | None = None  # a line that did not fit: what is indented under it goes too
    last: Line | None = None  # the item a quoted line would belong to
    quoted: dict[int, list[str]] = {}  # id(line) -> its description, a row at a time
    items = 0
    seen_format = False

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.startswith("## "):
            name = _section(line[3:])
            section = name if name is not None else "ignored"
            if name is None:
                inventory.warnings.append(
                    Remark(
                        number, f"the heading “{line[3:].strip()}” is ignored, and what is under it"
                    )
                )
            stack, skip_below, last = [], None, None
            continue
        quote = _QUOTE.match(line)
        if quote is not None:
            if section in (None, "ignored"):
                continue
            if last is None:
                inventory.warnings.append(
                    Remark(number, "a quoted line with no item above it in this section is ignored")
                )
                continue
            quoted.setdefault(id(last), []).append(quote["text"].rstrip())
            continue
        match = _ITEM.match(line)
        if match is None:
            if section is None:
                header = _HEADER.match(line)
                if header is not None:
                    key = header["key"].lower()
                    seen_format = seen_format or key == "format"
                    _header(inventory, number, key, header["value"])
            continue
        if section == "ignored":
            continue
        if section is None:
            inventory.problems.append(Remark(number, "an item before the first section"))
            continue
        indent = len(match["indent"])
        if "\t" in match["indent"] or indent % 2:
            inventory.problems.append(Remark(number, "indent with two spaces for each level"))
            continue
        level = indent // 2
        items += 1
        if items > MAX_LINES:
            if items == MAX_LINES + 1:
                inventory.problems.append(Remark(number, f"a file holds at most {MAX_LINES} lines"))
            continue
        if skip_below is not None and level > skip_below:
            last = None
            continue
        skip_below = None
        if level >= MAX_DEPTH:
            inventory.problems.append(
                Remark(number, f"containers go {MAX_DEPTH} levels deep, no more")
            )
            skip_below, last = level - 1, None
            continue
        if level > len(stack):
            inventory.problems.append(Remark(number, "indented one level too far"))
            skip_below, last = level - 1, None
            continue
        parsed = _line(inventory, number, match["rest"])
        if parsed is None:
            skip_below, last = level, None
            continue
        last = parsed
        del stack[level:]
        if level == 0:
            getattr(inventory, section).append(parsed)
        else:
            stack[level - 1].contents.append(parsed)
        stack.append(parsed)
    for item in walk(inventory.equipped) + walk(inventory.not_carried):
        if (rows := quoted.get(id(item))) is not None:
            item.description = "\n".join(rows).strip("\n") or None
    if not seen_format:
        inventory.problems.append(Remark(0, f"the file needs a “format: {FORMAT}” line first"))
    return inventory


def _header(inventory: Inventory, number: int, key: str, value: str) -> None:
    if key == "format":
        if value not in FORMATS:
            inventory.problems.append(Remark(number, f"this is “{value}”, and this reads {FORMAT}"))
    elif key == "owner":
        inventory.owner = value
    elif key == "library":
        inventory.library = value


def _line(inventory: Inventory, number: int, rest: str) -> Line | None:
    parts = _split(rest)
    main, fields = parts[0], parts[1:]
    quantity = 1
    counted = _COUNT.match(main)
    if counted is not None:
        quantity, main = int(counted["quantity"]), counted["rest"].strip()
    ref: str | None = None
    linked = _LINK.match(main)
    if linked is not None:
        main, ref = linked["label"].strip(), linked["ref"]
    if not main:
        inventory.problems.append(Remark(number, "an item with no name"))
        return None
    line = Line(name=main, quantity=quantity, ref=ref, number=number)
    for chunk in fields:
        key, colon, value = chunk.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not colon or key not in FIELDS:
            inventory.warnings.append(
                Remark(number, f"“{chunk}” is not a field this version knows, and is ignored")
            )
            continue
        if not value:
            continue
        if key == "weight":
            weight = _WEIGHT.match(value)
            if weight is None:
                inventory.warnings.append(
                    Remark(
                        number, f"the weight “{value}” is not a number of pounds, and is ignored"
                    )
                )
            else:
                line.weight = float(weight["number"].replace(",", "."))
        else:
            setattr(line, key, value)
    return line


def parse_json(text: str) -> Inventory:
    inventory = Inventory()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        inventory.problems.append(Remark(0, f"not JSON: {exc}"))
        return inventory
    if not isinstance(data, dict):
        inventory.problems.append(Remark(0, "a JSON inventory is an object"))
        return inventory
    if data.get("format") not in FORMATS:
        inventory.problems.append(
            Remark(0, f"this is “{data.get('format')}”, and this reads {FORMAT}")
        )
        return inventory
    for key in ("owner", "library"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            setattr(inventory, key, value.strip())
    for section in ("equipped", "not_carried"):
        entries = data.get(section, [])
        if not isinstance(entries, list):
            inventory.problems.append(Remark(0, f"“{section}” is a list"))
            continue
        setattr(
            inventory,
            section,
            [line for e in entries if (line := _json_line(inventory, e, section, 0)) is not None],
        )
    return inventory


def _json_line(inventory: Inventory, entry: Any, where: str, depth: int) -> Line | None:
    if (
        not isinstance(entry, dict)
        or not isinstance(entry.get("name"), str)
        or not entry["name"].strip()
    ):
        inventory.problems.append(Remark(0, f"an item in “{where}” with no name"))
        return None
    if depth >= MAX_DEPTH:
        inventory.problems.append(Remark(0, f"containers go {MAX_DEPTH} levels deep, no more"))
        return None
    quantity = entry.get("quantity", 1)
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        inventory.problems.append(Remark(0, f"“{entry['name']}”: quantity is a whole number"))
        quantity = 1
    line = Line(name=entry["name"].strip(), quantity=quantity)
    for key in ("ref", "item", "value", "kind", "note", "place", "description"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            setattr(line, key, value.strip())
    weight = entry.get("weight")
    if isinstance(weight, int | float) and not isinstance(weight, bool):
        line.weight = float(weight)
    elif isinstance(weight, str) and (m := _WEIGHT.match(weight.strip())):
        line.weight = float(m["number"].replace(",", "."))
    elif weight is not None:
        inventory.warnings.append(Remark(0, f"“{line.name}”: the weight is not a number of pounds"))
    contents = entry.get("contents", [])
    if isinstance(contents, list):
        line.contents = [
            child
            for e in contents
            if (child := _json_line(inventory, e, line.name, depth + 1)) is not None
        ]
    for key in entry:
        if key not in (*FIELDS, "description", "name", "quantity", "contents"):
            inventory.warnings.append(
                Remark(0, f"“{line.name}”: “{key}” is not known, and is ignored")
            )
    return line


def _check(inventory: Inventory) -> None:
    """What the structure demands, once the file is read (the guide's rules)."""
    total = count(inventory)
    if total > MAX_LINES and not any("at most" in p.message for p in inventory.problems):
        inventory.problems.append(Remark(0, f"a file holds at most {MAX_LINES} lines"))
    for top in (inventory.equipped, inventory.not_carried):
        for line in top:
            if line.quantity > 1 and not line.is_container:
                inventory.problems.append(
                    Remark(
                        line.number,
                        f"{line.quantity} x {line.name}: a stack needs a container, "
                        "so put it inside one",
                    )
                )
    for line in walk(inventory.equipped) + walk(inventory.not_carried):
        if line.description is not None and len(line.description) > MAX_DESCRIPTION:
            inventory.problems.append(
                Remark(
                    line.number,
                    f"{line.name}: a description is at most {MAX_DESCRIPTION:,} characters",
                )
            )
        if line.quantity < 1 or line.quantity > MAX_QUANTITY:
            inventory.problems.append(
                Remark(line.number, f"{line.name}: a count is from 1 to {MAX_QUANTITY}")
            )
        if line.is_container and line.quantity != 1:
            inventory.problems.append(
                Remark(
                    line.number, f"{line.name} holds things, so it is one: write it once for each"
                )
            )


# ---- writing --------------------------------------------------------------------------------


def _text(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def _weight(weight: float) -> str:
    return f"{weight:g}"


def render_line(line: Line, depth: int = 0) -> list[str]:
    head = f"{line.quantity} x " if line.quantity != 1 else ""
    parts = [f"{head}{_text(line.name)}"]
    for key in FIELDS:
        value = getattr(line, key)
        if value is None:
            continue
        parts.append(f"{key}: {_weight(value) if key == 'weight' else _text(value)}")
    rows = ["  " * depth + "- " + " | ".join(parts)]
    if line.description is not None:
        pad = "  " * (depth + 1)
        rows.extend(f"{pad}> {row}".rstrip() for row in line.description.split("\n"))
    for child in line.contents:
        rows.extend(render_line(child, depth + 1))
    return rows


def render_markdown(inventory: Inventory) -> str:
    rows = [f"format: {FORMAT}"]
    if inventory.owner:
        rows.append(f"owner: {_text(inventory.owner)}")
    if inventory.library:
        rows.append(f"library: {_text(inventory.library)}")
    for heading, lines in (
        ("Equipped", inventory.equipped),
        ("Not carried", inventory.not_carried),
    ):
        rows += ["", f"## {heading}"]
        for line in lines:
            rows.extend(render_line(line))
    return "\n".join(rows) + "\n"


def _json_form(line: Line) -> dict[str, Any]:
    out: dict[str, Any] = {"name": line.name}
    if line.quantity != 1:
        out["quantity"] = line.quantity
    for key in FIELDS:
        value = getattr(line, key)
        if value is not None:
            out[key] = value
    if line.description is not None:
        out["description"] = line.description
    if line.contents:
        out["contents"] = [_json_form(child) for child in line.contents]
    return out


def render_json(inventory: Inventory) -> str:
    document: dict[str, Any] = {"format": FORMAT}
    if inventory.owner:
        document["owner"] = inventory.owner
    if inventory.library:
        document["library"] = inventory.library
    document["equipped"] = [_json_form(line) for line in inventory.equipped]
    document["not_carried"] = [_json_form(line) for line in inventory.not_carried]
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
