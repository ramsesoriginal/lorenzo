"""The straight-line distance (ADR 0366): its golden file and the properties it must have."""

import itertools
import json
import math
from pathlib import Path

import pytest

from lorenzo_map import (
    METRICS,
    MapDocumentError,
    cell_centre,
    straight_distance,
    validate_system,
)

GOLDEN = json.loads((Path(__file__).parents[1] / "golden" / "distance.json").read_text("utf-8"))
F = "lorenzo.map-system/1"
MEASURE = {"per_cell": 1, "unit": "cells"}


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["name"])
def test_the_golden_vectors(case):
    got = straight_distance(case["system"], tuple(case["a"]), tuple(case["b"]))
    want = case["answer"]

    assert got["state"] == want["state"]
    if want["state"] == "known":
        assert got["unit"] == want["unit"]
        assert got["value"] == pytest.approx(want["value"], abs=1e-6)
    else:
        assert got["reason"] == want["reason"]
        assert "value" not in got


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["name"])
def test_the_golden_systems_are_valid_where_they_are_writable(case):
    if case["system"]["kind"] != "torus":
        assert validate_system(case["system"])["kind"] == case["system"]["kind"]


def square(metric=None, kind="square"):
    cell = {"size": 10} if kind == "square" else {"width": 10, "height": 10}
    system = {
        "format": F,
        "kind": kind,
        "extent": [0, 0, 200, 200],
        "cell": cell,
        "measure": MEASURE,
    }
    if metric:
        system["metric"] = metric
    return validate_system(system)


def centre(system, cell):
    return cell_centre(system, system["extent"], cell)


def apart(system, a, b):
    return straight_distance(system, centre(system, a), centre(system, b))["value"]


CELLS = list(itertools.product(range(0, 6), range(0, 6)))


@pytest.mark.parametrize("metric", METRICS)
@pytest.mark.parametrize("kind", ["square", "rect"])
def test_a_cell_is_nothing_from_itself_and_a_distance_is_the_same_both_ways(metric, kind):
    system = square(metric, kind)
    for a, b in itertools.product(CELLS[::5], CELLS[::7]):
        assert apart(system, a, a) == 0
        assert apart(system, a, b) == pytest.approx(apart(system, b, a))
        assert (apart(system, a, b) == 0) == (a == b)


@pytest.mark.parametrize("metric", METRICS)
def test_a_straight_step_is_one_cell_in_every_metric(metric):
    system = square(metric)
    assert apart(system, (2, 2), (3, 2)) == 1
    assert apart(system, (2, 2), (2, 3)) == 1


def test_the_triangle_inequality_holds_where_the_metric_has_one():
    # `alternating` is not a norm (a cell and its far neighbour round differently) and is left out.
    for metric in ("chebyshev", "manhattan", "euclidean"):
        system = square(metric)
        for a, b, c in itertools.product(CELLS[::4], CELLS[::5], CELLS[::6]):
            assert apart(system, a, c) <= apart(system, a, b) + apart(system, b, c) + 1e-6


def test_the_metrics_are_ordered_for_a_diagonal():
    a, b = (0, 0), (4, 4)
    got = {m: apart(square(m), a, b) for m in METRICS}

    assert got["chebyshev"] == 4
    assert got["alternating"] == 6
    assert got["euclidean"] == pytest.approx(math.sqrt(32))
    assert got["manhattan"] == 8
    assert got["chebyshev"] <= got["euclidean"] <= got["alternating"] <= got["manhattan"]


def hexes(orientation):
    return validate_system(
        {
            "format": F,
            "kind": "hex",
            "orientation": orientation,
            "extent": [0, 0, 400, 400],
            "cell": {"size": 20},
            "measure": MEASURE,
        }
    )


@pytest.mark.parametrize("orientation", ["pointy", "flat"])
def test_a_hex_has_six_neighbours_and_twelve_cells_at_two_steps(orientation):
    system = hexes(orientation)
    origin = (6, 6)
    got = [
        apart(system, origin, (col, row))
        for col, row in itertools.product(range(0, 14), range(0, 14))
    ]

    assert got.count(0) == 1
    assert got.count(1) == 6
    # 6n cells lie at n steps while the ring is on the sheet.
    assert got.count(2) == 12
    assert got.count(3) == 18


@pytest.mark.parametrize("orientation", ["pointy", "flat"])
def test_a_hex_distance_is_symmetric_and_obeys_the_triangle_inequality(orientation):
    system = hexes(orientation)
    for a, b, c in itertools.product(CELLS[::5], CELLS[::7], CELLS[::8]):
        assert apart(system, a, b) == apart(system, b, a)
        assert apart(system, a, c) <= apart(system, a, b) + apart(system, b, c)


def test_a_sphere_is_a_great_circle_and_a_planet_scales_with_its_radius():
    def sphere(radius):
        return validate_system(
            {
                "format": F,
                "kind": "sphere",
                "extent": [-180, -90, 180, 90],
                "radius": {"value": radius, "unit": "km"},
            }
        )

    # Along a parallel the way is shorter than the lines of longitude suggest.
    on_equator = straight_distance(sphere(1), (0, 0), (60, 0))["value"]
    high = straight_distance(sphere(1), (0, 80), (60, 80))["value"]
    assert on_equator == pytest.approx(math.pi / 3, abs=1e-6)
    assert high < on_equator
    assert straight_distance(sphere(10), (0, 0), (60, 0))["value"] == pytest.approx(
        10 * on_equator, abs=1e-5
    )
    # Across the antimeridian is the short way, as the sheet is cut there.
    assert straight_distance(sphere(1), (179, 0), (-179, 0))["value"] == pytest.approx(
        math.radians(2), abs=1e-6
    )


def test_a_distance_is_never_converted_and_is_rounded_to_six_decimals():
    system = validate_system(
        {
            "format": F,
            "kind": "plane",
            "extent": [0, 0, 1000, 800],
            "scale": {"per_unit": 0.333333, "unit": "fathoms"},
        }
    )
    got = straight_distance(system, (0, 0), (1, 1))

    assert got["unit"] == "fathoms"
    assert got["value"] == pytest.approx(0.471404, abs=1e-6)
    assert round(got["value"], 6) == got["value"]


# --- the metric key -------------------------------------------------------------------------


@pytest.mark.parametrize("metric", METRICS)
@pytest.mark.parametrize("kind", ["square", "rect"])
def test_a_square_or_rectangular_system_may_name_its_metric(metric, kind):
    assert square(metric, kind)["metric"] == metric


def test_a_system_without_a_metric_validates_as_before():
    assert "metric" not in square()


@pytest.mark.parametrize("metric", ["diagonal", "", None, 3, ["chebyshev"], "Chebyshev"])
def test_an_unknown_metric_is_refused(metric):
    system = {
        "format": F,
        "kind": "square",
        "extent": [0, 0, 200, 200],
        "cell": {"size": 10},
        "metric": metric,
    }
    with pytest.raises(MapDocumentError):
        validate_system(system)


@pytest.mark.parametrize(
    "extra",
    [
        {"kind": "plane"},
        {"kind": "outline"},
        {"kind": "hex", "orientation": "flat", "cell": {"size": 10}},
        {"kind": "sphere", "extent": [-180, -90, 180, 90]},
    ],
)
def test_only_a_square_or_rectangular_grid_has_a_metric(extra):
    system = {"format": F, "kind": "plane", "extent": [0, 0, 200, 200], "metric": "chebyshev"}
    system.update(extra)
    with pytest.raises(MapDocumentError):
        validate_system(system)
