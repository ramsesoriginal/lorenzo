"""Where an enum value's text is held, and what renames it - ADR 0390.

An enum value has no foreign key to its row: an entry's value of an enum stat is the text
(`entity_stat.value_text`), a comparison formula whose target is the enum returns one of two
texts (`computed_stat_comparison.true_value` and `false_value`), and a select formula returns
texts or matches them (ADR 0446). So "is this value in use" and
"rename it" are the same two places, and live here once for the routes and for the update engine.
"""

import uuid
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select, tuple_, union, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    ComputedStatComparison,
    ComputedStatExtremumInput,
    ComputedStatLinear,
    ComputedStatProductFactor,
    ComputedStatRatio,
    ComputedStatSelect,
    ComputedStatSelectStep,
    ComputedStatSumTerm,
    Entity,
    EntityStat,
    StatDefinition,
)

__all__ = [
    "EnumValueUses",
    "enum_value_uses",
    "formulas_reading_as_number",
    "rename_enum_value_text",
]


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


def _selects_naming(tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, value: str) -> Any:
    """The select formulas (as entity and stat) that name one value of an enum stat as text
    (ADR 0446): a step or `otherwise` that returns it, when the enum is the formula's target, and
    a step that matches it, when the enum is the source."""
    returns_in_a_step = select(
        ComputedStatSelectStep.entity_id, ComputedStatSelectStep.stat_definition_id
    ).where(
        ComputedStatSelectStep.tenant_id == tenant_id,
        ComputedStatSelectStep.stat_definition_id == stat_definition_id,
        ComputedStatSelectStep.result_text == value,
    )
    returns_otherwise = select(
        ComputedStatSelect.entity_id, ComputedStatSelect.stat_definition_id
    ).where(
        ComputedStatSelect.tenant_id == tenant_id,
        ComputedStatSelect.stat_definition_id == stat_definition_id,
        ComputedStatSelect.otherwise_text == value,
    )
    matches = (
        select(ComputedStatSelectStep.entity_id, ComputedStatSelectStep.stat_definition_id)
        .join(
            ComputedStatSelect,
            (ComputedStatSelect.entity_id == ComputedStatSelectStep.entity_id)
            & (ComputedStatSelect.stat_definition_id == ComputedStatSelectStep.stat_definition_id),
        )
        .where(
            ComputedStatSelectStep.tenant_id == tenant_id,
            ComputedStatSelect.source_stat_definition_id == stat_definition_id,
            ComputedStatSelectStep.match_value == value,
        )
    )
    return union(returns_in_a_step, returns_otherwise, matches)


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
    selecting = await session.scalar(
        select(func.count()).select_from(
            _selects_naming(tenant_id, stat_definition_id, value).subquery()
        )
    )
    return EnumValueUses(entries or 0, (formulas or 0) + (selecting or 0))


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
    # A select formula that returns the value, or matches it (ADR 0446).
    await session.execute(
        update(ComputedStatSelectStep)
        .where(
            ComputedStatSelectStep.tenant_id == tenant_id,
            ComputedStatSelectStep.stat_definition_id == stat_definition_id,
            ComputedStatSelectStep.result_text == old,
        )
        .values(result_text=new)
    )
    await session.execute(
        update(ComputedStatSelect)
        .where(
            ComputedStatSelect.tenant_id == tenant_id,
            ComputedStatSelect.stat_definition_id == stat_definition_id,
            ComputedStatSelect.otherwise_text == old,
        )
        .values(otherwise_text=new)
    )
    matching = select(ComputedStatSelect.entity_id, ComputedStatSelect.stat_definition_id).where(
        ComputedStatSelect.tenant_id == tenant_id,
        ComputedStatSelect.source_stat_definition_id == stat_definition_id,
    )
    await session.execute(
        update(ComputedStatSelectStep)
        .where(
            ComputedStatSelectStep.tenant_id == tenant_id,
            ComputedStatSelectStep.match_value == old,
            tuple_(ComputedStatSelectStep.entity_id, ComputedStatSelectStep.stat_definition_id).in_(
                matching
            ),
        )
        .values(match_value=new)
    )


async def formulas_reading_as_number(
    session: AsyncSession, tenant_id: uuid.UUID, stat_definition_id: uuid.UUID
) -> list[str]:
    """The formulas that read an enum stat as a number (ADR 0444), each as `stat name of entry
    name`: an enum counts as the `sort_order` of the value it holds, so moving or removing a value
    changes what these formulas say. Empty for an enum nothing reads that way."""
    formulas = union(
        select(ComputedStatLinear.entity_id, ComputedStatLinear.stat_definition_id).where(
            ComputedStatLinear.tenant_id == tenant_id,
            ComputedStatLinear.source_stat_definition_id == stat_definition_id,
        ),
        select(ComputedStatSumTerm.entity_id, ComputedStatSumTerm.stat_definition_id).where(
            ComputedStatSumTerm.tenant_id == tenant_id,
            ComputedStatSumTerm.source_stat_definition_id == stat_definition_id,
        ),
        select(
            ComputedStatExtremumInput.entity_id, ComputedStatExtremumInput.stat_definition_id
        ).where(
            ComputedStatExtremumInput.tenant_id == tenant_id,
            ComputedStatExtremumInput.source_stat_definition_id == stat_definition_id,
        ),
        select(
            ComputedStatProductFactor.entity_id, ComputedStatProductFactor.stat_definition_id
        ).where(
            ComputedStatProductFactor.tenant_id == tenant_id,
            ComputedStatProductFactor.source_stat_definition_id == stat_definition_id,
        ),
        select(ComputedStatRatio.entity_id, ComputedStatRatio.stat_definition_id).where(
            ComputedStatRatio.tenant_id == tenant_id,
            or_(
                ComputedStatRatio.numerator_stat_definition_id == stat_definition_id,
                ComputedStatRatio.denominator_stat_definition_id == stat_definition_id,
            ),
        ),
        select(ComputedStatSelect.entity_id, ComputedStatSelect.stat_definition_id).where(
            ComputedStatSelect.tenant_id == tenant_id,
            or_(
                (ComputedStatSelect.mode == "threshold")
                & (ComputedStatSelect.source_stat_definition_id == stat_definition_id),
                ComputedStatSelect.otherwise_stat_definition_id == stat_definition_id,
            ),
        ),
        select(ComputedStatSelectStep.entity_id, ComputedStatSelectStep.stat_definition_id).where(
            ComputedStatSelectStep.tenant_id == tenant_id,
            ComputedStatSelectStep.result_stat_definition_id == stat_definition_id,
        ),
    ).subquery()
    rows = await session.execute(
        select(StatDefinition.name, Entity.name)
        .join(formulas, formulas.c.stat_definition_id == StatDefinition.id)
        .join(Entity, Entity.id == formulas.c.entity_id)
        .order_by(StatDefinition.name, Entity.name)
    )
    return [f"{stat} of {entry}" for stat, entry in rows.tuples()]
