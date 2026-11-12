"""The features a holder has (ADR 0454, RFC 0054 F1): list, award, remove and switch.

Under `/tenants/{t}/entities/{holder}/features` for what a holder has and `/tenants/{t}/features`
for one instance. The catalogue of features is the bulk effective-stat read with `kind=feature`;
a feature's two columns have their own read here. `get_tenant_or_404` like the item instances:
browsing what a character has is for a player, who has no tenant-wide Membership (ADR 0022).
"""

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.change_feed import Change, holders, record_change
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_entity_or_404,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import unhidden
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    FeatureAlreadyHeldError,
    FeatureManagementForbiddenError,
    FeatureNotFoundError,
    InvalidFeatureError,
)
from lorenzo_api.features import (
    HolderKind,
    feature_of,
    held_feature_outs,
    held_instance_ids,
    holder_kind,
    holder_of,
    holds_feature,
    manages_holder,
    may_flip,
    require_holder,
    require_manager,
    usable_feature,
)
from lorenzo_api.information_visibility import InformationVisibility, resolve_information_visibility
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    FeatureInstance,
)
from lorenzo_api.routers.item_instances import caller_reach
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.features import (
    FeatureActiveIn,
    FeatureAwardIn,
    FeatureColumnsOut,
    HeldFeatureOut,
    HeldFeaturesOut,
)

entry_router = APIRouter(
    prefix="/tenants/{tenant_id}/entities/{entity_id}/features",
    tags=["features"],
    dependencies=[Depends(get_tenant_or_404)],
)
router = APIRouter(
    prefix="/tenants/{tenant_id}/features",
    tags=["features"],
    dependencies=[Depends(get_tenant_or_404)],
)


async def _may_read(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    visibility: InformationVisibility,
    holder_id: uuid.UUID,
    kind: HolderKind | None,
    instance_id: uuid.UUID | None = None,
) -> bool:
    """Whether the caller reads what the holder has: they reach the holder (ADR 0040's sets, as
    `held-by` has it), or manage it, so that what an administrator just awarded can be read back.
    An entry that holds nothing has no reach to ask for: whoever reads at all reads the 422."""
    if kind is None:
        return True
    reach = await caller_reach(session, tenant_id=tenant_id, user=user, visibility=visibility)
    if reach is None or holder_id in reach or (instance_id is not None and instance_id in reach):
        return True
    return await manages_holder(
        session, tenant_id=tenant_id, user_id=user.id, holder_id=holder_id, kind=kind
    )


