"""ADR 0214: the release document's format, with nothing but a `Content` in memory - what is
written, what is read back, what is refused. The database and the engines are in
test_repository_release_documents.py.
"""

import gzip
import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from _content_compare import differences
from _content_fixtures import DOCUMENT, PICTURE, full_content

from lorenzo_api import release_document as rd
from lorenzo_api.repository_content import Content, Formula

GOLDEN = Path(__file__).parent / "data" / "release_document_v1.json"


def _files() -> dict[str, bytes]:
    return {hashlib.sha256(b).hexdigest(): b for b in (PICTURE, DOCUMENT)}


def test_a_content_with_every_field_reads_back_exactly() -> None:
    content = full_content()
    document, files = rd.encode(content)

    back = rd.decode(rd.loads(rd.dumps(document)), files)

    assert differences(content, back) == []


def test_the_same_content_is_the_same_bytes_and_a_changed_one_is_not() -> None:
    first, second = full_content(), full_content()
    assert rd.dumps(rd.encode(first)[0]) == rd.dumps(rd.encode(second)[0])

    second.slugs[uuid.UUID(int=10)] = "renamed"
    assert rd.dumps(rd.encode(first)[0]) != rd.dumps(rd.encode(second)[0])


def test_the_document_is_standard_json_with_its_non_finite_floats_as_strings() -> None:
    document, _ = rd.encode(full_content())

    def refuse(token: str) -> Any:
        raise AssertionError(f"a bare {token} in the document")

    text = gzip.decompress(rd.dumps(document)).decode()
    parsed = json.loads(text, parse_constant=refuse)

    floats = {
        stat[2]["value_float"] for stat in parsed["stats"] if stat[2]["value_float"] is not None
    }
    assert {"nan", "inf", "-inf", 1.5} <= floats
    assert 0.1 + 0.2 in floats


def test_files_are_named_by_their_sha256_and_kept_beside_the_document() -> None:
    document, files = rd.encode(full_content())

    assert files == _files()
    pictures = [p for p in document["payloads"].values() if p["kind"] == "picture"]
    assert [p["fields"] for p in pictures] == [
        {"sha256": hashlib.sha256(PICTURE).hexdigest(), "file_type": "png"},
        # The same bytes under another type: one file, two payloads that say what it is.
        {"sha256": hashlib.sha256(PICTURE).hexdigest(), "file_type": "jpg"},
    ]
    assert b"PDF" not in gzip.decompress(rd.dumps(document))


def test_every_file_a_document_refers_to_is_among_its_files_and_there_is_no_other() -> None:
    document, files = rd.encode(full_content())

    referred = {
        p["fields"]["sha256"] for p in document["payloads"].values() if "sha256" in p["fields"]
    }
    assert referred == set(files)


def test_decimals_keep_their_scale_and_floats_their_last_digit() -> None:
    document, files = rd.encode(full_content())
    back = rd.decode(rd.loads(rd.dumps(document)), files)

    formula = back.formulas[(uuid.UUID(int=10), uuid.UUID(int=33))]
    assert str(formula.multiplier) == "0.50"
    assert back.stats[(uuid.UUID(int=11), uuid.UUID(int=31))].value_float == 0.1 + 0.2
    number = back.payloads[uuid.UUID(int=51)].fields["value"]
    assert isinstance(number, Decimal) and str(number) == "2.50"


