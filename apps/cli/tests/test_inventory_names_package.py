"""The table of other spellings is shared with inventory-web (ADR 0242): the package's file is the
one that is edited, this app carries a copy, and both readers give the same answers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lorenzo_cli.inventory import preprocess

PACKAGE = Path(__file__).resolve().parents[3] / "packages" / "inventory-names"
COPY = Path(preprocess.__file__).with_name("preprocess.toml")

# Outside the repository (an sdist's tests, say) there is no package to compare with.
pytestmark = pytest.mark.skipif(not PACKAGE.is_dir(), reason="packages/inventory-names not found")


def test_the_copy_is_the_packages_table() -> None:
    assert COPY.read_bytes() == (PACKAGE / "preprocess.toml").read_bytes(), (
        "apps/cli's preprocess.toml is stale - run `mise run //apps/cli:sync-names` and commit it."
    )


def test_the_readers_give_the_same_alternatives() -> None:
    vectors = json.loads((PACKAGE / "vectors.json").read_text("utf-8"))
    table = preprocess.builtin()

    assert vectors
    for vector in vectors:
        assert table.alternatives(vector["name"]) == vector["alternatives"], vector["name"]
