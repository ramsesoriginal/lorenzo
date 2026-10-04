"""This parser reads a pack's list as apps/api's does (ADR 0149, 0150).

Both are held to the same examples, in apps/api/tests/data/pack_lists.json. They are read here, not
with the unit tests, because of where CI runs a test: the unit tests don't run for a change to
apps/api (ADR 0148), but the end-to-end suite does, so a change to the examples, or to the API's
parser, reaches this parser's check. It needs no stack.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lorenzo_cli.importer.packs import PackLine, parse_description

EXAMPLES = Path(__file__).resolve().parents[3] / "api" / "tests" / "data" / "pack_lists.json"
CASES: list[dict[str, Any]] = json.loads(EXAMPLES.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_reads_every_shared_example_as_the_api_does(case: dict[str, Any]) -> None:
    expected = [
        PackLine(depth, quantity, label, slug) for depth, quantity, label, slug in case["lines"]
    ]
    assert parse_description(case["text"]) == expected
