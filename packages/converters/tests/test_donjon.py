from __future__ import annotations

import json
from decimal import Decimal

import pytest
from lorenzo_calendar import CalendarDate, moon_phases, weekday
from lorenzo_calendar.document import CalendarDocument
from typer.testing import CliRunner

from lorenzo_converters.cli import app
from lorenzo_converters.donjon import DonjonError, convert


def sample(year=3286):
    names = [
        "Rimsep",
        "Sogmen",
        "Temez",
        "Nordtage",
        "Querm",
        "Quirm",
        "Emsest",
        "Osttage",
        "Pestmen",
        "Vamoten",
        "Nesem",
        "Südtage",
        "Idemic",
        "Nunumde",
        "Dedomde",
        "Westtage",
        "Retedem",
        "Kameste",
        "Sprungfest",
    ]
    lengths = [27, 27, 27, 2, 27, 27, 27, 2, 27, 27, 27, 2, 27, 27, 27, 2, 27, 27, 1]
    return {
        "year_len": 387,
        "events": 1,
        "n_months": 19,
        "months": names,
        "month_len": dict(zip(names, lengths, strict=True)),
        "week_len": 7,
        "weekdays": [
            "Montag",
            "Dienstag",
            "Mittwoch",
            "Donnerstag",
            "Freitag",
            "Samstag",
            "Sonntag",
        ],
        "n_moons": 3,
        "moons": ["Maira", "Mendra", "Galon"],
        "lunar_cyc": {"Maira": 14, "Mendra": 23, "Galon": 42},
        "lunar_shf": {"Maira": 1, "Mendra": 0, "Galon": 0},
        "year": year,
        "first_day": 4 if year == 3286 else 0,
        "notes": {
            "3242-5-5": "A faraway storm",
            "3242-13-18": "",
            "3286-6-16": "A &amp;amp; B &amp; C",
        },
    }


def document(*snapshots, **options):
    return convert(
        "\n".join(json.dumps(s) for s in snapshots),
        name="Isles",
        source_key="isles",
        reference_year=3286,
        **options,
    )


def test_reference_year_matches_all_source_weekdays_and_moon_phases():
    source = sample()
    doc = document(source)
    assert len(doc.definition.segments) == 19
    day_offset = 0
    for i, name in enumerate(source["months"]):
        for day in range(1, source["month_len"][name] + 1):
            date = CalendarDate(year=3286, segment=f"segment-{i + 1}", day=day)
            assert weekday(doc.definition, date) == (4 + day_offset) % 7
            expected = {}
            for m, moon in enumerate(source["moons"]):
                epoch = Decimal(3286 * 387 + 4 + day_offset - source["lunar_shf"][moon])
                cycle = Decimal(source["lunar_cyc"][moon])
                expected[f"moon-{m + 1}"] = int((epoch % cycle) / cycle * 8)
            assert moon_phases(doc.definition, date) == expected
            day_offset += 1
    assert day_offset == 387
    assert doc.source["snapshots"] == [source]
    assert all(s.kind == "month" and s.in_week for s in doc.definition.segments)
    assert CalendarDocument.model_validate_json(doc.model_dump_json()) == doc


def test_snapshots_deduplicate_notes_skip_blanks_and_report_anchor_disagreement():
    old, new = sample(3242), sample()
    doc = document(old, new)
    assert len(doc.annotations) == 2
    assert all(a.classification == "note" for a in doc.annotations)
    assert doc.annotations[-1].text == "A &amp;amp; B &amp; C"
    assert {w.key for w in doc.warnings} == {"structure-review", "moon-anchor-3242"}
    cleaned = document(old, new, unescape_html=True)
    assert cleaned.annotations[-1].text == "A &amp; B & C"
    assert cleaned.annotations[-1].original_text == doc.annotations[-1].original_text
    assert (
        convert(
            "### 3242:\n" + json.dumps(old) + "\n### 3286:\n" + json.dumps(new),
            name="Isles",
            source_key="isles",
            reference_year=3286,
        )
        == doc
    )


def test_unnamed_segments_and_decimal_moons_and_duplicate_names():
    source = sample()
    source["months"][0] = ""
    source["month_len"]["0"] = source["month_len"].pop("Rimsep")
    source["moons"][0] = ""
    source["lunar_cyc"]["0"] = 14.5
    source["lunar_shf"]["0"] = 1.5
    source["lunar_cyc"].pop("Maira")
    source["lunar_shf"].pop("Maira")
    doc = document(source)
    assert doc.definition.segments[0].key == "segment-1"
    assert doc.definition.moons[0].period == Decimal("14.5")
    source["months"][0] = "Sogmen"
    with pytest.raises(DonjonError, match="Duplicate months"):
        document(source)


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda s: s.update(year_len=388), "Month lengths"),
        (lambda s: s.update(n_months=20), "months"),
        (lambda s: s["lunar_cyc"].update(Maira=0), "positive cycle"),
        (lambda s: s["notes"].update({"bad-date": "Text"}), "Invalid note date"),
    ],
)
def test_invalid_source_is_refused(change, message):
    source = sample()
    change(source)
    with pytest.raises(DonjonError, match=message):
        document(source)


def test_conflicting_notes_structures_and_weekday_anchors_are_not_guessed():
    old, new = sample(3242), sample()
    old["notes"]["3242-5-5"] = "Different text"
    with pytest.raises(DonjonError, match="differs between exports"):
        document(old, new)
    old = sample(3242)
    old["first_day"] = 1
    with pytest.raises(DonjonError, match="weekday anchors disagree"):
        document(old, new)
    old = sample(3242)
    old["week_len"] = 8
    with pytest.raises(DonjonError, match="different structures"):
        document(old, new)


def test_cli_stdout_is_native_json_and_warnings_stay_on_stderr(tmp_path):
    source = tmp_path / "donjon.json"
    source.write_text(json.dumps(sample()), encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "donjon",
            str(source),
            "--name",
            "Isles",
            "--source-key",
            "isles",
            "--reference-year",
            "3286",
        ],
    )
    assert result.exit_code == 0, result.output
    assert CalendarDocument.model_validate_json(result.stdout).name == "Isles"
    assert "structure-review" in result.stderr
    assert "warning" not in json.loads(result.stdout)["name"]


def test_nonfinite_and_duplicate_json_keys_are_refused():
    with pytest.raises(DonjonError, match="Non-finite"):
        convert('{"year": NaN}', name="Isles", source_key="isles", reference_year=3286)
    with pytest.raises(DonjonError, match="Duplicate JSON key"):
        convert('{"year": 1, "year": 2}', name="Isles", source_key="isles", reference_year=3286)
