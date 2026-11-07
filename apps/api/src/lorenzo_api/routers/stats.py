from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_admin_context,
    get_tenant_context,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    InvalidStatEnumValuesError,
    InvalidStatGroupError,
    InvalidStatHintError,
    InvalidStatOrderError,
    InvalidStatScaleError,
    StatDefinitionInUseError,
    StatDefinitionNameTakenError,
    StatDefinitionNotFoundError,
    StatEnumValueAlreadyExistsError,
    StatEnumValueInUseError,
    StatEnumValueNotFoundError,
    StatGroupInUseError,
    StatGroupNameTakenError,
    StatGroupNotFoundError,
    StatNameReservedError,
    StatScaleBreaksValuesError,
)
from lorenzo_api.library_counts import count_libraries, libraries_note
from lorenzo_api.models import (
    ComputedStat,
    ComputedStatComparison,
    ComputedStatContents,
    ComputedStatLinear,
    ComputedStatSumTerm,
    EntityStat,
    EntityStatGroup,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
)
from lorenzo_api.schemas.library_counts import LibraryCountOut
from lorenzo_api.schemas.stats import (
    StatDefinitionCreate,
    StatDefinitionOrder,
    StatDefinitionOut,
    StatDefinitionUpdate,
    StatEnumValueCreate,
    StatEnumValueUpdate,
    StatGroupCreate,
    StatGroupOrder,
    StatGroupOut,
    StatGroupUpdate,
)
from lorenzo_api.stat_enum_values import (
    RESERVED_ENUM_VALUES,
    RESERVED_STAT_NAMES,
    enum_value_uses,
    rename_enum_value_text,
)


# get_tenant_context here, not per-route (ADR 0020's revised guidance,
# matching routers/items.py's identical precedent) - every route on this
# router needs it and none read its return value. stat_group/stat_definition
# are the shared stat vocabulary ("physical," "weight," ...), the same kind
# of authored catalog concern as item's own prototypes (ADR 0032/ADR 0037, RFC
# 0008): any member, an Author too, adds to it; deleting from it is an
# administrator's (get_tenant_admin_context, ADR 0219) since subscribers use it.
async def _vocabulary_gate(
    request: Request, tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    """Writing the stat vocabulary is for the tenant's Owners, Organizers and Authors (ADR
    0219), and deleting from it for its administrators, on the route; reading it is for any
    participant of the tenant (ADR 0281). A sheet needs the groups and definitions - which
    numbers a table may change, units, order, pins - to draw a being for the player of it, who
    has no membership. Not a participant is the same 404 as ever."""
    if request.method == "GET":
        await get_tenant_or_404(tenant_id, session, user, request)
        await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    else:
        await get_tenant_context(tenant_id, session, user, request)


router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["stats"],
    dependencies=[Depends(_vocabulary_gate)],
)


async def _get_stat_group_or_404(
    tenant_id: uuid.UUID, stat_group_id: uuid.UUID, session: SessionDep
) -> StatGroup:
    stmt = select(StatGroup).where(StatGroup.id == stat_group_id, StatGroup.tenant_id == tenant_id)
    stat_group = (await session.execute(stmt)).scalar_one_or_none()
    if stat_group is None:
        raise StatGroupNotFoundError(
            detail=f"No stat group with id {stat_group_id} in tenant {tenant_id}"
        )
    return stat_group


async def _get_stat_definition_or_404(
    tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, session: SessionDep
) -> StatDefinition:
    stmt = (
        select(StatDefinition)
        .where(StatDefinition.id == stat_definition_id, StatDefinition.tenant_id == tenant_id)
        .options(selectinload(StatDefinition.enum_values))
        # A re-read after adding/removing a value in the same session must
        # see the new list, not the identity map's copy.
        .execution_options(populate_existing=True)
    )
    stat_definition = (await session.execute(stmt)).scalar_one_or_none()
    if stat_definition is None:
        raise StatDefinitionNotFoundError(
            detail=f"No stat definition with id {stat_definition_id} in tenant {tenant_id}"
        )
    return stat_definition


