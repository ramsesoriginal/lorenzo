"""The validator against the golden corpus and the limits of ADR 0337."""

import json
import math
import time
from pathlib import Path

import pytest

from lorenzo_map import (
    MAX_PARTS,
    MAX_PLACEMENT_BYTES,
    MAX_VERTICES,
    ROLES,
    MapDocumentError,
    effective_kind,
    read_role,
    validate_geometry,
    validate_placement,
    validate_role,
    validate_style,
    validate_system,
    validate_z,
)

GOLDEN = Path(__file__).parents[1] / "golden"
GEOMETRY = json.loads((GOLDEN / "geometry.json").read_text(encoding="utf-8"))
SYSTEM = json.loads((GOLDEN / "system.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", GEOMETRY["accepted"], ids=lambda c: c["name"])
def test_geometry_the_golden_corpus_accepts(case):
    checked = validate_geometry(case["document"])
    # Validating what it returned changes nothing: the stored form is a fixed point.
    assert validate_geometry(checked.geometry).geometry == checked.geometry
    assert checked.bytes == len(
        json.dumps(checked.geometry, separators=(",", ":"), ensure_ascii=False).encode()
    )


@pytest.mark.parametrize("case", GEOMETRY["refused"], ids=lambda c: c["name"])
def test_geometry_the_golden_corpus_refuses(case):
    with pytest.raises(MapDocumentError) as refused:
        validate_geometry(case["document"])
    # The sentence is the validator's own: it repeats nothing of the input.
    assert str(refused.value) == refused.value.reason
    assert json.dumps(case["document"]) not in str(refused.value)


@pytest.mark.parametrize("case", SYSTEM["accepted"], ids=lambda c: c["name"])
def test_systems_the_golden_corpus_accepts(case):
    stored = validate_system(case["document"])
    assert validate_system(stored) == stored


@pytest.mark.parametrize("case", SYSTEM["refused"], ids=lambda c: c["name"])
def test_systems_the_golden_corpus_refuses(case):
    with pytest.raises(MapDocumentError):
        validate_system(case["document"])


def point(x, y):
    return {"format": "lorenzo.geometry/1", "parts": [{"shape": "point", "at": [x, y]}]}


def test_the_bounding_box_is_a_superset_of_the_shape():
    bezier = {
        "format": "lorenzo.geometry/1",
        "parts": [
            {"shape": "bezier", "start": [0, 0], "segs": [[[10, -40], [20, 40], [30, 0]]]},
            {"shape": "circle", "at": [100, 100], "r": 5},
        ],
    }
    # The hull of the control points, and the square around the circle.
    assert validate_geometry(bezier).bbox == (0, -40, 105, 105)
    assert validate_geometry(point(3, 4)).bbox == (3, 4, 3, 4)


def test_numbers_are_stored_in_their_canonical_form():
    stored = validate_geometry(point(1.0, 2.5)).geometry["parts"][0]["at"]
    assert stored == [1, 2.5] and isinstance(stored[0], int)
    assert validate_geometry(point(0.1 + 0.2, 0)).geometry["parts"][0]["at"][0] == 0.3


def test_not_a_number_is_refused():
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(MapDocumentError):
            validate_geometry(point(bad, 0))


def test_a_vertex_limit_and_a_part_limit():
    ok = {
        "format": "lorenzo.geometry/1",
        "parts": [{"shape": "polyline", "pts": [[i, 0] for i in range(MAX_VERTICES)]}],
    }
    assert validate_geometry(ok).vertices == MAX_VERTICES
    over = {
        "format": "lorenzo.geometry/1",
        "parts": [{"shape": "polyline", "pts": [[i, 0] for i in range(MAX_VERTICES + 1)]}],
    }
    with pytest.raises(MapDocumentError):
        validate_geometry(over)
    parts = [{"shape": "point", "at": [i, 0]} for i in range(MAX_PARTS)]
    assert validate_geometry({"format": "lorenzo.geometry/1", "parts": parts}).vertices == MAX_PARTS
    parts.append({"shape": "point", "at": [0, 0]})
    with pytest.raises(MapDocumentError):
        validate_geometry({"format": "lorenzo.geometry/1", "parts": parts})


def test_a_placement_has_at_most_sixty_four_kib():
    big = {
        "format": "lorenzo.geometry/1",
        "parts": [
            {
                "shape": "polyline",
                "pts": [[1234567.123456 + i, -7654321.654321] for i in range(1999)],
            }
        ],
    }
    with pytest.raises(MapDocumentError) as refused:
        validate_geometry(big)
    assert "too large" in str(refused.value)
    small = {
        "format": "lorenzo.geometry/1",
        "parts": [{"shape": "polyline", "pts": [[i, 0] for i in range(300)]}],
    }
    assert validate_geometry(small).bytes < MAX_PLACEMENT_BYTES


def test_the_worst_legal_polygon_is_checked_within_its_budget():
    n = MAX_VERTICES
    ring = [
        [
            round(1_000_000 * math.cos(2 * math.pi * i / n)),
            round(1_000_000 * math.sin(2 * math.pi * i / n)),
        ]
        for i in range(n)
    ]
    started = time.perf_counter()
    checked = validate_geometry(
        {"format": "lorenzo.geometry/1", "parts": [{"shape": "polygon", "rings": [ring]}]}
    )
    assert checked.vertices == n
    assert time.perf_counter() - started < 20


def test_a_zigzag_polygon_that_is_simple_and_one_that_is_not():
    comb = [[0, 0], [100, 0], [100, 10]]
    for i in range(8):
        comb += [
            [100 - 10 * (i + 1) + 5, 10],
            [100 - 10 * (i + 1) + 5, 50],
            [100 - 10 * (i + 1), 50],
            [100 - 10 * (i + 1), 10],
        ]
    comb += [[0, 10]]
    assert validate_geometry(
        {"format": "lorenzo.geometry/1", "parts": [{"shape": "polygon", "rings": [comb]}]}
    )
    crossing = [[0, 0], [100, 0], [100, 100], [50, -10], [0, 100]]
    with pytest.raises(MapDocumentError):
        validate_geometry(
            {"format": "lorenzo.geometry/1", "parts": [{"shape": "polygon", "rings": [crossing]}]}
        )


def test_roles_styles_and_drawing_order():
    assert len(ROLES) == 21 and "grouping" not in ROLES
    assert validate_role(None) is None and validate_role("water") == "water"
    with pytest.raises(MapDocumentError):
        validate_role("dragon")
    assert read_role("dragon") is None and read_role("route") == "route"
    assert validate_style({}) is None and validate_style(None) is None
    assert validate_style({"stroke": "none"}) == {"stroke": "none"}
    assert validate_style({"stroke": "dashed", "weight": "thick"}) == {
        "stroke": "dashed",
        "weight": "thick",
    }
    for bad in ({"stroke": "wavy"}, {"weight": "huge"}, {"colour": "red"}, "dashed"):
        with pytest.raises(MapDocumentError):
            validate_style(bad)
    assert validate_z(0) == 0 and validate_z(-100) == -100 and validate_z(100) == 100
    for bad in (101, -101, 1.5, True, "1"):
        with pytest.raises(MapDocumentError):
            validate_z(bad)


def test_a_whole_placement():
    checked = validate_placement(point(1, 2), "presence", {"stroke": "none"}, 5)
    assert (checked.role, checked.style, checked.z) == ("presence", {"stroke": "none"}, 5)
    with pytest.raises(MapDocumentError):
        validate_placement(point(1, 2), "dragon")


def test_a_system_a_reader_does_not_know_is_an_outline():
    assert effective_kind({"kind": "plane"}) == "plane"
    assert effective_kind({"kind": "hex"}) == "outline"
    assert effective_kind(None) == "outline"


def test_theme_names_are_the_golden_list_and_a_stored_name_is_read_kindly():
    from lorenzo_map import THEME_NAMES, keep_theme_hint, read_theme_hint, validate_theme_hint

    golden = json.loads((GOLDEN / "themes.json").read_text(encoding="utf-8"))

    assert list(THEME_NAMES) == golden["names"]
    assert validate_theme_hint(None) is None and validate_theme_hint("plain") == "plain"
    for refused in ("Plain", "tube", "", 3, ["plain"]):
        with pytest.raises(MapDocumentError):
            validate_theme_hint(refused)
    # A newer version's name is read as the default but carried unchanged by a copy.
    assert read_theme_hint("tube") is None and read_theme_hint("plain") == "plain"
    assert keep_theme_hint("tube") == "tube" and keep_theme_hint("x" * 33) is None
    assert keep_theme_hint(None) is None and keep_theme_hint("") is None
