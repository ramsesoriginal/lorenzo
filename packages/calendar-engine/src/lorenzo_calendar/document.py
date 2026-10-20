"""Portable, bounded calendar authoring documents (ADR 0311).

Source material is preserved independently of authored text and interpretation. This is not
LorenzoLedger, an import receipt, or a statement of temporal truth.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal, Self

from pydantic import Field, JsonValue, model_validator

from lorenzo_calendar import (
    CalendarDate,
    CalendarDefinition,
    Key,
    Name,
    RecurrenceRule,
    Value,
    segment_for,
    validate_recurrence,
)

Text = Annotated[str, Field(max_length=40000)]


class DocumentWarning(Value):
    key: Key
    message: Annotated[str, Field(min_length=1, max_length=2000)]


class Annotation(Value):
    key: Key
    date: CalendarDate
    text: Text
    original_text: Text
    classification: Literal["note", "observance", "fact", "event"] = "note"
    title: Name | None = None
    group: Key | None = None
    recurrence: RecurrenceRule | None = None
    is_public: bool = False
    information_is_public: bool = False

    @model_validator(mode="after")
    def valid_annotation(self) -> Self:
        if (self.classification == "observance") != (self.recurrence is not None):
            raise ValueError("Only an observance needs a recurrence rule")
        if self.group is not None and self.classification != "event":
            raise ValueError("Only Event annotations can share an explicit group")
        if not self.text.strip():
            raise ValueError("Blank source notes are not annotations")
        return self


class CalendarDocument(Value):
    format: Literal["lorenzo.calendar-document/1"] = "lorenzo.calendar-document/1"
    source_key: Key
    name: Name
    definition: CalendarDefinition
    annotations: Annotated[tuple[Annotation, ...], Field(max_length=1000)] = ()
    source: dict[str, JsonValue] = Field(default_factory=dict)
    warnings: Annotated[tuple[DocumentWarning, ...], Field(max_length=100)] = ()
    is_public: bool = False
    period_is_public: bool = False

    @model_validator(mode="after")
    def valid_document(self) -> Self:
        if (
            len(
                json.dumps(
                    self.model_dump(mode="json"),
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            > 2_000_000
        ):
            raise ValueError("Calendar document exceeds the 2 MB limit")
        if len({a.key for a in self.annotations}) != len(self.annotations):
            raise ValueError("Source annotation keys must be unique")
        if len({w.key for w in self.warnings}) != len(self.warnings):
            raise ValueError("Warning keys must be unique")
        groups: dict[str, Annotation] = {}
        for annotation in self.annotations:
            segment_for(self.definition, annotation.date)
            if annotation.recurrence is not None:
                validate_recurrence(self.definition, annotation.recurrence)
            if annotation.group is not None:
                previous = groups.setdefault(annotation.group, annotation)
                if (previous.title, previous.is_public) != (annotation.title, annotation.is_public):
                    raise ValueError(
                        "Grouped Event annotations need the same title and outer audience"
                    )
        return self


def parse_document(data: str | bytes) -> CalendarDocument:
    """Read one portable file strictly before passing its values to the typed validator."""
    if len(data.encode("utf-8") if isinstance(data, str) else data) > 2_000_000:
        raise ValueError("Calendar document exceeds the 2 MB limit")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value: str) -> Any:
        raise ValueError(f"Non-finite JSON number: {value}")

    value = json.loads(data, object_pairs_hook=unique_object, parse_constant=nonfinite)
    return CalendarDocument.model_validate(value)
