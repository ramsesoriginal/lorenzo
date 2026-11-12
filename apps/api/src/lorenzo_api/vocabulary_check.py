"""What a library's stats get wrong without saying so (ADR 0458, RFC 0055).

A read, never a gate: it reports what the resolution rules (ADR 0037, 0266) and the scales and hints
(ADR 0279, 0403) already did, and refuses, writes and stores nothing. Entry-level findings are made
for a page of entries from the bulk read's loading (ADR 0387), with no query for each entry;
vocabulary-level findings read the definition-level graph of formulas.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.effective_stats import load_effective_rows
from lorenzo_api.models import ComputedStat, Entity, StatDefinition, formula_load_options
from lorenzo_api.stat_evaluation import evaluate, formula_chains_below

Code = Literal["computed-outside-scale", "above-hint", "formula-chain-depth"]
Severity = Literal["warning", "info"]

# Warnings are what an author most likely did not mean; info is what the rules produce on purpose
# (a computed value outside a scale, a value above a hint).
SEVERITY: dict[str, Severity] = {
    "computed-outside-scale": "info",
    "above-hint": "info",
    "formula-chain-depth": "info",
}

# A chain of formulas longer than this is reported; the write-time limit is MAX_FORMULA_CHAIN
# (ADR 0443), far above it.
CHAIN_REPORTED_ABOVE = 50


@dataclass
class Finding:
    code: str
    entry_id: uuid.UUID | None
    stat_definition_id: uuid.UUID
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> Severity:
        return SEVERITY[self.code]


def plain(number: float | int) -> float | int:
    """A number as a finding says it: whole when it is."""
    return int(number) if float(number).is_integer() else float(number)


def _number(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value


async def scan_entries(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entities: Sequence[Entity],
    codes: Collection[str],
    stat_definition_id: uuid.UUID | None,
) -> list[Finding]:
    """The entry-level findings of a page of entries, each entry's stats read as an entity read
    gives them (formulas evaluated), by entry then by the stat's name."""
    ids = [entity.id for entity in entities]
    rows, contents = await load_effective_rows(session, tenant_id=tenant_id, entity_ids=ids)
    found: list[Finding] = []
    for entity in entities:
        values = evaluate(rows[entity.id], entity_id=entity.id, contents=contents)
        winners = {stat.stat_definition_id: stat for stat in rows[entity.id]}
        for definition_id in sorted(
            values, key=lambda d: (winners[d].stat_definition.name, str(d))
        ):
            if stat_definition_id is not None and definition_id != stat_definition_id:
                continue
            row = winners[definition_id]
            definition = row.stat_definition
            value = _number(values[definition_id])
            if value is None:
                continue
            name = definition.name
            if "computed-outside-scale" in codes and row.computed_entity_id is not None:
                low, high = definition.min_value, definition.max_value
                if (low is not None and value < low) or (high is not None and value > high):
                    found.append(
                        Finding(
                            "computed-outside-scale",
                            entity.id,
                            definition_id,
                            f"{name} computes to {plain(value)}, outside its scale of "
                            f"{'no minimum' if low is None else plain(low)} to "
                            f"{'no maximum' if high is None else plain(high)}.",
                            {
                                "value": plain(value),
                                "minimum": None if low is None else plain(low),
                                "maximum": None if high is None else plain(high),
                            },
                        )
                    )
            if "above-hint" in codes:
                for hint, side in (
                    (definition.max_hint_id, "maximum"),
                    (definition.min_hint_id, "minimum"),
                ):
                    hinted = _number(values.get(hint)) if hint is not None else None
                    if hint is None or hinted is None:
                        continue
                    if (side == "maximum" and value > hinted) or (
                        side == "minimum" and value < hinted
                    ):
                        word = "above" if side == "maximum" else "below"
                        found.append(
                            Finding(
                                "above-hint",
                                entity.id,
                                definition_id,
                                f"{name} is {plain(value)}, {word} its {side} hint of "
                                f"{plain(hinted)}.",
                                {
                                    "value": plain(value),
                                    "hint": side,
                                    "hinted_stat_definition_id": str(hint),
                                    "hinted_value": plain(hinted),
                                },
                            )
                        )
    return found


async def vocabulary_findings(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    codes: Collection[str],
    stat_definition_id: uuid.UUID | None,
) -> list[Finding]:
    """The findings that are about the library's formulas and no entry: `formula-chain-depth`, a
    stat with more than 50 formulas below it in the longest chain, one finding for the top of each
    chain (a stat no longer chain reads)."""
    if "formula-chain-depth" not in codes:
        return []
    edges: dict[uuid.UUID, set[uuid.UUID]] = {}
    for row in await session.scalars(
        select(ComputedStat)
        .where(ComputedStat.tenant_id == tenant_id)
        .options(*formula_load_options())
    ):
        edges.setdefault(row.stat_definition_id, set()).update(row.source_stat_definition_ids())
    below = formula_chains_below(edges)
    long = {stat for stat, length in below.items() if length > CHAIN_REPORTED_ABOVE}
    tops = sorted(stat for stat in long if not any(stat in edges.get(other, ()) for other in long))
    if stat_definition_id is not None:
        tops = [stat for stat in tops if stat == stat_definition_id]
    if not tops:
        return []
    names = dict(
        (
            await session.execute(
                select(StatDefinition.id, StatDefinition.name).where(
                    StatDefinition.tenant_id == tenant_id, StatDefinition.id.in_(tops)
                )
            )
        )
        .tuples()
        .all()
    )
    return [
        Finding(
            "formula-chain-depth",
            None,
            stat,
            f"{names.get(stat, stat)} has {below[stat]} formulas below it, each reading the next; "
            "a chain this long is hard to follow.",
            {"length": below[stat]},
        )
        for stat in sorted(tops, key=lambda s: (names.get(s, ""), str(s)))
    ]
