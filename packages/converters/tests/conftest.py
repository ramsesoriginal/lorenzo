"""Made-up inventories with the quirks of a real spreadsheet; never a real player's rows."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from openpyxl import Workbook

ITEM_HEADER = [
    "Name", "Anzahl", "Gewicht", "gesch. Wert", "Container", "Art", "Beschreibung", "Totalgewicht",
]  # fmt: skip

# Name, count, weight of one, value, container, kind, description. Rucksack is spelled two ways, a
# bag sits inside a bag, one weight is a formula, one is empty, one description has two lines.
ITEMS: list[list[object]] = [
    ["Dolch", 1, 1, "2 G", "holding", "weapon", None],
    ["Bolzen", 20, 0.04, "5 Cp", "Köcher", "ammo", None],
    ["Köcher", 1, 1, "1 G", "holding", "container", None],
    ["Rucksack", 1, 5, "2 G", "holding", "contianer", None],
    ["Seil 50 ft", 1, 10, "1 G", "rucksack", "gear", None],
    ["Zunderkasten", 1, None, "5 Sb", "Rucksack", "gear", None],
    ["Tragetasche", 1, 0, "2000 G", "Rucksack", "container", None],
    ["Edelsteine", 3, 0.1, "?", "Tragetasche", "item", "Beutel mit Edelsteinen"],
    ["Brief", 1, 0.01, None, "Tragetasche", "item", "Zeile eins\nZeile zwei"],
    ["Schleuder", 1, "=B9*2", "1 G", "holding", "weapon", None],
    ["Ersatzumhang", 1, 2, None, "Kiste", "gear", None],
    ["Pilz", 2, 0.1, "0", "Korb", "consumable", "mit | Strich"],
    ["Glücksbringer", 1, 0, 0, None, "item", None],
]
CONTAINERS: list[list[object]] = [
    ["Name", "Ort", "Gewicht des Inhalts"],
    ["holding", "Burg", "=SUM(A1)"],
    ["Rucksack", "Burg", None],
    ["Tragetasche", "Burg", None],
    ["Köcher", "Burg", None],
    ["Kiste", "Hafenstadt", None],
    ["Leere Tasche", "Burg", None],
]


@pytest.fixture
def make_book(tmp_path: Path) -> Callable[..., Path]:
    def make(
        items: list[list[object]] | None = None,
        containers: list[list[object]] | None = None,
        header: list[object] | None = None,
        name: str = "inventory.xlsx",
    ) -> Path:
        book = Workbook()
        sheet = book.active
        assert sheet is not None
        sheet.title = "Items"
        sheet.append(header or ITEM_HEADER)
        for row in ITEMS if items is None else items:
            sheet.append([*row, *([None] * (len(ITEM_HEADER) - 1 - len(row))), "=1"])
        if containers is None or containers:
            places = book.create_sheet("Container")
            for row in CONTAINERS if containers is None else containers:
                places.append(row)
        path = tmp_path / name
        book.save(path)
        return path

    return make
