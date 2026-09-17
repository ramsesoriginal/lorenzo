import re
import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Request, Response, UploadFile
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
from lorenzo_api.exceptions import (
    InvalidUserError,
    LastOwnerError,
    MembershipAlreadyExistsError,
    MembershipManagementForbiddenError,
    MembershipNotFoundError,
    SlugConflictError,
    TenantNotFoundError,
)
from lorenzo_api.models import (
    Being,
    CampaignGm,
    Character,
    CharacterPlayer,
    Membership,
    MembershipRole,
    Player,
    Tenant,
    User,
)
from lorenzo_api.notifications import create_tenant_notification
from lorenzo_api.profile_pictures import (
    delete_tenant_profile_picture,
    read_and_validate_upload,
    upsert_tenant_profile_picture,
)
from lorenzo_api.schemas.notifications import NotificationCreate, NotificationOut
from lorenzo_api.schemas.tenants import (
    GmRosterEntryOut,
    MembershipCreate,
    MembershipRosterEntryOut,
    MembershipUpdate,
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


@router.put("/{tenant_id}/picture", status_code=204)
async def upload_tenant_picture(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    file: UploadFile,
) -> None:
    """Same gate `update_tenant` uses (ADR 0052) - ORGA+, not OWNER-only:
    a tenant's picture is day-to-day tenant administration, not a
    membership-management decision.
    """
    data, file_type = await read_and_validate_upload(file)
    await upsert_tenant_profile_picture(
        session, tenant_id=tenant_id, data=data, file_type=file_type
    )
    await session.commit()


@router.delete("/{tenant_id}/picture", status_code=204)
async def delete_tenant_picture(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)], session: SessionDep
) -> None:
    await delete_tenant_profile_picture(session, tenant_id=tenant_id)
    await session.commit()


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

    # One extra query for every user_id appearing above, not a join per
    # row/table (ADR 0050) - keeps each of the three source queries
    # unchanged and matches this function's own "combined in Python, not a
    # SQL UNION" precedent already given below.
    user_ids = (
        {m.user_id for m in memberships}
        | {p.user_id for p in players}
        | {g.user_id for g in campaign_gms}
    )
    nickname_rows = await session.execute(
        select(User.id, User.nickname).where(User.id.in_(user_ids))
    )
    nickname_by_user_id: dict[uuid.UUID, str | None] = {
        row.id: row.nickname for row in nickname_rows
    }

    entries: list[TenantRosterEntryOut] = [
        *(
            MembershipRosterEntryOut.from_membership(m, nickname=nickname_by_user_id.get(m.user_id))
            for m in memberships
        ),
        *(
            PlayerRosterEntryOut.from_player(p, nickname=nickname_by_user_id.get(p.user_id))
            for p in players
        ),
        *(
            GmRosterEntryOut.from_campaign_gm(g, nickname=nickname_by_user_id.get(g.user_id))
            for g in campaign_gms
        ),
    ]
    entries.sort(key=lambda entry: entry.user_id)
    # paginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(Page[TenantRosterEntryOut], paginate(entries, params))


# --- Membership invite/role-change/revoke (ADR 0036/RFC 0007) ------------
#
# OWNER-only, not ORGA - a deliberate narrowing this RFC introduces:
# granting/revoking tenant-wide administrative access is more sensitive
# than day-to-day tenant administration (which ORGA already covers
# everywhere else, e.g. update_tenant above). PATCH/DELETE both guard
# against removing the tenant's last OWNER (409 LastOwnerError) - the same
# structural concern DELETE /me (routers/users.py) guards for the
# "removing yourself" path, expressed here for "someone else removes/
# demotes you."