@entry_router.get("")
async def list_held_features(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> HeldFeaturesOut:
    """What the holder has: each instance with its feature, the feature's types, its switch and
    its effective stats, by name then id. The holder must be one the caller reaches (ADR 0040's
    sets, as `held-by` has it), else `404` like an entry that does not exist; an instance a
    library hides (ADR 0437) is left out. `422` for an entry that is not a being, an item instance
    or a group."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    holder = await get_entity_or_404(session, entity_id, tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    kind = await holder_kind(session, tenant_id=tenant_id, entity_id=entity_id)
    if not await _may_read(
        session,
        tenant_id=tenant_id,
        user=user,
        visibility=visibility,
        holder_id=entity_id,
        kind=kind,
    ):
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    await require_holder(session, tenant_id=tenant_id, entity_id=entity_id)
    ids = await held_instance_ids(session, tenant_id=tenant_id, holder_id=entity_id)
    if ids:
        ids = list(
            await session.scalars(
                select(FeatureInstance.entity_id).where(
                    FeatureInstance.entity_id.in_(ids),
                    FeatureInstance.tenant_id == tenant_id,
                    await unhidden(session, tenant_id, FeatureInstance.entity_id),
                )
            )
        )
    return HeldFeaturesOut(
        holder=EntitySummary.from_entity(holder),
        features=await held_feature_outs(
            session, tenant_id=tenant_id, instance_ids=ids, visibility=visibility
        ),
    )


@entry_router.post("", status_code=201)
async def award_feature(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: FeatureAwardIn,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> HeldFeatureOut:
    """An award (ADR 0454): the holder has the feature, with no rule behind it. An instance is a
    new entry named as the feature, with the feature as its one prototype, contained by the holder,
    switched on unless the feature starts its instances inactive or the body says. The holder's
    manager only (`403`): a GM of its campaigns, an administrator for one in none, an Author in a
    repository. `409` for a feature the holder has and that is not `repeatable`, `422` for an entry
    that is no feature here (a hidden one included) or a holder that holds nothing."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    holder = await get_entity_or_404(session, entity_id, tenant_id)
    kind = await require_holder(session, tenant_id=tenant_id, entity_id=entity_id)
    await require_manager(
        session, tenant_id=tenant_id, user_id=user.id, holder_id=entity_id, kind=kind
    )
    feature = await usable_feature(session, tenant_id=tenant_id, feature_id=body.feature_id)
    if feature is None:
        raise InvalidFeatureError(
            detail=f"{body.feature_id} is not a feature in tenant {tenant_id}"
        )
    if not feature.repeatable and await holds_feature(
        session, tenant_id=tenant_id, holder_id=entity_id, feature_id=feature.entity_id
    ):
        raise FeatureAlreadyHeldError(
            detail=f"{holder.name} already has this feature, which is not repeatable"
        )
    feature_entity = await session.get_one(Entity, feature.entity_id)
    instance = Entity(
        tenant_id=tenant_id, name=feature_entity.name, created_by=user.id, updated_by=user.id
    )
    session.add(instance)
    await session.flush()
    session.add(
        FeatureInstance(
            entity_id=instance.id,
            tenant_id=tenant_id,
            active=body.active if body.active is not None else not feature.starts_inactive,
        )
    )
    session.add(
        EntityPrototype(
            entity_id=instance.id,
            prototype_id=feature.entity_id,
            tenant_id=tenant_id,
            position=0,
        )
    )
    session.add(
        Containment(
            child_entity_id=instance.id,
            parent_entity_id=entity_id,
            tenant_id=tenant_id,
            quantity=1,
        )
    )
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="feature.awarded",
        target_type="feature_instance",
        target_id=instance.id,
        detail=f"holder={entity_id},feature={feature.entity_id}",
    )
    await record_change(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        changes=[Change(entity_id=instance.id, before=frozenset(), both_kind=None)],
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_held_feature", tenant_id=tenant_id, instance_id=instance.id)
    )
    return await _one(session, tenant_id=tenant_id, instance_id=instance.id, user=user)


