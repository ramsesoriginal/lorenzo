"""The conservative guard shares fixtures with canonical parser tests in Writing."""

import json
from pathlib import Path

import pytest

from lorenzo_api.manuscript_split_points import split_points

CASES = json.loads(
    (Path(__file__).parent / "fixtures/manuscript-splits.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_safe_boundary(case: dict) -> None:
    left, right = case["marked"].split("<SPLIT>")
    source = left + right
    assert (len(left) in split_points(source)) == case["allowed"]
    assert source[: len(left)] + source[len(left) :] == source


def test_long_prose_boundaries_are_stable() -> None:
    source = "Paragraph 🐉.\n\n" * 10000
    points = split_points(source)
    assert len(points) == 9999
    assert points[0] == len("Paragraph 🐉.\n\n")
