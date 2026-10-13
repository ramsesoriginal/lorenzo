"""A `Content` with every field of it, and of every dataclass inside it, filled - for the release
document tests (ADR 0214), which need to know that nothing is left out. Built in memory with ids
that are the same on every run, so the golden file of the format can be compared with it.
"""

import uuid
from decimal import Decimal

from lorenzo_api.models import StatValueType
from lorenzo_api.repository_content import (
    Content,
    Formula,
    InformationData,
    PayloadData,
    StatValue,
)

PICTURE = bytes(range(256)) * 4
DOCUMENT = b"%PDF-1.7 a handout\n" * 20


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def full_content() -> Content:
    t = _id(1)
    sword, dagger, orc, chest, guild = (_id(n) for n in (10, 11, 12, 13, 14))
    group, other_group = _id(20), _id(21)
    strength, speed, mood, damage, reach, load, might, name_text = (_id(n) for n in range(30, 38))
    info_lore, info_map = _id(40), _id(41)
    p_text, p_number, p_picture, p_picture_again, p_document = (_id(n) for n in range(50, 55))
    upstream, source_entity, source_group, source_definition, gone, parent = (
        _id(n) for n in range(60, 66)
    )

    c = Content(tenant_id=t)
    c.entities = {sword: "Longsword", dagger: "Dagger", orc: "Orc", chest: "Chest", guild: "Guild"}
    c.kinds[sword] = {"item"}
    c.kinds[dagger] = {"item", "item_instance"}
    c.kinds[orc] = {"being", "character"}
    c.kinds[chest] = {"item"}
    c.in_public_catalog = {sword: True, dagger: False, chest: True}
    c.slugs = {sword: "longsword", orc: "orc"}
    c.prototypes = [(dagger, sword), (sword, chest)]
    c.groups = {
        group: {"name": "Abilities", "priority": 3, "mandatory": True},
        other_group: {"name": "Extras", "priority": 0, "mandatory": False},
    }
    c.definitions = {
        strength: {"name": "Strength", "value_type": StatValueType.INT, "group": group},
        speed: {"name": "Speed", "value_type": StatValueType.FLOAT, "group": group},
        mood: {"name": "Mood", "value_type": StatValueType.ENUM, "group": group},
        damage: {"name": "Damage", "value_type": StatValueType.INT, "group": group},
        reach: {"name": "Reach", "value_type": StatValueType.BOOL, "group": other_group},
        load: {"name": "Load", "value_type": StatValueType.INT, "group": other_group},
        might: {"name": "Might", "value_type": StatValueType.INT, "group": other_group},
        name_text: {"name": "Title", "value_type": StatValueType.TEXT, "group": other_group},
    }
    # The display fields of a definition (ADR 0278, 0279): every one filled somewhere, hints too.
    for position, definition in enumerate(c.definitions.values()):
        definition.update(
            unit="kg" if position % 2 else None,
            adjustable_in_play=bool(position % 2),
            pin=bool(position % 3),
            signed=bool(position % 2),
            position=position,
            hints={"max_hint": None, "min_hint": None, "resolved_hint": None},
        )
    c.definitions[strength]["hints"] = {
        "max_hint": speed,
        "min_hint": damage,
        "resolved_hint": None,
    }
    c.enum_values[mood] = [("calm", 0), ("angry", 1), ("héroïque", 2)]
    c.entity_groups = [(sword, group), (dagger, other_group)]
    c.stats = {
        (sword, strength): StatValue(10, None, None, None),
        (sword, mood): StatValue(None, "calm", None, None),
        (sword, speed): StatValue(None, None, 1.5, None),
        (dagger, speed): StatValue(None, None, 0.1 + 0.2, None),
        (orc, speed): StatValue(None, None, float("nan"), None),
        (chest, speed): StatValue(None, None, float("inf"), None),
        (guild, speed): StatValue(None, None, float("-inf"), None),
        (sword, reach): StatValue(None, None, None, True),
        (dagger, reach): StatValue(None, None, None, False),
        (sword, name_text): StatValue(None, "the blade", None, None),
        (orc, strength): StatValue(0, None, None, None),
    }
    c.formulas = {
        (sword, damage): Formula(
            kind="linear",
            source=strength,
            multiplier=Decimal("0.50"),
            offset=Decimal("-1"),
            round_mode="floor",
        ),
        (dagger, reach): Formula(
            kind="comparison",
            left=strength,
            comparator="ge",
            right=speed,
            true_value="yes",
            false_value="no",
        ),
        (orc, reach): Formula(
            kind="comparison",
            left=strength,
            comparator="lt",
            right_constant=Decimal("15.250"),
        ),
        (chest, load): Formula(kind="contents", source=strength),
        (sword, might): Formula(
            kind="sum",
            offset=Decimal("1"),
            round_mode="none",
            terms=[(strength, Decimal("1")), (damage, Decimal("2.5"))],
        ),
        (dagger, might): Formula(kind="sum", offset=Decimal("0"), round_mode="none", terms=[]),
    }
    c.containment = {dagger: (chest, 3), orc: (chest, 1)}
    c.ownership = {sword: orc}
    c.group_members = [(guild, orc)]
    c.information = {
        info_lore: InformationData(sword, "Lore", "description", True, 0),
        info_map: InformationData(sword, "Maps", "note", False, 1),
    }
    c.payloads = {
        p_text: PayloadData(
            info_lore, 0, "description", {"locale": "en", "content": "Forged for [[orc]]. ✓"}
        ),
        p_number: PayloadData(info_lore, 1, "number", {"value": Decimal("2.50")}),
        p_picture: PayloadData(info_map, 0, "picture", {"data": PICTURE, "file_type": "png"}),
        p_picture_again: PayloadData(info_map, 1, "picture", {"data": PICTURE, "file_type": "jpg"}),
        p_document: PayloadData(
            info_map, 2, "document", {"data": DOCUMENT, "filename": "maps.pdf", "file_type": "pdf"}
        ),
    }
    c.knowledge = [(info_map, orc)]

    links = c.links
    links.entity = {chest: source_entity}
    links.stat_group = {other_group: source_group}
    links.stat_definition = {load: source_definition}
    links.origin_tenant = {
        source_entity: upstream,
        source_group: upstream,
        source_definition: upstream,
        gone: upstream,
    }
    links.merged = {source_group}
    links.deleted["entity"] = {gone}
    links.deleted["stat_definition"] = {_id(70), _id(71)}
    links.snapshots = {
        source_entity: {
            "name": "Chest",
            "kinds": ["item"],
            "in_public_catalog": True,
            "slug": None,
            "prototypes": [str(parent)],
            "stats": {str(source_definition): 1.5, str(source_group): None},
            "formulas": {},
        },
        gone: {"name": "Gone", "stats": {"a": [1, 2.5, "x", False]}},
    }
    links.copies = {upstream, _id(80)}
    links.attachments[upstream] = {(source_entity, parent), (gone, parent)}
    links.attachments[_id(81)] = set()
    return c
