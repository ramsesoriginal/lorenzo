"""Cells, the hex convention and the tie rule (ADR 0354, 0355), against the golden file the
TypeScript mirror also reads, and the properties that must hold for any grid."""

import json
import math
from pathlib import Path

import pytest

from lorenzo_map import (
    MapDocumentError,
    cell_at,
    cell_centre,
    cell_count,
    cell_polygon,
    in_grid,
    validate_system,
    validate_view,
)

GOLDEN = json.loads((Path(__file__).parents[1] / "golden" / "cells.json").read_text("utf-8"))
F = "lorenzo.map-system/1"


def near(a, b, eps=1e-6):
    return len(a) == len(b) and all(abs(x - y) < eps for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize("case", GOLDEN["grids"], ids=lambda c: c["name"])
def test_the_golden_vectors(case):
    grid, extent = case["grid"], case["extent"]

    assert cell_count(grid, extent) == case["count"]
    for item in case["points"]:
        assert list(cell_at(grid, extent, tuple(item["point"]))) == item["cell"], item
    for item in case["cells"]:
        cell = tuple(item["cell"])
        assert near(cell_centre(grid, extent, cell), item["centre"]), item
        polygon = cell_polygon(grid, extent, cell)
        assert len(polygon) == len(item["polygon"])
        assert all(near(p, q) for p, q in zip(polygon, item["polygon"], strict=True)), item


@pytest.mark.parametrize("case", GOLDEN["grids"], ids=lambda c: c["name"])
def test_a_cell_contains_its_centre_and_the_counts_are_the_cells_in_the_extent(case):
    grid, extent = case["grid"], case["extent"]
    inside = 0
    for row in range(-3, 80):
        for col in range(-3, 80):
            centre = cell_centre(grid, extent, (col, row))
            assert cell_at(grid, extent, centre) == (col, row)
            inside += in_grid(grid, extent, (col, row))
    # The scan covers the whole sheet of the larger grids; the smaller ones are counted in full.
    if case["count"] < 6000:
        assert inside == case["count"]


def test_hex_cells_are_a_cell_size_apart_and_their_corners_a_circumradius_from_the_centre():
    for orientation in ("pointy", "flat"):
        grid = {"kind": "hex", "orientation": orientation, "cell": {"size": 7}}
        extent = [10, 20, 500, 400]
        radius = 7 / math.sqrt(3)
        for cell in ((3, 4), (4, 3), (0, 0), (-2, 5)):
            centre = cell_centre(grid, extent, cell)
            assert all(
                abs(math.dist(centre, p) - radius) < 1e-9 for p in cell_polygon(grid, extent, cell)
            )
            neighbours = [
                other
                for dc in (-2, -1, 0, 1, 2)
                for dr in (-2, -1, 0, 1, 2)
                if (other := (cell[0] + dc, cell[1] + dr)) != cell
                and abs(math.dist(centre, cell_centre(grid, extent, other)) - 7) < 1e-9
            ]
            assert len(neighbours) == 6, (orientation, cell)


def test_ties_go_to_the_lower_row_and_then_the_lower_column():
    pointy = {"kind": "hex", "orientation": "pointy", "cell": {"size": 2}}
    flat = {"kind": "hex", "orientation": "flat", "cell": {"size": 2}}
    r = 2 / math.sqrt(3)
    extent = [0, 0, 100, 100]

    assert cell_at(pointy, extent, (2, r)) == (0, 0)  # between (0, 0) and (1, 0)
    assert cell_at(flat, extent, (r, 2)) == (0, 0)  # between (0, 0) and (0, 1)
    # A shared edge of squares belongs to the cell on its higher side.
    square = {"kind": "square", "cell": {"size": 10}}

    assert cell_at(square, extent, (10, 5)) == (1, 0)
    assert cell_at(square, extent, (5, 10)) == (0, 1)
    assert cell_at(square, extent, (9.999999, 9.999999)) == (0, 0)


def test_the_count_of_every_kind_is_the_cells_whose_centre_is_in_the_extent():
    for grid in (
        {"kind": "square", "cell": {"size": 30}},
        {"kind": "rect", "cell": {"width": 25, "height": 40}},
        {"kind": "hex", "orientation": "pointy", "cell": {"size": 13}},
        {"kind": "hex", "orientation": "flat", "cell": {"size": 13}},
    ):
        for extent in ([0, 0, 200, 140], [5, -7, 111, 90]):
            brute = sum(in_grid(grid, extent, (c, r)) for r in range(-5, 60) for c in range(-5, 60))
            assert cell_count(grid, extent) == brute, (grid, extent)


def test_a_view_is_a_visual_grid_over_a_system_that_has_none():
    plane = validate_system({"format": F, "kind": "plane", "extent": [0, 0, 1000, 800]})
    grid = {
        "grid": {"kind": "hex", "orientation": "flat", "cell": {"size": 40}, "sub": {"aperture": 4}}
    }

    assert validate_view(grid, plane) == grid
    assert validate_view(None, plane) is None and validate_view({}, plane) is None
    outline = validate_system({"format": F, "kind": "outline", "extent": [0, 0, 10, 10]})
    assert validate_view({"grid": {"kind": "square", "cell": {"size": 2}}}, outline)
    for refused in (
        {"grid": {"kind": "sphere", "cell": {"size": 1}}},
        {"grid": {"kind": "hex", "cell": {"size": 40}}},
        {"grid": {"kind": "square", "cell": {"size": 40}, "measure": {"per_cell": 1, "unit": "m"}}},
        {"grid": {"kind": "square", "cell": {"size": 0.0001}}},
        {"grid": {"kind": "square", "cell": {"size": 40}}, "sphere": 1},
        [],
    ):
        with pytest.raises(MapDocumentError):
            validate_view(refused, plane)
    own = validate_system(
        {"format": F, "kind": "square", "extent": [0, 0, 100, 100], "cell": {"size": 10}}
    )
    with pytest.raises(MapDocumentError):
        validate_view({"grid": {"kind": "square", "cell": {"size": 5}}}, own)


def test_a_stored_grid_is_a_fixed_point_and_measures_nothing_unsaid():
    stored = validate_system(
        {"format": F, "kind": "square", "extent": [0, 0, 100, 100], "cell": {"size": 10.0}}
    )

    assert "measure" not in stored and stored["cell"] == {"size": 10}
    assert validate_system(stored) == stored
