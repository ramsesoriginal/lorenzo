import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request, UploadFile
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import AwareDatetime
from sqlalchemy import delete, select, text
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.change_feed import RETENTION_DAYS
from lorenzo_api.dependencies import CurrentUser, ParamsDep, SessionDep, set_tenant_rls_context
from lorenzo_api.exceptions import (
    LastOwnerError,
    NicknameConflictError,
    NotificationNotFoundError,
    UserNotFoundError,
)
from lorenzo_api.models import (
    Being,
    Campaign,
    CampaignGm,
    Character,
    CharacterPlayer,
    EntityChange,
    Membership,
    MembershipRole,
    Notification,
    Player,
    Tenant,
    User,
)
from lorenzo_api.profile_pictures import (
    delete_user_profile_picture,
    read_and_validate_upload,
    upsert_user_profile_picture,
)
from lorenzo_api.schemas.changes import EntityChangeOut
from lorenzo_api.schemas.managed import ManagedCampaignOut, ManagedScopeOut, ManagedTenantOut
from lorenzo_api.schemas.notifications import NotificationOut
from lorenzo_api.schemas.users import MeOut, ProfileUpdate, UserRefOut

router = APIRouter(tags=["users"])

_character_eager_load = (
    selectinload(Player.character_links)
    .selectinload(CharacterPlayer.character)
    .selectinload(Character.being)
    .selectinload(Being.entity)
)


async def _me_out(user_id: uuid.UUID, request: Request, session: SessionDep) -> MeOut:
    """Shared by GET /me and PATCH /me (ADR 0054) - the caller's own
    identity, tenant-wide memberships, campaign memberships, and GM grants.

    Re-fetched with memberships eager-loaded rather than reusing whatever
    `User` instance the caller already had - that one only ever needs
    `.id` itself.

    Players/campaign_gm_grants (ADR 0031/RFC 0004) are resolved tenant by
    tenant, deliberately not in one eager-loaded query off `user`. `Player`/
    `CampaignGm` rows self-authorize via `user_id` regardless of
    `app.tenant_id` (ADR 0030's addendum), but what each one references -
    `character_player`/`character`/`being`/`entity` via `Player`; `Campaign`
    via `CampaignGm` - has no `user_id` column of its own for RLS to
    self-authorize against, and this user's players/GM grants can
    legitimately span *multiple* tenants, so there is no single
    `app.tenant_id` that would correctly authorize all of them at once
    regardless (unlike `/me`'s own memberships, campaign_gm, and player
    rows themselves). Confirmed empirically, not assumed: querying this
    chain with `app.tenant_id` never set at all raises
    `UndefinedObjectError`, the same "genuinely never set" failure mode
    every other RLS-protected table already has - `player`/`campaign_gm`
    just happen to have a `user_id`-based escape hatch, and nothing past
    them does.
    """
    stmt = select(User).where(User.id == user_id).options(selectinload(User.memberships))
    full_user = (await session.execute(stmt)).scalar_one()

    player_tenant_ids = (
        await session.execute(select(Player.tenant_id).where(Player.user_id == user_id).distinct())
    ).scalars()
    gm_tenant_ids = (
        await session.execute(
            select(CampaignGm.tenant_id).where(CampaignGm.user_id == user_id).distinct()
        )
    ).scalars()

    players: list[Player] = []
    campaign_gms: list[CampaignGm] = []
    for tenant_id in set(player_tenant_ids) | set(gm_tenant_ids):
        await session.execute(
            text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
        )
        tenant_players = await session.execute(
            select(Player)
            .where(Player.user_id == user_id, Player.tenant_id == tenant_id)
            .options(_character_eager_load)
        )
        players.extend(tenant_players.scalars().all())

        tenant_gms = await session.execute(
            select(CampaignGm)
            .where(CampaignGm.user_id == user_id, CampaignGm.tenant_id == tenant_id)
            .options(selectinload(CampaignGm.campaign))
        )
        campaign_gms.extend(tenant_gms.scalars().all())

    return MeOut.from_user(full_user, request=request, players=players, campaign_gms=campaign_gms)


@router.get("/me")
async def get_me(user: CurrentUser, request: Request, session: SessionDep) -> MeOut:
    """Proves the whole token-verification pipeline end to end over real
    HTTP - see ADR 0023. Not nested under /tenants/{tenant_id}/... - this
    is about the caller's own identity across every tenant they belong to,
    not scoped to one.
    """
    return await _me_out(user.id, request, session)


