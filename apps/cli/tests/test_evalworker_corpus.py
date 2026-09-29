"""The golden corpus (ADR 0138): fixture files in the shapes of MPMB's syntax templates, and the
exact tagged JSON the worker must return for each.

It is what makes the engine replaceable: a second engine passes when it returns the same
`expected.json` files. To rewrite them after a deliberate change, run with
LORENZO_UPDATE_GOLDEN=1 and read the diff.

The upstream templates and the sheet's own data are GPL-3.0 and are not copied into this
repository; test_evalworker_upstream.py runs against a local checkout when one is given.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from lorenzo_cli.evalworker import EvalRequest, EvalResult, WorkerEngine, read_sources

CORPUS = Path(__file__).parent / "corpus"
CASES = sorted(path for path in CORPUS.iterdir() if (path / "case.json").exists())


def snapshot(result: EvalResult) -> dict[str, Any]:
    """The parts of a result that are a pure function of the input (not the heap or timings)."""
    return {
        "ok": result.ok,
        "restarts": result.restarts,
        "files": [[f.name, f.role, f.status] for f in result.files],
        "lists": result.lists,
        "origins": result.origins,
        "overrides": [[o.list, o.key, o.replaced_file, o.by_file] for o in result.overrides],
        "stubs": [[s.name, s.calls, s.first_file] for s in result.stubs],
        "stubs_in_data": [[s.path, s.stub] for s in result.stubs_in_data],
    }


def run_case(case: Path) -> EvalResult:
    spec = json.loads((case / "case.json").read_text())
    request = EvalRequest(
        base=read_sources([case / name for name in spec["base"]]),
        files=read_sources([case / name for name in spec["files"]]),
    )
    return WorkerEngine().evaluate(request)


@pytest.mark.parametrize("case", CASES, ids=lambda path: path.name)
def test_the_worker_returns_the_golden_json(case: Path) -> None:
    actual = snapshot(run_case(case))
    expected_path = case / "expected.json"
    if os.environ.get("LORENZO_UPDATE_GOLDEN"):
        expected_path.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n")
    assert actual == json.loads(expected_path.read_text())


def test_every_case_has_a_description_and_a_golden_file() -> None:
    assert CASES, "no corpus cases found"
    for case in CASES:
        spec = json.loads((case / "case.json").read_text())
        assert spec["about"], f"{case.name} needs an 'about'"
        assert (case / "expected.json").exists() or os.environ.get("LORENZO_UPDATE_GOLDEN")
