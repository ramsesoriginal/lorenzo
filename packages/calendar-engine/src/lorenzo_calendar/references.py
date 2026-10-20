"""Read-only authored calendar coordinates; no clock or period materialization."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote

from pydantic import Field

from lorenzo_calendar import CalendarDefinition, Value, Year


class CalendarReference(Value):
    calendar: str = Field(min_length=1, max_length=200)
    year: Year
    segment: str | None = None
    day: int | None = None


def parse_reference(expression: str) -> CalendarReference:
    parts = expression.strip().split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Use calendar-link-name year[/month[/day]]")
    coordinates = parts[1].split("/")
    if not 1 <= len(coordinates) <= 3 or not re.fullmatch(r"-?[0-9]{1,7}", coordinates[0]):
        raise ValueError("Invalid calendar coordinates")
    segment = unquote(coordinates[1]) if len(coordinates) > 1 else None
    day = None
    if len(coordinates) == 3:
        if not re.fullmatch(r"[0-9]{1,4}", coordinates[2]):
            raise ValueError("Invalid day")
        day = int(coordinates[2])
    if segment == "":
        raise ValueError("Empty month")
    return CalendarReference(calendar=parts[0], year=int(coordinates[0]), segment=segment, day=day)


def resolve_reference(
    definition: CalendarDefinition, reference: CalendarReference
) -> tuple[str | None, str]:
    """Return a stable segment key and readable date; ambiguous names stay unresolved."""
    value = reference.segment
    if value is None:
        return None, str(reference.year)

    def normalize(name: str) -> str:
        return unicodedata.normalize("NFKC", name).casefold()

    if value.isascii() and value.isdecimal():
        ordinal = int(value)
        matches = list(definition.segments[ordinal - 1 : ordinal]) if ordinal > 0 else []
    elif value.startswith("key:"):
        matches = [s for s in definition.segments if s.key == value[4:]]
    elif value.startswith("name:"):
        matches = [s for s in definition.segments if normalize(s.name) == normalize(value[5:])]
    else:
        matches = [
            s
            for s in definition.segments
            if s.key == value or normalize(s.name) == normalize(value)
        ]
    if len(matches) != 1 or not matches[0].includes(reference.year):
        raise ValueError("Unknown or ambiguous month")
    segment = matches[0]
    if reference.day is not None and not 1 <= reference.day <= segment.days:
        raise ValueError("Day does not exist")
    text = f"{segment.name} {reference.year}"
    if reference.day is not None:
        text = f"{reference.day} {text}"
    return segment.key, text
