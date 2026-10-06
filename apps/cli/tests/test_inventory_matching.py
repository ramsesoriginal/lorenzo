"""Finding a line's item, and other ways to write a name (ADR 0193)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from lorenzo_cli.client.models import ItemOut
from lorenzo_cli.inventory import preprocess
from lorenzo_cli.inventory.format import Line
from lorenzo_cli.inventory.matching import Library, match


def item(n: int, title: str) -> ItemOut:
    nothing: dict[str, Any] = dict.fromkeys(
        ("weight", "height", "price", "rarity", "hp", "armor", "container_entity_id", "quantity"),
        None,
    )
    return ItemOut.model_validate(
        {
            **nothing,
            "entity_id": str(uuid.UUID(int=n)),
            "title": title,
            "prototype_ids": [],
            "is_container": None,
            "descriptions": [],
            "pictures": [],
            "physical_stats": [],
            "economic_stats": [],
            "destroyable_stats": [],
            "damaging_stats": [],
            "tags": [],
            "created_by": None,
            "updated_by": None,
            "updated_at": "2026-01-01T00:00:00Z",
            "in_public_catalog": True,
        }
    )


def library(*items: ItemOut, slugs: dict[str, int] | None = None) -> Library:
    found = Library()
    for one in items:
        found.items[one.entity_id] = one
        found.titles.setdefault(one.title.strip().lower(), []).append(one)
    for slug, n in (slugs or {}).items():
        found.slugs[slug] = uuid.UUID(int=n)
    return found


ROPE, TORCH, ROPE2 = item(1, "Rope"), item(2, "Torch"), item(3, "Rope")
TABLE = preprocess.builtin()


def test_an_instance_id_of_the_owners_own_item_is_that_item_moved() -> None:
    mine = uuid.UUID(int=99)
    found = library(ROPE)
    found.instances.add(mine)

    result = match(Line("Old rope", ref=str(mine)), found, TABLE)

    assert (result.via, result.instance_id, result.item) == ("instance", mine, None)


def test_the_order_is_ref_then_item_then_title() -> None:
    found = library(ROPE, TORCH, slugs={"torch": 2})

    by_id = match(Line("Anything", ref=str(ROPE.entity_id)), found, TABLE)
    by_slug = match(Line("Anything", ref="TORCH"), found, TABLE)
    by_item = match(Line("Anything", item=str(TORCH.entity_id)), found, TABLE)
    by_title = match(Line("  rope "), found, TABLE)
    # A ref that finds nothing falls through to the name.
    fallen = match(Line("Torch", ref="no-such-slug"), found, TABLE)

    assert [r.via for r in (by_id, by_slug, by_item, by_title, fallen)] == [
        "id",
        "slug",
        "id",
        "title",
        "title",
    ]
    assert by_id.item == ROPE and by_slug.item == TORCH and by_title.item == ROPE


def test_a_title_that_names_several_items_is_not_guessed() -> None:
    result = match(Line("Rope"), library(ROPE, ROPE2), TABLE)

    assert result.via == "placeholder" and result.item is None
    assert "title of 2 items" in (result.note or "")


def test_another_spelling_finds_an_item_when_the_name_does_not() -> None:
    found = library(item(5, "Rope"), item(6, "Potion of healing"), item(7, "Crossbow, heavy"))

    assert match(Line("Seil"), found, TABLE).via == "spelling"
    assert match(Line("Seil"), found, TABLE).item == found.items[uuid.UUID(int=5)]
    assert match(Line("Rope (50 ft)"), found, TABLE).item == found.items[uuid.UUID(int=5)]
    assert match(Line("Ropes"), found, TABLE).item == found.items[uuid.UUID(int=5)]
    assert match(Line("Heiltrank"), found, TABLE).item == found.items[uuid.UUID(int=6)]
    assert match(Line("Heavy crossbow"), found, TABLE).item == found.items[uuid.UUID(int=7)]


def test_what_nothing_finds_is_a_placeholder() -> None:
    result = match(Line("Hydra Zahn"), library(ROPE), TABLE)

    assert (result.via, result.item, result.note) == ("placeholder", None, None)


def test_alternatives_come_most_likely_first_and_never_include_the_name() -> None:
    assert TABLE.alternatives("Torches") == ["torch"]
    assert TABLE.alternatives("Hanfseil 50 ft") == ["hanfseil", "rope, hempen"]
    assert TABLE.alternatives("Rope") == []
    assert TABLE.alternatives("Fackeln") == ["torches", "torch"]


def test_a_table_of_ones_own_goes_on_top_of_the_built_in_one(tmp_path: Path) -> None:
    mine = tmp_path / "mine.toml"
    mine.write_text('[names]\n"seil" = "line"\n[words]\n"kiste" = "chest"\n', encoding="utf-8")

    table = preprocess.load(mine)

    assert table.alternatives("Seil") == ["line"]
    assert table.alternatives("Kiste") == ["chest"]
    assert table.alternatives("Schild") == ["shield"]
