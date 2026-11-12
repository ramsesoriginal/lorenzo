"""What a holder is entitled to, what it was given and why, and revoking what no longer holds
(ADR 0456, RFC 0054 section 3 to 5).

A holder has two kinds of sources: the entries on its prototype walk (a race, a class, an
archetype, with the rules of the whole walk) and the active instances it holds (an item, a feature),
each of whose prototype walk brings its rules, with the instance as the source reference. A rule
holds for a (rule, source) while its conditions do; a `grant_record` says what a rule gave and from
which source, and a (rule, source, feature) is given once while its record is active.

`compute` reads, and writes nothing: what is held, what is due (an `all` rule's options not yet
given), the choices still open, and what is orphaned (an active record whose source or conditions no
longer hold). Writing is `grant`, `revoke` and the revocation checks the requests that remove a
source call (`revoke_orphans`, `revoke_by_sources`, `revoke_after_stat_write`).
"""

from __future__ import annotations

import operator
import uuid
from collections import defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.change_feed import Change, holders, record_change
from lorenzo_api.entity_access import prototype_descendants_cte
from lorenzo_api.exceptions import FeatureAlreadyHeldError, InvalidGrantPickError
from lorenzo_api.features import create_instance
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    Feature,
    FeatureInstance,
    FeaturePrerequisite,
    GrantRecord,
    GrantRule,
    GrantRuleCondition,
    ItemInstance,
    StatDefinition,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.stat_contents import contents_for_rows
from lorenzo_api.stat_evaluation import evaluate, numeric_value

# The most grants an apply follows: a granted feature is itself a source, so one rule's gift may
# bring another's, and a chain this long is a cycle of rules, not content.
MAX_DEPTH = 8

Numbers = dict[uuid.UUID, dict[uuid.UUID, Decimal]]
Reason = Literal["source", "conditions", "removed"]

_COMPARE = {
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ne": operator.ne,
    "ge": operator.ge,
    "gt": operator.gt,
}


@dataclass(frozen=True)
class Standing:
    """A rule that applies to a holder through a source, and whether it holds."""

    rule: GrantRule
    ref_id: uuid.UUID
    kind: Literal["ancestor", "instance"]
    holds: bool


@dataclass
class DueGrant:
    standing: Standing
    feature_id: uuid.UUID


@dataclass
class OpenChoice:
    standing: Standing
    minimum: int
    maximum: int
    picked: list[uuid.UUID]
    # Every option the rule offers that is not already picked or held, and the ones among them
    # whose prerequisites hold for the holder.
    offered: list[uuid.UUID]
    passing: set[uuid.UUID]


@dataclass
class Orphan:
    record: GrantRecord
    reason: Reason


@dataclass
class Computed:
    holder_id: uuid.UUID
    standings: list[Standing] = field(default_factory=list)
    numbers: Numbers = field(default_factory=dict)
    active: list[GrantRecord] = field(default_factory=list)
    due: list[DueGrant] = field(default_factory=list)
    open_choices: list[OpenChoice] = field(default_factory=list)
    orphans: list[Orphan] = field(default_factory=list)
    features: dict[uuid.UUID, Feature] = field(default_factory=dict)
    prerequisites: dict[uuid.UUID, list[FeaturePrerequisite]] = field(default_factory=dict)
    # The features the holder has right now, whatever way it came to have them.
    held: set[uuid.UUID] = field(default_factory=set)


# --- reading -------------------------------------------------------------------------------


