"""What a library's stats get wrong without saying so (ADR 0458 to 0460, RFC 0055).

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
from lorenzo_api.grants import ancestors_of
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import (
    ComputedStat,
    Entity,
    StatDefinition,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.stat_evaluation import evaluate, formula_chains_below

Code = Literal[
    "computed-outside-scale",
    "above-hint",
    "formula-chain-depth",
    "unset-input",
    "own-value-shadows-formula",
]
Severity = Literal["warning", "info"]

# Warnings are what an author most likely did not mean; info is what the rules produce on purpose
# (a computed value outside a scale, a value above a hint).
SEVERITY: dict[str, Severity] = {
    "computed-outside-scale": "info",
    "above-hint": "info",
    "formula-chain-depth": "info",
    "unset-input": "warning",
    "own-value-shadows-formula": "warning",
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


def _formula_entry(entry_id: uuid.UUID | None, visibility: InformationVisibility) -> dict[str, Any]:
    """An entry a finding names, as the caller may read it: one a library hides (ADR 0437) has no
    id there and says so."""
    if entry_id is None or visibility.can_see_entry(entry_id):
        return {"formula_entry_id": None if entry_id is None else str(entry_id)}
    return {"formula_entry_id": None, "formula_entry_hidden": True}


async def _formulas_above(
    session: AsyncSession, tenant_id: uuid.UUID, own: dict[uuid.UUID, list[uuid.UUID]]
) -> dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID]:
    """For each (entry, stat) of `own` (the stats an entry holds by its own value), the first entry
    on its prototype walk that holds a formula for the stat, if any: one query for the ancestors
    and one for the formulas, however many entries."""
    asking = {entity_id: stats for entity_id, stats in own.items() if stats}
    if not asking:
        return {}
    above = await ancestors_of(session, tenant_id, set(asking))
    held = {
        (entry_id, stat_id)
        for entry_id, stat_id in await session.execute(
            select(ComputedStat.entity_id, ComputedStat.stat_definition_id).where(
                ComputedStat.tenant_id == tenant_id,
                ComputedStat.entity_id.in_({a for entries in above.values() for a in entries}),
                ComputedStat.stat_definition_id.in_(
                    {s for stats in asking.values() for s in stats}
                ),
            )
        )
    }
    found: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
    for entity_id, stats in asking.items():
        for stat_id in stats:
            for ancestor in sorted(above[entity_id], key=str):
                if (ancestor, stat_id) in held:
                    found[(entity_id, stat_id)] = ancestor
                    break
    return found


def _missing_inputs(row: VEffectiveStat, values: dict[uuid.UUID, Any]) -> list[uuid.UUID]:
    """The stats a computed stat reads on its own entry that have no value there."""
    if row.computed_entity_id is None or row.computed_stat is None:
        return []
    return [i for i in row.computed_stat.source_stat_definition_ids() if i not in values]


async def _names(
    session: AsyncSession, tenant_id: uuid.UUID, ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await session.execute(
        select(StatDefinition.id, StatDefinition.name).where(
            StatDefinition.tenant_id == tenant_id, StatDefinition.id.in_(set(ids))
        )
    )
    return {stat_id: name for stat_id, name in rows.tuples()}


async def scan_entries(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entities: Sequence[Entity],
    visibility: InformationVisibility,
    codes: Collection[str],
    stat_definition_id: uuid.UUID | None,
) -> list[Finding]:
    """The entry-level findings of a page of entries, each entry's stats read as an entity read
    gives them (formulas evaluated), by entry then by the stat's name."""
    ids = [entity.id for entity in entities]
    rows, contents = await load_effective_rows(session, tenant_id=tenant_id, entity_ids=ids)
    values = {
        entity.id: evaluate(rows[entity.id], entity_id=entity.id, contents=contents)
        for entity in entities
    }
    winners = {
        entity.id: {stat.stat_definition_id: stat for stat in rows[entity.id]}
        for entity in entities
    }

    def wanted(definition_id: uuid.UUID) -> bool:
        return stat_definition_id is None or definition_id == stat_definition_id

    own: dict[uuid.UUID, list[uuid.UUID]] = {}
    if "own-value-shadows-formula" in codes:
        own = {
            entity.id: [
                d
                for d, stat in winners[entity.id].items()
                if d in values[entity.id]
                and stat.computed_entity_id is None
                and stat.source_entity_id == entity.id
                and wanted(d)
            ]
            for entity in entities
        }
    shadowing = await _formulas_above(session, tenant_id, own)
    unnamed: set[uuid.UUID] = set()
    if "unset-input" in codes:
        for entity in entities:
            for d, stat in winners[entity.id].items():
                if d not in values[entity.id] and wanted(d):
                    unnamed |= set(_missing_inputs(stat, values[entity.id]))
    names = await _names(session, tenant_id, unnamed)

    found: list[Finding] = []
    for entity in entities:
        entry_values = values[entity.id]
        stats_here = winners[entity.id]
        for definition_id in sorted(
            stats_here, key=lambda d: (stats_here[d].stat_definition.name, str(d))
        ):
            if not wanted(definition_id):
                continue
            row = winners[entity.id][definition_id]
            definition = row.stat_definition
            name = definition.name
            if definition_id not in entry_values:
                missing = _missing_inputs(row, entry_values)
                if "unset-input" in codes and missing:
                    assert row.computed_stat is not None
                    found.append(
                        Finding(
                            "unset-input",
                            entity.id,
                            definition_id,
                            f"{name} has no value because "
                            + ", ".join(names.get(m, str(m)) for m in missing)
                            + (" has" if len(missing) == 1 else " have")
                            + " none.",
                            {
                                **_formula_entry(row.computed_entity_id, visibility),
                                "kind": row.computed_stat.kind,
                                "inputs_without_value": [str(m) for m in missing],
                            },
                        )
                    )
                continue
            if (entity.id, definition_id) in shadowing:
                found.append(
                    Finding(
                        "own-value-shadows-formula",
                        entity.id,
                        definition_id,
                        f"{name} has a value of its own, which wins over the formula an "
                        "ancestor holds for it.",
                        {
                            "own_value": entry_values[definition_id],
                            **_formula_entry(shadowing[(entity.id, definition_id)], visibility),
                        },
                    )
                )
            value = _number(entry_values[definition_id])
            if value is None:
                continue
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
                    hinted = _number(entry_values.get(hint)) if hint is not None else None
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
    names = await _names(session, tenant_id, tops)
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
