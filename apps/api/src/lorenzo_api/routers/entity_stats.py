from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select

from lorenzo_api.campaign_access import (
    campaign_ids_for_character,
    can_manage_any_campaign_in_tenant,
    can_manage_any_of_campaigns,
)
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_entity_or_404,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import can_self_manage_entity
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import (
    ComputedStatConflictError,
    EntityStatManagementForbiddenError,
    InvalidStatValueError,
    InvalidStatValueTypeError,
    StatDefinitionNotFoundError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    ComputedStat,
    EntityStat,
    EntityStatGroup,
    Ownership,
    StatDefinition,
    StatDefinitionEnumValue,
    StatValueType,
)
from lorenzo_api.routers.entities import get_entity_detail_or_404
from lorenzo_api.schemas.entities import EntityDetailOut
from lorenzo_api.schemas.stats import SetEntityStatRequest

# get_tenant_or_404 here, not get_tenant_context (mirrors
# routers/item_instances.py's identical ADR 0032/RFC 0005 precedent) -
# setting your own character's or item's stats is self-or-managed (RFC
# 0008/ADR 0037), and neither a plain Player nor a campaign's own GM implies
# a tenant-wide Membership row (ADR 0022). Every write route below does its
# own explicit self-or-managed check instead. Serves both .../stats/{id}
# and ADR 0103's .../tags/{id}, which share one write path.
router = APIRouter(
    prefix="/tenants/{tenant_id}/entities/{entity_id}",
    tags=["entity-stats"],
    dependencies=[Depends(get_tenant_or_404)],
)


async def _authorize_entity_stat_write(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, entity_id: uuid.UUID
) -> None:
    """RFC 0008/ADR 0037's self-or-managed tier for entity_stat writes -
    generalized from routers/item_instances.py's own _authorize_instance_write
    (ADR 0032/RFC 0005) from "an item instance" to "any entity": self-service
    if entity_id is reachable from one of the caller's own characters
    (entity_access.can_self_manage_entity - this already covers a player's
    own character directly, not just their owned items, since a controlled
    character is itself one of reachable_entity_ids' own roots); otherwise,
    if the entity is Ownership-owned by some character, that owner's own
    campaign(s) need can_manage_campaign; an entity with no owner at all
    (a catalog prototype like "Sword"/"Flaming Sword", never owned by
    anyone) falls back to can_manage_any_campaign_in_tenant - which a tenant
    OWNER/ORGA always satisfies regardless of whether any campaign exists
    yet (campaign_access.is_tenant_admin), so authoring catalog stats stays
    reachable for the same tenant-admin-shaped callers items.py's own
    tenant-admin tier already serves, without a second, separate check here.
    """
    if await can_self_manage_entity(
        session, entity_id=entity_id, user_id=user.id, tenant_id=tenant_id
    ):
        return
    owner_stmt = select(Ownership.owner_character_id).where(
        Ownership.owned_entity_id == entity_id, Ownership.tenant_id == tenant_id
    )
    current_owner_id = (await session.execute(owner_stmt)).scalar_one_or_none()
    if current_owner_id is not None:
        campaign_ids = await campaign_ids_for_character(
            session, character_entity_id=current_owner_id, tenant_id=tenant_id
        )
        if campaign_ids and await can_manage_any_of_campaigns(
            session, user_id=user.id, campaign_ids=campaign_ids, tenant_id=tenant_id
        ):
            return
    elif await can_manage_any_campaign_in_tenant(session, user_id=user.id, tenant_id=tenant_id):
        return
    raise EntityStatManagementForbiddenError(
        detail=f"Not authorized to manage stats on entity {entity_id}"
    )


async def _validate_value(
    session: SessionDep, value: int | str | float | bool, stat_definition: StatDefinition
) -> None:
    """Real type-checking at the application level (ADR 0014's own gap:
    entity_stat's CHECK constraint only enforces "exactly one value_* column
    is set," not which one matches stat_definition.value_type). bool is
    checked before int since Python's bool is an int subclass - a JSON
    `true`/`false` must resolve to BOOL, never INT. No int<->float
    coercion: a stat declared `float` must be sent as a JSON number with a
    fractional/exponent part, matching this project's existing preference
    for real typed columns over a single untyped one every write has to be
    trusted against. An `enum` stat takes a string that must be one of its
    allowed values (ADR 0103).
    """
    if isinstance(value, bool):
        actual = StatValueType.BOOL
    elif isinstance(value, int):
        actual = StatValueType.INT
    elif isinstance(value, float):
        actual = StatValueType.FLOAT
    else:
        actual = StatValueType.TEXT
    expected = stat_definition.value_type
    if expected is StatValueType.ENUM and actual is StatValueType.TEXT:
        allowed = await session.scalar(
            select(StatDefinitionEnumValue.id).where(
                StatDefinitionEnumValue.stat_definition_id == stat_definition.id,
                StatDefinitionEnumValue.value == value,
            )
        )
        if allowed is None:
            raise InvalidStatValueError(
                detail=f"{value!r} is not an allowed value of stat {stat_definition.name!r}"
            )
        return
    if actual is not expected:
        raise InvalidStatValueTypeError(
            detail=(
                f"Stat {stat_definition.name!r} is declared "
                f"{expected.value}, got a {actual.value} value"
            )
        )