async def ancestors_of(
    session: AsyncSession, tenant_id: uuid.UUID, roots: Collection[uuid.UUID]
) -> dict[uuid.UUID, set[uuid.UUID]]:
    """Every entry on each root's prototype walk, the root itself left out. A plain UNION, so a
    cycle of prototypes ends the walk."""
    found: dict[uuid.UUID, set[uuid.UUID]] = {root: set() for root in roots}
    if not roots:
        return found
    walk = (
        select(EntityPrototype.entity_id.label("root"), EntityPrototype.prototype_id.label("above"))
        .where(EntityPrototype.tenant_id == tenant_id, EntityPrototype.entity_id.in_(set(roots)))
        .cte("grant_walk", recursive=True)
    )
    walk = walk.union(
        select(walk.c.root, EntityPrototype.prototype_id)
        .select_from(walk.join(EntityPrototype, EntityPrototype.entity_id == walk.c.above))
        .where(EntityPrototype.tenant_id == tenant_id)
    )
    for root, above in await session.execute(select(walk.c.root, walk.c.above)):
        found[root].add(above)
    return found


async def numbers_of(
    session: AsyncSession, tenant_id: uuid.UUID, entity_ids: Iterable[uuid.UUID]
) -> Numbers:
    """The stats of each entry as a comparison reads them: the effective value, formulas
    evaluated, a bool as 1 or 0 and an enum as its `sort_order` (ADR 0444); a stat with no
    number is left out."""
    ids = set(entity_ids)
    out: Numbers = {entity_id: {} for entity_id in ids}
    if not ids:
        return out
    rows: dict[uuid.UUID, list[VEffectiveStat]] = {entity_id: [] for entity_id in ids}
    for stat in await session.scalars(
        select(VEffectiveStat)
        .where(VEffectiveStat.entity_id.in_(ids), VEffectiveStat.tenant_id == tenant_id)
        .options(
            selectinload(VEffectiveStat.stat_definition),
            selectinload(VEffectiveStat.stat_definition).selectinload(StatDefinition.enum_values),
            *formula_load_options(selectinload(VEffectiveStat.computed_stat)),
        )
    ):
        rows[stat.entity_id].append(stat)
    contents = await contents_for_rows(session, tenant_id=tenant_id, stats=rows)
    for entity_id in ids:
        definitions = {s.stat_definition_id: s.stat_definition for s in rows[entity_id]}
        values = evaluate(rows[entity_id], entity_id=entity_id, contents=contents)
        for stat_id, value in values.items():
            number = numeric_value(value, definitions.get(stat_id))
            if isinstance(number, int | float) and not isinstance(number, bool):
                out[entity_id][stat_id] = Decimal(str(number))
    return out


def holds_comparison(
    comparison: GrantRuleCondition | FeaturePrerequisite, numbers: dict[uuid.UUID, Decimal]
) -> bool:
    """`stat <comparator> right` on one entry's numbers; false when either side has no number."""
    left = numbers.get(comparison.stat_definition_id)
    right = (
        comparison.right_constant
        if comparison.right_stat_definition_id is None
        else numbers.get(comparison.right_stat_definition_id)
    )
    return left is not None and right is not None and _COMPARE[comparison.comparator](left, right)


async def _active_instances(
    session: AsyncSession, tenant_id: uuid.UUID, holder_id: uuid.UUID
) -> list[uuid.UUID]:
    """The instances the holder holds directly whose `active` switch is on: feature instances and
    item instances, the two things that carry one."""
    found: list[uuid.UUID] = []
    for model in (FeatureInstance, ItemInstance):
        found += list(
            await session.scalars(
                select(Containment.child_entity_id)
                .join(
                    model,
                    (model.entity_id == Containment.child_entity_id)
                    & (model.tenant_id == Containment.tenant_id),
                )
                .where(
                    Containment.parent_entity_id == holder_id,
                    Containment.tenant_id == tenant_id,
                    model.active.is_(True),
                )
            )
        )
    return found


