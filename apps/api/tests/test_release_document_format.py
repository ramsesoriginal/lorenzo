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
from lorenzo_api.repository_content import (
    Content,
    Formula,
    SelectResultData,
    SelectStepData,
)

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


# What a formula record of a later version holds that version 1 did not: operands (format 38,
# ADR 0444) and a select (format 39, ADR 0446).
_NEW_FORMULA_FIELDS = {"operands": None, "select_mode": None, "steps": None, "otherwise": None}


def test_version_one_is_read_as_it_was_written() -> None:
    """The golden file is a version 1 document. A change that cannot read it is a new version
    with a reader of its own, and the old reader stays (ADR 0214)."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert differences(full_content(), rd.decode(golden, _files(), format=1)) == []
    # V3 adds calendars; V1 and V2 remain readable unchanged.
    assert rd.FORMAT == 39
    assert rd.encode(full_content())[0] == {
        **golden,
        "formulas": [
            [entity, definition, {**_NEW_FORMULA_FIELDS, **record}]
            for entity, definition, record in golden["formulas"]
        ],
        "definitions": {
            key: {"min_value": None, "max_value": None, **definition}
            for key, definition in golden["definitions"].items()
        },
        "calendars": {},
        "sources": {},
        "location_parts": {},
        "entity_locations": {},
        "frames": {},
        "entity_frames": {},
        "maps": {},
        "map_placements": [],
        "map_layers": {},
        "connections": {},
        "relationships": {},
        "relationship_through": {},
        "social_webs": {},
        "social_web_entries": [],
        "social_web_types": [],
        "clocks": {},
        "clock_readings": [],
        "clock_relationships": [],
        "calendar_reckonings": [],
        "scenes": {},
        "editions": {},
        "manuscript_placements": {},
        "manuscript_redirects": {},
        "carrier_coverage": {},
        "manuscript_numbering": {},
        "manuscript_contents": {},
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


def test_join_redirects_round_trip_and_old_releases_have_none() -> None:
    content = full_content()
    content.manuscript_redirects = {
        uuid.UUID(int=10): {
            "destination": uuid.UUID(int=11),
            "payload": uuid.UUID(int=50),
            "child": None,
        }
    }
    document, files = rd.encode(content)
    assert rd.decode(document, files).manuscript_redirects == content.manuscript_redirects
    old = {k: v for k, v in document.items() if k != "manuscript_redirects"}
    assert rd.decode(old, files, format=27).manuscript_redirects == {}


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


def test_version_twenty_three_maps_have_no_layers() -> None:
    """A Map written before it could have pictures under it reads with none (ADR 0361)."""
    document, files = rd.encode(full_content())
    old = {key: value for key, value in document.items() if key != "map_layers"}

    assert rd.READERS[23](old, files).map_layers == {}


def test_layers_survive_a_round_trip() -> None:
    identity = uuid.UUID(int=80)
    layers = [
        {
            "information": str(uuid.UUID(int=81)),
            "calibration": {"anchors": [{"image": [0, 0], "at": [0, 0]}]},
            "opacity": 0.5,
            "reviewed": "ab" * 32,
        }
    ]
    content = full_content()
    content.map_layers = {identity: layers}

    document, files = rd.encode(content)

    assert rd.decode(document, files).map_layers == {identity: layers}


def test_version_twenty_four_has_no_connections() -> None:
    """A repository written before connections reads with none (ADR 0363)."""
    document, files = rd.encode(full_content())
    old = {key: value for key, value in document.items() if key != "connections"}

    assert rd.READERS[24](old, files).connections == {}


def test_connections_survive_a_round_trip() -> None:
    identity, first, second = uuid.UUID(int=90), uuid.UUID(int=91), uuid.UUID(int=92)
    content = full_content()
    content.connections = {
        identity: {
            "end_a": first,
            "end_b": second,
            "one_way": True,
        },
        uuid.UUID(int=93): {"end_a": second, "end_b": first, "one_way": None},
    }

    document, files = rd.encode(content)

    assert rd.decode(document, files).connections == content.connections


def test_version_twenty_five_reads_as_twenty_six() -> None:
    """Format 26 only widens what a square or rectangular Map system may hold (ADR 0366)."""
    document, files = rd.encode(full_content())

    assert differences(rd.READERS[25](document, files), rd.READERS[26](document, files)) == []


def test_version_twenty_six_has_no_frames() -> None:
    """A repository written before frames reads with none (ADR 0369)."""
    document, files = rd.encode(full_content())
    old = {k: v for k, v in document.items() if k not in ("frames", "entity_frames")}
    content = rd.READERS[26](old, files)

    assert content.frames == {} and content.entity_frames == {}


def test_frames_survive_a_round_trip() -> None:
    sky, ether, elf = uuid.UUID(int=95), uuid.UUID(int=96), uuid.UUID(int=97)
    content = full_content()
    content.frames = {sky: ["plane", "universe"], ether: ["plane"]}
    content.entity_frames = {ether: {"plane": sky}, elf: {"plane": ether, "universe": sky}}

    document, files = rd.encode(content)

    back = rd.decode(document, files)
    assert back.frames == content.frames and back.entity_frames == content.entity_frames


def test_carrier_coverage_round_trip_and_old_releases_have_none() -> None:
    content = full_content()
    content.carrier_coverage = {
        uuid.UUID(int=100): {
            "carrier": uuid.UUID(int=10),
            "entry": None,
            "payload": uuid.UUID(int=50),
            "before": None,
            "position": 0,
        }
    }
    document, files = rd.encode(content)
    assert rd.decode(document, files).carrier_coverage == content.carrier_coverage
    old = {k: v for k, v in document.items() if k != "carrier_coverage"}
    assert rd.decode(old, files, format=28).carrier_coverage == {}


def test_numbering_format_and_previous_reader() -> None:
    content = Content(tenant_id=uuid.uuid4())
    content.manuscript_numbering[uuid.uuid4()] = {"enabled": True, "levels": [{"style": "roman"}]}
    document, files = rd.encode(content)
    assert rd.decode(document, files).manuscript_numbering == content.manuscript_numbering
    old = {k: v for k, v in document.items() if k != "manuscript_numbering"}
    assert rd.decode(old, files, format=29).manuscript_numbering == {}


def test_contents_format_and_previous_reader() -> None:
    content = Content(tenant_id=uuid.uuid4())
    content.manuscript_contents[uuid.uuid4()] = {"enabled": True, "depth": 2}
    document, files = rd.encode(content)
    assert rd.decode(document, files).manuscript_contents == content.manuscript_contents
    old = {key: value for key, value in document.items() if key != "manuscript_contents"}
    assert rd.decode(old, files, format=30).manuscript_contents == {}


def test_version_thirty_one_has_no_relationships() -> None:
    """A repository written before relationships reads with none (ADR 0399)."""
    document, files = rd.encode(full_content())
    old = {key: value for key, value in document.items() if key != "relationships"}

    assert rd.READERS[31](old, files).relationships == {}


def test_relationships_survive_a_round_trip() -> None:
    identity, first, second = uuid.UUID(int=190), uuid.UUID(int=191), uuid.UUID(int=192)
    content = full_content()
    content.relationships = {
        identity: {
            "end_a": first,
            "end_b": second,
            "one_way": True,
            "starts_at": None,
            "ends_at": None,
        },
        uuid.UUID(int=193): {
            "end_a": second,
            "end_b": first,
            "one_way": None,
            "starts_at": first,
            "ends_at": None,
        },
    }

    document, files = rd.encode(content)

    assert rd.decode(document, files).relationships == content.relationships


def test_version_thirty_two_has_no_stat_scales() -> None:
    """A repository written before stat scales reads with none (ADR 0403)."""
    document, files = rd.encode(full_content())
    old = {
        **document,
        "definitions": {
            key: {k: v for k, v in definition.items() if k not in ("min_value", "max_value")}
            for key, definition in document["definitions"].items()
        },
    }

    back = rd.READERS[32](old, files)

    assert all(d["min_value"] is None and d["max_value"] is None for d in back.definitions.values())


def test_stat_scales_survive_a_round_trip() -> None:
    content = full_content()
    first = next(iter(content.definitions))
    content.definitions[first]["min_value"] = -10.0
    content.definitions[first]["max_value"] = 10.0

    document, files = rd.encode(content)

    back = rd.decode(document, files)
    assert (back.definitions[first]["min_value"], back.definitions[first]["max_value"]) == (
        -10.0,
        10.0,
    )


def test_version_thirty_three_has_no_relationship_chains() -> None:
    """A repository written before chains reads with none (ADR 0402)."""
    document, files = rd.encode(full_content())
    old = {key: value for key, value in document.items() if key != "relationship_through"}

    assert rd.READERS[33](old, files).relationship_through == {}


def test_relationship_chains_survive_a_round_trip_in_order() -> None:
    head, one, two, three = (uuid.UUID(int=n) for n in (200, 201, 202, 203))
    content = full_content()
    content.relationship_through = {head: [three, one, two]}

    document, files = rd.encode(content)

    assert rd.decode(document, files).relationship_through == {head: [three, one, two]}


def test_version_thirty_four_has_no_relationship_limits() -> None:
    """A repository written before limits in time reads with none (ADR 0405)."""
    identity, first, second = uuid.UUID(int=210), uuid.UUID(int=211), uuid.UUID(int=212)
    content = full_content()
    content.relationships = {
        identity: {
            "end_a": first,
            "end_b": second,
            "one_way": None,
            "starts_at": None,
            "ends_at": None,
        }
    }
    document, files = rd.encode(content)
    old = {
        **document,
        "relationships": {
            key: {k: v for k, v in tied.items() if k not in ("starts_at", "ends_at")}
            for key, tied in document["relationships"].items()
        },
    }

    back = rd.READERS[34](old, files)

    assert back.relationships == content.relationships


def test_version_thirty_five_has_no_social_webs() -> None:
    """A repository written before social webs reads with none (ADR 0406)."""
    document, files = rd.encode(full_content())
    old = {
        key: value
        for key, value in document.items()
        if key not in ("social_webs", "social_web_entries", "social_web_types")
    }

    back = rd.READERS[35](old, files)

    assert (back.social_webs, back.social_web_entries, back.social_web_types) == ({}, {}, set())


def test_social_webs_survive_a_round_trip() -> None:
    web, member, kind, stat = (uuid.UUID(int=n) for n in (220, 221, 222, 223))
    content = full_content()
    content.social_webs = {
        web: {
            "layout": "manual",
            "layout_seed": 7,
            "theme_hint": "parchment",
            "view": {"labels": True},
            "standing_stat": stat,
            "as_of_event": None,
        }
    }
    content.social_web_entries = {(web, member): {"x": 1.5, "y": -2.0}}
    content.social_web_types = {(web, kind)}

    document, files = rd.encode(content)

    back = rd.decode(document, files)
    assert back.social_webs == content.social_webs
    assert back.social_web_entries == content.social_web_entries
    assert back.social_web_types == content.social_web_types


def test_version_thirty_six_has_no_sources() -> None:
    """A release written before a repository could include one it is built on says nothing of how
    it carried what it was built on (ADR 0431)."""
    document, files = rd.encode(full_content())
    old = {key: value for key, value in document.items() if key != "sources"}

    back = rd.READERS[36](old, files)

    assert back.sources == {}
    assert differences(full_content(), back) == []


def test_sources_survive_a_round_trip() -> None:
    included, shown = uuid.UUID(int=240), uuid.UUID(int=241)
    content = full_content()
    content.sources = {
        included: {
            "inclusion": "include",
            "name": "Armoury",
            "licence": {
                "label": "CC BY 4.0",
                "url": "https://creativecommons.org/licenses/by/4.0/",
            },
        },
        shown: {"inclusion": "show", "name": "Rules", "licence": {"label": "OGL", "url": None}},
    }

    document, files = rd.encode(content)

    back = rd.decode(rd.loads(rd.dumps(document)), files)
    assert differences(content, back) == []
    assert back.sources == content.sources


def test_a_source_with_a_field_the_format_does_not_write_is_refused() -> None:
    content = full_content()
    content.sources = {
        uuid.UUID(int=240): {"inclusion": "include", "name": "A", "licence": None, "x": 1}
    }

    with pytest.raises(rd.ContentFieldNotSerialisedError):
        rd.encode(content)


def test_a_min_formula_round_trips_with_a_stat_and_a_constant() -> None:
    """ADR 0444: the operands of a min, max or product are stored with a stat or a constant each,
    and a document of version 37, which has none, reads with none."""
    content = full_content()
    key = (uuid.UUID(int=10), uuid.UUID(int=34))
    operands = [(uuid.UUID(int=31), None), (None, Decimal("2.50"))]
    content.formulas[key] = Formula(kind="min", round_mode="none", operands=operands)

    document, files = rd.encode(content)
    back = rd.decode(rd.loads(rd.dumps(document)), files)

    assert back.formulas[key].operands == operands
    assert str(back.formulas[key].operands[1][1]) == "2.50"
    v37 = {
        **document,
        "formulas": [row for row in document["formulas"] if row[:2] != [str(key[0]), str(key[1])]],
    }
    for _, _, record in v37["formulas"]:
        for field in _NEW_FORMULA_FIELDS:
            del record[field]
    assert all(
        formula.operands is None for formula in rd.decode(v37, files, format=37).formulas.values()
    )


def test_a_select_formula_round_trips_every_kind_of_result() -> None:
    """ADR 0446: a select's steps and its otherwise are stored, a result being a number, a text, a
    flag or a stat, and a document of version 38 reads with none."""
    content = full_content()
    key = (uuid.UUID(int=10), uuid.UUID(int=35))
    steps = [
        SelectStepData(Decimal("1"), None, SelectResultData(number=Decimal("2.50"))),
        SelectStepData(Decimal("5"), None, SelectResultData(stat=uuid.UUID(int=31))),
        SelectStepData(None, "heavy", SelectResultData(text="slow")),
        SelectStepData(None, "light", SelectResultData(flag=False)),
    ]
    otherwise = SelectResultData(text="none")
    content.formulas[key] = Formula(
        kind="select",
        source=uuid.UUID(int=31),
        select_mode="threshold",
        steps=steps,
        otherwise=otherwise,
    )

    document, files = rd.encode(content)
    back = rd.decode(rd.loads(rd.dumps(document)), files)

    assert back.formulas[key].steps == steps
    assert back.formulas[key].otherwise == otherwise
    assert str(back.formulas[key].steps[0].result.number) == "2.50"
    v38 = {
        **document,
        "formulas": [row for row in document["formulas"] if row[:2] != [str(key[0]), str(key[1])]],
    }
    for _, _, record in v38["formulas"]:
        for field in ("select_mode", "steps", "otherwise"):
            del record[field]
    assert all(
        formula.steps is None and formula.otherwise is None
        for formula in rd.decode(v38, files, format=38).formulas.values()
    )
