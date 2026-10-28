"""A sphere Map: its system, the geometry on it and its projection (ADR 0357)."""

import json
from pathlib import Path

import pytest

from lorenzo_map import (
    PROJECTIONS,
    SPHERE_EXTENT,
    MapDocumentError,
    effective_kind,
    is_sphere,
    validate_geometry,
    validate_placement,
    validate_system,
    validate_view,
)

GOLDEN = json.loads(
    (Path(__file__).parents[1] / "golden" / "geometry-sphere.json").read_text("utf-8")
)
F = "lorenzo.map-system/1"
SPHERE = {"format": F, "kind": "sphere", "extent": SPHERE_EXTENT}


@pytest.mark.parametrize("case", GOLDEN["accepted"], ids=lambda c: c["name"])
def test_what_a_sphere_draws(case):
    checked = validate_geometry(case["document"], sphere=True)
    assert validate_geometry(checked.geometry, sphere=True).geometry == checked.geometry


@pytest.mark.parametrize("case", GOLDEN["refused"], ids=lambda c: c["name"])
def test_what_a_sphere_refuses(case):
    with pytest.raises(MapDocumentError) as refused:
        validate_geometry(case["document"], sphere=True)
    assert str(refused.value) == refused.value.reason
    assert json.dumps(case["document"]) not in str(refused.value)


def test_the_same_geometry_is_not_held_to_a_range_on_other_kinds():
    circle = {
        "format": "lorenzo.geometry/1",
        "parts": [{"shape": "circle", "at": [900, 900], "r": 5}],
    }
    assert validate_geometry(circle).bbox == (895, 895, 905, 905)
    assert validate_placement(circle, system={"kind": "plane"}).bbox == (895, 895, 905, 905)
    with pytest.raises(MapDocumentError):
        validate_placement(circle, system=SPHERE)


def test_a_sphere_is_a_writable_kind_and_a_fixed_point():
    stored = validate_system({**SPHERE, "radius": {"value": 6371.5, "unit": " km "}})
    assert stored["radius"] == {"value": 6371.5, "unit": "km"}
    assert validate_system(stored) == stored
    assert effective_kind(stored) == "sphere" and is_sphere(stored) and not is_sphere(None)
    assert "radius" not in validate_system(SPHERE)


def test_a_projection_is_for_a_sphere_and_a_centre_is_for_a_globe():
    sphere = validate_system(SPHERE)
    plane = validate_system({"format": F, "kind": "plane", "extent": [0, 0, 10, 10]})

    assert PROJECTIONS == ("equirectangular", "mercator", "orthographic")
    for kind in ("equirectangular", "mercator"):
        assert validate_view({"projection": {"kind": kind}}, sphere) == {
            "projection": {"kind": kind}
        }
    globe = {"projection": {"kind": "orthographic", "centre": [12.5, -40]}}
    assert validate_view(globe, sphere) == globe
    assert validate_view({"projection": {"kind": "orthographic"}}, sphere) == {
        "projection": {"kind": "orthographic"}
    }
    assert validate_view({}, sphere) is None
    for refused in (
        {"projection": {"kind": "mollweide"}},
        {"projection": {"kind": "mercator", "centre": [0, 0]}},
        {"projection": {"kind": "orthographic", "centre": [181, 0]}},
        {"projection": {"kind": "orthographic", "centre": [0, -90.5]}},
        {"projection": {"kind": "orthographic", "centre": [0]}},
        {"projection": {"kind": "orthographic", "centre": [0, 0], "tilt": 3}},
        {"projection": "mercator"},
        {"grid": {"kind": "square", "cell": {"size": 5}}},
    ):
        with pytest.raises(MapDocumentError):
            validate_view(refused, sphere)
    with pytest.raises(MapDocumentError):
        validate_view({"projection": {"kind": "mercator"}}, plane)