_NUMERIC = (StatValueType.INT, StatValueType.FLOAT)


def _check_scale(value_type: StatValueType, low: float | None, high: float | None) -> None:
    """A scale is for an int or float stat, and its minimum is not above its maximum (ADR 0403)."""
    if (low is not None or high is not None) and value_type not in _NUMERIC:
        raise InvalidStatScaleError(
            detail=f"A scale is for an int or float stat, not {value_type.value}"
        )
    if low is not None and high is not None and low > high:
        raise InvalidStatScaleError(detail=f"The minimum {low:g} is above the maximum {high:g}")


async def _check_scale_holds(
    session: SessionDep, definition: StatDefinition, low: float | None, high: float | None
) -> None:
    """A bound that own values already break is a 409 with the number of entries (ADR 0403)."""
    column = (
        EntityStat.value_int
        if definition.value_type is StatValueType.INT
        else EntityStat.value_float
    )
    outside = [column < low] if low is not None else []
    if high is not None:
        outside.append(column > high)
    if not outside:
        return
    broken = await session.scalar(
        select(func.count())
        .select_from(EntityStat)
        .where(
            EntityStat.tenant_id == definition.tenant_id,
            EntityStat.stat_definition_id == definition.id,
            or_(*outside),
        )
    )
    if broken:
        raise StatScaleBreaksValuesError(
            detail=f"{broken} entries hold a value of {definition.name!r} outside that scale"
        )


async def _check_hints(
    session: SessionDep,
    tenant_id: uuid.UUID,
    hints: dict[str, uuid.UUID | None],
    *,
    own_id: uuid.UUID | None,
) -> None:
    """Every hint set is a definition of this tenant other than `own_id`, and a minimum or
    maximum is a number (ADR 0279). The database's key already keeps a hint in its tenant; this
    says so in words, before it would refuse in code."""
    wanted = {name: target for name, target in hints.items() if target is not None}
    if not wanted:
        return
    found = {
        row.id: row.value_type
        for row in await session.execute(
            select(StatDefinition.id, StatDefinition.value_type).where(
                StatDefinition.tenant_id == tenant_id, StatDefinition.id.in_(set(wanted.values()))
            )
        )
    }
    for name, target in wanted.items():
        label = name.removesuffix("_id")
        if target not in found:
            raise InvalidStatHintError(
                detail=f"{label} {target} is not a stat definition in tenant {tenant_id}"
            )
        if target == own_id:
            raise InvalidStatHintError(detail=f"A stat definition cannot be its own {label}")
        if name in ("max_hint_id", "min_hint_id") and found[target] not in _NUMERIC:
            raise InvalidStatHintError(
                detail=f"{label} must be an int or float stat, not {found[target].value}"
            )


@router.post("/stat-groups", status_code=201)
async def create_stat_group(
    tenant_id: uuid.UUID,
    body: StatGroupCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> StatGroupOut:
    """No post-commit re-read (unlike routers/items.py's create_item) - the
    response is built straight from the in-memory row create/committed just
    above, and async_session_factory's expire_on_commit=False (db.py) keeps
    its attributes readable without a fresh SELECT. Nothing here goes back
    through a security_invoker view after the commit, so
    dependencies.set_tenant_rls_context's "call it again after a mid-request
    commit" rule (ADR 0032) doesn't apply - it's only needed once a route
    actually re-queries.
    """
    stat_group = StatGroup(
        tenant_id=tenant_id, name=body.name, priority=body.priority, mandatory=body.mandatory
    )
    if body.position is not None:
        stat_group.position = body.position
    session.add(stat_group)
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="stat_group.created",
        target_type="stat_group",
        target_id=stat_group.id,
        detail=f"priority={body.priority}",
    )
    await session.commit()
    response.headers["Location"] = str(
        request.url_for("get_stat_group", tenant_id=tenant_id, stat_group_id=stat_group.id)
    )
    return StatGroupOut.model_validate(stat_group)


