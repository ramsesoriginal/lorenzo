from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.being_deletion import authorize_being_deletion, settle_inventory
from lorenzo_api.campaign_access import is_tenant_admin, is_tenant_gm
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_campaign_context,
    get_entity_or_404,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.entity_access import entity_id_among
from lorenzo_api.entity_kinds import require_deletable
from lorenzo_api.entry_visibility import unhidden
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import EntityNotFoundError, TenantNotFoundError
from lorenzo_api.information_visibility import (
    resolve_information_visibility,
    visible_information_clause,
)
from lorenzo_api.models import (
    Being,
    Campaign,
    Containment,
    Entity,
    Information,
    StatDefinition,
    Tenant,
    VEffectiveStat,
    VItemInstance,
)
from lorenzo_api.routers.entities import _INFORMATION_LOAD_OPTIONS
from lorenzo_api.routers.item_instances import _owner_predicate_for, caller_reach
from lorenzo_api.routers.items import eager_load_options
from lorenzo_api.routers.templates import (
    held_column_names,
    pick_sheet_template,
    system_slugs,
    template_summary,
)
from lorenzo_api.schemas.beings import BeingSummaryOut, SheetOut, SheetWeaponOut
from lorenzo_api.schemas.entities import InformationOut, _stats_out
from lorenzo_api.stat_contents import attach_contents

# No router-level gate: who may list, and which beings, is decided in the
# route (ADR 0078's original tier, as amended by ADR 0173). The tenant must
# exist (get_tenant_or_404, existence only), and then the caller is a tenant
# administrator (every being), a GM (the beings in their reach), or neither.
router = APIRouter(prefix="/tenants/{tenant_id}/beings", tags=["beings"])


@router.get("")
async def list_beings(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_or_404)],
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match against the being's name."),
    ] = None,
) -> Page[BeingSummaryOut]:
    """Every Being in this tenant - PCs, NPCs, and bare beings with no
    Character row at all (ADR 0031's "a bare being with no character row
    remains perfectly valid" case, invisible to GET .../characters) - see
    ADR 0078/issue #94. Item-instance ownership (ADR 0019/RFC 0005)
    already targets any entity generically; this is the missing "pick a
    being" discovery step for a GM assigning loot to an NPC that was never
    promoted into a tracked Character.

    Who asks decides which (ADR 0173, amending ADR 0078's membership-only
    gate): a tenant administrator (OWNER or ORGA) lists every being, as
    before; a GM with no membership lists the beings in their reach
    (`gm_reachable_entity_ids`, ADR 0035/0046/0124/0152: their campaigns'
    characters, the scenes those stand in, and the beings in no campaign the
    tenant's `npcs_shared_with_gms` setting gives them), so another table's
    player characters stay private; anyone else - a player, a participant with
    no GM role - gets the same 404 a non-member always did.
    """
    reach: frozenset[uuid.UUID] | None = None
    if not await is_tenant_admin(session, tenant_id=tenant_id, user_id=user.id):
        if not await is_tenant_gm(session, tenant_id=tenant_id, user_id=user.id):
            raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
        reach = (
            await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
        ).gm_reachable_entity_ids

    stmt = (
        select(Being)
        .join(Entity, Entity.id == Being.entity_id)
        .where(Being.tenant_id == tenant_id, await unhidden(session, tenant_id, Being.entity_id))
        .options(selectinload(Being.entity), selectinload(Being.character))
        .order_by(Entity.name, Being.entity_id)
    )
    if reach is not None:
        stmt = stmt.where(entity_id_among(Being.entity_id, reach))
    if q is not None:
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))

    def _beings_out(beings: Sequence[Being]) -> list[BeingSummaryOut]:
        return [BeingSummaryOut.from_being(b) for b in beings]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise
    # exact.
    return cast(
        Page[BeingSummaryOut],
        await apaginate(session, stmt, params, transformer=_beings_out),
    )


