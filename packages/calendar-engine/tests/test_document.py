import pytest
from pydantic import ValidationError

from lorenzo_calendar.document import CalendarDocument, parse_document

BASE = {
    "source_key": "isles",
    "name": "Isles",
    "definition": {"segments": [{"key": "first", "name": "First", "days": 3}]},
}


def annotation(**fields):
    return {
        "key": "note-1",
        "date": {"year": 0, "segment": "first", "day": 1},
        "text": "A note",
        "original_text": "A note",
        **fields,
    }


def test_native_document_is_bounded_and_does_not_guess_classifications():
    doc = CalendarDocument.model_validate({**BASE, "annotations": [annotation()]})
    assert doc.annotations[0].classification == "note"
    assert not doc.is_public and not doc.annotations[0].information_is_public
    assert CalendarDocument.model_validate_json(doc.model_dump_json()) == doc
    with pytest.raises(ValidationError):
        CalendarDocument.model_validate({**BASE, "annotations": [annotation(), annotation()]})
    with pytest.raises(ValidationError):
        CalendarDocument.model_validate({**BASE, "format": "unknown/1"})
    with pytest.raises(ValidationError):
        CalendarDocument.model_validate({**BASE, "source": {"large": "x" * 2000000}})


def test_classifications_and_grouping_are_explicit_and_dates_validated():
    with pytest.raises(ValidationError):
        CalendarDocument.model_validate(
            {**BASE, "annotations": [annotation(classification="observance")]}
        )
    with pytest.raises(ValidationError):
        CalendarDocument.model_validate({**BASE, "annotations": [annotation(group="one-event")]})
    with pytest.raises(ValidationError):
        CalendarDocument.model_validate(
            {**BASE, "annotations": [annotation(date={"year": 0, "segment": "first", "day": 4})]}
        )
    doc = CalendarDocument.model_validate(
        {
            **BASE,
            "annotations": [
                annotation(classification="observance", recurrence={"segment": "first", "day": 2})
            ],
        }
    )
    assert doc.annotations[0].recurrence.day == 2


def test_native_file_parser_rejects_duplicate_keys_and_nonfinite_values():
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        parse_document('{"source_key": "a", "source_key": "b"}')
    with pytest.raises(ValueError, match="Non-finite"):
        parse_document('{"bad": NaN}')
    with pytest.raises(ValidationError):
        CalendarDocument.model_validate({**BASE, "source": {"bad": float("inf")}})
