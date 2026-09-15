import re
import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi_pagination import Page, paginate
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_context,
    require_tenant_creator_role,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import SlugConflictError, TenantNotFoundError
from lorenzo_api.models import (
    Being,
    CampaignGm,
    Character,
    CharacterPlayer,
    Membership,
    MembershipRole,
    Player,
    Tenant,
)
from lorenzo_api.schemas.tenants import (
    GmRosterEntryOut,
    MembershipRosterEntryOut,
    PlayerRosterEntryOut,
    TenantCreate,
    TenantOut,
    TenantRole,
    TenantRosterEntryOut,
    TenantSummaryOut,
    TenantUpdate,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])

_SLUG_COLLAPSE_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Lowercased, non-alphanumeric runs collapsed to a single '-', leading/
    trailing '-' stripped - RFC 0012's own auto-derivation rule. A name with
    no alphanumeric characters at all collapses to '' - falls back to
    "tenant", so _unique_slug_for below still has a real base to suffix
    rather than ever considering an empty slug.
    """
    return _SLUG_COLLAPSE_RE.sub("-", name.strip().lower()).strip("-") or "tenant"


async def _slug_taken(
    session: SessionDep, slug: str, *, exclude_tenant_id: uuid.UUID | None
) -> bool:
    stmt = select(Tenant.id).where(Tenant.slug == slug).limit(1)
    if exclude_tenant_id is not None:
        stmt = stmt.where(Tenant.id != exclude_tenant_id)
    return (await session.execute(stmt)).first() is not None


async def _unique_slug_for(session: SessionDep, name: str) -> str:
    """Auto-suffixed on collision (my-world, my-world-2, my-world-3, ...) -
    creating a tenant never fails just because someone else already picked
    a similar name. Only reached when the caller omitted slug entirely; an
    explicit slug goes through _resolve_create_slug's hard-conflict path
    instead. `tenant.slug` has no tenant_id to scope uniqueness by - it's
    global (ADR 0022) - so this checks across every tenant, not just the
    caller's own.
    """
    base = _slugify(name)
    candidate = base
    suffix = 2
    while await _slug_taken(session, candidate, exclude_tenant_id=None):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


async def _resolve_create_slug(session: SessionDep, requested_slug: str | None, name: str) -> str:
    if requested_slug is None:
        return await _unique_slug_for(session, name)
    if await _slug_taken(session, requested_slug, exclude_tenant_id=None):
        raise SlugConflictError(detail=f"Slug '{requested_slug}' is already in use")
    return requested_slug


async def _check_slug_available_for_update(
    session: SessionDep, tenant_id: uuid.UUID, requested_slug: str
) -> None:
    if await _slug_taken(session, requested_slug, exclude_tenant_id=tenant_id):
        raise SlugConflictError(detail=f"Slug '{requested_slug}' is already in use")


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
    return await _tenant_out(tenant_id, session)


async def _tenant_out(tenant_id: uuid.UUID, session: SessionDep) -> TenantOut:
    # Callers that already confirmed tenant_id is real (get_tenant_context,
    # or POST/PATCH below re-reading the row they just wrote) still get a
    # real 404 here rather than an unchecked None - same "re-query for the
    # real row, dependency already did the 404 check" division of labor as
    # get_entity_or_404; raising is dead code in practice for the
    # get_tenant_context case (tenant_id can't disappear mid-transaction),
    # just what lets mypy narrow tenant to non-None below.
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    return TenantOut.model_validate(tenant)


@router.post("", status_code=201, dependencies=[Depends(require_tenant_creator_role)])
async def create_tenant(
    body: TenantCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> TenantOut:
    """Gated by require_tenant_creator_role (ADR 0033/RFC 0012), not
    get_tenant_context - nothing tenant-scoped can exist before the tenant
    itself does, so there's no tenant-scoped privilege to check yet; this
    is a platform-level gate instead. One transaction creates the Tenant
    row and a Membership(role=OWNER) for the caller - they become the new
    tenant's owner atomically, the same "create the whole coherent unit in
    one commit" precedent every other CRUD RFC here already follows.
    """
    slug = await _resolve_create_slug(session, body.slug, body.name)
    tenant = Tenant(name=body.name, slug=slug, created_by=user.id, updated_by=user.id)
    if body.description is not None:
        tenant.description = body.description
    session.add(tenant)
    await session.flush()
    session.add(Membership(tenant_id=tenant.id, user_id=user.id, role=MembershipRole.OWNER))
    await session.commit()
    # tenant itself carries no RLS policy (it *is* the RLS boundary, ADR
    # 0002/0022) - re-reading it below needs no scoping. Still follows ADR
    # 0032's established commit-then-read convention for consistency with
    # every other write route, in case TenantOut's shape ever grows to pull
    # in RLS-scoped data.
    await set_tenant_rls_context(session, tenant.id)
    response.headers["Location"] = str(request.url_for("get_tenant", tenant_id=tenant.id))
    return await _tenant_out(tenant.id, session)


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    body: TenantUpdate,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> TenantOut:
    """Unchanged get_tenant_context gate, not narrowed to OWNER-only -
    renaming/re-describing the world is squarely tenant-wide administrative
    access, exactly what ORGA already means (ADR 0010), not something to
    reserve for OWNER alone (ADR 0033/RFC 0012). Renaming never regenerates
    slug; changing slug here goes through the same explicit-collision-check
    path POST uses, no auto-suffix.
    """
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    check_if_match(if_match, updated_at=tenant.updated_at)

    update = body.model_dump(exclude_unset=True)
    if update.get("slug") is not None:
        await _check_slug_available_for_update(session, tenant_id, update["slug"])

    changed = False
    if update.get("name") is not None:
        tenant.name = update["name"]
        changed = True
    if update.get("slug") is not None:
        tenant.slug = update["slug"]
        changed = True
    if update.get("description") is not None:
        tenant.description = update["description"]
        changed = True
    if changed:
        tenant.updated_by = user.id

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _tenant_out(tenant_id, session)


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
