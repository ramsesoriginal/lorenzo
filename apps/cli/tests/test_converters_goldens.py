"""The ledgers `lorenzo-convert` is tested to write (packages/converters/tests/golden, ADR 0246)
are read by the importer's own parser, so a converter cannot write what it reads differently."""

from __future__ import annotations

from pathlib import Path

import pytest

from lorenzo_cli.inventory import format as ledger

GOLDEN = Path(__file__).resolve().parents[3] / "packages" / "converters" / "tests" / "golden"
FILES = sorted(GOLDEN.glob("*.ledger")) if GOLDEN.is_dir() else []

# Outside the repository (an sdist's tests, say) there are no goldens to read.
pytestmark = pytest.mark.skipif(not FILES, reason="packages/converters goldens not found")


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_the_importer_reads_the_golden_without_complaint(path: Path) -> None:
    inventory = ledger.parse(path.read_text("utf-8"))

    assert [str(problem) for problem in inventory.problems] == []
    assert [str(warning) for warning in inventory.warnings] == []
    assert inventory.owner == "Mira"
    assert ledger.count(inventory) > 0


def test_the_sheet_golden_keeps_its_nesting_and_places() -> None:
    inventory = ledger.parse((GOLDEN / "sheet-de.ledger").read_text("utf-8"))
    rucksack = next(line for line in inventory.equipped if line.name == "Rucksack")
    kiste = next(line for line in inventory.not_carried if line.name == "Kiste")

    assert [line.name for line in rucksack.contents[2].contents] == ["Edelsteine", "Brief"]
    assert rucksack.contents[2].contents[1].description == "Zeile eins\nZeile zwei"
    assert kiste.place == "Hafenstadt"
    assert kiste.contents[0].name == "Ersatzumhang"