async def standings_of(
    session: AsyncSession, tenant_id: uuid.UUID, holder_id: uuid.UUID
) -> tuple[list[Standing], Numbers]:
    """The rules that apply to the holder, with each one's source, and whether it holds. The rules
    of the holder's own entry do not: a source is above it or held by it."""
    instances = await _active_instances(session, tenant_id, holder_id)
    above = await ancestors_of(session, tenant_id, {holder_id, *instances})
    entries = set(above[holder_id])
    for instance_id in instances:
        entries |= {instance_id, *above[instance_id]}
    by_entry: dict[uuid.UUID, list[GrantRule]] = defaultdict(list)
    if entries:
        for rule in await session.scalars(
            select(GrantRule)
            .where(GrantRule.tenant_id == tenant_id, GrantRule.entry_id.in_(entries))
            .options(selectinload(GrantRule.conditions), selectinload(GrantRule.options))
            .order_by(GrantRule.entry_id, GrantRule.position, GrantRule.id)
        ):
            by_entry[rule.entry_id].append(rule)
    pairs: list[tuple[GrantRule, uuid.UUID, Literal["ancestor", "instance"]]] = [
        (rule, entry, "ancestor")
        for entry in sorted(above[holder_id], key=str)
        for rule in by_entry[entry]
    ]
    for instance_id in sorted(instances, key=str):
        for entry in sorted({instance_id, *above[instance_id]}, key=str):
            pairs.extend((rule, instance_id, "instance") for rule in by_entry[entry])
    numbers = await numbers_of(session, tenant_id, {holder_id, *(ref for _, ref, _ in pairs)})
    standings: list[Standing] = []
    for rule, ref, kind in pairs:
        standings.append(
            Standing(
                rule,
                ref,
                kind,
                all(
                    holds_comparison(
                        c, numbers[holder_id] if c.subject == "holder" else numbers[ref]
                    )
                    for c in rule.conditions
                ),
            )
        )
    return standings, numbers


async def offered_features(
    session: AsyncSession, tenant_id: uuid.UUID, rule: GrantRule
) -> list[uuid.UUID]:
    """The features a rule offers: its explicit options in order, or those under its category,
    by name. An option that has stopped being a feature is not offered."""
    if rule.option_category_entry_id is not None:
        below = prototype_descendants_cte(rule.option_category_entry_id, tenant_id)
        return list(
            await session.scalars(
                select(Feature.entity_id)
                .join(Entity, Entity.id == Feature.entity_id)
                .where(
                    Feature.tenant_id == tenant_id,
                    Feature.entity_id.in_(select(below.c.descendant_id)),
                )
                .order_by(Entity.name, Entity.id)
            )
        )
    wanted = [option.option_entry_id for option in rule.options]
    if not wanted:
        return []
    real = set(
        await session.scalars(
            select(Feature.entity_id).where(
                Feature.tenant_id == tenant_id, Feature.entity_id.in_(wanted)
            )
        )
    )
    return [feature for feature in wanted if feature in real]


def maximum_of(rule: GrantRule, holder_numbers: dict[uuid.UUID, Decimal]) -> int:
    """How many a choose rule lets the holder pick: its constant, or the holder's count stat
    rounded down (none, or a negative one, is 0)."""
    if rule.max_count is not None:
        return rule.max_count
    assert rule.count_stat_definition_id is not None
    number = holder_numbers.get(rule.count_stat_definition_id)
    return 0 if number is None else max(int(number.to_integral_value(ROUND_FLOOR)), 0)


