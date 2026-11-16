"""The features a holder has (ADR 0454, RFC 0054 F1).

A feature is an entry of the kind `feature`; what a holder has of it is an entry of the kind
`feature_instance`, with the feature as its one prototype, contained by the holder. This module
reads and writes those: who holds, who may manage a holder, the instances of one holder with their
effective stats, and the removal of what a holder held when the holder goes.
"""

import uuid
from collections.abc import Collection, Sequence
from typing import Literal

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from lorenzo_api.campaign_access import (
    can_author_entry,
    can_manage_any_campaign_in_tenant,
    can_manage_owner,
)
from lorenzo_api.entity_access import can_self_manage_entity
from lorenzo_api.entry_visibility import unhidden
from lorenzo_api.exceptions import FeatureManagementForbiddenError, InvalidFeatureHolderError
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import (
    Being,
    Containment,
    Entity,
    EntityPrototype,
    Feature,
    FeatureInstance,
    GrantRecord,
    GrantRule,
    GroupMember,
    ItemInstance,
    Ownership,
    StatDefinition,
    StatGroup,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import _stats_out
from lorenzo_api.schemas.features import GrantedByOut, HeldFeatureOut
from lorenzo_api.schemas.grant_rules import RuleOptionOut
from lorenzo_api.stat_contents import attach_contents

HolderKind = Literal["being", "item_instance", "group"]


async def holder_kind(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> HolderKind | None:
    """What kind of holder the entry is: a being, an item instance, or a group (an entry that has
    members, ADR 0045: a group has no table of its own), else `None`."""
    if await session.scalar(
        select(Being.entity_id).where(Being.entity_id == entity_id, Being.tenant_id == tenant_id)
    ):
        return "being"
    if await session.scalar(
        select(ItemInstance.entity_id).where(
            ItemInstance.entity_id == entity_id, ItemInstance.tenant_id == tenant_id
        )
    ):
        return "item_instance"
    if await session.scalar(
        select(GroupMember.group_entity_id)
        .where(GroupMember.group_entity_id == entity_id, GroupMember.tenant_id == tenant_id)
        .limit(1)
    ):
        return "group"
    return None


async def require_holder(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> HolderKind:
    kind = await holder_kind(session, tenant_id=tenant_id, entity_id=entity_id)
    if kind is None:
        raise InvalidFeatureHolderError(
            detail=f"Entry {entity_id} is not a being, an item instance or a group"
        )
    return kind


async def manages_holder(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    holder_id: uuid.UUID,
    kind: HolderKind,
) -> bool:
    """Whether the caller manages what the holder has: a GM of a campaign it plays in (a group's
    are its members', ADR 0124); for a being or group in none, an administrator and the GMs ADR
    0151 names; for an item instance, whoever manages its owner, or any GM in the tenant when
    nobody owns it. In a repository, an Author, whose reach is every entry (ADR 0219)."""
    if kind == "item_instance":
        owner = await session.scalar(
            select(Ownership.owner_character_id).where(
                Ownership.owned_entity_id == holder_id, Ownership.tenant_id == tenant_id
            )
        )
        managed = (
            await can_manage_owner(
                session, user_id=user_id, owner_entity_id=owner, tenant_id=tenant_id
            )
            if owner is not None
            else await can_manage_any_campaign_in_tenant(
                session, user_id=user_id, tenant_id=tenant_id
            )
        )
    else:
        managed = await can_manage_owner(
            session, user_id=user_id, owner_entity_id=holder_id, tenant_id=tenant_id
        )
    return managed or await can_author_entry(
        session, tenant_id=tenant_id, user_id=user_id, entity_id=holder_id
    )


async def require_manager(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    holder_id: uuid.UUID,
    kind: HolderKind,
) -> None:
    if not await manages_holder(
        session, tenant_id=tenant_id, user_id=user_id, holder_id=holder_id, kind=kind
    ):
        raise FeatureManagementForbiddenError(
            detail=f"Not authorized to manage the features of {holder_id}"
        )


async def may_flip(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    holder_id: uuid.UUID,
    instance_id: uuid.UUID,
    kind: HolderKind,
) -> bool:
    """The switch is the holder's to flip: anyone whose characters or groups reach the instance
    (ADR 0124's rule for editing what one holds), or a manager of the holder."""
    return await can_self_manage_entity(
        session, entity_id=instance_id, user_id=user_id, tenant_id=tenant_id
    ) or await manages_holder(
        session, tenant_id=tenant_id, user_id=user_id, holder_id=holder_id, kind=kind
    )


async def holder_of(
    session: AsyncSession, *, tenant_id: uuid.UUID, instance_id: uuid.UUID
) -> uuid.UUID | None:
    """The holder of a feature instance: the entry that contains it."""
    found: uuid.UUID | None = await session.scalar(
        select(Containment.parent_entity_id).where(
            Containment.child_entity_id == instance_id, Containment.tenant_id == tenant_id
        )
    )
    return found


async def feature_of(
    session: AsyncSession, *, tenant_id: uuid.UUID, instance_id: uuid.UUID
) -> uuid.UUID | None:
    """The feature an instance is of: its one prototype."""
    found: uuid.UUID | None = await session.scalar(
        select(EntityPrototype.prototype_id).where(
            EntityPrototype.entity_id == instance_id, EntityPrototype.tenant_id == tenant_id
        )
    )
    return found


async def held_instance_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, holder_id: uuid.UUID
) -> list[uuid.UUID]:
    """The feature instances a holder has, directly: what is contained by it and is an instance."""
    return list(
        await session.scalars(
            select(Containment.child_entity_id)
            .join(
                FeatureInstance,
                (FeatureInstance.entity_id == Containment.child_entity_id)
                & (FeatureInstance.tenant_id == Containment.tenant_id),
            )
            .where(Containment.parent_entity_id == holder_id, Containment.tenant_id == tenant_id)
        )
    )


async def create_instance(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    holder_id: uuid.UUID,
    feature: Feature,
    active: bool | None = None,
) -> Entity:
    """The instance of a feature a holder has: an entry named as the feature (no slug), the marker,
    the feature as its one prototype, and the holder as its container; switched on unless the
    feature starts its instances inactive or `active` says. Flushed, not committed."""
    feature_entity = await session.get_one(Entity, feature.entity_id)
    instance = Entity(
        tenant_id=tenant_id, name=feature_entity.name, created_by=actor_id, updated_by=actor_id
    )
    session.add(instance)
    await session.flush()
    session.add(
        FeatureInstance(
            entity_id=instance.id,
            tenant_id=tenant_id,
            active=active if active is not None else not feature.starts_inactive,
        )
    )
    session.add(
        EntityPrototype(
            entity_id=instance.id, prototype_id=feature.entity_id, tenant_id=tenant_id, position=0
        )
    )
    session.add(
        Containment(
            child_entity_id=instance.id, parent_entity_id=holder_id, tenant_id=tenant_id, quantity=1
        )
    )
    await session.flush()
    return instance


async def granted_by(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    instance_ids: Collection[uuid.UUID],
    visibility: InformationVisibility,
) -> dict[uuid.UUID, GrantedByOut]:
    """For each instance a rule gave, the rule and the source it was given from (ADR 0456): what
    `GET .../features` calls `granted_by`. An award has none. An entry the caller may not see (a
    library's hide, ADR 0437) is named `a hidden entry`, with no id."""
    if not instance_ids:
        return {}
    rows = (
        await session.execute(
            select(GrantRecord, GrantRule.label, Entity.name)
            .join(GrantRule, GrantRule.id == GrantRecord.rule_id)
            .outerjoin(Entity, Entity.id == GrantRecord.source_ref_id)
            .where(
                GrantRecord.tenant_id == tenant_id,
                GrantRecord.feature_instance_id.in_(set(instance_ids)),
                GrantRecord.state == "active",
            )
        )
    ).all()
    instances = set(
        await session.scalars(
            select(FeatureInstance.entity_id).where(
                FeatureInstance.tenant_id == tenant_id,
                FeatureInstance.entity_id.in_(
                    {r.source_ref_id for r, _, _ in rows if r.source_ref_id}
                ),
            )
        )
    ) | set(
        await session.scalars(
            select(ItemInstance.entity_id).where(
                ItemInstance.tenant_id == tenant_id,
                ItemInstance.entity_id.in_(
                    {r.source_ref_id for r, _, _ in rows if r.source_ref_id}
                ),
            )
        )
    )
    out: dict[uuid.UUID, GrantedByOut] = {}
    for record, label, source_name in rows:
        assert record.feature_instance_id is not None
        source = record.source_ref_id
        out[record.feature_instance_id] = GrantedByOut(
            record_id=record.id,
            rule_id=record.rule_id,
            label=label,
            source=(
                None
                if source is None
                else (
                    RuleOptionOut(id=source, name=source_name or "")
                    if visibility.can_see_entry(source)
                    else RuleOptionOut(id=None, name="a hidden entry", hidden=True)
                )
            ),
            source_kind=None
            if source is None
            else ("instance" if source in instances else "ancestor"),
        )
    return out


async def delete_held_features(
    session: AsyncSession, *, tenant_id: uuid.UUID, holder_ids: Collection[uuid.UUID]
) -> list[uuid.UUID]:
    """Deletes the feature instances the holders have, with their entries, and says which: an
    instance has no life of its own, so it goes with the holder (ADR 0454). Call before deleting
    a holder, whose containment rows would otherwise leave the instances behind."""
    if not holder_ids:
        return []
    held = (
        select(Containment.child_entity_id)
        .join(
            FeatureInstance,
            (FeatureInstance.entity_id == Containment.child_entity_id)
            & (FeatureInstance.tenant_id == Containment.tenant_id),
        )
        .where(Containment.parent_entity_id.in_(holder_ids), Containment.tenant_id == tenant_id)
    )
    return list(
        await session.scalars(
            delete(Entity)
            .where(Entity.tenant_id == tenant_id, Entity.id.in_(held))
            .returning(Entity.id)
        )
    )


async def visible_instance_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, holder_id: uuid.UUID
) -> list[uuid.UUID]:
    """The feature instances a holder has directly that the library does not hide (ADR 0437)."""
    ids = await held_instance_ids(session, tenant_id=tenant_id, holder_id=holder_id)
    if not ids:
        return []
    return list(
        await session.scalars(
            select(FeatureInstance.entity_id).where(
                FeatureInstance.entity_id.in_(ids),
                FeatureInstance.tenant_id == tenant_id,
                await unhidden(session, tenant_id, FeatureInstance.entity_id),
            )
        )
    )


async def holds_feature(
    session: AsyncSession, *, tenant_id: uuid.UUID, holder_id: uuid.UUID, feature_id: uuid.UUID
) -> bool:
    """Whether the holder has an instance of this feature."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Containment.parent_entity_id == holder_id,
                    Containment.tenant_id == tenant_id,
                    EntityPrototype.entity_id == Containment.child_entity_id,
                    EntityPrototype.prototype_id == feature_id,
                    EntityPrototype.tenant_id == tenant_id,
                    FeatureInstance.entity_id == Containment.child_entity_id,
                )
            )
        )
    )


async def usable_feature(
    session: AsyncSession, *, tenant_id: uuid.UUID, feature_id: uuid.UUID
) -> Feature | None:
    """The feature row, or `None` when the entry is not a feature of this tenant or the library
    hides it (ADR 0437): a hidden entry is answered as an unknown one."""
    found: Feature | None = await session.scalar(
        select(Feature).where(
            Feature.entity_id == feature_id,
            Feature.tenant_id == tenant_id,
            await unhidden(session, tenant_id, Feature.entity_id),
        )
    )
    return found


async def held_feature_outs(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    instance_ids: Sequence[uuid.UUID],
    visibility: InformationVisibility,
) -> list[HeldFeatureOut]:
    """The instances as the caller reads them, by name then id: the instance, its feature, the
    feature's types (its direct parents the caller may see), the switch and the effective stats
    (the instance's own over what it inherits, formulas evaluated as on an entry's read)."""
    if not instance_ids:
        return []
    entities = list(
        (
            await session.scalars(
                select(Entity)
                .where(Entity.tenant_id == tenant_id, Entity.id.in_(instance_ids))
                .options(
                    selectinload(Entity.effective_stats)
                    .joinedload(VEffectiveStat.stat_definition)
                    .joinedload(StatDefinition.stat_group)
                    .joinedload(StatGroup.system),
                    selectinload(Entity.effective_stats)
                    .joinedload(VEffectiveStat.stat_definition)
                    .selectinload(StatDefinition.enum_values),
                    selectinload(Entity.effective_stats).joinedload(VEffectiveStat.source_entity),
                    *formula_load_options(
                        selectinload(Entity.effective_stats).selectinload(
                            VEffectiveStat.computed_stat
                        )
                    ),
                    joinedload(Entity.feature_instance_marker),
                )
                .order_by(Entity.name, Entity.id)
            )
        )
        .unique()
        .all()
    )
    await attach_contents(session, entities, tenant_id=tenant_id)
    feature_by_instance: dict[uuid.UUID, uuid.UUID] = {}
    for instance_id, feature_id in await session.execute(
        select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
            EntityPrototype.tenant_id == tenant_id,
            EntityPrototype.entity_id.in_(instance_ids),
        )
    ):
        feature_by_instance[instance_id] = feature_id
    features = {
        entity.id: entity
        for entity in await session.scalars(
            select(Entity).where(
                Entity.tenant_id == tenant_id, Entity.id.in_(set(feature_by_instance.values()))
            )
        )
    }
    type_ids: dict[uuid.UUID, list[uuid.UUID]] = {}
    for feature_id, parent_id in await session.execute(
        select(EntityPrototype.entity_id, EntityPrototype.prototype_id)
        .where(
            EntityPrototype.tenant_id == tenant_id,
            EntityPrototype.entity_id.in_(set(feature_by_instance.values())),
        )
        .order_by(EntityPrototype.entity_id, EntityPrototype.position, EntityPrototype.prototype_id)
    ):
        if visibility.can_see_entry(parent_id):
            type_ids.setdefault(feature_id, []).append(parent_id)
    parents = {
        entity.id: entity
        for entity in await session.scalars(
            select(Entity).where(
                Entity.tenant_id == tenant_id,
                Entity.id.in_({p for ids in type_ids.values() for p in ids}),
            )
        )
    }
    given = await granted_by(
        session, tenant_id=tenant_id, instance_ids=instance_ids, visibility=visibility
    )
    out: list[HeldFeatureOut] = []
    for entity in entities:
        feature_id = feature_by_instance.get(entity.id)
        feature = features.get(feature_id) if feature_id is not None else None
        if feature is None or entity.feature_instance_marker is None:
            continue
        out.append(
            HeldFeatureOut(
                id=entity.id,
                name=entity.name,
                feature=EntitySummary.from_entity(feature),
                types=[EntitySummary.from_entity(parents[p]) for p in type_ids.get(feature.id, [])],
                active=entity.feature_instance_marker.active,
                stats=_stats_out(entity, visibility),
                granted_by=given.get(entity.id),
            )
        )
    return out