async def _require_owner(session: SessionDep, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """membership is None should be unreachable here in practice - every
    caller already cleared get_tenant_context, which itself already
    requires a Membership row. Kept as the real check anyway, the same
    dead-but-documented-intent shape get_tenant's own re-fetch and
    routers/campaigns.py's is_tenant_admin check already use.
    """
    membership = await session.get(Membership, (tenant_id, user_id))
    if membership is None or membership.role is not MembershipRole.OWNER:
        raise MembershipManagementForbiddenError(
            detail=f"Not authorized to manage memberships in tenant {tenant_id}"
        )


async def _is_sole_owner(session: SessionDep, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    stmt = select(Membership.user_id).where(
        Membership.tenant_id == tenant_id, Membership.role == MembershipRole.OWNER
    )
    owner_ids = (await session.execute(stmt)).scalars().all()
    return owner_ids == [user_id]


async def _membership_out(
    tenant_id: uuid.UUID, user_id: uuid.UUID, session: SessionDep
) -> MembershipRosterEntryOut:
    membership = await session.get(Membership, (tenant_id, user_id))
    if membership is None:
        raise MembershipNotFoundError(
            detail=f"No membership for user {user_id} in tenant {tenant_id}"
        )
    user = await session.get(User, user_id)
    nickname = user.nickname if user is not None else None
    return MembershipRosterEntryOut.from_membership(membership, nickname=nickname)


@router.post("/{tenant_id}/memberships", status_code=201)
async def create_membership(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    body: MembershipCreate,
    session: SessionDep,
    user: CurrentUser,
) -> MembershipRosterEntryOut:
    """No Location header - unlike every other POST in this codebase,
    there is no single-resource GET .../memberships/{user_id} route to
    point one at (only the broadened roster list above); RFC 0007's own
    endpoint table doesn't add one either. Deliberately not making one up.

    Also creates a `scope="tenant", type="tenant_invite"` notification for
    the new member, in the same transaction (ADR 0054) - the one
    system-triggered notification this pass wires in, proving the pattern
    end to end rather than leaving it purely theoretical.
    """
    await _require_owner(session, tenant_id=tenant_id, user_id=user.id)
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    if await session.get(User, body.user_id) is None:
        raise InvalidUserError(detail=f"{body.user_id} is not an existing user")
    if await session.get(Membership, (tenant_id, body.user_id)) is not None:
        raise MembershipAlreadyExistsError(
            detail=f"User {body.user_id} already has a membership in tenant {tenant_id}"
        )

    session.add(
        Membership(
            tenant_id=tenant_id,
            user_id=body.user_id,
            role=MembershipRole(body.role),
            created_by=user.id,
            updated_by=user.id,
        )
    )
    await create_tenant_notification(
        session,
        tenant_id=tenant_id,
        recipient_user_id=body.user_id,
        type="tenant_invite",
        title=f"You were added to {tenant.name}",
        body=f"You now have {body.role} access to {tenant.name}.",
        created_by=user.id,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _membership_out(tenant_id, body.user_id, session)


@router.patch("/{tenant_id}/memberships/{user_id}")
async def update_membership(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    user_id: uuid.UUID,
    body: MembershipUpdate,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> MembershipRosterEntryOut:
    await _require_owner(session, tenant_id=tenant_id, user_id=user.id)
    membership = await session.get(Membership, (tenant_id, user_id))
    if membership is None:
        raise MembershipNotFoundError(
            detail=f"No membership for user {user_id} in tenant {tenant_id}"
        )
    check_if_match(if_match, updated_at=membership.updated_at)

    new_role = MembershipRole(body.role)
    if (
        membership.role is MembershipRole.OWNER
        and new_role is not MembershipRole.OWNER
        and await _is_sole_owner(session, tenant_id=tenant_id, user_id=user_id)
    ):
        raise LastOwnerError(detail=f"User {user_id} is the sole OWNER of tenant {tenant_id}")

    if membership.role != new_role:
        membership.role = new_role
        membership.updated_by = user.id

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _membership_out(tenant_id, user_id, session)


@router.delete("/{tenant_id}/memberships/{user_id}", status_code=204)
async def delete_membership(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    user_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """OWNER, or removing your own membership (leaving the tenant) - no
    manage permission needed for that self-service half, mirroring
    revoke_campaign_gm's identical self-removal carve-out.
    """
    if user_id != user.id:
        await _require_owner(session, tenant_id=tenant_id, user_id=user.id)

    membership = await session.get(Membership, (tenant_id, user_id))
    if membership is None:
        raise MembershipNotFoundError(
            detail=f"No membership for user {user_id} in tenant {tenant_id}"
        )
    check_if_match(if_match, updated_at=membership.updated_at)

    if membership.role is MembershipRole.OWNER and await _is_sole_owner(
        session, tenant_id=tenant_id, user_id=user_id
    ):
        raise LastOwnerError(detail=f"User {user_id} is the sole OWNER of tenant {tenant_id}")

    await session.delete(membership)
    await session.commit()


@router.post("/{tenant_id}/notifications", status_code=201)
async def create_tenant_notification_route(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    body: NotificationCreate,
    session: SessionDep,
    user: CurrentUser,
) -> list[NotificationOut]:
    """scope="tenant" - see ADR 0054. Gated by `get_tenant_context`, same as
    `update_tenant` - any tenant-wide member, not OWNER-only (unlike
    membership management above). An omitted `recipient_user_id` broadcasts
    to the tenant's full roster, so this can return more than one row.
    """
    if (
        body.recipient_user_id is not None
        and await session.get(User, body.recipient_user_id) is None
    ):
        raise InvalidUserError(detail=f"{body.recipient_user_id} is not an existing user")

    notifications = await create_tenant_notification(
        session,
        tenant_id=tenant_id,
        recipient_user_id=body.recipient_user_id,
        type=body.type,
        title=body.title,
        body=body.body,
        created_by=user.id,
    )
    await session.commit()
    return [NotificationOut.model_validate(n) for n in notifications]