@router.get("/me/managed")
async def get_my_managed_scope(user: CurrentUser, session: SessionDep) -> ManagedScopeOut:
    """What the caller runs, across every tenant - see ADR 0086. Tenants
    where they hold a tenant-wide OWNER/ORGA Membership (with every
    campaign in them), plus tenants where they only GM (with just the
    campaigns they GM). Not paginated, like `GET /me`: bounded by the
    caller's own memberships and GM rows. Authenticated but not
    tenant-scoped.

    Resolved tenant by tenant for the same reason `_me_out` is: `membership`
    and `campaign_gm` admit the caller's own rows by `app.user_id`, but
    `campaign` has no `user_id` to self-authorize against, and these rows
    span several tenants - so `app.tenant_id` is set per tenant rather than
    any policy being weakened. A tenant administrator's opt-out from a
    campaign's *play* visibility (ADR 0034) is irrelevant here: this is the
    administrative axis, so they still see it.
    """
    admin_role_by_tenant = {
        tenant_id: role
        for tenant_id, role in (
            await session.execute(
                select(Membership.tenant_id, Membership.role).where(Membership.user_id == user.id)
            )
        ).all()
        if role in (MembershipRole.OWNER, MembershipRole.ORGA)
    }
    gm_campaign_ids_by_tenant: dict[uuid.UUID, set[uuid.UUID]] = {}
    for tenant_id, campaign_id in (
        await session.execute(
            select(CampaignGm.tenant_id, CampaignGm.campaign_id).where(
                CampaignGm.user_id == user.id
            )
        )
    ).all():
        gm_campaign_ids_by_tenant.setdefault(tenant_id, set()).add(campaign_id)

    tenants: list[ManagedTenantOut] = []
    for tenant_id in set(admin_role_by_tenant) | set(gm_campaign_ids_by_tenant):
        await set_tenant_rls_context(session, tenant_id)
        tenant_row = (
            await session.execute(select(Tenant.name, Tenant.slug).where(Tenant.id == tenant_id))
        ).one()
        gm_campaign_ids = gm_campaign_ids_by_tenant.get(tenant_id, set())
        campaign_stmt = (
            select(Campaign.id, Campaign.name)
            .where(Campaign.tenant_id == tenant_id)
            .order_by(Campaign.name, Campaign.id)
        )
        if tenant_id not in admin_role_by_tenant:
            campaign_stmt = campaign_stmt.where(Campaign.id.in_(gm_campaign_ids))
        campaigns = [
            ManagedCampaignOut(
                campaign_id=campaign_id, name=name, is_gm=campaign_id in gm_campaign_ids
            )
            for campaign_id, name in (await session.execute(campaign_stmt)).all()
        ]
        role = admin_role_by_tenant.get(tenant_id)
        tenants.append(
            ManagedTenantOut(
                tenant_id=tenant_id,
                name=tenant_row.name,
                slug=tenant_row.slug,
                role=role.value if role is not None else None,
                campaigns=campaigns,
            )
        )
    tenants.sort(key=lambda t: (t.name, str(t.tenant_id)))
    return ManagedScopeOut(tenants=tenants)


