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

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.effective_stats import load_effective_rows
from lorenzo_api.grants import ancestors_of
from lorenzo_api.information_visibility import InformationVisibility, resolve_information_visibility
from lorenzo_api.models import (
    ComputedStat,
    Entity,
    EntityStat,
    EntityStatGroup,
    StatDefinition,
    StatGroup,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.schemas.vocabulary_check import FindingOut
from lorenzo_api.stat_evaluation import evaluate, formula_chains_below

Code = Literal[
    "computed-outside-scale",
    "above-hint",
    "formula-chain-depth",
    "unset-input",
    "own-value-shadows-formula",
    "tie",
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
    "tie": "warning",
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


# --- a tie (ADR 0460) ---------------------------------------------------------------------------

_TIE_WALK = text(
    """
    WITH RECURSIVE walk(ancestor_id, hops, path) AS (
        SELECT CAST(:entity AS uuid), 0, ARRAY[]::integer[]
        UNION ALL
        SELECT ep.prototype_id, w.hops + 1, w.path || ep.position
        FROM walk w
        JOIN entity_prototype ep ON ep.entity_id = w.ancestor_id
        WHERE w.hops < 50
    )
    SELECT ancestor_id, hops, path FROM walk
    """
)


@dataclass(frozen=True)
class _Candidate:
    holder_id: uuid.UUID
    hops: int
    computed: bool
    priority: int
    path: tuple[int, ...]


def _says(candidate: _Candidate, visibility: InformationVisibility) -> dict[str, Any]:
    """A candidate as a finding names it: the entry (none when the caller may not see it), how far
    it is and whether it holds a formula."""
    seen = visibility.can_see_entry(candidate.holder_id)
    return {
        "entry_id": str(candidate.holder_id) if seen else None,
        **({} if seen else {"hidden": True}),
        "distance": candidate.hops,
        "computed": candidate.computed,
    }


async def tie_findings(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity: Entity,
    visibility: InformationVisibility,
    stat_definition_id: uuid.UUID | None,
) -> list[Finding]:
    """The ties of one entry (ADR 0460, RFC 0055 section 2): a stat that two or more entries on its
    prototype walk set at the same distance, so that a rule had to choose. The candidates are read
    as the effective-stat view orders them (distance, a stored value before a formula, the highest
    priority of the groups the holder has acquired, the places taken from the entry down, the
    id), in a walk of its own, since the view returns the winner only: four queries, however
    many stats."""
    # The view keeps the first way to an ancestor that its order finds, by hops and then path.
    ways: dict[uuid.UUID, tuple[int, tuple[int, ...]]] = {}
    for row in (await session.execute(_TIE_WALK, {"entity": entity.id})).all():
        way = (row.hops, tuple(row.path))
        if row.ancestor_id not in ways or way < ways[row.ancestor_id]:
            ways[row.ancestor_id] = way
    holders = list(ways)
    priority = {
        holder: int(top)
        for holder, top in await session.execute(
            select(EntityStatGroup.entity_id, func.max(StatGroup.priority))
            .join(StatGroup, StatGroup.id == EntityStatGroup.stat_group_id)
            .where(EntityStatGroup.tenant_id == tenant_id, EntityStatGroup.entity_id.in_(holders))
            .group_by(EntityStatGroup.entity_id)
        )
    }
    candidates: dict[uuid.UUID, list[_Candidate]] = {}
    for model, computed in ((EntityStat, False), (ComputedStat, True)):
        for holder_id, stat_id in await session.execute(
            select(model.entity_id, model.stat_definition_id).where(
                model.tenant_id == tenant_id, model.entity_id.in_(holders)
            )
        ):
            if stat_definition_id is not None and stat_id != stat_definition_id:
                continue
            hops, path = ways[holder_id]
            candidates.setdefault(stat_id, []).append(
                _Candidate(holder_id, hops, computed, priority.get(holder_id, 0), path)
            )
    tied: dict[uuid.UUID, list[_Candidate]] = {}
    for stat_id, found in candidates.items():
        ordered = sorted(
            found, key=lambda c: (c.hops, c.computed, -c.priority, c.path, str(c.holder_id))
        )
        winner = ordered[0]
        same = [c for c in ordered if (c.hops, c.computed) == (winner.hops, winner.computed)]
        if len(same) > 1:
            tied[stat_id] = same
    if not tied:
        return []
    names = await _names(session, tenant_id, tied)
    entry_names = dict(
        (
            await session.execute(
                select(Entity.id, Entity.name).where(
                    Entity.tenant_id == tenant_id,
                    Entity.id.in_({c.holder_id for same in tied.values() for c in same}),
                )
            )
        )
        .tuples()
        .all()
    )
    out: list[Finding] = []
    for stat_id in sorted(tied, key=lambda s: (names.get(s, ""), str(s))):
        winner, *others = tied[stat_id]
        runner_up = others[0]
        if winner.priority != runner_up.priority:
            reason = "group priority"
        elif winner.path != runner_up.path:
            reason = "parent order"
        else:
            reason = "id"
        label = (
            entry_names.get(winner.holder_id, "an entry")
            if visibility.can_see_entry(winner.holder_id)
            else "a hidden entry"
        )
        out.append(
            Finding(
                "tie",
                entity.id,
                stat_id,
                f"{names.get(stat_id, stat_id)} is set by {len(others) + 1} entries at the same "
                f"distance; {label} won by {reason}.",
                {
                    "winner": _says(winner, visibility),
                    "others": [_says(c, visibility) for c in others],
                    "reason": reason,
                },
            )
        )
    return out


# --- warnings on a write (ADR 0461) ---------------------------------------------------------

WARNINGS_HELP = (
    "Answer with `warnings`: what the vocabulary check says of the stat just written on this entry "
    "(ADR 0461). Without it no check runs and the answer is as it was."
)

ALL_CODES: tuple[str, ...] = (
    "computed-outside-scale",
    "above-hint",
    "formula-chain-depth",
    "unset-input",
    "own-value-shadows-formula",
    "tie",
)


def finding_out(finding: Finding) -> FindingOut:
    return FindingOut(
        code=finding.code,
        severity=finding.severity,
        entry_id=finding.entry_id,
        stat_definition_id=finding.stat_definition_id,
        message=finding.message,
        details=finding.details,
    )


async def warnings_for_write(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
) -> list[FindingOut]:
    """The findings, of any severity, for the stat that was just written on the entry it was
    written on (RFC 0055 section 4): what `GET .../vocabulary-check` would say of that entry and
    stat. Asked for by the write with `warnings=true`; without it nothing here runs."""
    visibility = await resolve_information_visibility(session, user_id=user_id, tenant_id=tenant_id)
    entity = await session.get_one(Entity, entity_id)
    codes = list(ALL_CODES)
    found = await scan_entries(
        session,
        tenant_id=tenant_id,
        entities=[entity],
        visibility=visibility,
        codes=codes,
        stat_definition_id=stat_definition_id,
    )
    found += await tie_findings(
        session,
        tenant_id=tenant_id,
        entity=entity,
        visibility=visibility,
        stat_definition_id=stat_definition_id,
    )
    found += await vocabulary_findings(
        session, tenant_id=tenant_id, codes=codes, stat_definition_id=stat_definition_id
    )
    return [finding_out(f) for f in found]