async def compute(session: AsyncSession, tenant_id: uuid.UUID, holder_id: uuid.UUID) -> Computed:
    """Reads what the holder has, is due, may still pick and has lost the ground for. Writes
    nothing."""
    result = Computed(holder_id=holder_id)
    result.standings, result.numbers = await standings_of(session, tenant_id, holder_id)
    records = list(
        await session.scalars(
            select(GrantRecord).where(
                GrantRecord.tenant_id == tenant_id, GrantRecord.holder_id == holder_id
            )
        )
    )
    result.active = [r for r in records if r.state == "active"]
    removed = {
        (r.rule_id, r.source_ref_id, r.feature_id)
        for r in records
        if r.state == "revoked" and r.revoked_reason == "removed"
    }
    held_rows = await session.execute(
        select(EntityPrototype.prototype_id)
        .join(Containment, Containment.child_entity_id == EntityPrototype.entity_id)
        .join(
            FeatureInstance,
            (FeatureInstance.entity_id == Containment.child_entity_id)
            & (FeatureInstance.tenant_id == Containment.tenant_id),
        )
        .where(Containment.parent_entity_id == holder_id, Containment.tenant_id == tenant_id)
    )
    result.held = {feature for (feature,) in held_rows}
    options: dict[uuid.UUID, list[uuid.UUID]] = {}
    for standing in result.standings:
        if standing.holds and standing.rule.id not in options:
            options[standing.rule.id] = await offered_features(session, tenant_id, standing.rule)
    every = {f for ids in options.values() for f in ids}
    if every:
        result.features = {
            f.entity_id: f
            for f in await session.scalars(
                select(Feature).where(Feature.tenant_id == tenant_id, Feature.entity_id.in_(every))
            )
        }
        for row in await session.scalars(
            select(FeaturePrerequisite)
            .where(
                FeaturePrerequisite.tenant_id == tenant_id,
                FeaturePrerequisite.feature_id.in_(every),
            )
            .order_by(FeaturePrerequisite.feature_id, FeaturePrerequisite.position)
        ):
            result.prerequisites.setdefault(row.feature_id, []).append(row)
    holder_numbers = result.numbers[holder_id]

    def passes(feature_id: uuid.UUID) -> bool:
        return all(
            holds_comparison(p, holder_numbers) for p in result.prerequisites.get(feature_id, [])
        )

    def available(feature_id: uuid.UUID) -> bool:
        """Not held already, unless it is repeatable."""
        return feature_id not in result.held or result.features[feature_id].repeatable

    for standing in result.standings:
        if not standing.holds:
            continue
        rule = standing.rule
        here = [
            r for r in result.active if r.rule_id == rule.id and r.source_ref_id == standing.ref_id
        ]
        given = {r.feature_id for r in here}
        if rule.mode == "all":
            result.due.extend(
                DueGrant(standing, feature_id)
                for feature_id in options[rule.id]
                if feature_id not in given
                and (rule.id, standing.ref_id, feature_id) not in removed
                and passes(feature_id)
                and available(feature_id)
            )
            continue
        maximum = maximum_of(rule, holder_numbers)
        if len(given) < maximum:
            left = [f for f in options[rule.id] if f not in given and available(f)]
            result.open_choices.append(
                OpenChoice(
                    standing,
                    rule.min_count,
                    maximum,
                    [r.feature_id for r in here],
                    left,
                    {f for f in left if passes(f)},
                )
            )
    holding = {(s.rule.id, s.ref_id) for s in result.standings if s.holds}
    known = {(s.rule.id, s.ref_id) for s in result.standings}
    rule_lasts = {s.rule.id: s.rule.lasts for s in result.standings}
    missing = {r.rule_id for r in result.active if r.rule_id is not None} - set(rule_lasts)
    if missing:
        for rule_id, lasts in await session.execute(
            select(GrantRule.id, GrantRule.lasts).where(
                GrantRule.tenant_id == tenant_id, GrantRule.id.in_(missing)
            )
        ):
            rule_lasts[rule_id] = lasts
    for record in result.active:
        # A permanent grant stays when its source or its conditions go (RFC 0054 section 5).
        if record.rule_id is None or rule_lasts.get(record.rule_id) != "while_source":
            continue
        key = (record.rule_id, record.source_ref_id)
        if key not in holding:
            result.orphans.append(Orphan(record, "conditions" if key in known else "source"))
    return result


# --- writing -------------------------------------------------------------------------------


@dataclass
class Granted:
    record: GrantRecord
    feature_id: uuid.UUID
    instance_id: uuid.UUID


