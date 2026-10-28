"""The parser-aware guard shares fixtures with canonical parser tests in Writing."""

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
    points = split_points(source)
    assert points == case["points"]
    assert (len(left) in points) == case["allowed"]
    assert source[: len(left)] + source[len(left) :] == source


def test_long_prose_boundaries_are_stable() -> None:
    source = "Paragraph 🐉.\n\n" * 10000
    points = split_points(source)
    assert len(points) == 9999
    assert points[0] == len("Paragraph 🐉.\n\n")


def test_many_distinct_headings() -> None:
    source = "".join(f"# Section {i}\n\n" for i in range(10000))
    assert len(split_points(source)) == 9999


def test_long_heading_suffix_chain_and_unclosed_labels() -> None:
    # Neither a failed label search nor each removed numeric suffix may scan
    # the same large tail again (ADR 0110). Code keeps the label test in this guard.
    heading = "# Section" + "-2" * 25000 + "\n\n"
    assert split_points(heading + "After.") == [len(heading)]
    code = "```\n" + "[^" * 25000 + "\n```\n\n"
    assert split_points(code + "After.") == [len(code)]
