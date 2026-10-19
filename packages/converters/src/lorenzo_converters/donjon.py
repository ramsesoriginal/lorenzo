"""Offline conversion of donjon's saved JSON, retaining source text (ADR 0311)."""

from __future__ import annotations

import html
import json
import re
from decimal import Decimal
from typing import Any

from lorenzo_calendar import CalendarDate, CalendarDefinition, Moon, Segment, Week, to_day
from lorenzo_calendar.document import Annotation, CalendarDocument, DocumentWarning
from pydantic import JsonValue, TypeAdapter

MAX_SOURCE_BYTES = 2_000_000


class DonjonError(ValueError):
    pass


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise DonjonError(f"{label} must be an integer between {minimum} and {maximum}")
    return value


def _names(source: dict[str, Any], field: str, count: int) -> list[str]:
    values = source.get(field)
    if (
        not isinstance(values, list)
        or len(values) != count
        or any(not isinstance(v, str) for v in values)
    ):
        raise DonjonError(f"{field} must match its declared count")
    named = [v for v in values if v]
    if field in {"months", "moons"} and len(set(named)) != len(named):
        raise DonjonError(
            f"Duplicate {field} names collide in donjon's dictionaries; resolve them in the source"
        )
    return values


def parse_exports(text: str) -> list[dict[str, Any]]:
    if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise DonjonError("Calendar source exceeds the 2 MB limit")
    # Accept a JSON object/list, or several pasted exports with optional ### year headings.
    text = re.sub(r"(?m)^\s*###\s*-?\d+:?\s*$", "", text)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise DonjonError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value: str) -> Any:
        raise DonjonError(f"Non-finite JSON number: {value}")

    decoder = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=nonfinite)
    values = []
    while text.strip():
        text = text.lstrip()
        try:
            value, end = decoder.raw_decode(text)
        except json.JSONDecodeError as error:
            raise DonjonError(f"Invalid JSON at character {error.pos}") from error
        values.extend(value if isinstance(value, list) else [value])
        text = text[end:]
    if not 1 <= len(values) <= 32 or any(not isinstance(v, dict) for v in values):
        raise DonjonError("Provide between 1 and 32 donjon JSON exports")
    return values


