"""Where an enum value's text is held, and what renames it - ADR 0385.

An enum value has no foreign key to its row: an entry's value of an enum stat is the text
(`entity_stat.value_text`), and a comparison formula whose target is the enum returns one of two
texts (`computed_stat_comparison.true_value` and `false_value`). So "is this value in use" and
"rename it" are the same two places, and live here once for the routes and for the update engine.
"""

import uuid

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import ComputedStatComparison, EntityStat

__all__ = [
    "RESERVED_ENUM_VALUES",
    "RESERVED_STAT_NAMES",
    "EnumValueUses",
    "enum_value_uses",
    "rename_enum_value_text",
]

# The stats the API reads by name, tenant data it looks up rather than a column of its own: the
# item views' six (`v_item`, `v_item_instance`), the capacity checks (capacity.py), the binding
# stat (binding.py) and the container tag (schemas/items.py). Renaming one would change what the
# API does without a word, so it is refused.
RESERVED_STAT_NAMES = frozenset(
    {
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
    }
)
# The values of those stats the API writes or reads as text.
RESERVED_ENUM_VALUES = {"binding": frozenset({"none"})}


class EnumValueUses:
    """What holds one value of an enum stat: entries that hold it and formulas that return it."""

    def __init__(self, entries: int, formulas: int) -> None:
        self.entries = entries
        self.formulas = formulas

    def __bool__(self) -> bool:
        return bool(self.entries or self.formulas)

    def describe(self, value: str) -> str:
        parts = []
        if self.entries:
            parts.append(f"held by {self.entries} entr{'y' if self.entries == 1 else 'ies'}")
        if self.formulas:
            parts.append(f"returned by {self.formulas} formula{'' if self.formulas == 1 else 's'}")
        return f"{value!r} is still " + " and ".join(parts)


def _comparison_returns(
    tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, value: str
) -> tuple[ColumnElement[bool], ...]:
    return (
        ComputedStatComparison.tenant_id == tenant_id,
        ComputedStatComparison.stat_definition_id == stat_definition_id,
        or_(
            ComputedStatComparison.true_value == value, ComputedStatComparison.false_value == value
        ),
    )


async def enum_value_uses(
    session: AsyncSession, tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, value: str
) -> EnumValueUses:
    entries = await session.scalar(
        select(func.count())
        .select_from(EntityStat)
        .where(
            EntityStat.tenant_id == tenant_id,
            EntityStat.stat_definition_id == stat_definition_id,
            EntityStat.value_text == value,
        )
    )
    formulas = await session.scalar(
        select(func.count())
        .select_from(ComputedStatComparison)
        .where(*_comparison_returns(tenant_id, stat_definition_id, value))
    )
    return EnumValueUses(entries or 0, formulas or 0)


async def rename_enum_value_text(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    old: str,
    new: str,
) -> None:
    """Rewrites every stored copy of `old` to `new`, in the caller's transaction."""
    await session.execute(
        update(EntityStat)
        .where(
            EntityStat.tenant_id == tenant_id,
            EntityStat.stat_definition_id == stat_definition_id,
            EntityStat.value_text == old,
        )
        .values(value_text=new)
    )
    for column in (ComputedStatComparison.true_value, ComputedStatComparison.false_value):
        await session.execute(
            update(ComputedStatComparison)
            .where(
                ComputedStatComparison.tenant_id == tenant_id,
                ComputedStatComparison.stat_definition_id == stat_definition_id,
                column == old,
            )
            .values({column.key: new})
        )
