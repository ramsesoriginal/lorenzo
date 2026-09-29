"""The same worker against the sheet's own data, when a local checkout of the upstream repository
is given (RFC 0025 R1's spike, kept runnable).

    git clone https://github.com/morepurplemorebetter/MPMBs-Character-Record-Sheet
    export LORENZO_UPSTREAM_CORPUS=/path/to/MPMBs-Character-Record-Sheet
    uv run pytest tests/test_evalworker_upstream.py

Upstream is GPL-3.0, so none of it is copied here. Last checked against commit
076507da369d3982cde9f96dc1ca309000ee8ad1 (2026-09): 84 weapons, 14 armours, 107 gear items,
11 packs, 37 tools and 16 ammunition entries; 12 stubbed names; live V8 heap under 1 MB.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lorenzo_cli.evalworker import EvalRequest, WorkerEngine, read_sources

_ROOT = os.environ.get("LORENZO_UPSTREAM_CORPUS")

pytestmark = pytest.mark.skipif(not _ROOT, reason="LORENZO_UPSTREAM_CORPUS is not set")


def test_the_sheets_own_srd_data_evaluates_and_homebrew_patches_it() -> None:
    root = Path(_ROOT or "")
    variables = root / "_variables"
    homebrew = next((root / "additional content" / "Gear").glob("Expanded Armory*.js"))

    result = WorkerEngine().evaluate(
        EvalRequest(
            base=read_sources(
                [variables / "ListsSources.js", variables / "Lists.js", variables / "ListsGear.js"]
            ),
            files=read_sources([homebrew]),
        )
    )

    assert result.ok
    assert [f.status for f in result.files] == ["ok", "ok", "ok", "ok"]
    assert result.counts["ArmourList"] >= 14
    assert result.counts["WeaponsList"] >= 84
    assert result.counts["GearList"] >= 100
    assert result.heap_used_mb < 64
    origins = set(result.origins["WeaponsList"].values())
    assert origins == {"ListsGear.js", homebrew.name}
    # Every weapon type the sheet itself uses, including the ones that are not items.
    types = {w.get("type") for w in result.lists["WeaponsList"].values()}
    assert {"Simple", "Martial", "Natural", "Cantrip", "Spell"} <= types
