import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends
from fastapi_pagination import Page, paginate
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import CurrentUser, ParamsDep, SessionDep, get_tenant_context
from lorenzo_api.exceptions import TenantNotFoundError
from lorenzo_api.models import (
    Being,
    CampaignGm,
    Character,
    CharacterPlayer,
    Membership,
    Player,
    Tenant,
)
from lorenzo_api.schemas.tenants import (
    GmRosterEntryOut,
    MembershipRosterEntryOut,
    PlayerRosterEntryOut,
    TenantOut,
    TenantRole,
    TenantRosterEntryOut,
    TenantSummaryOut,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("")
async def list_tenants(
    user: CurrentUser, session: SessionDep, params: ParamsDep
) -> Page[TenantSummaryOut]:
    """Every tenant the caller belongs to in *any* capacity - a Membership
    row, a Player row, or a CampaignGm row, anywhere in it (ADR 0030/RFC
    0003). Filtered directly in SQL via EXISTS (not combined in Python the
    way information_visibility.resolve_information_visibility does it) so
    real pagination works over an arbitrarily large tenant list - unlike
    that module's use case, this one needs Page[...]/apaginate's LIMIT/
    OFFSET to operate on one real query, not a small in-memory id set.
    """
    stmt = (
        select(Tenant)
        .where(
            exists().where(Membership.tenant_id == Tenant.id, Membership.user_id == user.id)
            | exists().where(Player.tenant_id == Tenant.id, Player.user_id == user.id)
            | exists().where(CampaignGm.tenant_id == Tenant.id, CampaignGm.user_id == user.id)
        )
        .order_by(Tenant.name, Tenant.id)
    )
    # Resolved once per request, not once per row - mirrors
    # resolve_information_visibility's own precedent. A user's own
    # Membership rows are small in practice, so this doesn't need scoping
    # down to just the current page first. Its role directly says owner/
    # orga; absence means "participant" (reachable only via Player/
    # CampaignGm), which ADR 0022 already established as legitimate, not a
    # gap.
    memberships = await session.execute(
        select(Membership.tenant_id, Membership.role).where(Membership.user_id == user.id)
    )
    role_by_tenant_id: dict[uuid.UUID, TenantRole] = {
        tenant_id: role.value for tenant_id, role in memberships
    }

    def _tenants_out(tenants: Sequence[Tenant]) -> list[TenantSummaryOut]:
        return [
            TenantSummaryOut.from_tenant(t, role=role_by_tenant_id.get(t.id, "participant"))
            for t in tenants
        ]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(
        Page[TenantSummaryOut], await apaginate(session, stmt, params, transformer=_tenants_out)
    )


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)], session: SessionDep
) -> TenantOut:
    # get_tenant_context already confirmed tenant_id is real; TenantOut's
    # from_attributes mapping needs the actual row, not just the id. Same
    # "re-query for the real row, dependency already did the 404 check"
    # division of labor as get_entity_or_404 - raising here is dead code in
    # practice (tenant_id can't disappear mid-transaction), just what lets
    # mypy narrow tenant to non-None below.
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    return TenantOut.model_validate(tenant)


@router.get("/{tenant_id}/memberships")
async def list_tenant_roster(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[TenantRosterEntryOut]:
    """Broadened from a pure membership list to the tenant's full roster -
    every user with *any* standing in this tenant, not just its tenant-wide
    admins (ADR 0031/RFC 0004). One row per relationship, not per user - a
    user who is ORGA, GMs one campaign, and plays in another appears three
    times. Still gated by get_tenant_context, unchanged: an ordinary player
    doesn't need this to find their own standing, `/me` already covers that.

    Combined in Python from three separate queries (mirroring
    resolve_information_visibility's own precedent), not one SQL UNION -
    the three row shapes are genuinely heterogeneous, and this is
    tenant-admin-only, so the data is bounded by how many people administer
    one world, not by total tenant traffic - paginating the already-fetched
    list, not the query, is a reasonable trade at that scale.
    """
    memberships = (
        (await session.execute(select(Membership).where(Membership.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    players = (
        (
            await session.execute(
                select(Player)
                .where(Player.tenant_id == tenant_id)
                .options(
                    selectinload(Player.character_links)
                    .selectinload(CharacterPlayer.character)
                    .selectinload(Character.being)
                    .selectinload(Being.entity)
                )
            )
        )
        .scalars()
        .all()
    )
    campaign_gms = (
        (await session.execute(select(CampaignGm).where(CampaignGm.tenant_id == tenant_id)))
        .scalars()
        .all()
    )

    entries: list[TenantRosterEntryOut] = [
        *(MembershipRosterEntryOut.from_membership(m) for m in memberships),
        *(PlayerRosterEntryOut.from_player(p) for p in players),
        *(GmRosterEntryOut.from_campaign_gm(g) for g in campaign_gms),
    ]
    entries.sort(key=lambda entry: entry.user_id)
    # paginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(Page[TenantRosterEntryOut], paginate(entries, params))