def _apply_stat_value(
    stat: EntityStat, *, value: int | str | float | bool, value_type: StatValueType
) -> None:
    """Sets exactly the value_* column stat_definition.value_type calls for
    and clears the other three, keeping entity_stat's own
    num_nonnulls(...) = 1 CHECK constraint (ADR 0014) satisfied even when
    overwriting a row that - in principle, though _validate_value_type
    above never lets a mismatched value reach here - previously held a
    different type. The isinstance asserts are pure type-narrowing for
    mypy; _validate_value_type already guarantees each one holds.
    """
    stat.value_int = None
    stat.value_text = None
    stat.value_float = None
    stat.value_bool = None
    if value_type is StatValueType.INT:
        assert isinstance(value, int) and not isinstance(value, bool)
        stat.value_int = value
    elif value_type in (StatValueType.TEXT, StatValueType.ENUM):
        assert isinstance(value, str)
        stat.value_text = value
    elif value_type is StatValueType.FLOAT:
        assert isinstance(value, float)
        stat.value_float = value
    else:
        assert isinstance(value, bool)
        stat.value_bool = value


async def _get_stat_definition_or_404(
    session: SessionDep, stat_definition_id: uuid.UUID, tenant_id: uuid.UUID
) -> StatDefinition:
    stmt = select(StatDefinition).where(
        StatDefinition.id == stat_definition_id, StatDefinition.tenant_id == tenant_id
    )
    stat_definition = (await session.execute(stmt)).scalar_one_or_none()
    if stat_definition is None:
        raise StatDefinitionNotFoundError(
            detail=f"No stat definition with id {stat_definition_id} in tenant {tenant_id}"
        )
    return stat_definition


async def _write_own_value(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition: StatDefinition,
    value: int | str | float | bool,
    if_match: str | None,
    acquire_group: bool,
) -> None:
    """The one path that sets an entity's own entity_stat row - shared by
    the stat PUT and ADR 0103's tag PUT/PATCH so they can't drift. 409 if
    the entity holds a formula for this stat (ADR 0104: one or the other).
    `acquire_group` adds the stat's group to the entity (entity_stat_group)
    when missing: the tag routes do, closing ADR 0037's named gap for them;
    the generic stat PUT keeps its original behavior. The caller has
    already authorized and validated `value`.
    """
    if await session.get(ComputedStat, (entity_id, stat_definition.id)) is not None:
        raise ComputedStatConflictError(
            detail=(
                f"Entity {entity_id} has a formula for {stat_definition.name!r}; "
                "delete it before setting a direct value"
            )
        )
    existing = await session.get(EntityStat, (entity_id, stat_definition.id))
    if existing is not None:
        check_if_match(if_match, updated_at=existing.updated_at)
        stat = existing
    else:
        stat = EntityStat(
            entity_id=entity_id, stat_definition_id=stat_definition.id, tenant_id=tenant_id
        )
        session.add(stat)
    _apply_stat_value(stat, value=value, value_type=stat_definition.value_type)
    if acquire_group:
        link = await session.get(EntityStatGroup, (entity_id, stat_definition.stat_group_id))
        if link is None:
            session.add(
                EntityStatGroup(
                    entity_id=entity_id,
                    stat_group_id=stat_definition.stat_group_id,
                    tenant_id=tenant_id,
                )
            )


