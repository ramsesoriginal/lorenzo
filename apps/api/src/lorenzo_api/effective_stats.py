"""The effective value of some stats on a page of entries, in one read - ADR 0387.

`GET /entities/{id}` loads an entry's effective rows with its formulas and evaluates them;
this loads them for the page's entries at once and evaluates each with the same function, so a
stat reads the same here as there. Every effective row of an entry is loaded whatever columns
were asked for, since a formula needs the rows it reads; the requested ones are picked out after.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import (
    Entity,
    StatDefinition,
    StatGroup,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.effective_stats import EffectiveStatOut, EntryEffectiveStatsOut
from lorenzo_api.stat_contents import contents_for_rows
from lorenzo_api.stat_evaluation import Contents, evaluate

__all__ = ["effective_stats_of", "load_effective_rows"]


async def load_effective_rows(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_ids: Sequence[uuid.UUID]
) -> tuple[dict[uuid.UUID, list[VEffectiveStat]], Contents | None]:
    """Every effective row of each entry, with what evaluating it needs (the definitions and their
    enum values, the stat's group and system, the entry a value comes from, the winning formulas),
    and what the contents formulas among them read: the bulk read's loading, in one pass for all
    the entries (ADR 0387), shared with the vocabulary check (ADR 0458)."""
    rows: dict[uuid.UUID, list[VEffectiveStat]] = {entity_id: [] for entity_id in entity_ids}
    if entity_ids:
        for stat in await session.scalars(
            select(VEffectiveStat)
            .where(VEffectiveStat.entity_id.in_(entity_ids), VEffectiveStat.tenant_id == tenant_id)
            .options(
                selectinload(VEffectiveStat.stat_definition),
                selectinload(VEffectiveStat.stat_definition).selectinload(
                    StatDefinition.enum_values
                ),
                selectinload(VEffectiveStat.stat_definition)
                .joinedload(StatDefinition.stat_group)
                .joinedload(StatGroup.system),
                selectinload(VEffectiveStat.source_entity),
                *formula_load_options(selectinload(VEffectiveStat.computed_stat)),
            )
        ):
            rows[stat.entity_id].append(stat)
    return rows, await contents_for_rows(session, tenant_id=tenant_id, stats=rows)


async def effective_stats_of(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entities: Sequence[Entity],
    wanted: Sequence[uuid.UUID],
    visibility: InformationVisibility,
    system: str | None = None,
) -> list[EntryEffectiveStatsOut]:
    """For each of `entities`, the effective value of each of `wanted` it has, in the order
    asked: whether it holds the value itself, which entry it comes from (null for a source the
    caller may not see, as on the entry's own read), and whether a formula decided it. With
    `system`, a stat of another game system is left out (ADR 0450): after the evaluation, so a
    formula still reads it."""
    ids = [entity.id for entity in entities]
    rows, contents = await load_effective_rows(session, tenant_id=tenant_id, entity_ids=ids)
    out: list[EntryEffectiveStatsOut] = []
    for entity in entities:
        values = evaluate(rows[entity.id], entity_id=entity.id, contents=contents)
        winners = {stat.stat_definition_id: stat for stat in rows[entity.id]}
        stats: list[EffectiveStatOut] = []
        for stat_definition_id in wanted:
            if stat_definition_id not in values:
                continue
            winner = winners[stat_definition_id]
            if system is not None and winner.system_slug() not in (None, system):
                continue
            own = winner.source_entity_id == entity.id
            stats.append(
                EffectiveStatOut(
                    stat_definition_id=stat_definition_id,
                    group_id=winner.stat_definition.stat_group_id,
                    system=winner.system_slug(),
                    value=values[stat_definition_id],
                    own=own,
                    from_entity=(
                        None
                        if own or not visibility.can_see_entry(winner.source_entity_id)
                        else EntitySummary.from_entity(winner.source_entity)
                    ),
                    from_hidden=(
                        True
                        if not own and not visibility.can_see_entry(winner.source_entity_id)
                        else None
                    ),
                    computed=winner.computed_entity_id is not None,
                )
            )
        out.append(EntryEffectiveStatsOut(id=entity.id, name=entity.name, stats=stats))
    return out