@router.put("/stat-groups/order")
async def reorder_stat_groups(
    tenant_id: uuid.UUID, body: StatGroupOrder, session: SessionDep
) -> list[StatGroupOut]:
    """Puts the tenant's stat groups in this order - ADR 0278. The ids must be
    every group of the tenant, each once (422 otherwise); positions are
    renumbered from 0. Registered before `/stat-groups/{id}`, whose path would
    otherwise take "order" for an id."""
    groups = list(
        await session.scalars(
            select(StatGroup).where(StatGroup.tenant_id == tenant_id).with_for_update()
        )
    )
    by_id = {group.id: group for group in groups}
    if len(set(body.stat_group_ids)) != len(body.stat_group_ids) or set(body.stat_group_ids) != set(
        by_id
    ):
        raise InvalidStatOrderError(
            detail=f"The order lists {len(body.stat_group_ids)} id(s); the tenant has "
            f"{len(by_id)} stat group(s), and each must appear once"
        )
    for position, stat_group_id in enumerate(body.stat_group_ids):
        by_id[stat_group_id].position = position
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    reread = await session.scalars(
        select(StatGroup)
        .where(StatGroup.tenant_id == tenant_id)
        .order_by(StatGroup.position, StatGroup.name, StatGroup.id)
        .execution_options(populate_existing=True)
    )
    return [StatGroupOut.model_validate(group) for group in reread]


@router.patch("/stat-groups/{stat_group_id}")
async def update_stat_group(
    tenant_id: uuid.UUID, stat_group_id: uuid.UUID, body: StatGroupUpdate, session: SessionDep
) -> StatGroupOut:
    """Edits a stat group's name, priority, `mandatory` flag or position - ADR
    0278, which also says why this is not recorded in the activity log: it
    changes how things are drawn, not what exists or who can see it (ADR
    0084)."""
    stat_group = await _get_stat_group_or_404(tenant_id, stat_group_id, session)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != stat_group.name:
        taken = await session.scalar(
            select(StatGroup.id).where(
                StatGroup.tenant_id == tenant_id,
                StatGroup.name == changes["name"],
                StatGroup.id != stat_group_id,
            )
        )
        if taken is not None:
            raise StatGroupNameTakenError(
                detail=f"Another stat group in tenant {tenant_id} is already called "
                f"{changes['name']!r}"
            )
    for field, value in changes.items():
        setattr(stat_group, field, value)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return StatGroupOut.model_validate(
        await _get_stat_group_or_404(tenant_id, stat_group_id, session)
    )


@router.put("/stat-groups/{stat_group_id}/order")
async def reorder_stat_definitions(
    tenant_id: uuid.UUID, stat_group_id: uuid.UUID, body: StatDefinitionOrder, session: SessionDep
) -> list[StatDefinitionOut]:
    """Puts this group's stat definitions in this order - ADR 0278. The ids
    must be every definition of the group, each once (422 otherwise);
    positions are renumbered from 0."""
    await _get_stat_group_or_404(tenant_id, stat_group_id, session)
    definitions = list(
        await session.scalars(
            select(StatDefinition)
            .where(
                StatDefinition.tenant_id == tenant_id, StatDefinition.stat_group_id == stat_group_id
            )
            .options(selectinload(StatDefinition.enum_values))
            .with_for_update()
        )
    )
    by_id = {definition.id: definition for definition in definitions}
    if len(set(body.stat_definition_ids)) != len(body.stat_definition_ids) or set(
        body.stat_definition_ids
    ) != set(by_id):
        raise InvalidStatOrderError(
            detail=f"The order lists {len(body.stat_definition_ids)} id(s); the group has "
            f"{len(by_id)} stat definition(s), and each must appear once"
        )
    for position, definition_id in enumerate(body.stat_definition_ids):
        by_id[definition_id].position = position
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    reread = await session.scalars(
        select(StatDefinition)
        .where(StatDefinition.tenant_id == tenant_id, StatDefinition.stat_group_id == stat_group_id)
        .options(selectinload(StatDefinition.enum_values))
        .order_by(StatDefinition.position, StatDefinition.name, StatDefinition.id)
        .execution_options(populate_existing=True)
    )
    return [StatDefinitionOut.from_definition(definition) for definition in reread]


