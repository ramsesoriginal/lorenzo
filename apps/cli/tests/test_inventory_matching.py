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
    assert TABLE.alternatives("Hanfseil 50 ft") == ["hanfseil", "rope, hempen (50 feet)"]
    assert TABLE.alternatives("Rope") == []
    assert TABLE.alternatives("Fackeln") == ["torch", "torches"]


def test_a_table_of_ones_own_goes_on_top_of_the_built_in_one(tmp_path: Path) -> None:
    mine = tmp_path / "mine.toml"
    mine.write_text('[names]\n"seil" = "line"\n[words]\n"kiste" = "chest"\n', encoding="utf-8")

    table = preprocess.load(mine)

    assert table.alternatives("Seil") == ["line"]
    assert table.alternatives("Kiste") == ["chest"]
    assert table.alternatives("Schild") == ["shield"]


# The two real inventories this table was written for (the LaTeX list and the spreadsheet), as
# their names stand once a converter has taken the counts and markers off: each is looked up in a
# catalog written the way the SRD and the sheets write titles.
CATALOG = [
    "Dagger", "Quarterstaff", "Greatclub", "Mace", "Crossbow, light", "Crossbow bolts (20)",
    "Bedroll", "Waterskin", "Hammer", "Signal whistle", "Mess kit", "Tinderbox", "Bell",
    "Blanket", "Lantern, hooded", "Alms box", "Holy symbol (amulet)", "Incense (block)",
    "Acid (vial)", "Ring of resistance", "Spell scroll (dimension door)", "Clothes, common",
    "Leather armor", "Shield", "Backpack", "Bag of holding", "Climber's kit", "Crowbar",
    "Fishing tackle", "Hammer, sledge", "Pick, miner's", "Playing card set",
    "Ink (1 ounce bottle)", "Ink pen", "Spellbook", "Pearl (100 gp)", "Emerald (100 gp)",
    "Manual of golems", "Gold bar", "Dart", "Torch", "Candle", "Rations (1 day)",
    "Ball bearings (bag of 1,000)", "Chalk (1 piece)", "Paper (one sheet)", "Pouch", "Sack",
    "Rope, hempen (50 feet)", "Rope, silk (50 feet)", "Barrel", "Saddle, riding", "Saddlebags",
    "Riding horse", "Grappling hook", "Tinker's tools", "Potion of healing",
    "Potion of greater healing", "Cloak of displacement", "Battleaxe", "Greatsword",
    "Crossbow, heavy", "Longbow", "Shortsword", "Scimitar", "Longsword", "Amulet",
    "Bullets, firearm (10)", "Diamond",
]  # fmt: skip

KNOWN = {
    "Quarterstaff": "Quarterstaff",
    "Crossbow Bolts": "Crossbow bolts (20)",
    "Flint 'n Steel": "Tinderbox",
    "Belt pouch": "Pouch",
    "Hooded Lantern": "Lantern, hooded",
    "Holy Symbol": "Holy symbol (amulet)",
    "Sticks of Incense": "Incense (block)",
    "Vial of Acid": "Acid (vial)",
    "Ring of magic Resistance": "Ring of resistance",
    "Dimension Door Scroll": "Spell scroll (dimension door)",
    "Common clothes": "Clothes, common",
    "Bag of Holding ($125m^3$)": "Bag of holding",
    "Climbers Kit": "Climber's kit",
    "Sledgehammer": "Hammer, sledge",
    "Miners Pick": "Pick, miner's",
    "Pickaxe": "Pick, miner's",
    "Bottle of black ink": "Ink (1 ounce bottle)",
    "Quill": "Ink pen",
    "Pearl": "Pearl (100 gp)",
    "Manual of Iron Golem": "Manual of golems",
    "Goldbarren": "Gold bar",
    "Diamanten": "Diamond",
    "Darts": "Dart",
    "Torches": "Torch",
    "Day rations": "Rations (1 day)",
    "Ball Bearings": "Ball bearings (bag of 1,000)",
    "Chalk": "Chalk (1 piece)",
    "Paper": "Paper (one sheet)",
    "16m Rope, Hempen": "Rope, hempen (50 feet)",
    "untrustworthy 16m Rope, Hempen": "Rope, hempen (50 feet)",
    "Sack, $0.5m^3$": "Sack",
    "Fass": "Barrel",
    "Barrels": "Barrel",
    "light brown Riding horse": "Riding horse",
    "Saddle Bag": "Saddlebags",
    "Saddle": "Saddle, riding",
    "Rations": "Rations (1 day)",
    "normal pistole bullets": "Bullets, firearm (10)",
    "Tinder box": "Tinderbox",
    "Mess Kit": "Mess kit",
    "Enterhacken": "Grappling hook",
    "Hanfseil 50 ft": "Rope, hempen (50 feet)",
    "Seide Seil 50 ft": "Rope, silk (50 feet)",
    "Seide Seil 150 ft": "Rope, silk (50 feet)",
    "Tinkers Tools": "Tinker's tools",
    "Münzbeutel": "Pouch",
    "Amulett": "Amulet",
    "Poition of Greater Healing": "Potion of greater healing",
    "Cloak of Dissplacement": "Cloak of displacement",
    "Battle Axe (low quality)": "Battleaxe",
    "great sword": "Greatsword",
    "heavy crossbow": "Crossbow, heavy",
    "Kurzschwert": "Shortsword",
    "Lanbogen": "Longbow",
    "Scimital": "Scimitar",
}