@dataclass
class Revoked:
    record_id: uuid.UUID
    holder_id: uuid.UUID
    rule_id: uuid.UUID | None
    source_ref_id: uuid.UUID | None
    feature_id: uuid.UUID
    instance_id: uuid.UUID | None
    reason: Reason


async def grant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    holder_id: uuid.UUID,
    feature: Feature,
    rule_id: uuid.UUID | None,
    source_ref_id: uuid.UUID | None,
    active: bool | None = None,
) -> Granted:
    """Gives the holder the feature, with its record: the instance, the record, an activity entry
    and a change-feed row for whoever holds the holder (ADR 0099)."""
    instance = await create_instance(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        holder_id=holder_id,
        feature=feature,
        active=active,
    )
    record = GrantRecord(
        tenant_id=tenant_id,
        holder_id=holder_id,
        rule_id=rule_id,
        source_ref_id=source_ref_id,
        feature_id=feature.entity_id,
        feature_instance_id=instance.id,
        state="active",
        created_by=actor_id,
    )
    session.add(record)
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action="grant.granted" if rule_id is not None else "feature.awarded",
        target_type="feature_instance",
        target_id=instance.id,
        detail=(
            f"holder={holder_id},feature={feature.entity_id}"
            + (f",rule={rule_id},source={source_ref_id}" if rule_id is not None else "")
        ),
    )
    await record_change(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        changes=[Change(entity_id=instance.id, before=frozenset(), both_kind=None)],
    )
    return Granted(record, feature.entity_id, instance.id)


async def revoke(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    records: Iterable[GrantRecord],
    reason: Reason,
) -> list[Revoked]:
    """Revokes the records: each keeps its feature and loses its instance, which is deleted, and
    so is every grant whose source was that instance, and theirs in turn (an item that gives a
    feature that gives a spell choice takes all three with it). One activity entry for each, and
    the feed tells whoever held them."""
    out: list[Revoked] = []
    changes: list[Change] = []

    async def one(record: GrantRecord, why: Reason) -> None:
        if record.state != "active":
            return
        instance_id = record.feature_instance_id
        name = None
        before: frozenset[uuid.UUID] = frozenset()
        if instance_id is not None:
            # What the instance gave goes first: its records point at it.
            for child in list(
                await session.scalars(
                    select(GrantRecord).where(
                        GrantRecord.tenant_id == tenant_id,
                        GrantRecord.source_ref_id == instance_id,
                        GrantRecord.state == "active",
                    )
                )
            ):
                await one(child, "source")
            name = await session.scalar(select(Entity.name).where(Entity.id == instance_id))
            before = await holders(session, tenant_id=tenant_id, entity_id=instance_id)
        record.state = "revoked"
        record.revoked_reason = why
        record.feature_instance_id = None
        await session.flush()
        out.append(
            Revoked(
                record.id,
                record.holder_id,
                record.rule_id,
                record.source_ref_id,
                record.feature_id,
                instance_id,
                why,
            )
        )
        if instance_id is None:
            return
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="grant.revoked",
            target_type="feature_instance",
            target_id=instance_id,
            detail=f"holder={record.holder_id},feature={record.feature_id},reason={why}",
        )
        changes.append(
            Change(
                entity_id=instance_id,
                before=before,
                both_kind=None,
                deleted=True,
                entity_name=name,
            )
        )
        entity = await session.get(Entity, instance_id)
        if entity is not None:
            await session.delete(entity)
        await session.flush()

    for record in list(records):
        await one(record, reason)
    if changes and actor_id is not None:
        await record_change(session, tenant_id=tenant_id, actor_id=actor_id, changes=changes)
    return out


async def watched_holders(
    session: AsyncSession, tenant_id: uuid.UUID, holder_ids: Collection[uuid.UUID]
) -> set[uuid.UUID]:
    """Which of the holders have an active record that lasts while its source does: the only ones
    a revocation check has to look at (RFC 0054 section 5), asked in one statement."""
    if not holder_ids:
        return set()
    return set(
        await session.scalars(
            select(GrantRecord.holder_id)
            .join(GrantRule, GrantRule.id == GrantRecord.rule_id)
            .where(
                GrantRecord.tenant_id == tenant_id,
                GrantRecord.holder_id.in_(set(holder_ids)),
                GrantRecord.state == "active",
                GrantRule.lasts == "while_source",
            )
            .distinct()
        )
    )