@router.get(
    "/stat-groups/{stat_group_id}/libraries", dependencies=[Depends(get_tenant_admin_context)]
)
async def count_stat_group_libraries(
    tenant_id: uuid.UUID, stat_group_id: uuid.UUID, session: SessionDep
) -> LibraryCountOut:
    """How many libraries hold a copy of this stat group of a repository, never which (ADR 0386).
    An admin, as the delete is. A read, not a gate."""
    await _get_stat_group_or_404(tenant_id, stat_group_id, session)
    return LibraryCountOut(
        count=await count_libraries(session, tenant_id, "stat_group", stat_group_id)
    )


@router.delete(
    "/stat-groups/{stat_group_id}",
    status_code=204,
    dependencies=[Depends(get_tenant_admin_context)],
)
async def delete_stat_group(
    tenant_id: uuid.UUID,
    stat_group_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Deletes an unused group - ADR 0167. 409 while it holds any stat
    definition or any entity has acquired it: the database would cascade to
    both, and through the definitions to every value held for them, so
    nothing is deleted behind the caller's back. No `?force`.
    """
    stat_group = await _get_stat_group_or_404(tenant_id, stat_group_id, session)
    definitions = await session.scalar(
        select(func.count())
        .select_from(StatDefinition)
        .where(StatDefinition.stat_group_id == stat_group_id)
    )
    acquired = await session.scalar(
        select(func.count())
        .select_from(EntityStatGroup)
        .where(EntityStatGroup.stat_group_id == stat_group_id)
    )
    in_use = _in_use_parts(
        (definitions, "stat definition(s) in it"), (acquired, "entity(ies) that acquired it")
    )
    if in_use:
        raise StatGroupInUseError(detail=f"Stat group {stat_group_id} is still in use: {in_use}")
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="stat_group.deleted",
        target_type="stat_group",
        target_id=stat_group_id,
        detail=f"priority={stat_group.priority}"
        + libraries_note(await count_libraries(session, tenant_id, "stat_group", stat_group_id)),
    )
    await session.delete(stat_group)
    await session.commit()


@router.get("/stat-groups")
async def list_stat_groups(
    tenant_id: uuid.UUID, session: SessionDep, params: ParamsDep
) -> Page[StatGroupOut]:
    """Every stat group in the tenant, in display order (position, then
    name; ADR 0278) - the listing the by-id route below never had, so a stat
    vocabulary is discoverable (and exportable, ADR 0085) without already
    knowing its ids.
    """
    stmt = (
        select(StatGroup)
        .where(StatGroup.tenant_id == tenant_id)
        .order_by(StatGroup.position, StatGroup.name, StatGroup.id)
    )
    page: Page[StatGroupOut] = await apaginate(session, stmt, params)
    return page


@router.get("/stat-groups/{stat_group_id}")
async def get_stat_group(
    tenant_id: uuid.UUID, stat_group_id: uuid.UUID, session: SessionDep
) -> StatGroupOut:
    stat_group = await _get_stat_group_or_404(tenant_id, stat_group_id, session)
    return StatGroupOut.model_validate(stat_group)


@router.post("/stat-definitions", status_code=201)
async def create_stat_definition(
    tenant_id: uuid.UUID,
    body: StatDefinitionCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> StatDefinitionOut:
    """stat_group_id must resolve to a stat group in this tenant (422
    InvalidStatGroupError otherwise) - mirrors create_item_instance's own
    prototype_id validation (ADR 0032). An enum stat's allowed values are
    created in the same transaction (ADR 0103): required, non-empty, and
    duplicate-free for value_type=enum, and rejected for any other type.
    """
    stat_group_stmt = select(StatGroup.id).where(
        StatGroup.id == body.stat_group_id, StatGroup.tenant_id == tenant_id
    )
    if (await session.execute(stat_group_stmt)).first() is None:
        raise InvalidStatGroupError(
            detail=f"{body.stat_group_id} is not a stat group in tenant {tenant_id}"
        )

    enum_values = body.enum_values or []
    if body.value_type is StatValueType.ENUM:
        if not enum_values:
            raise InvalidStatEnumValuesError(detail="An enum stat needs at least one allowed value")
        if len(set(enum_values)) != len(enum_values):
            raise InvalidStatEnumValuesError(detail="enum_values contains duplicates")
    elif enum_values:
        raise InvalidStatEnumValuesError(
            detail=f"enum_values only apply to enum stats, not {body.value_type.value}"
        )

    await _check_hints(
        session,
        tenant_id,
        {
            "max_hint_id": body.max_hint_id,
            "min_hint_id": body.min_hint_id,
            "resolved_hint_id": body.resolved_hint_id,
        },
        own_id=None,
    )
    _check_scale(body.value_type, body.min_value, body.max_value)
    stat_definition = StatDefinition(
        tenant_id=tenant_id,
        stat_group_id=body.stat_group_id,
        name=body.name,
        value_type=body.value_type,
        unit=body.unit,
        adjustable_in_play=body.adjustable_in_play,
        pin=body.pin,
        signed=body.signed,
        max_hint_id=body.max_hint_id,
        min_hint_id=body.min_hint_id,
        resolved_hint_id=body.resolved_hint_id,
        min_value=body.min_value,
        max_value=body.max_value,
    )
    if body.position is not None:
        stat_definition.position = body.position
    session.add(stat_definition)
    await session.flush()
    for position, value in enumerate(enum_values):
        session.add(
            StatDefinitionEnumValue(
                tenant_id=tenant_id,
                stat_definition_id=stat_definition.id,
                value=value,
                sort_order=position,
            )
        )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="stat_definition.created",
        target_type="stat_definition",
        target_id=stat_definition.id,
        detail=f"stat_group={body.stat_group_id}, value_type={body.value_type.value}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for(
            "get_stat_definition", tenant_id=tenant_id, stat_definition_id=stat_definition.id
        )
    )
    return StatDefinitionOut.from_definition(
        await _get_stat_definition_or_404(tenant_id, stat_definition.id, session)
    )


@router.get("/stat-definitions")
async def list_stat_definitions(
    tenant_id: uuid.UUID, session: SessionDep, params: ParamsDep
) -> Page[StatDefinitionOut]:
    """Every stat definition in the tenant, in display order (its group's
    position and name, then its own position and name; ADR 0278) - see
    `list_stat_groups` (ADR 0085).
    """
    stmt = (
        select(StatDefinition)
        .join(StatGroup, StatGroup.id == StatDefinition.stat_group_id)
        .where(StatDefinition.tenant_id == tenant_id)
        .options(selectinload(StatDefinition.enum_values))
        .order_by(
            StatGroup.position,
            StatGroup.name,
            StatDefinition.position,
            StatDefinition.name,
            StatDefinition.id,
        )
    )
    page: Page[StatDefinitionOut] = await apaginate(
        session,
        stmt,
        params,
        transformer=lambda rows: [StatDefinitionOut.from_definition(row) for row in rows],
    )
    return page


@router.get("/stat-definitions/{stat_definition_id}")
async def get_stat_definition(
    tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, session: SessionDep
) -> StatDefinitionOut:
    stat_definition = await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    return StatDefinitionOut.from_definition(stat_definition)


@router.patch("/stat-definitions/{stat_definition_id}")
async def update_stat_definition(
    tenant_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    body: StatDefinitionUpdate,
    session: SessionDep,
) -> StatDefinitionOut:
    """Edits a stat's name (ADR 0390) and how it is shown - its unit, sign,
    adjustable-in-play and pinned flags, its position in its group (ADR 0278)
    and its hints (ADR 0279). A definition's type and group are not editable
    here; a retype is breaking for the libraries that copied it. A name
    another definition has is a 409, and so is renaming one the API reads by
    name. Not recorded in the activity log (ADR 0084: naming and drawing, not
    what exists or who can see it)."""
    stat_definition = await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != stat_definition.name:
        if stat_definition.name in RESERVED_STAT_NAMES:
            raise StatNameReservedError(
                detail=f"The API reads {stat_definition.name!r} by name, so it cannot be renamed"
            )
        taken = await session.scalar(
            select(StatDefinition.id).where(
                StatDefinition.tenant_id == tenant_id,
                StatDefinition.name == changes["name"],
                StatDefinition.id != stat_definition_id,
            )
        )
        if taken is not None:
            raise StatDefinitionNameTakenError(
                detail=f"Another stat in tenant {tenant_id} is already called {changes['name']!r}"
            )
    await _check_hints(
        session,
        tenant_id,
        {k: v for k, v in changes.items() if k.endswith("_hint_id")},
        own_id=stat_definition_id,
    )
    if "min_value" in changes or "max_value" in changes:
        low = changes.get("min_value", stat_definition.min_value)
        high = changes.get("max_value", stat_definition.max_value)
        _check_scale(stat_definition.value_type, low, high)
        await _check_scale_holds(session, stat_definition, low, high)
    for field, value in changes.items():
        setattr(stat_definition, field, value)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return StatDefinitionOut.from_definition(
        await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    )


def _in_use_parts(*counted: tuple[int | None, str]) -> str:
    """ "2 values held, 1 formula" - the nonzero counts of what uses something."""
    return ", ".join(f"{count} {what}" for count, what in counted if count)


@router.get(
    "/stat-definitions/{stat_definition_id}/libraries",
    dependencies=[Depends(get_tenant_admin_context)],
)
async def count_stat_definition_libraries(
    tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, session: SessionDep
) -> LibraryCountOut:
    """How many libraries hold a copy of this stat of a repository, never which (ADR 0386). An
    admin, as the delete is. A read, not a gate."""
    await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    return LibraryCountOut(
        count=await count_libraries(session, tenant_id, "stat_definition", stat_definition_id)
    )


@router.delete(
    "/stat-definitions/{stat_definition_id}",
    status_code=204,
    dependencies=[Depends(get_tenant_admin_context)],
)
async def delete_stat_definition(
    tenant_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Deletes an unused definition - ADR 0167. 409 while an entity holds a
    value for it, has a formula for it, or has a formula that reads it as a
    source (the database refuses the last, and would cascade the first two).
    Its enum values go with it. No `?force`: a caller removes the values or
    formulas first.
    """
    stat_definition = await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)

    async def count(model: type, *conditions: object) -> int:
        stmt = select(func.count()).select_from(model).where(*conditions)  # type: ignore[arg-type]
        return await session.scalar(stmt) or 0

    values = await count(EntityStat, EntityStat.stat_definition_id == stat_definition_id)
    formulas = await count(ComputedStat, ComputedStat.stat_definition_id == stat_definition_id)
    reads = (
        await count(
            ComputedStatLinear, ComputedStatLinear.source_stat_definition_id == stat_definition_id
        )
        + await count(
            ComputedStatComparison,
            (ComputedStatComparison.left_stat_definition_id == stat_definition_id)
            | (ComputedStatComparison.right_stat_definition_id == stat_definition_id),
        )
        + await count(
            ComputedStatSumTerm, ComputedStatSumTerm.source_stat_definition_id == stat_definition_id
        )
        + await count(
            ComputedStatContents,
            ComputedStatContents.source_stat_definition_id == stat_definition_id,
        )
    )
    in_use = _in_use_parts(
        (values, "value(s) held"), (formulas, "formula(s) for it"), (reads, "formula(s) reading it")
    )
    if in_use:
        raise StatDefinitionInUseError(
            detail=f"Stat definition {stat_definition_id} is still in use: {in_use}"
        )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="stat_definition.deleted",
        target_type="stat_definition",
        target_id=stat_definition_id,
        detail=(
            f"stat_group={stat_definition.stat_group_id}, "
            f"value_type={stat_definition.value_type.value}"
            + libraries_note(
                await count_libraries(session, tenant_id, "stat_definition", stat_definition_id)
            )
        ),
    )
    await session.delete(stat_definition)
    await session.commit()