@router.patch("/me")
async def update_me(
    user: CurrentUser, body: ProfileUpdate, request: Request, session: SessionDep
) -> MeOut:
    """Sets any of the caller's own self-editable profile fields (ADR
    0054/0060) - `email` isn't settable here at all, it's a read-only
    Authgear-derived cache (dependencies.get_current_user), and everything
    else on MeOut is derived, not directly editable.

    `exclude_unset=True`: a client updating just `bio` doesn't have to
    resend every other field to avoid wiping them - matches
    `update_tenant`/`update_campaign`'s own established PATCH convention,
    unlike the narrower single-required-field `NicknameUpdate` this
    replaced. `nickname`'s own conflict is still checked-then-written, not
    caught off the partial unique index's own conflict - matches this
    codebase's existing slug-conflict precedent (routers/tenants.py's
    `_resolve_create_slug`/`_check_slug_available_for_update`). No
    `If-Match`: see ADR 0054 for why self-editable fields on your own
    record aren't a meaningful concurrent-write risk.

    Re-fetched via `session.get_one`, not mutated directly on `user` - the
    `CurrentUser` the request was resolved with isn't guaranteed to be the
    same session-attached instance a write needs (the `client` test
    fixture's own fake override returns a transient one), the same
    "re-fetch before mutating" precedent every other write route already
    follows.
    """
    update = body.model_dump(exclude_unset=True)
    if "nickname" in update and update["nickname"] != user.nickname:
        conflict = await session.execute(
            select(User.id).where(User.nickname == update["nickname"], User.id != user.id).limit(1)
        )
        if conflict.first() is not None:
            raise NicknameConflictError(detail=f"Nickname '{update['nickname']}' is already in use")

    db_user = await session.get_one(User, user.id)
    for field in ("nickname", "display_name", "pronouns", "bio", "user_color"):
        if field in update:
            setattr(db_user, field, update[field])
    if "locales" in update:
        db_user.locales = update["locales"] or []
    await session.commit()
    return await _me_out(user.id, request, session)


@router.put("/me/picture", status_code=204)
async def upload_my_picture(user: CurrentUser, session: SessionDep, file: UploadFile) -> None:
    """Uploads or replaces the caller's own profile picture - see ADR 0056.
    No `If-Match`, same reasoning as `PATCH /me`: a single self-editable
    resource on your own record isn't a meaningful concurrent-write risk.
    """
    data, file_type = await read_and_validate_upload(file)
    await upsert_user_profile_picture(session, user_id=user.id, data=data, file_type=file_type)
    await session.commit()


@router.delete("/me/picture", status_code=204)
async def delete_my_picture(user: CurrentUser, session: SessionDep) -> None:
    """No-op (still 204), not 404, if there was never a custom picture to
    delete - matches DELETE's own general idempotency expectation.
    """
    await delete_user_profile_picture(session, user_id=user.id)
    await session.commit()


@router.get("/me/notifications")
async def list_my_notifications(
    user: CurrentUser,
    session: SessionDep,
    params: ParamsDep,
    unread_only: bool = False,
    since: Annotated[AwareDatetime | None, Query()] = None,
) -> Page[NotificationOut]:
    """See ADR 0058 - a single flat query, no per-tenant RLS-context
    looping needed (unlike `_me_out`'s own Player/CampaignGm resolution):
    `notification`'s RLS policy already admits a caller's own rows via
    `app.user_id` regardless of `app.tenant_id` (the same self-access
    shape `player`/`campaign_gm` have, ADR 0030's addendum), and every
    field this response needs is already denormalized onto the row
    itself - nothing here is joined from live, tenant-scoped data.

    `since` (ADR 0086): only rows with `created_at >= since`, a
    timezone-aware ISO 8601 timestamp (a naive one is a 422). Inclusive on
    purpose - a client sends back the newest `created_at` it has seen, and
    with `>` it would silently miss a second row sharing that exact
    timestamp; with `>=` it may see the boundary row again and dedupes by
    `id`. Known limitation: a row from a transaction that began before,
    but committed after, the client's last poll can carry an earlier
    `created_at` and be skipped - narrow, since notifications are written
    in short single transactions.
    """
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if since is not None:
        stmt = stmt.where(Notification.created_at >= since)
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id)
    page: Page[NotificationOut] = await apaginate(session, stmt, params)
    return page