async def revoke_orphans(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    holder_ids: Collection[uuid.UUID],
) -> list[Revoked]:
    """Revokes, for each holder that has records that last while their source does, those whose
    source is gone or inactive or whose conditions no longer hold. Granting is never done here: a
    feature that becomes due waits for an apply. A holder with no such record costs one statement
    for all of them."""
    out: list[Revoked] = []
    for holder_id in sorted(await watched_holders(session, tenant_id, holder_ids), key=str):
        found = await compute(session, tenant_id, holder_id)
        by_reason: dict[Reason, list[GrantRecord]] = defaultdict(list)
        for orphan in found.orphans:
            by_reason[orphan.reason].append(orphan.record)
        for reason, records in by_reason.items():
            out += await revoke(
                session, tenant_id=tenant_id, actor_id=actor_id, records=records, reason=reason
            )
    return out


async def revoke_by_sources(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    source_ids: Collection[uuid.UUID],
) -> list[Revoked]:
    """Revokes what was granted from sources that are about to be deleted (an entry, an instance):
    the records that last while their source does, before the rows go (a permanent grant stays)."""
    if not source_ids:
        return []
    records = list(
        await session.scalars(
            select(GrantRecord)
            .join(GrantRule, GrantRule.id == GrantRecord.rule_id)
            .where(
                GrantRecord.tenant_id == tenant_id,
                GrantRecord.source_ref_id.in_(set(source_ids)),
                GrantRecord.state == "active",
                GrantRule.lasts == "while_source",
            )
        )
    )
    return await revoke(
        session, tenant_id=tenant_id, actor_id=actor_id, records=records, reason="source"
    )


async def revoke_after_stat_write(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
) -> list[Revoked]:
    """After a stat is written on an entry: if a condition of an active record that lasts while
    its source does reads that stat, the holder (the entry itself, or whoever has it as a source)
    is checked. When none does, that is the one statement this costs (ADR 0285)."""
    watched = await session.scalar(
        select(
            exists().where(
                GrantRecord.tenant_id == tenant_id,
                GrantRecord.state == "active",
                GrantRule.id == GrantRecord.rule_id,
                GrantRule.lasts == "while_source",
                GrantRuleCondition.rule_id == GrantRule.id,
                (GrantRuleCondition.stat_definition_id == stat_definition_id)
                | (GrantRuleCondition.right_stat_definition_id == stat_definition_id),
            )
        )
    )
    if not watched:
        return []
    affected = {entity_id}
    affected |= set(
        await session.scalars(
            select(GrantRecord.holder_id).where(
                GrantRecord.tenant_id == tenant_id,
                GrantRecord.state == "active",
                GrantRecord.source_ref_id == entity_id,
            )
        )
    )
    return await revoke_orphans(
        session, tenant_id=tenant_id, actor_id=actor_id, holder_ids=affected
    )


# --- apply ---------------------------------------------------------------------------------


@dataclass
class PickSpec:
    rule_id: uuid.UUID
    source_id: uuid.UUID
    options: list[uuid.UUID]


@dataclass
class Applied:
    created: list[Granted] = field(default_factory=list)
    revoked: list[Revoked] = field(default_factory=list)
    truncated: bool = False