@router.get("/{entity_id}/sheet")
async def get_being_sheet(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_or_404)],
    entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    campaign_id: Annotated[
        uuid.UUID | None,
        Query(
            description=(
                "A campaign of the tenant the caller can read. When it names a game system, the "
                "sheet is drawn from that system's template for the being, if exactly one "
                "matches (ADR 0452)."
            )
        ),
    ] = None,
    template_id: Annotated[
        uuid.UUID | None,
        Query(
            description=(
                "A template of the library the being matches: the sheet is drawn from it, "
                "whatever the campaign names (409 when it is not for the being)."
            )
        ),
    ] = None,
) -> SheetOut:
    """The datasheet's weapons and abilities (ADR 0281). The weapons are the items the being
    holds directly (contained by it), with the stats of the tenant's weapon group; what the
    caller may see of them is ADR 0040's, so another player's being shows none. The abilities
    are the being's information of the tenant's ability type, as the caller can see it.

    With a template (named by `template_id`, or the one of the campaign's game system that matches
    the being) those three settings come from it instead: the first `stats` slot's group, the
    columns of the first `held` slot and the type of the first `information` slot (ADR 0452). A
    slot it has not is a section not configured. `templates` lists the matches of the campaign's
    system, so a client can offer the choice when there are several."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    campaign_system_id: uuid.UUID | None = None
    if campaign_id is not None:
        await get_campaign_context(tenant_id, campaign_id, session, user)
        campaign_system_id = await session.scalar(
            select(Campaign.system_id).where(
                Campaign.id == campaign_id, Campaign.tenant_id == tenant_id
            )
        )
    await get_entity_or_404(session, entity_id, tenant_id)
    if await session.get(Being, entity_id) is None:
        raise EntityNotFoundError(detail=f"No being with id {entity_id} in tenant {tenant_id}")
    tenant = await session.get_one(Tenant, tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)

    chosen, candidates = await pick_sheet_template(
        session, tenant_id, entity_id, system_id=campaign_system_id, template_id=template_id
    )
    being_group_id = tenant.being_stat_group_id
    weapon_names: set[str] | None = None
    ability_type = tenant.ability_information_type
    if chosen is not None:
        slots = chosen.slots
        being_group_id = next(
            (s.stat_group_id for s in slots if s.kind == "stats" and s.stat_group_id), None
        )
        held = next((s for s in slots if s.kind == "held"), None)
        weapon_names = (
            await held_column_names(session, tenant_id, held) if held is not None else None
        )
        ability_type = next((s.information_type for s in slots if s.kind == "information"), None)
    elif tenant.weapon_stat_group_id is not None:
        weapon_names = set(
            (
                await session.scalars(
                    select(StatDefinition.name).where(
                        StatDefinition.stat_group_id == tenant.weapon_stat_group_id,
                        StatDefinition.tenant_id == tenant_id,
                    )
                )
            ).all()
        )

    weapons: list[SheetWeaponOut] = []
    if weapon_names is not None:
        names = weapon_names
        reach = await caller_reach(session, tenant_id=tenant_id, user=user, visibility=visibility)
        views = (
            (
                await session.execute(
                    select(VItemInstance)
                    .join(Entity, Entity.id == VItemInstance.entity_id)
                    .where(
                        VItemInstance.tenant_id == tenant_id,
                        VItemInstance.entity_id.in_(
                            select(Containment.child_entity_id).where(
                                Containment.parent_entity_id == entity_id,
                                Containment.tenant_id == tenant_id,
                            )
                        ),
                        _owner_predicate_for(reach),
                    )
                    .options(
                        *eager_load_options(VItemInstance.entity),
                        # The sheet reports inherited stat provenance (ADR 0276), unlike
                        # the item view's numeric lists. Load the source before _stats_out.
                        joinedload(VItemInstance.entity)
                        .selectinload(Entity.effective_stats)
                        .joinedload(VEffectiveStat.source_entity),
                    )
                    .order_by(Entity.name, VItemInstance.entity_id)
                )
            )
            .scalars()
            .all()
        )
        await attach_contents(session, [view.entity for view in views], tenant_id=tenant_id)
        for view in views:
            stats = [s for s in _stats_out(view.entity, visibility) if s.name in names]
            if stats:
                weapons.append(
                    SheetWeaponOut(
                        entity_id=view.entity_id,
                        name=view.entity.name,
                        quantity=view.quantity,
                        stats=stats,
                    )
                )

    abilities: list[InformationOut] = []
    if ability_type is not None:
        rows = (
            await session.scalars(
                select(Information)
                .where(
                    Information.entity_id == entity_id,
                    Information.tenant_id == tenant_id,
                    Information.type == ability_type,
                    visible_information_clause(visibility),
                )
                .options(*_INFORMATION_LOAD_OPTIONS)
                .order_by(Information.order, Information.id)
            )
        ).all()
        abilities = [InformationOut.from_information(row, request) for row in rows]

    slugs = await system_slugs(session, tenant_id) if (chosen or candidates) else {}
    return SheetOut(
        being_stat_group_id=being_group_id,
        weapons_configured=weapon_names is not None,
        abilities_configured=ability_type is not None,
        weapons=weapons,
        abilities=abilities,
        template=template_summary(chosen, slugs) if chosen is not None else None,
        templates=[template_summary(t, slugs) for t in candidates],
    )


@router.delete("/{entity_id}", status_code=204)
async def delete_being(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_or_404)],
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Permanently delete a being, its entry and its owned-and-carried inventory (ADR 0302).

    Other carried items survive; owned items elsewhere become unowned and uncarried.
    Unlike DELETE /characters/{id}, this removes the entry rather than demoting it.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    # Serialize with other writes before reading the version and the inventory.
    entity = (
        await session.scalars(
            select(Entity)
            .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
            .with_for_update()
        )
    ).one_or_none()
    if entity is None or await session.get(Being, entity_id) is None:
        raise EntityNotFoundError(detail=f"No being with id {entity_id} in tenant {tenant_id}")
    await authorize_being_deletion(
        session, tenant_id=tenant_id, user_id=user.id, entity_id=entity_id
    )
    check_if_match(if_match, updated_at=entity.updated_at)
    await require_deletable(session, tenant_id=tenant_id, entity_id=entity_id, allow_character=True)
    await settle_inventory(session, tenant_id=tenant_id, actor_id=user.id, being_id=entity_id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="being.deleted",
        target_type="being",
        target_id=entity_id,
        detail=None,
    )
    await session.delete(entity)
    await session.commit()