def test_the_names_in_the_two_real_inventories_find_their_items() -> None:
    from_titles = {t.lower(): i for i, t in enumerate(CATALOG, start=100)}
    found = library(
        *(item(n, title) for title, n in zip(CATALOG, from_titles.values(), strict=True))
    )
    wrong = {}
    for written, wanted in KNOWN.items():
        result = match(Line(written), found, TABLE)
        got = result.item.title if result.item is not None else None
        if got != wanted:
            wrong[written] = got
    assert wrong == {}


def test_homebrew_creatures_and_one_offs_stay_unsorted() -> None:
    found = library(*(item(100 + i, title) for i, title in enumerate(CATALOG)))
    for name in (
        "Hydra Zahn",
        "Gorilla Fleisch",
        "Kopflose skelette",
        "Farasi",
        "Magic Pseudo Dragon (Gundula)",
        "Letter from a dead colleague",
        "Explosions for Dummies",
        "Black Feathers Daggers with Box (schwarze Armee)",
    ):
        assert match(Line(name), found, TABLE).via == "placeholder", name


MORE_CATALOG = [
    "Shortsword", "Handaxe", "Greataxe", "Warhammer", "Morningstar", "Quarterstaff", "Javelin",
    "Sling", "Halberd", "Rapier", "Arrows (20)", "Quiver", "Leather armor", "Chain shirt",
    "Chain mail", "Scale mail", "Plate armor", "Studded leather armor", "Backpack", "Bedroll",
    "Lantern, bullseye", "Tent, two-person", "Oil (flask)", "Candle", "Crowbar", "Piton",
    "Healer's kit", "Thieves' tools", "Spellbook", "Parchment (one sheet)", "Soap",
    "Hunting trap", "Spyglass", "Component pouch", "Bucket", "Chest", "Holy water (flask)",
    "Alchemist's fire (flask)", "Antitoxin (vial)", "Caltrops (bag of 20)", "Pole (10-foot)",
    "Shovel", "Bag of holding", "Potion of greater healing", "Potion of healing", "Spell scroll",
    "Ruby (1,000 gp)", "Gold bar", "Arcane focus (orb)", "Wand", "Saddlebags", "Riding horse",
    "Rations (1 day)", "Ink (1 ounce bottle)", "Mirror, steel", "Climber's kit", "Waterskin",
]  # fmt: skip

MORE_KNOWN = {
    "Short sword": "Shortsword",
    "Hand axe": "Handaxe",
    "Great axe": "Greataxe",
    "War hammer": "Warhammer",
    "Morning star": "Morningstar",
    "Quaterstaff": "Quarterstaff",
    "Kampfstab": "Quarterstaff",
    "Wurfspeer": "Javelin",
    "Schleuder": "Sling",
    "Hellebarde": "Halberd",
    "Degen": "Rapier",
    "Pfeile": "Arrows (20)",
    "Köcher": "Quiver",
    "Leather armour": "Leather armor",
    "Lederrüstung": "Leather armor",
    "Kettenhemd": "Chain shirt",
    "Kettenpanzer": "Chain mail",
    "Schuppenpanzer": "Scale mail",
    "Plattenpanzer": "Plate armor",
    "Beschlagenes Leder": "Studded leather armor",
    "Back pack": "Backpack",
    "Bed roll": "Bedroll",
    "Bettrolle": "Bedroll",
    "Blendlaterne": "Lantern, bullseye",
    "Zelt": "Tent, two-person",
    "Ölflasche": "Oil (flask)",
    "Kerzen": "Candle",
    "Brecheisen": "Crowbar",
    "Kletterhaken": "Piton",
    "Heilerset": "Healer's kit",
    "Thieves tools": "Thieves' tools",
    "Zauberbuch": "Spellbook",
    "Pergament": "Parchment (one sheet)",
    "Seife": "Soap",
    "Falle": "Hunting trap",
    "Fernrohr": "Spyglass",
    "Komponentenbeutel": "Component pouch",
    "Eimer": "Bucket",
    "Truhe": "Chest",
    "Weihwasser": "Holy water (flask)",
    "Alchemists fire": "Alchemist's fire (flask)",
    "Gegengift": "Antitoxin (vial)",
    "Caltrops": "Caltrops (bag of 20)",
    "Stange": "Pole (10-foot)",
    "Schaufel": "Shovel",
    "Nimmervoller Beutel": "Bag of holding",
    "Greater healing potion": "Potion of greater healing",
    "Healing potion": "Potion of healing",
    "Zauberschriftrolle": "Spell scroll",
    "Rubin": "Ruby (1,000 gp)",
    "Goldbarren": "Gold bar",
    "Arcane focus - Orb": "Arcane focus (orb)",
    "Zauberstab": "Wand",
    "Satteltaschen": "Saddlebags",
    "Reitpferd": "Riding horse",
    "Tagesrationen": "Rations (1 day)",
    "Tinte": "Ink (1 ounce bottle)",
    "Spiegel": "Mirror, steel",
    "Kletterausrüstung": "Climber's kit",
    "Wasserflasche": "Waterskin",
}


def test_more_names_players_are_likely_to_write_find_their_items() -> None:
    found = library(*(item(200 + i, title) for i, title in enumerate(MORE_CATALOG)))
    wrong = {}
    for written, wanted in MORE_KNOWN.items():
        result = match(Line(written), found, TABLE)
        got = result.item.title if result.item is not None else None
        if got != wanted:
            wrong[written] = got
    assert wrong == {}