async def _pick(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    holder_id: uuid.UUID,
    found: Computed,
    choice: OpenChoice,
    wanted: list[uuid.UUID],
    override: bool,
) -> list[Granted]:
    """Records a holder's picks for an open choice: only what the rule offers, within its count
    and the options' prerequisites, unless a GM overrides, and never a feature the holder has
    that is not repeatable."""
    rule = choice.standing.rule
    offered = set(await offered_features(session, tenant_id, rule))
    features = {
        f.entity_id: f
        for f in await session.scalars(
            select(Feature).where(Feature.tenant_id == tenant_id, Feature.entity_id.in_(wanted))
        )
    }
    holder_numbers = found.numbers[holder_id]
    for feature_id in wanted:
        if feature_id not in offered or feature_id not in features:
            raise InvalidGrantPickError(detail=f"{feature_id} is not an option of this rule")
        if feature_id in choice.picked:
            raise InvalidGrantPickError(detail=f"{feature_id} is already picked for this rule")
        if feature_id in found.held and not features[feature_id].repeatable:
            raise FeatureAlreadyHeldError(
                detail=f"The holder already has {feature_id}, which is not repeatable"
            )
        met = all(
            holds_comparison(p, holder_numbers) for p in found.prerequisites.get(feature_id, [])
        )
        if not met and not override:
            raise InvalidGrantPickError(detail=f"The holder does not meet what {feature_id} needs")
    total = len(choice.picked) + len(wanted)
    if total > choice.maximum and not override:
        raise InvalidGrantPickError(
            detail=f"That is {total} picks, and this rule allows {choice.maximum}"
        )
    if total < choice.minimum and not override:
        raise InvalidGrantPickError(
            detail=f"That is {total} picks, and this rule needs at least {choice.minimum}"
        )
    return [
        await grant(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            holder_id=holder_id,
            feature=features[feature_id],
            rule_id=rule.id,
            source_ref_id=choice.standing.ref_id,
        )
        for feature_id in wanted
    ]


async def apply_grants(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    holder_id: uuid.UUID,
    picks: list[PickSpec],
    override: bool,
) -> Applied:
    """Revokes what is orphaned, makes the automatic grants that are due and records the picks,
    and repeats until nothing more changes, because a granted feature is itself a source
    (RFC 0054 section 4). A (rule, source) grants once, so a second apply grants nothing new, and
    `MAX_DEPTH` stops a cycle of rules. A pick that no open choice takes by the end is refused."""
    pending: dict[tuple[uuid.UUID, uuid.UUID], list[uuid.UUID]] = {}
    for pick in picks:
        pending.setdefault((pick.rule_id, pick.source_id), []).extend(pick.options)
    applied = Applied()
    for _ in range(MAX_DEPTH):
        progress = False
        found = await compute(session, tenant_id, holder_id)
        if found.orphans:
            by_reason: dict[Reason, list[GrantRecord]] = defaultdict(list)
            for orphan in found.orphans:
                by_reason[orphan.reason].append(orphan.record)
            for reason, records in by_reason.items():
                applied.revoked += await revoke(
                    session, tenant_id=tenant_id, actor_id=actor_id, records=records, reason=reason
                )
            progress = True
            found = await compute(session, tenant_id, holder_id)
        for due in found.due:
            applied.created.append(
                await grant(
                    session,
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    holder_id=holder_id,
                    feature=found.features[due.feature_id],
                    rule_id=due.standing.rule.id,
                    source_ref_id=due.standing.ref_id,
                )
            )
            progress = True
        if found.due:
            found = await compute(session, tenant_id, holder_id)
        for choice in found.open_choices:
            wanted = pending.pop((choice.standing.rule.id, choice.standing.ref_id), None)
            if wanted is None:
                continue
            applied.created += await _pick(
                session,
                tenant_id=tenant_id,
                actor_id=actor_id,
                holder_id=holder_id,
                found=found,
                choice=choice,
                wanted=list(dict.fromkeys(wanted)),
                override=override,
            )
            progress = True
        if not progress:
            break
    else:
        applied.truncated = True
    if pending:
        rule_id, source_id = next(iter(pending))
        raise InvalidGrantPickError(
            detail=f"No open choice for rule {rule_id} through source {source_id}"
        )
    return applied