@router.get("/prototypes/{feature_id}")
async def get_feature_columns(
    tenant_id: uuid.UUID, feature_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> FeatureColumnsOut:
    """The two columns of a feature, `repeatable` and `starts_inactive`, which `PUT
    .../entities/{id}/kinds/feature` sets."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    entity = await get_entity_or_404(session, feature_id, tenant_id)
    feature = await usable_feature(session, tenant_id=tenant_id, feature_id=feature_id)
    if feature is None:
        raise FeatureNotFoundError(detail=f"No feature with id {feature_id} in tenant {tenant_id}")
    return FeatureColumnsOut(
        id=entity.id,
        name=entity.name,
        repeatable=feature.repeatable,
        starts_inactive=feature.starts_inactive,
    )


async def _one(
    session: SessionDep, *, tenant_id: uuid.UUID, instance_id: uuid.UUID, user: CurrentUser
) -> HeldFeatureOut:
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    found = await held_feature_outs(
        session, tenant_id=tenant_id, instance_ids=[instance_id], visibility=visibility
    )
    if not found:
        raise FeatureNotFoundError(detail=f"No feature with id {instance_id} in tenant {tenant_id}")
    return found[0]


async def _instance_or_404(
    session: SessionDep, *, tenant_id: uuid.UUID, instance_id: uuid.UUID
) -> uuid.UUID:
    """The instance's holder, or `404` for an id that is no feature instance of this tenant."""
    holder_id = await holder_of(session, tenant_id=tenant_id, instance_id=instance_id)
    if holder_id is None or not await session.scalar(
        select(func.count()).where(
            FeatureInstance.entity_id == instance_id, FeatureInstance.tenant_id == tenant_id
        )
    ):
        raise FeatureNotFoundError(detail=f"No feature with id {instance_id} in tenant {tenant_id}")
    return holder_id


@router.get("/{instance_id}")
async def get_held_feature(
    tenant_id: uuid.UUID, instance_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> HeldFeatureOut:
    """One feature a holder has. `404` for an instance the caller does not reach: it is as
    visible as what the holder holds (ADR 0040)."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    holder_id = await _instance_or_404(session, tenant_id=tenant_id, instance_id=instance_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    kind = await holder_kind(session, tenant_id=tenant_id, entity_id=holder_id)
    if not await _may_read(
        session,
        tenant_id=tenant_id,
        user=user,
        visibility=visibility,
        holder_id=holder_id,
        kind=kind,
        instance_id=instance_id,
    ):
        raise FeatureNotFoundError(detail=f"No feature with id {instance_id} in tenant {tenant_id}")
    return await _one(session, tenant_id=tenant_id, instance_id=instance_id, user=user)


@router.put("/{instance_id}/active")
async def set_feature_active(
    tenant_id: uuid.UUID,
    instance_id: uuid.UUID,
    body: FeatureActiveIn,
    session: SessionDep,
    user: CurrentUser,
) -> HeldFeatureOut:
    """The switch a formula reads with `only_active` (ADR 0447), flipped by whoever reaches the
    instance (ADR 0124) or manages its holder. It is no activity-log event, like an item's."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    holder_id = await _instance_or_404(session, tenant_id=tenant_id, instance_id=instance_id)
    kind = await holder_kind(session, tenant_id=tenant_id, entity_id=holder_id)
    if kind is None or not await may_flip(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        holder_id=holder_id,
        instance_id=instance_id,
        kind=kind,
    ):
        raise FeatureManagementForbiddenError(
            detail=f"Not authorized to change feature {instance_id}"
        )
    instance = await session.get_one(FeatureInstance, instance_id)
    if instance.active != body.active:
        instance.active = body.active
        entity = await session.get_one(Entity, instance_id)
        entity.updated_by = user.id
        entity.updated_at = func.now()
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _one(session, tenant_id=tenant_id, instance_id=instance_id, user=user)


@router.delete("/{instance_id}", status_code=204)
async def remove_feature(
    tenant_id: uuid.UUID, instance_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    """Takes the feature from its holder: the instance goes, with what it kept (its own stats).
    The holder's manager only (`403`)."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    holder_id = await _instance_or_404(session, tenant_id=tenant_id, instance_id=instance_id)
    kind = await holder_kind(session, tenant_id=tenant_id, entity_id=holder_id)
    if kind is None:
        raise FeatureNotFoundError(detail=f"No feature with id {instance_id} in tenant {tenant_id}")
    await require_manager(
        session, tenant_id=tenant_id, user_id=user.id, holder_id=holder_id, kind=kind
    )
    entity = await session.get_one(Entity, instance_id)
    feature_id = await feature_of(session, tenant_id=tenant_id, instance_id=instance_id)
    before = await holders(session, tenant_id=tenant_id, entity_id=instance_id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="feature.removed",
        target_type="feature_instance",
        target_id=instance_id,
        detail=f"holder={holder_id},feature={feature_id}",
    )
    await record_change(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        changes=[
            Change(
                entity_id=instance_id,
                before=before,
                both_kind=None,
                deleted=True,
                entity_name=entity.name,
            )
        ],
    )
    await session.delete(entity)
    await session.commit()