def test_version_one_is_read_as_it_was_written() -> None:
    """The golden file is a version 1 document. A change that cannot read it is a new version
    with a reader of its own, and the old reader stays (ADR 0214)."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert differences(full_content(), rd.decode(golden, _files(), format=1)) == []
    # V3 adds calendars; V1 and V2 remain readable unchanged.
    assert rd.FORMAT == 23
    assert rd.encode(full_content())[0] == {
        **golden,
        "calendars": {},
        "location_parts": {},
        "entity_locations": {},
        "maps": {},
        "map_placements": [],
        "clocks": {},
        "clock_readings": [],
        "clock_relationships": [],
        "calendar_reckonings": [],
        "scenes": {},
        "editions": {},
        "manuscript_placements": {},
        "tellings": {},
        "writing_biographies": [],
        "scene_facts": [],
        "lived_before": [],
        "scene_events": [],
        "scene_beings": [],
        "observances": {},
        "calendar_periods": {},
        "entry_dates": [],
        "event_relationships": [],
        "event_participants": [],
        "event_learning": [],
        "shared_event_relationships": [],
        "participant_entry_audiences": [],
        "participant_information_audiences": [],
        "entry_audiences": {},
        "entry_knowledge": [],
        "fact_about": [],
    }


@pytest.mark.parametrize("format_", [0, rd.FORMAT + 1, 99])
def test_a_version_nobody_knows_is_refused(format_: int) -> None:
    document, files = rd.encode(full_content())

    with pytest.raises(rd.UnknownDocumentFormatError, match=str(format_)):
        rd.decode(document, files, format=format_)


def test_the_current_version_has_a_reader() -> None:
    assert rd.FORMAT in rd.READERS


def test_a_content_with_a_field_the_format_does_not_write_is_refused() -> None:
    @dataclass
    class Wider(Content):
        notes: str = ""

    with pytest.raises(rd.ContentFieldNotSerialisedError, match="notes"):
        rd.encode(Wider(tenant_id=uuid.uuid4()))


def test_a_field_added_to_a_part_of_a_content_is_refused_too() -> None:
    @dataclass
    class WiderFormula(Formula):
        rounding: str = ""

    content = full_content()
    content.formulas[(uuid.UUID(int=10), uuid.UUID(int=34))] = WiderFormula(kind="contents")

    with pytest.raises(rd.ContentFieldNotSerialisedError, match="rounding"):
        rd.encode(content)


def test_a_document_that_refers_to_a_file_that_is_not_there_is_corrupt() -> None:
    document, files = rd.encode(full_content())
    files.pop(hashlib.sha256(DOCUMENT).hexdigest())

    with pytest.raises(rd.ReleaseDocumentCorruptError, match="file"):
        rd.decode(document, files)


@pytest.mark.parametrize(
    "data",
    [b"not gzip at all", gzip.compress(b"{not json"), gzip.compress(b"[1, 2]")],
    ids=["not gzip", "not json", "not an object"],
)
def test_bytes_that_are_not_a_document_are_corrupt(data: bytes) -> None:
    with pytest.raises(rd.ReleaseDocumentCorruptError):
        rd.loads(data)


def test_an_empty_content_round_trips() -> None:
    content = Content(tenant_id=uuid.uuid4())
    document, files = rd.encode(content)

    assert files == {}
    assert differences(content, rd.decode(rd.loads(rd.dumps(document)), files)) == []


def test_event_assertions_round_trip_and_old_releases_have_none():
    content = full_content()
    content.event_relationships = [(uuid.UUID(int=10), uuid.UUID(int=11), "causes")]
    document, files = rd.encode(content)
    assert rd.decode(document, files).event_relationships == content.event_relationships
    old = {k: v for k, v in document.items() if k != "event_relationships"}
    assert rd.decode(old, files, format=5).event_relationships == []


def test_version_twenty_maps_have_no_theme_name() -> None:
    """A Map written before a theme name existed reads with none (ADR 0352)."""
    identity = uuid.UUID(int=77)
    system = {"format": "lorenzo.map-system/1", "kind": "plane", "extent": [0, 0, 1, 1]}
    document, files = rd.encode(full_content())
    old = {**document, "maps": {str(identity): {"system": system, "subject": None}}}

    content = rd.READERS[20](old, files)

    assert content.maps[identity] == {
        "system": system,
        "subject": None,
        "theme": None,
        "view": None,
    }


def test_version_twentyone_maps_have_no_view() -> None:
    """A Map written before it could draw a grid of its own reads with no view (ADR 0354)."""
    identity = uuid.UUID(int=78)
    system = {"format": "lorenzo.map-system/1", "kind": "plane", "extent": [0, 0, 1, 1]}
    document, files = rd.encode(full_content())
    old = {
        **document,
        "maps": {str(identity): {"system": system, "subject": None, "theme": "plain"}},
    }

    content = rd.READERS[21](old, files)

    assert content.maps[identity] == {
        "system": system,
        "subject": None,
        "theme": "plain",
        "view": None,
    }


def test_version_twentytwo_maps_are_read_as_they_are_written() -> None:
    """Format 23 only widens what a system and a view may hold (ADR 0357)."""
    identity = uuid.UUID(int=79)
    system = {"format": "lorenzo.map-system/1", "kind": "plane", "extent": [0, 0, 1, 1]}
    record = {
        "system": system,
        "subject": None,
        "theme": None,
        "view": {"grid": {"kind": "square", "cell": {"size": 2}}},
    }
    document, files = rd.encode(full_content())

    content = rd.READERS[22]({**document, "maps": {str(identity): record}}, files)

    assert content.maps[identity] == record