def convert(
    text: str, *, name: str, source_key: str, reference_year: int, unescape_html: bool = False
) -> CalendarDocument:
    snapshots = parse_exports(text)
    years = [_integer(s.get("year"), "year", -1000000, 1000000) for s in snapshots]
    if reference_year not in years:
        raise DonjonError("Choose an exported year as the reference")
    if len({s.get("first_day") for s in snapshots if s.get("year") == reference_year}) != 1:
        raise DonjonError("The reference year's weekday anchors disagree")
    source = snapshots[years.index(reference_year)]
    structural = (
        "year_len",
        "n_months",
        "months",
        "month_len",
        "week_len",
        "weekdays",
        "n_moons",
        "moons",
        "lunar_cyc",
        "lunar_shf",
    )
    if any(any(s.get(k) != source.get(k) for k in structural) for s in snapshots):
        raise DonjonError(
            "The exports have different structures; reconcile their definitions explicitly"
        )
    count = _integer(source.get("n_months"), "n_months", 1, 128)
    names = _names(source, "months", count)
    lengths = source.get("month_len")
    if not isinstance(lengths, dict):
        raise DonjonError("month_len must be a dictionary")
    segments = tuple(
        Segment(
            key=f"segment-{i + 1}",
            name=v or f"Month {i + 1}",
            days=_integer(lengths.get(v or str(i)), "month length", 1, 1000),
        )
        for i, v in enumerate(names)
    )
    year_len = _integer(source.get("year_len"), "year_len", 1, 10000)
    if sum(s.days for s in segments) != year_len:
        raise DonjonError(
            "Month lengths do not equal year_len; resolve donjon's implicit padding explicitly"
        )
    week_len = _integer(source.get("week_len"), "week_len", 1, 100)
    weekdays = _names(source, "weekdays", week_len)
    first_day = _integer(source.get("first_day"), "first_day", 0, week_len - 1)
    reference = CalendarDate(year=reference_year, segment=segments[0].key, day=1)
    week = Week(
        length=week_len,
        names=tuple(v or f"Day {i + 1}" for i, v in enumerate(weekdays)),
        reference=reference,
        weekday=first_day,
    )
    moon_count = _integer(source.get("n_moons"), "n_moons", 0, 32)
    moon_names = _names(source, "moons", moon_count)
    cycles, shifts = source.get("lunar_cyc"), source.get("lunar_shf")
    if not isinstance(cycles, dict) or not isinstance(shifts, dict):
        raise DonjonError("lunar_cyc and lunar_shf must be dictionaries")
    moons = []
    for i, value in enumerate(moon_names):
        key = value or str(i)
        try:
            cycle, shift = Decimal(str(cycles[key])), Decimal(str(shifts[key]))
            if not cycle.is_finite() or cycle <= 0 or not shift.is_finite():
                raise ValueError("Invalid moon cycle or shift")
            # Donjon's epoch is year*year_len + first_day + dayOffset.
            offset = (shift - Decimal(reference_year * year_len + first_day)) % cycle
            offset = (offset + cycle) % cycle
            moons.append(
                Moon(
                    key=f"moon-{i + 1}",
                    name=value or f"Moon {i + 1}",
                    period=cycle,
                    reference=reference,
                    offset=offset,
                )
            )
        except (KeyError, ValueError, ArithmeticError) as error:
            raise DonjonError("Each moon needs a positive cycle and a finite shift") from error
    definition = CalendarDefinition(segments=segments, week=week, moons=tuple(moons))
    warnings = [
        DocumentWarning(
            key="structure-review",
            message="All source segments retain donjon's annual month and "
            "weekday-advancing behavior. Choose festival, leap or weekless rules "
            "explicitly when appropriate.",
        )
    ]
    for s, year in zip(snapshots, years, strict=True):
        day = _integer(s.get("first_day"), "first_day", 0, week_len - 1)
        elapsed = to_day(
            definition, CalendarDate(year=year, segment=segments[0].key, day=1)
        ) - to_day(definition, reference)
        if (first_day + elapsed) % week_len != day:
            raise DonjonError(
                "The exported weekday anchors disagree; reconcile the intended anchor explicitly"
            )
        if moon_count and any(
            (
                (Decimal(year * year_len + day) - Decimal(str(shifts[value or str(i)])))
                - (
                    Decimal(reference_year * year_len + first_day)
                    - Decimal(str(shifts[value or str(i)]))
                )
                - Decimal(elapsed)
            )
            % Decimal(str(cycles[value or str(i)]))
            != 0
            for i, value in enumerate(moon_names)
        ):
            warnings.append(
                DocumentWarning(
                    key=f"moon-anchor-{year}".replace("--", "-negative-"),
                    message=f"Donjon's moon anchors for {year} disagree with continuous "
                    f"progression from {reference_year}. The chosen reference is preserved; "
                    "no fictional jump is inferred.",
                )
            )
    notes: dict[str, str] = {}
    for s in snapshots:
        if not isinstance(s.get("notes", {}), dict):
            raise DonjonError("notes must be a dictionary")
        for date_key, original in s.get("notes", {}).items():
            if not isinstance(original, str):
                raise DonjonError("Each source note must be text")
            if date_key in notes and notes[date_key] != original:
                raise DonjonError(
                    f"Note {date_key} differs between exports; choose its text explicitly"
                )
            notes[date_key] = original
    annotations = []
    for date_key, original in sorted(notes.items()):
        match = re.fullmatch(r"(-?\d+)-(\d+)-(\d+)", date_key)
        if not match:
            raise DonjonError(f"Invalid note date: {date_key}")
        year, ordinal, day = map(int, match.groups())
        if not 1 <= ordinal <= len(segments):
            raise DonjonError(f"Invalid note month: {date_key}")
        date = CalendarDate(year=year, segment=segments[ordinal - 1].key, day=day)
        if not original.strip():
            continue
        annotations.append(
            Annotation(
                key="note-" + date_key,
                date=date,
                text=html.unescape(original) if unescape_html else original,
                original_text=original,
            )
        )
    return CalendarDocument(
        source_key=source_key,
        name=name,
        definition=definition,
        annotations=tuple(annotations),
        warnings=tuple({w.key: w for w in warnings}.values()),
        source={
            "format": "donjon",
            "reference_year": reference_year,
            "html_unescaped": unescape_html,
            "snapshots": TypeAdapter(JsonValue).validate_python(snapshots),
        },
    )