@router.get("/me/changes")
async def list_my_changes(
    user: CurrentUser,
    session: SessionDep,
    params: ParamsDep,
    since: Annotated[AwareDatetime | None, Query()] = None,
) -> Page[EntityChangeOut]:
    """What happened to things the caller's characters own or carry, across
    every tenant, newest first - see ADR 0099. `since` is inclusive and
    timezone-aware, exactly like `GET /me/notifications` (ADR 0086).

    One flat query, no per-tenant looping: `entity_change`'s RLS admits a
    row only to its recipient (`user_id = app.user_id`), whatever the
    tenant. Also filtered by `user_id` here, not left to RLS alone (ADR
    0002). There is no job runner (ADR 0008), so this is where the 90-day
    retention happens: expired rows are excluded from the listing, then the
    caller's own are deleted.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=RETENTION_DAYS)
    stmt = select(EntityChange).where(
        EntityChange.user_id == user.id, EntityChange.occurred_at >= cutoff
    )
    if since is not None:
        stmt = stmt.where(EntityChange.occurred_at >= since)
    stmt = stmt.order_by(EntityChange.occurred_at.desc(), EntityChange.id)

    def _out(rows: Sequence[EntityChange]) -> list[EntityChangeOut]:
        return [EntityChangeOut.from_change(row) for row in rows]

    page: Page[EntityChangeOut] = await apaginate(session, stmt, params, transformer=_out)

    # Pruned last, not first: app.user_id is transaction-local
    # (get_current_user), and this commit ends the transaction - any query
    # after it would run with no user set and see nothing through RLS.
    await session.execute(
        delete(EntityChange).where(
            EntityChange.user_id == user.id, EntityChange.occurred_at < cutoff
        )
    )
    await session.commit()
    return page


@router.get("/me/notifications/sent")
async def list_my_sent_notifications(
    user: CurrentUser,
    session: SessionDep,
    params: ParamsDep,
    batch_id: uuid.UUID | None = None,
) -> Page[NotificationOut]:
    """See ADR 0061 - the sender's side of read receipts: did anyone
    actually read what I sent? `WHERE created_by = caller.id`, not
    `user_id` - works today with no RLS change, since the
    `created_by = app.user_id` clause ADR 0058 already added (for the
    `INSERT ... RETURNING` fix) already permits exactly this read.
    Optional `batch_id` pulls just one broadcast's full recipient list -
    every row a single creation call fanned out shares one.
    """
    stmt = select(Notification).where(Notification.created_by == user.id)
    if batch_id is not None:
        stmt = stmt.where(Notification.batch_id == batch_id)
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id)
    page: Page[NotificationOut] = await apaginate(session, stmt, params)
    return page


@router.post("/me/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> NotificationOut:
    """Idempotent - re-marking an already-read notification is a no-op,
    not an error, mirroring `grant_campaign_gm`'s own idempotent-PUT
    precedent. Explicitly filtered by `user_id == caller.id`, not left to
    RLS alone (defense in depth, ADR 0002) - an unknown or not-mine id
    both 404, collapsed indistinguishably.
    """
    stmt = select(Notification).where(
        Notification.id == notification_id, Notification.user_id == user.id
    )
    notification = (await session.execute(stmt)).scalar_one_or_none()
    if notification is None:
        raise NotificationNotFoundError(detail=f"No notification with id {notification_id}")

    if notification.read_at is None:
        notification.read_at = datetime.now(tz=UTC)
        await session.commit()
    return NotificationOut.model_validate(notification)


@router.get("/users/by-email/{email}")
async def get_user_by_email(email: str, user: CurrentUser, session: SessionDep) -> UserRefOut:
    """Exact match only, open to any authenticated user - see ADR 0055.
    `user` isn't otherwise used - CurrentUser's own token verification is
    the entire gate here, no tenant/role check on top of it.
    """
    found = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if found is None:
        raise UserNotFoundError(detail=f"No user with email {email}")
    return UserRefOut.from_user(found)


@router.get("/users/by-nickname/{nickname}")
async def get_user_by_nickname(nickname: str, user: CurrentUser, session: SessionDep) -> UserRefOut:
    """Exact match only, open to any authenticated user - see ADR 0055."""
    found = (
        await session.execute(select(User).where(User.nickname == nickname))
    ).scalar_one_or_none()
    if found is None:
        raise UserNotFoundError(detail=f"No user with nickname {nickname}")
    return UserRefOut.from_user(found)


async def _record_account_departure(session: SessionDep, *, user_id: uuid.UUID) -> None:
    """ADR 0084's addendum: deleting an account cascades away every
    membership, player seat and GM grant the user held, in every tenant, so
    record each one first - in the tenant it belonged to, under the action
    an ordinary removal of that relationship already uses, with the reason
    `account deleted`. Written with the user as actor; `audit_log.actor_id`
    is ON DELETE SET NULL, so that clears once the account is gone, and the
    user stays identifiable by `target_id`. No notification: the only
    recipient would be the account being deleted.

    `audit_log`'s RLS is tenant-scoped, so each tenant's entries are
    written under that tenant's own RLS context. The three source tables
    admit the caller's own rows by `app.user_id` regardless of tenant.
    """
    memberships = (
        await session.execute(
            select(Membership.tenant_id, Membership.role).where(Membership.user_id == user_id)
        )
    ).all()
    players = (
        await session.execute(select(Player.tenant_id, Player.id).where(Player.user_id == user_id))
    ).all()
    gm_grants = (
        await session.execute(
            select(CampaignGm.tenant_id, CampaignGm.campaign_id).where(
                CampaignGm.user_id == user_id
            )
        )
    ).all()

    tenant_ids = (
        {tenant_id for tenant_id, _ in memberships}
        | {tenant_id for tenant_id, _ in players}
        | {tenant_id for tenant_id, _ in gm_grants}
    )
    for tenant_id in sorted(tenant_ids, key=str):
        await set_tenant_rls_context(session, tenant_id)
        for member_tenant_id, role in memberships:
            if member_tenant_id == tenant_id:
                await record_activity(
                    session,
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="membership.deleted",
                    target_type="membership",
                    target_id=user_id,
                    detail=f"account deleted, role={role.value}",
                )
        for player_tenant_id, player_id in players:
            if player_tenant_id == tenant_id:
                await record_activity(
                    session,
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="player.removed",
                    target_type="player",
                    target_id=player_id,
                    detail=f"account deleted, user={user_id}",
                )
        for gm_tenant_id, campaign_id in gm_grants:
            if gm_tenant_id == tenant_id:
                await record_activity(
                    session,
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="campaign_gm.revoked",
                    target_type="campaign_gm",
                    target_id=user_id,
                    detail=f"account deleted, campaign_id={campaign_id}",
                )
        # Flush while this tenant's context is still the active one - the
        # INSERT's RLS check runs at flush time, not at session.add().
        await session.flush()


@router.delete("/me", status_code=204)
async def delete_me(user: CurrentUser, session: SessionDep) -> None:
    """ADR 0036/RFC 0007 - removes the caller's own app_user row. Guarded:
    409 LastOwnerError if the caller is the sole OWNER Membership of any
    tenant they belong to - deleting themselves would leave that tenant
    with no one able to administer it at all (the same lockout PATCH/
    DELETE /memberships also guard, from the other direction).

    Every owner-tenant is checked *before* anything is deleted - one
    tenant failing the guard must not leave a half-completed deletion
    behind. Each check needs its own set_tenant_rls_context call first:
    membership's RLS policy admits a caller's own rows via app.user_id
    (ADR 0023's own self-access carve-out for GET /me), but *other* users'
    OWNER rows in the same tenant only become visible once app.tenant_id
    is set for that specific tenant - unlike this function's own
    Membership.user_id-scoped query just below, which needs no such
    context at all.

    Once past every guard, the actual deletion is a bare `DELETE FROM
    app_user`, no RLS context needed for it either: every cascade this
    triggers (Membership/Player/CampaignGm/TenantAdminCampaignOptOut rows
    in *every* tenant this user touched, and every created_by/updated_by
    this user ever left behind, all `ON DELETE CASCADE`/`SET NULL` per ADR
    0029) is a foreign-key referential action, which Postgres always runs
    regardless of row security policies on the referencing tables -
    confirmed against Postgres's own documented row-security semantics,
    not just assumed, and proven out by this module's own cascade test.
    """
    owner_tenant_ids = (
        (
            await session.execute(
                select(Membership.tenant_id).where(
                    Membership.user_id == user.id, Membership.role == MembershipRole.OWNER
                )
            )
        )
        .scalars()
        .all()
    )

    for tenant_id in owner_tenant_ids:
        await set_tenant_rls_context(session, tenant_id)
        owner_ids = (
            (
                await session.execute(
                    select(Membership.user_id).where(
                        Membership.tenant_id == tenant_id, Membership.role == MembershipRole.OWNER
                    )
                )
            )
            .scalars()
            .all()
        )
        if owner_ids == [user.id]:
            raise LastOwnerError(detail=f"User {user.id} is the sole OWNER of tenant {tenant_id}")

    await _record_account_departure(session, user_id=user.id)

    # The user_profile_picture link cascades away with the User row below,
    # but nothing points the other way - the profile_picture row itself
    # would otherwise be orphaned forever (ADR 0056).
    await delete_user_profile_picture(session, user_id=user.id)
    await session.delete(await session.get_one(User, user.id))
    await session.commit()
