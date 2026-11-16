"""The roles a stat definition or a stat group may hold - ADR 0449, RFC 0052.

The API reads some stats by what they are for, not by their name: the weight of an item, the
capacity of a being, the binding of an instance, the groups that make up an item's named lists.
A role names that, so a library's stat may be called anything and a game system's own `ds_weight`
is an ordinary stat. One definition holds a role in a library, and one group; a role-holder
belongs to no game system.
"""

from __future__ import annotations

from typing import Literal, get_args

from lorenzo_api.models import StatValueType

__all__ = [
    "DEFINITION_ROLES",
    "DefinitionRole",
    "GroupRole",
    "GROUP_ROLES",
    "RESERVED_ENUM_VALUES",
    "role_fits",
]

DefinitionRole = Literal[
    "weight",
    "height",
    "price",
    "rarity",
    "hp",
    "armor",
    "size",
    "carry_capacity",
    "containment_capacity",
    "max_item_size",
    "binding",
    "is_container",
]
GroupRole = Literal["physical", "economic", "destroyable", "damaging", "tags"]
DEFINITION_ROLES: tuple[str, ...] = get_args(DefinitionRole)
GROUP_ROLES: tuple[str, ...] = get_args(GroupRole)

_NUMBER = (StatValueType.INT, StatValueType.FLOAT)
# What a new assignment of a role accepts: the types the API reads that role as. `rarity` is read
# as a number by the named field and shown as text by the hover card, so a text or an enum fit.
# The migration gave each role to every existing stat of that name whatever its type, so each read
# answers as it did; only an assignment made now is checked.
_TYPES: dict[str, tuple[StatValueType, ...]] = {
    "weight": _NUMBER,
    "height": _NUMBER,
    "price": _NUMBER,
    "rarity": (*_NUMBER, StatValueType.TEXT, StatValueType.ENUM),
    "hp": _NUMBER,
    "armor": _NUMBER,
    "size": _NUMBER,
    "carry_capacity": _NUMBER,
    "containment_capacity": _NUMBER,
    "max_item_size": _NUMBER,
    "binding": (StatValueType.ENUM,),
    "is_container": (StatValueType.BOOL,),
}

# The values of a role's stat the API writes or reads as text: `none` of a binding is what a
# lifted binding is set to (ADR 0129), so it is neither renamed nor removed.
RESERVED_ENUM_VALUES = {"binding": frozenset({"none"})}


def role_fits(role: str, value_type: StatValueType) -> bool:
    """Whether a stat of this type may take the role now."""
    return value_type in _TYPES[role]