async def _entity_detail(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
) -> EntityDetailOut:
    detail_entity = await get_entity_detail_or_404(session, entity_id, tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return EntityDetailOut.from_entity(detail_entity, request, visibility=visibility)


@router.put("/stats/{stat_definition_id}")
async def set_entity_stat(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    body: SetEntityStatRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Deliberately not recorded in the activity log (ADR 0084: stat-value
    writes are descriptive-content edits, not structural changes).

    Sets (creating or overwriting) entity_id's own direct value for one
    stat_definition - see ADR 0037/RFC 0008. Returns the full
    EntityDetailOut, not a narrower per-stat shape: this write is
    entity-generic (a character's hp, an item's or item-instance's weight,
    a bare catalog prototype's own base value), so there's no single
    item/item-instance-shaped canonical resource to return the way
    routers/items.py's writes do - GET /entities/{id}'s own existing shape
    (routers/entities.get_entity_detail_or_404) already is that canonical
    shape for an entity, reused here rather than inventing a new one.

    Check order: both path-addressed resources first (entity, then
    stat_definition - 404, existence hidden, ADR 0032's own convention),
    then authorization (403 - the caller can already see both by this
    point, they may just lack a specific write permission), then the body's
    value (422), then If-Match (412) against the entity_stat row's own
    updated_at if one already exists. Deliberately not the exact order
    routers/item_instances.py's writes use (If-Match before authorization)
    - that order relies on the write's target (Entity) always already
    existing by the time If-Match is checked; entity_stat itself might not
    exist yet (a first-time set), so there is nothing to compare an
    If-Match header against until the target stat_definition is confirmed
    valid. A caller sending If-Match on a first-ever set is not rejected -
    there is no prior version to have gone stale relative to.
    """
    entity = await get_entity_or_404(session, entity_id, tenant_id)
    stat_definition = await _get_stat_definition_or_404(session, stat_definition_id, tenant_id)
    await _authorize_entity_stat_write(session, tenant_id=tenant_id, user=user, entity_id=entity.id)
    await _validate_value(session, body.value, stat_definition)

    await _write_own_value(
        session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        stat_definition=stat_definition,
        value=body.value,
        if_match=if_match,
        acquire_group=False,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _entity_detail(
        session, tenant_id=tenant_id, entity_id=entity_id, request=request, user=user
    )


async def _set_tag(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    value: bool,
    request: Request,
    user: CurrentUser,
    if_match: str | None,
) -> EntityDetailOut:
    entity = await get_entity_or_404(session, entity_id, tenant_id)
    stat_definition = await _get_stat_definition_or_404(session, stat_definition_id, tenant_id)
    await _authorize_entity_stat_write(session, tenant_id=tenant_id, user=user, entity_id=entity.id)
    await _validate_value(session, value, stat_definition)
    await _write_own_value(
        session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        stat_definition=stat_definition,
        value=value,
        if_match=if_match,
        acquire_group=True,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _entity_detail(
        session, tenant_id=tenant_id, entity_id=entity_id, request=request, user=user
    )


@router.put("/tags/{stat_definition_id}")
async def set_entity_tag(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Sets a bool stat to `true` on this entity itself, and adds the
    stat's group to the entity if missing - ADR 0103/RFC 0016. No body.
    Same checks, order, and authorization as set_entity_stat; a non-bool
    stat is 422. Not logged (ADR 0084: stat values).
    """
    return await _set_tag(
        session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        stat_definition_id=stat_definition_id,
        value=True,
        request=request,
        user=user,
        if_match=if_match,
    )


@router.patch("/tags/{stat_definition_id}")
async def unset_entity_tag(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Sets a bool stat to an explicit `false` on this entity itself - an
    override of whatever a prototype says, not silence (ADR 0103: the door
    built on the `wood` prototype but since rebuilt in metal). Otherwise
    identical to set_entity_tag, group acquisition included.
    """
    return await _set_tag(
        session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        stat_definition_id=stat_definition_id,
        value=False,
        request=request,
        user=user,
        if_match=if_match,
    )


@router.delete("/tags/{stat_definition_id}")
async def clear_entity_tag(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Removes this entity's own value for a bool stat, so it's inherited
    through the prototype chain again - ADR 0103. Idempotent: nothing to
    remove is still 200. Returns the entity (like the stat PUT), not 204,
    so the caller sees the inherited value it now resolves to. Leaves
    group acquisition alone - other stats in the group may still need it.
    """
    entity = await get_entity_or_404(session, entity_id, tenant_id)
    stat_definition = await _get_stat_definition_or_404(session, stat_definition_id, tenant_id)
    await _authorize_entity_stat_write(session, tenant_id=tenant_id, user=user, entity_id=entity.id)
    if stat_definition.value_type is not StatValueType.BOOL:
        raise InvalidStatValueTypeError(
            detail=f"Stat {stat_definition.name!r} is {stat_definition.value_type.value}, not bool"
        )
    existing = await session.get(EntityStat, (entity_id, stat_definition_id))
    if existing is not None:
        check_if_match(if_match, updated_at=existing.updated_at)
        await session.delete(existing)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _entity_detail(
        session, tenant_id=tenant_id, entity_id=entity_id, request=request, user=user
    )
