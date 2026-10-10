"""Writing a LorenzoLedger (format v1, ADR 0191, 0226; docs/guides/inventory-file-format.md).

Only what a converter needs: a tree of lines under two sections, written as the format says. The
reader, and every rule about what a line means, is `lorenzo inventory import`'s (apps/cli); a test
there parses the golden files kept with this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FORMAT = "lorenzo-ledger/1"
# The importer's limits (ADR 0191): a converter says so before the importer has to refuse.
MAX_LINES = 1024
MAX_DEPTH = 6
MAX_QUANTITY = 1000


@dataclass
class Line:
    """One thing; a container when `contents` is not empty."""

    name: str
    quantity: int = 1
    weight: float | None = None  # pounds, one piece
    value: str | None = None
    kind: str | None = None
    note: str | None = None  # one line
    place: str | None = None
    description: str | None = None  # several lines, written as a quoted block
    contents: list[Line] = field(default_factory=list)


@dataclass
class Ledger:
    owner: str
    equipped: list[Line] = field(default_factory=list)
    not_carried: list[Line] = field(default_factory=list)


def _text(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def _weight(weight: float) -> str:
    return f"{weight:g}"


def render_line(line: Line, depth: int = 0) -> list[str]:
    head = f"{line.quantity} x " if line.quantity != 1 else ""
    parts = [f"{head}{_text(line.name)}"]
    if line.weight is not None:
        parts.append(f"weight: {_weight(line.weight)}")
    for key in ("value", "kind", "note", "place"):
        value = getattr(line, key)
        if value:
            parts.append(f"{key}: {_text(value)}")
    rows = ["  " * depth + "- " + " | ".join(parts)]
    if line.description:
        pad = "  " * (depth + 1)
        rows.extend(f"{pad}> {row}".rstrip() for row in line.description.split("\n"))
    for child in line.contents:
        rows.extend(render_line(child, depth + 1))
    return rows


def render(ledger: Ledger) -> str:
    rows = [f"format: {FORMAT}", f"owner: {_text(ledger.owner)}"]
    for heading, lines in (("Equipped", ledger.equipped), ("Not carried", ledger.not_carried)):
        rows += ["", f"## {heading}"]
        for line in lines:
            rows.extend(render_line(line))
    return "\n".join(rows) + "\n"


def count(lines: list[Line]) -> int:
    return sum(1 + count(line.contents) for line in lines)


def depth(lines: list[Line]) -> int:
    return max((1 + depth(line.contents) for line in lines), default=0)