@router.post("/stat-definitions/{stat_definition_id}/enum-values", status_code=201)
async def add_stat_enum_value(
    tenant_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    body: StatEnumValueCreate,
    session: SessionDep,
) -> StatDefinitionOut:
    """Adds one allowed value to an enum stat - ADR 0103. Tenant-admin tier
    like the rest of this router. 422 for a non-enum definition, 409 for a
    value already allowed. An omitted sort_order goes after the last.
    Returns the whole definition, whose enum_values now include it. Not
    logged: vocabulary, not structure (ADR 0084).
    """
    stat_definition = await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    if stat_definition.value_type is not StatValueType.ENUM:
        raise InvalidStatEnumValuesError(
            detail=f"Stat {stat_definition.name!r} is {stat_definition.value_type.value}, not enum"
        )
    if any(row.value == body.value for row in stat_definition.enum_values):
        raise StatEnumValueAlreadyExistsError(
            detail=f"{body.value!r} is already allowed for stat {stat_definition.name!r}"
        )
    sort_order = body.sort_order
    if sort_order is None:
        last = await session.scalar(
            select(func.max(StatDefinitionEnumValue.sort_order)).where(
                StatDefinitionEnumValue.stat_definition_id == stat_definition_id
            )
        )
        sort_order = 0 if last is None else last + 1
    session.add(
        StatDefinitionEnumValue(
            tenant_id=tenant_id,
            stat_definition_id=stat_definition_id,
            value=body.value,
            sort_order=sort_order,
        )
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return StatDefinitionOut.from_definition(
        await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    )


@router.delete(
    "/stat-definitions/{stat_definition_id}/enum-values/{enum_value_id}",
    dependencies=[Depends(get_tenant_admin_context)],
)
async def remove_stat_enum_value(
    tenant_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    enum_value_id: uuid.UUID,
    session: SessionDep,
) -> StatDefinitionOut:
    """Removes one allowed value - ADR 0103. 409 while any entity directly
    holds it or a comparison formula for this stat returns it (ADR 0390):
    removing it would leave stored values outside the allowed set. Returns
    the definition, like the add route.
    """
    stat_definition = await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    row = next((row for row in stat_definition.enum_values if row.id == enum_value_id), None)
    if row is None:
        raise StatEnumValueNotFoundError(
            detail=f"No enum value {enum_value_id} on stat definition {stat_definition_id}"
        )
    uses = await enum_value_uses(session, tenant_id, stat_definition_id, row.value)
    if uses:
        raise StatEnumValueInUseError(detail=uses.describe(row.value))
    await session.delete(row)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return StatDefinitionOut.from_definition(
        await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    )


@router.patch("/stat-definitions/{stat_definition_id}/enum-values/{enum_value_id}")
async def update_stat_enum_value(
    tenant_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    enum_value_id: uuid.UUID,
    body: StatEnumValueUpdate,
    session: SessionDep,
) -> StatDefinitionOut:
    """Renames an allowed value and/or sets its sort_order - ADR 0390. A
    rename rewrites every stored copy of the old text (entries' values and
    a comparison formula's `true_value`/`false_value`) in the same
    transaction. 409 for a value this stat already allows, and for the value
    `none` of `binding`, which the API writes. Returns the definition. Not
    logged: naming and order, not structure (ADR 0084).
    """
    stat_definition = await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    row = next((row for row in stat_definition.enum_values if row.id == enum_value_id), None)
    if row is None:
        raise StatEnumValueNotFoundError(
            detail=f"No enum value {enum_value_id} on stat definition {stat_definition_id}"
        )
    changes = body.model_dump(exclude_unset=True)
    old = row.value
    new = changes.get("value", old)
    if new != old:
        if old in RESERVED_ENUM_VALUES.get(stat_definition.name, frozenset()):
            raise StatNameReservedError(
                detail=f"The API writes {old!r} for stat {stat_definition.name!r}, so it "
                "cannot be renamed"
            )
        if any(other.value == new for other in stat_definition.enum_values):
            raise StatEnumValueAlreadyExistsError(
                detail=f"{new!r} is already allowed for stat {stat_definition.name!r}"
            )
        await rename_enum_value_text(session, tenant_id, stat_definition_id, old, new)
    for field, value in changes.items():
        setattr(row, field, value)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return StatDefinitionOut.from_definition(
        await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    )
