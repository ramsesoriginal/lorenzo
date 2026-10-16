"""Repositories - RFC 0024, ADR 0118 onward.

A repository is a tenant of kind `repository`: a reusable setting other
tenants are granted access to and copy from. This router holds what's
repository-specific; authoring a repository's content goes through the
same routes as any other tenant's.

Two sides, both under /tenants/{tenant_id}: the repository's own
(`/published`, `/subscribers`), and a granted tenant's (`/repositories`).
"""

import uuid
from collections.abc import Callable, Sequence
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from fastapi_pagination import Page, Params, paginate
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import is_tenant_admin, is_tenant_owner
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_admin_context,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    InvalidSubscriberError,
    NotARepositoryError,
    PublicRepositoryCannotBeUnpublishedError,
    ReleaseNotFoundError,
    RepositoryManagementForbiddenError,
    RepositoryNotCopiedError,
    RepositoryNotFoundError,
    SubscriptionNotFoundError,
    TenantAdminRequiredError,
    TenantNotFoundError,
)
from lorenzo_api.models import (
    AuditLog,
    Being,
    Character,
    Entity,
    EntityAudience,
    EntityPrototype,
    Fact,
    Item,
    ItemInstance,
    RepositoryCopy,
    RepositoryCopyLinkAttachment,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    RepositoryRelease,
    RepositorySubscription,
    StatDefinition,
    StatGroup,
    Tenant,
    TenantKind,
)
from lorenzo_api.release_current import make_release_current
from lorenzo_api.release_document_store import (
    kept_documents,
)
from lorenzo_api.release_fanout import announce, drain_after_response
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_built_on import built_on_behind
from lorenzo_api.repository_content import attachments_of, load_attachment_content
from lorenzo_api.repository_copying import (
    Plan,
    Resolution,
    Step,
    apply_plan,
    dependencies_of,
    forget_copy,
    plan_copy,
)
from lorenzo_api.repository_digest import BreakingNote, Row, assess
from lorenzo_api.repository_grants import (
    grant_repository_access,
    notify_tenant_admins,
    subscribe_to_public,
)
from lorenzo_api.repository_preview import preview_of, read_content, rules_for, showcase_ids
from lorenzo_api.repository_profiles import profile_of
from lorenzo_api.repository_publishing import publish_release
from lorenzo_api.repository_releases import (
    ReleaseRef,
    current_notice,
    current_release,
    relabel,
    releases_named,
)
from lorenzo_api.repository_updates import (
    COLLISION_KIND,
    AttachmentAction,
    AttachmentRef,
    RowRef,
    UpdateAction,
    apply_updates,
    compute_updates,
)
from lorenzo_api.repository_upstream import (
    entity_rows,
    is_public,
    stat_group_rows,
)
from lorenzo_api.schemas.repositories import (
    AddedOut,
    ApplyUpdatesOut,
    ApplyUpdatesRequest,
    AttachmentAddedOut,
    AttachmentChangeOut,
    AttachmentRefOut,
    BreakingNoteOut,
    BreakingRowOut,
    BuiltOnBehindOut,
    CollisionOut,
    ContributionCountsOut,
    ContributionOut,
    CopyOut,
    CopyPlanOut,
    CopyRequest,
    CopyStepOut,
    DroppedOut,
    EntityKindName,
    FieldChangeOut,
    MakeCurrentRequest,
    NotAppliedOut,
    PreviousCopyOut,
    PublishedOut,
    PublishRequest,
    ReleaseAuthoredOut,
    ReleaseCountsOut,
    ReleaseOut,
    ReleasePreviewOut,
    ReleaseRefOut,
    ReleaseUpdate,
    RepositoryDependencyOut,
    RepositoryEntityOut,
    RepositoryStatDefinitionOut,
    RepositoryStatGroupOut,
    RepositorySummaryOut,
    RowChangeOut,
    RowNameOut,
    RowRefOut,
    SubscriberOut,
    SubscribersSummaryOut,
    SubscriptionOut,
    UnprovenKindOut,
    UpdatesOut,
)
from lorenzo_api.schemas.tenants import TenantOut

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["repositories"])


async def _require_owner(session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser) -> None:
    if not await is_tenant_owner(session, tenant_id=tenant_id, user_id=user.id):
        raise RepositoryManagementForbiddenError(
            detail=f"Only an owner of tenant {tenant_id} can do this"
        )


async def _require_admin_unless_dry_run(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, dry_run: bool
) -> None:
    """Copying a repository and applying its updates bring stat groups and entries in, so they are
    for an Owner or an Organizer; an Author may run either as a dry run, to check what it would
    do (RFC 0040, ADR 0219)."""
    if not dry_run and not await is_tenant_admin(session, tenant_id=tenant_id, user_id=user.id):
        raise TenantAdminRequiredError(
            detail="Only an Owner or an Organizer can do this; an Author can check it as a dry run"
        )


async def _require_repository(session: SessionDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = await session.get_one(Tenant, tenant_id)
    if tenant.kind is not TenantKind.REPOSITORY:
        raise NotARepositoryError(detail=f"Tenant {tenant_id} is for play, not a repository")
    return tenant


# --- The repository's own side ----------------------------------------------


def _readable(release: RepositoryRelease | ReleaseRef, *, current: bool) -> ReleaseOut:
    """A release as any reader sees it, with whether it is the one libraries read (ADR 0288)."""
    fields = {n: getattr(release, n) for n in ReleaseOut.model_fields if n != "current"}
    return ReleaseOut.model_validate({**fields, "current": current})


def _authored(release: RepositoryRelease, *, current: bool, kept: bool) -> ReleaseAuthoredOut:
    """A release as the repository's members see it: and whether its content is still kept."""
    fields = {
        n: getattr(release, n)
        for n in ReleaseAuthoredOut.model_fields
        if n not in ("current", "kept")
    }
    return ReleaseAuthoredOut.model_validate({**fields, "current": current, "kept": kept})


@router.put("/published")
async def publish_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    body: PublishRequest | None = None,
) -> PublishedOut:
    """Publishes a repository, or announces an update to one already
    published: either way it makes a release (ADR 0207), `published_at`
    becomes now, and every granted tenant's members are told (ADR 0118). The
    body is optional: without a label the release is called by its number.
    `409` if the label is taken, and `409 release-has-breaking-changes` while it holds
    changes the update engine cannot carry to the libraries that copied it, unless
    `acknowledge_breaking` (ADR 0208), and, for a public repository, `409 built-on-behind` while
    a repository it is built on has a release it has not taken (ADR 0289). The release records
    the digest of what was published, what it added, changed and removed, and those changes,
    and the repository's released rows become what was published. Until the first publish, no
    subscriber can see anything of it.
    """
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    published = await publish_release(
        session, repository=tenant, user_id=user.id, body=body or PublishRequest()
    )
    release_out = _authored(published.release, current=True, kept=published.public)
    await session.commit()
    drain_after_response(background_tasks, session)
    await set_tenant_rls_context(session, tenant_id)
    return PublishedOut(
        **TenantOut.model_validate(await session.get_one(Tenant, tenant_id)).model_dump(),
        release=release_out,
    )


@router.delete("/published")
async def unpublish_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
) -> TenantOut:
    """Back to draft: subscribers can no longer browse, copy, or check
    for updates. What they already copied is theirs and stays (RFC 0024
    §6)."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    if await is_public(session, tenant_id):
        raise PublicRepositoryCannotBeUnpublishedError(
            detail="Make this repository private first: unpublishing it would cut off every "
            "library that reads it without telling you how many."
        )
    if tenant.published_at is not None:
        tenant.published_at = None
        tenant.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="repository.unpublished",
            target_type="tenant",
            target_id=tenant_id,
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return TenantOut.model_validate(await session.get_one(Tenant, tenant_id))


@router.get("/release-preview")
async def preview_release(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
) -> ReleasePreviewOut:
    """What publishing now would release, before it is made (ADR 0208): this repository's live
    content against what its latest release saw, for any of its members. Whether it matches
    that release, which rows were added, changed or removed, what the detector would refuse,
    the hint of descriptions edited, and how many libraries would be told. Writes nothing;
    loads the repository once, like a publish. `409` for a play tenant."""
    await _require_repository(session, tenant_id)
    assessed = await assess(session, tenant_id)
    behind = await built_on_behind(session, tenant_id)
    told = await session.scalar(
        select(func.count())
        .select_from(RepositorySubscription)
        .where(RepositorySubscription.repository_tenant_id == tenant_id)
    )
    found = assessed.comparison
    return ReleasePreviewOut(
        release=(_readable(assessed.release, current=True) if assessed.release else None),
        baseline=assessed.baseline,
        matches=assessed.matches,
        live_digest=assessed.digest,
        differing_rows=found.differing,
        counts=ReleaseCountsOut.model_validate(assessed.counts),
        added=_row_names(found.added),
        changed=_row_names([now for _, now in found.changed]),
        removed=_row_names(found.removed),
        breaking=[BreakingRowOut.model_validate(b.as_json()) for b in assessed.hits],
        warnings=[BreakingRowOut.model_validate(b.as_json()) for b in assessed.warnings],
        unproven_kinds=[UnprovenKindOut.model_validate(e) for e in assessed.unproven_kinds],
        descriptions_edited=assessed.descriptions_edited,
        libraries_told=told or 0,
        built_on_behind=[
            BuiltOnBehindOut(
                repository_id=b.repository_id,
                name=b.name,
                taken=_release_ref(b.taken),
                current=_release_ref(b.current),
                readable=b.readable,
            )
            for b in behind
        ],
        built_on_blocks_publish=bool(behind) and await is_public(session, tenant_id),
    )


@router.get("/releases")
async def list_releases(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[ReleaseAuthoredOut]:
    """What this repository has published, newest first (ADR 0207), for any of its
    members. A library reads the same list through
    `/tenants/{id}/repositories/{repository_id}/releases`. `409` for a play tenant."""
    await _require_repository(session, tenant_id)
    stmt = (
        select(RepositoryRelease)
        .where(RepositoryRelease.tenant_id == tenant_id)
        .order_by(RepositoryRelease.number.desc())
    )

    current = await current_release(session, tenant_id)
    kept = await kept_documents(session, tenant_id)

    def _out(rows: Sequence[RepositoryRelease]) -> list[ReleaseAuthoredOut]:
        return [
            _authored(r, current=bool(current and current.id == r.id), kept=r.id in kept)
            for r in rows
        ]

    return cast(
        Page[ReleaseAuthoredOut],
        await apaginate(session, stmt, params, transformer=_out),
    )


@router.patch("/releases/{release_id}")
async def edit_release(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    release_id: uuid.UUID,
    body: ReleaseUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ReleaseAuthoredOut:
    """Corrects a release's label or notes, which are the author's words about it
    (ADR 0207); its number, its breaking flag and what was published are not
    editable. Owner only. `409` if the label is taken, `404` for a release this
    repository did not make."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    release = await session.scalar(
        select(RepositoryRelease).where(
            RepositoryRelease.tenant_id == tenant_id, RepositoryRelease.id == release_id
        )
    )
    if release is None:
        raise ReleaseNotFoundError(detail=f"This repository has no release {release_id}")
    changed: list[str] = []
    if "label" in body.model_fields_set and body.label is not None:
        await relabel(session, release, body.label)
        listing = await profile_of(session, tenant_id)
        if tenant.current_release_id == release.id:
            listing.release_label = release.label
        changed.append("label")
    if "notes" in body.model_fields_set:
        release.notes = body.notes
        changed.append("notes")
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.release_edited",
        target_type="tenant",
        target_id=tenant_id,
        detail=f"release={release.number},fields={'+'.join(changed) or 'none'}",
    )
    await session.flush()
    current = await current_release(session, tenant_id)
    out = _authored(
        release,
        current=bool(current and current.id == release.id),
        kept=release.id in await kept_documents(session, tenant_id),
    )
    await session.commit()
    return out


@router.put("/releases/{release_id}/current")
async def make_release_current_route(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    release_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    body: MakeCurrentRequest | None = None,
) -> ReleaseAuthoredOut:
    """Makes an earlier release the one libraries read, the rollback of a bad release (ADR 0288,
    RFC 0037 section 5). Owner only. The released rows are recomputed from that release's
    document, "Edited since" compares with it from now on, and the libraries are told. `409
    release-not-retained` if its content is no longer kept, `409 release-has-breaking-changes`
    while moving from the release that is current to it breaks what libraries on that one hold,
    unless `acknowledge_breaking`. Making the current release current is a no-op."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    body = body or MakeCurrentRequest()
    moved = await make_release_current(
        session,
        repository=tenant,
        release_id=release_id,
        acknowledge_breaking=body.acknowledge_breaking,
    )
    release = moved.release
    if moved.changed:
        tenant.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="repository.release_made_current",
            target_type="tenant",
            target_id=tenant_id,
            detail=f"release={release.number},label={release.label}",
        )
        # A delisted repository reads as unpublished to the libraries (ADR 0303): nothing to tell.
        subscribers = (
            []
            if tenant.delisted_at is not None
            else (
                await session.scalars(
                    select(RepositorySubscription.subscriber_tenant_id).where(
                        RepositorySubscription.repository_tenant_id == tenant_id
                    )
                )
            ).all()
        )
        title, notice = current_notice(repository_name=tenant.name, release=release)
        await announce(
            session,
            repository_id=tenant_id,
            release_id=release.id,
            type="repository_updated",
            title=title,
            body=notice,
            created_by=user.id,
            recipients=subscribers,
        )
    out = _authored(release, current=True, kept=True)
    await session.commit()
    drain_after_response(background_tasks, session)
    return out


# What a preview names of what a publish would add, change or remove; the counts say the rest.
PREVIEW_NAMES = 200


def _row_names(rows: Sequence[Row]) -> list[RowNameOut]:
    return [
        RowNameOut(
            kind=r.kind,
            row_id=r.row_id,
            parent_id=r.parent_id,
            name=r.name,
            parent_name=r.facts.get("parent_name"),
        )
        for r in rows[:PREVIEW_NAMES]
    ]


def _release_ref(release: ReleaseRef | None) -> ReleaseRefOut | None:
    if release is None:
        return None
    return ReleaseRefOut(id=release.id, number=release.number, label=release.label)


def _subscriber_out(
    tenant: Tenant,
    subscription: RepositorySubscription | None,
    copy: RepositoryCopy | None,
    releases: dict[uuid.UUID, ReleaseRef],
) -> SubscriberOut:
    return SubscriberOut(
        tenant_id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        granted_at=subscription.created_at if subscription else None,
        granted_by=subscription.created_by if subscription else None,
        copied_at=copy.copied_at if copy else None,
        synced_at=copy.synced_at if copy else None,
        synced_release=_release_ref(
            releases.get(copy.synced_release_id) if copy and copy.synced_release_id else None
        ),
    )


async def _releases_taken_by(
    session: SessionDep, repository_id: uuid.UUID, copies: Sequence[RepositoryCopy | None]
) -> dict[uuid.UUID, ReleaseRef]:
    """The repository's releases that these copies say they last took."""
    return await releases_named(
        session, repository_id, [c.synced_release_id for c in copies if c and c.synced_release_id]
    )


# What a repository's log records of a library it named itself: an invitation and the end of one.
# A library a repository has never named is not named by it (ADR 0299).
_NAMED_ACTIONS = ("repository.granted", "repository.revoked")


def _holders(tenant_id: uuid.UUID, *columns: Any) -> Any:
    """The libraries that hold a grant to the repository or a copy of it, one row each:
    `Tenant`, its grant and its copy, joined, for `columns` to read."""
    return (
        select(*columns)
        .select_from(Tenant)
        .outerjoin(
            RepositorySubscription,
            (RepositorySubscription.subscriber_tenant_id == Tenant.id)
            & (RepositorySubscription.repository_tenant_id == tenant_id),
        )
        .outerjoin(
            RepositoryCopy,
            (RepositoryCopy.tenant_id == Tenant.id)
            & (RepositoryCopy.repository_tenant_id == tenant_id),
        )
    )


def _once_named(tenant_id: uuid.UUID) -> Any:
    """Whether the repository's own log names the library: its Owner invited it, or stopped
    inviting it, so the Owner knows it already."""
    return Tenant.id.in_(
        select(AuditLog.target_id).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action.in_(_NAMED_ACTIONS),
            AuditLog.target_id.is_not(None),
        )
    )


def _is_named(tenant_id: uuid.UUID) -> Any:
    """The libraries a repository's members are told by name: those it invited, and those it
    invited once that still hold a copy of it (ADR 0204). A library that copied a public
    repository by itself is not among them, whether its grant stands or went when the repository
    went private: it is counted (`_is_public_copy`) and never named (ADR 0299)."""
    return or_(
        RepositorySubscription.source == "invited",
        and_(
            RepositorySubscription.subscriber_tenant_id.is_(None),
            RepositoryCopy.tenant_id.is_not(None),
            _once_named(tenant_id),
        ),
    )


def _is_public_copy(tenant_id: uuid.UUID) -> Any:
    """The libraries that copied it by themselves, from Discover: a grant they gave themselves,
    or a copy and no grant that the repository's log never names (its public grants are
    revoked when it goes private, and the copies stay)."""
    return or_(
        RepositorySubscription.source == "public",
        and_(
            RepositorySubscription.subscriber_tenant_id.is_(None),
            RepositoryCopy.tenant_id.is_not(None),
            ~_once_named(tenant_id),
        ),
    )


@router.get("/subscribers")
async def list_subscribers(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_admin_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[SubscriberOut]:
    """The libraries this repository invited, and those it invited once that still hold a copy,
    for any of its members (ADR 0204): whether and when each copied it and last updated, and, for
    one whose invitation is gone but whose copy stays, no `granted_at`. A library that copied a
    public repository by itself is not named here, only counted by `GET /subscribers/summary`
    (ADR 0299)."""
    await _require_repository(session, tenant_id)
    stmt = (
        _holders(tenant_id, Tenant, RepositorySubscription, RepositoryCopy)
        .where(_is_named(tenant_id))
        .order_by(Tenant.name, Tenant.id)
    )

    async def _rows_out(
        rows: Sequence[tuple[Tenant, RepositorySubscription | None, RepositoryCopy | None]],
    ) -> list[SubscriberOut]:
        releases = await _releases_taken_by(session, tenant_id, [copy for _, _, copy in rows])
        return [_subscriber_out(tenant, sub, copy, releases) for tenant, sub, copy in rows]

    return cast(
        Page[SubscriberOut],
        await apaginate(session, stmt, params, transformer=_rows_out, unique=False),
    )


@router.get("/subscribers/summary")
async def summarize_subscribers(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_admin_context)], session: SessionDep
) -> SubscribersSummaryOut:
    """How many libraries `GET /subscribers` names (`named`) and how many copied the repository
    by themselves from Discover (`public_copies`), which is all a repository learns of them
    (ADR 0299, RFC 0038 section 6). For its Owners and Organizers."""
    await _require_repository(session, tenant_id)
    named = await session.scalar(
        _holders(tenant_id, func.count(Tenant.id)).where(_is_named(tenant_id))
    )
    public_copies = await session.scalar(
        _holders(tenant_id, func.count(Tenant.id)).where(_is_public_copy(tenant_id))
    )
    return SubscribersSummaryOut(named=named or 0, public_copies=public_copies or 0)


@router.get("/attachments")
async def list_attachments(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[AttachmentRefOut]:
    """The parents this repository added to entities it holds copies of, which a
    tenant that copies it takes along (ADR 0172, 0174): what its authors can't see
    in its own rows, since a parent that arrived with a copy looks the same. Both
    ends are the repository's own rows, named by their origin too. For any of its
    members; `409` for a play tenant."""
    await _require_repository(session, tenant_id)
    content = await load_attachment_content(session, tenant_id)
    rows = [
        AttachmentRefOut(
            child_source_id=a.child_source_id,
            child_local_id=a.child,
            child_name=content.entities[a.child],
            parent_source_id=a.parent_source_id,
            parent_local_id=a.parent,
            parent_name=content.entities[a.parent],
        )
        for a in attachments_of(content)
    ]
    rows.sort(key=lambda r: (r.child_name, r.parent_name, str(r.child_source_id)))
    return cast(Page[AttachmentRefOut], paginate(rows, params))


@router.put("/subscribers/{subscriber_tenant_id}")
async def grant_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    subscriber_tenant_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SubscriberOut:
    """Grants another tenant access (ADR 0118): `201` for a new grant,
    `200` if it already had one. The tenant is named by its id, which its
    own members pass on; there's no directory of tenants to pick from.
    Its members are told. A library that holds a public grant, which it gave itself by copying
    a public repository, is invited all the same (an invitation outranks it, ADR 0287): its
    grant becomes an invitation and the answer is `201`, as for any new one, so that what
    comes back says nothing of whether it had copied the repository by itself (ADR 0299).
    """
    await _require_owner(session, tenant_id=tenant_id, user=user)
    repository = await _require_repository(session, tenant_id)
    if subscriber_tenant_id == tenant_id:
        raise InvalidSubscriberError(detail="A repository can't be granted to itself")
    subscriber = await session.get(Tenant, subscriber_tenant_id)
    if subscriber is None:
        raise TenantNotFoundError(detail=f"No tenant with id {subscriber_tenant_id}")
    subscription = await session.get(RepositorySubscription, (tenant_id, subscriber_tenant_id))
    if subscription is not None and subscription.source == "public":
        await session.delete(subscription)
        await session.flush()
    elif subscription is not None:
        held = await session.get(RepositoryCopy, (subscriber_tenant_id, tenant_id))
        return _subscriber_out(
            subscriber, subscription, held, await _releases_taken_by(session, tenant_id, [held])
        )

    await grant_repository_access(
        session, repository=repository, subscriber=subscriber, granted_by=user.id
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.status_code = 201
    held = await session.get(RepositoryCopy, (subscriber_tenant_id, tenant_id))
    return _subscriber_out(
        subscriber,
        await session.get_one(RepositorySubscription, (tenant_id, subscriber_tenant_id)),
        held,
        await _releases_taken_by(session, tenant_id, [held]),
    )


@router.delete("/subscribers/{subscriber_tenant_id}", status_code=204)
async def revoke_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    subscriber_tenant_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Revokes a grant. What the tenant already copied stays theirs (RFC
    0024 §6). Its members are told (ADR 0199); the subscribing side giving
    its own grant up is not announced.
    """
    await _require_owner(session, tenant_id=tenant_id, user=user)
    repository = await _require_repository(session, tenant_id)
    # A grant a library gave itself by copying a public repository is not the repository's to end,
    # or to know by id: for the repository it is not there (ADR 0299).
    subscription = await session.get(RepositorySubscription, (tenant_id, subscriber_tenant_id))
    if subscription is None or subscription.source != "invited":
        raise SubscriptionNotFoundError(
            detail=f"Tenant {subscriber_tenant_id} holds no grant for repository {tenant_id}"
        )
    await session.delete(subscription)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.revoked",
        target_type="tenant",
        target_id=subscriber_tenant_id,
    )
    await notify_tenant_admins(
        session,
        recipient_tenant_ids=[subscriber_tenant_id],
        current_tenant_id=tenant_id,
        type="repository_revoked",
        title=f"{repository.name} is no longer shared with your library",
        body=(
            "What your library already copied from it stays yours. It will not get"
            " updates from it unless it is invited again."
        ),
        created_by=user.id,
    )
    await session.commit()


# --- A granted tenant's side --------------------------------------------------


async def _contribution_counts(
    session: SessionDep, tenant_id: uuid.UUID
) -> dict[uuid.UUID, ContributionCountsOut]:
    counts: dict[uuid.UUID, dict[str, int]] = {}

    def bump(repository: uuid.UUID, key: str, n: int) -> None:
        counts.setdefault(repository, {}).setdefault(key, 0)
        counts[repository][key] += n

    for repository, n in await session.execute(
        select(RepositoryCopyLinkEntity.source_tenant_id, func.count())
        .where(
            RepositoryCopyLinkEntity.tenant_id == tenant_id,
            RepositoryCopyLinkEntity.entity_id.is_not(None),
        )
        .group_by(RepositoryCopyLinkEntity.source_tenant_id)
    ):
        bump(repository, "entities", n)
    for model, local, name in (
        (RepositoryCopyLinkStatGroup, RepositoryCopyLinkStatGroup.stat_group_id, "stat_groups"),
        (
            RepositoryCopyLinkStatDefinition,
            RepositoryCopyLinkStatDefinition.stat_definition_id,
            "stat_definitions",
        ),
    ):
        for repository, mode, n in await session.execute(
            select(model.source_tenant_id, model.mode, func.count())
            .where(model.tenant_id == tenant_id, local.is_not(None))
            .group_by(model.source_tenant_id, model.mode)
        ):
            bump(repository, f"{name}_{mode}", n)
    for repository, n in await session.execute(
        select(RepositoryCopyLinkAttachment.source_tenant_id, func.count())
        .where(RepositoryCopyLinkAttachment.tenant_id == tenant_id)
        .group_by(RepositoryCopyLinkAttachment.source_tenant_id)
    ):
        bump(repository, "attachments", n)
    return {
        repository: ContributionCountsOut(
            entities=c.get("entities", 0),
            stat_groups_copied=c.get("stat_groups_copied", 0),
            stat_groups_merged=c.get("stat_groups_merged", 0),
            stat_definitions_copied=c.get("stat_definitions_copied", 0),
            stat_definitions_merged=c.get("stat_definitions_merged", 0),
            attachments=c.get("attachments", 0),
        )
        for repository, c in counts.items()
    }


@router.get("/repositories")
async def list_repositories(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[SubscriptionOut]:
    """Every repository granted to this tenant, published or not, and
    every one it has copied, granted or not (ADR 0118, 0119), with what
    each copy contributed. For any of its members."""
    grants = {
        s.repository_tenant_id: s
        for s in await session.scalars(
            select(RepositorySubscription).where(
                RepositorySubscription.subscriber_tenant_id == tenant_id
            )
        )
    }
    copies = {
        c.repository_tenant_id: c
        for c in await session.scalars(
            select(RepositoryCopy).where(RepositoryCopy.tenant_id == tenant_id)
        )
    }
    ids = set(grants) | set(copies)
    repositories = {
        r.id: r for r in await session.scalars(select(Tenant).where(Tenant.id.in_(ids)))
    }
    counts = await _contribution_counts(session, tenant_id)
    synced: dict[uuid.UUID, ReleaseRef] = {}
    current: dict[uuid.UUID, ReleaseRef] = {}
    for repository_id, offered in repositories.items():
        if (
            offered.published_at is None
            or offered.delisted_at is not None
            or offered.kind is not TenantKind.REPOSITORY
        ):
            continue
        # What a library may read of a repository's releases it reads through the gated
        # read: an invitation withdrawn, or a repository back in draft, leaves it none.
        async with reading_repository(session, repository_id) as allowed:
            if not allowed:
                continue
            if read := await current_release(session, repository_id):
                current[repository_id] = read
            held = copies.get(repository_id)
            if held and held.synced_release_id:
                taken = await releases_named(session, repository_id, [held.synced_release_id])
                if held.synced_release_id in taken:
                    synced[repository_id] = taken[held.synced_release_id]
    rows: list[SubscriptionOut] = []
    for repository_id in ids:
        repository, grant, copy = (
            repositories.get(repository_id),
            grants.get(repository_id),
            copies.get(repository_id),
        )
        rows.append(
            SubscriptionOut(
                repository=RepositorySummaryOut(
                    id=repository_id,
                    name=repository.name if repository else (copy.repository_name if copy else ""),
                    slug=repository.slug if repository else "",
                    description=repository.description if repository else "",
                    # A delisted repository reads as unpublished to the libraries (ADR 0303).
                    published_at=(
                        repository.published_at
                        if repository and repository.delisted_at is None
                        else None
                    ),
                ),
                granted_at=grant.created_at if grant else None,
                copied_at=copy.copied_at if copy else None,
                synced_at=copy.synced_at if copy else None,
                contributed=(
                    counts.get(
                        repository_id,
                        ContributionCountsOut(
                            entities=0,
                            stat_groups_copied=0,
                            stat_groups_merged=0,
                            stat_definitions_copied=0,
                            stat_definitions_merged=0,
                            attachments=0,
                        ),
                    )
                    if copy
                    else None
                ),
                synced_release=_release_ref(synced.get(repository_id)),
                current_release=_release_ref(current.get(repository_id)),
            )
        )
    rows.sort(key=lambda r: (r.repository.name, str(r.repository.id)))
    return cast(Page[SubscriptionOut], paginate(rows, params))


@router.get("/repositories/{repository_id}/contributions")
async def list_repository_contributions(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
    params: ParamsDep,
    kind: Literal["entity", "stat_group", "stat_definition"] | None = None,
) -> Page[ContributionOut]:
    """The rows a copy of this repository contributed, still here or
    deleted since (ADR 0119). Reads only this tenant's own data, so it
    works without a grant. `409` if it was never copied."""
    if await session.get(RepositoryCopy, (tenant_id, repository_id)) is None:
        raise RepositoryNotCopiedError(detail=f"Repository {repository_id} wasn't copied here")
    rows: list[ContributionOut] = []
    sources: list[tuple[Any, Any, Any, Any]] = [
        ("entity", RepositoryCopyLinkEntity, RepositoryCopyLinkEntity.entity_id, Entity),
        (
            "stat_group",
            RepositoryCopyLinkStatGroup,
            RepositoryCopyLinkStatGroup.stat_group_id,
            StatGroup,
        ),
        (
            "stat_definition",
            RepositoryCopyLinkStatDefinition,
            RepositoryCopyLinkStatDefinition.stat_definition_id,
            StatDefinition,
        ),
    ]
    for row_kind, model, local, target in sources:
        if kind is not None and kind != row_kind:
            continue
        mode = getattr(model, "mode", None)
        stmt = (
            select(local, model.source_id, model.snapshot, target.name, *([mode] if mode else []))
            .outerjoin(target, (target.id == local) & (target.tenant_id == tenant_id))
            .where(model.tenant_id == tenant_id, model.source_tenant_id == repository_id)
        )
        for row in await session.execute(stmt):
            rows.append(
                ContributionOut(
                    kind=row_kind,
                    local_id=row[0],
                    source_id=row[1],
                    name=row[3] if row[3] is not None else str(row[2].get("name", "")),
                    mode=row[4] if mode else None,
                )
            )
    rows.sort(key=lambda r: (r.kind, r.name, str(r.source_id)))
    return cast(Page[ContributionOut], paginate(rows, params))


@router.delete("/repositories/{repository_id}", status_code=204)
async def remove_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Gives up a grant from the subscribing side, OWNER only. Nothing
    already copied is touched (RFC 0024 §6)."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    subscription = await session.get(RepositorySubscription, (repository_id, tenant_id))
    if subscription is None:
        raise SubscriptionNotFoundError(
            detail=f"Tenant {tenant_id} holds no grant for repository {repository_id}"
        )
    await session.delete(subscription)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.removed",
        target_type="tenant",
        target_id=repository_id,
    )
    await session.commit()


def _not_found(tenant_id: uuid.UUID, repository_id: uuid.UUID) -> RepositoryNotFoundError:
    return RepositoryNotFoundError(
        detail=f"No published repository {repository_id} is granted to tenant {tenant_id}"
    )


async def is_holder(session: AsyncSession, tenant_id: uuid.UUID, repository_id: uuid.UUID) -> bool:
    """Whether the library holds access to the repository, invited or from a copy: what makes it
    a holder and not a visitor of a public repository (ADR 0293)."""
    return (await session.get(RepositorySubscription, (repository_id, tenant_id))) is not None


NotFound = Callable[[], RepositoryNotFoundError]


async def releases_page(
    session: AsyncSession, repository_id: uuid.UUID, params: Params, not_found: NotFound
) -> Page[ReleaseOut]:
    """What a repository has released, newest first (ADR 0207), through the gated read: the same
    list its own members have, without who published it. `not_found` makes the error for a
    repository this reader may not read (ADR 0287: a library and a user with none ask the same)."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise not_found()
        stmt = (
            select(RepositoryRelease)
            .where(RepositoryRelease.tenant_id == repository_id)
            .order_by(RepositoryRelease.number.desc())
        )

        current = await current_release(session, repository_id)

        def _out(rows: Sequence[RepositoryRelease]) -> list[ReleaseOut]:
            return [_readable(r, current=bool(current and current.id == r.id)) for r in rows]

        page = cast(Page[ReleaseOut], await apaginate(session, stmt, params, transformer=_out))
    return page


@router.get("/repositories/{repository_id}/releases")
async def list_repository_releases(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
    params: ParamsDep,
) -> Page[ReleaseOut]:
    """What a granted, published repository has released, newest first (ADR 0207),
    through the gated read: the same list its own members have, without who
    published it."""
    return await releases_page(
        session, repository_id, params, lambda: _not_found(tenant_id, repository_id)
    )


async def entities_page(
    session: AsyncSession,
    repository_id: uuid.UUID,
    params: Params,
    q: str | None,
    not_found: NotFound,
    *,
    holder: bool,
) -> Page[RepositoryEntityOut]:
    """A repository's entities, before copying: each one's name, kinds, and prototypes, never its
    text (ADR 0118). `q` filters by name. A visitor of a public repository (one that holds no
    access to it) sees as many as the Owner's preview switch says (ADR 0293): none, the featured
    ones, or all."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise not_found()
        if await is_public(session, repository_id):
            rules = rules_for(await preview_of(session, repository_id), holder=holder)
            content = await read_content(session, repository_id)
            rows = entity_rows(content, q, public_only=True)
            if rules.names == "none":
                rows = []
            elif rules.names == "showcase":
                featured = set(await showcase_ids(session, repository_id))
                rows = [r for r in rows if r.id in featured]
            return cast(
                Page[RepositoryEntityOut],
                paginate(
                    [
                        RepositoryEntityOut(
                            id=e.id, name=e.name, kinds=e.kinds, prototype_ids=e.prototype_ids
                        )
                        for e in rows
                    ],
                    params,
                ),
            )
        stmt = select(Entity).where(
            Entity.tenant_id == repository_id,
            ~exists().where(
                EntityAudience.entity_id == Entity.id, EntityAudience.is_public.is_(False)
            ),
        )
        if q is not None:
            stmt = stmt.where(Entity.name.ilike(f"%{q}%"))
        stmt = stmt.order_by(Entity.name, Entity.id)

        async def _entities_out(entities: Sequence[Entity]) -> list[RepositoryEntityOut]:
            ids = [e.id for e in entities]
            kinds: dict[uuid.UUID, list[EntityKindName]] = {i: [] for i in ids}
            kind_tables: list[
                tuple[EntityKindName, type[Item | ItemInstance | Being | Character | Fact]]
            ] = [
                ("item", Item),
                ("item_instance", ItemInstance),
                ("being", Being),
                ("character", Character),
                ("fact", Fact),
            ]
            for name, model in kind_tables:
                for entity_id in await session.scalars(
                    select(model.entity_id).where(
                        model.entity_id.in_(ids), model.tenant_id == repository_id
                    )
                ):
                    kinds[entity_id].append(name)
            prototypes: dict[uuid.UUID, list[uuid.UUID]] = {i: [] for i in ids}
            for entity_id, prototype_id in await session.execute(
                select(EntityPrototype.entity_id, EntityPrototype.prototype_id)
                .where(
                    EntityPrototype.entity_id.in_(ids),
                    EntityPrototype.tenant_id == repository_id,
                    ~exists().where(
                        EntityAudience.entity_id == EntityPrototype.prototype_id,
                        EntityAudience.is_public.is_(False),
                    ),
                )
                .order_by(EntityPrototype.position, EntityPrototype.prototype_id)
            ):
                prototypes[entity_id].append(prototype_id)
            return [
                RepositoryEntityOut(
                    id=e.id, name=e.name, kinds=kinds[e.id], prototype_ids=prototypes[e.id]
                )
                for e in entities
            ]

        page = cast(
            Page[RepositoryEntityOut],
            await apaginate(session, stmt, params, transformer=_entities_out),
        )
    return page


@router.get("/repositories/{repository_id}/entities")
async def browse_repository_entities(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
    params: ParamsDep,
    q: str | None = None,
) -> Page[RepositoryEntityOut]:
    """A granted, published repository's entities, before copying: each
    one's name, kinds, and prototypes, never its text (ADR 0118). `q`
    filters by name."""
    return await entities_page(
        session,
        repository_id,
        params,
        q,
        lambda: _not_found(tenant_id, repository_id),
        holder=await is_holder(session, tenant_id, repository_id),
    )


async def stat_groups_of(
    session: AsyncSession, repository_id: uuid.UUID, not_found: NotFound, *, holder: bool
) -> list[RepositoryStatGroupOut]:
    """A repository's stat groups and their definitions, before copying (ADR 0118). A visitor of a
    public repository sees them only when the Owner's preview switch is `public` (ADR 0293)."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise not_found()
        if await is_public(session, repository_id):
            rules = rules_for(await preview_of(session, repository_id), holder=holder)
            if rules.names != "all":
                return []
            content = await read_content(session, repository_id)
            return [
                RepositoryStatGroupOut(
                    id=g.id,
                    name=g.name,
                    priority=g.priority,
                    mandatory=g.mandatory,
                    definitions=[
                        RepositoryStatDefinitionOut(
                            id=d.id, name=d.name, value_type=d.value_type, enum_values=d.enum_values
                        )
                        for d in g.definitions
                    ],
                )
                for g in stat_group_rows(content)
            ]
        groups = (
            await session.scalars(
                select(StatGroup)
                .where(StatGroup.tenant_id == repository_id)
                .order_by(StatGroup.priority.desc(), StatGroup.name)
            )
        ).all()
        definitions = (
            await session.scalars(
                select(StatDefinition)
                .where(StatDefinition.tenant_id == repository_id)
                .options(selectinload(StatDefinition.enum_values))
                .order_by(StatDefinition.name)
            )
        ).all()
    by_group: dict[uuid.UUID, list[RepositoryStatDefinitionOut]] = {g.id: [] for g in groups}
    for definition in definitions:
        by_group[definition.stat_group_id].append(
            RepositoryStatDefinitionOut(
                id=definition.id,
                name=definition.name,
                value_type=definition.value_type,
                enum_values=[v.value for v in definition.enum_values],
            )
        )
    return [
        RepositoryStatGroupOut(
            id=g.id,
            name=g.name,
            priority=g.priority,
            mandatory=g.mandatory,
            definitions=by_group[g.id],
        )
        for g in groups
    ]


@router.get("/repositories/{repository_id}/stat-groups")
async def browse_repository_stat_groups(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
) -> list[RepositoryStatGroupOut]:
    """A granted, published repository's stat groups and their definitions,
    before copying (ADR 0118)."""
    return await stat_groups_of(
        session,
        repository_id,
        lambda: _not_found(tenant_id, repository_id),
        holder=await is_holder(session, tenant_id, repository_id),
    )


@router.get("/repositories/{repository_id}/dependencies")
async def list_repository_dependencies(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
) -> list[RepositoryDependencyOut]:
    """The repositories a granted, published repository is built on, as this
    library stands with each: its id, name and slug, whether the library is
    invited to it, has copied it, and whether it is published (ADR 0198).
    Dependencies first, as `copy-plan` orders them. Plans no copy and returns
    no content: a library that is not invited to a dependency learns whom to
    ask, and nothing more of it.
    """
    steps = await dependencies_of(session, tenant_id=tenant_id, repository_id=repository_id)
    slugs = {
        id_: slug
        for id_, slug in await session.execute(
            select(Tenant.id, Tenant.slug).where(Tenant.id.in_([s.repository_id for s in steps]))
        )
    }
    return [
        RepositoryDependencyOut(
            id=step.repository_id,
            name=step.name,
            slug=slugs[step.repository_id],
            invited=step.granted,
            copied=step.already_copied,
            published=step.published,
            public=step.public,
        )
        for step in steps
        # One whose tenant is gone has nothing to ask, invite or copy.
        if step.repository_id in slugs
    ]


# --- Copying (ADR 0119, 0120) ---------------------------------------------------


def _step_out(step: Step) -> CopyStepOut:
    return CopyStepOut(
        repository_id=step.repository_id,
        name=step.name,
        granted=step.granted,
        published=step.published,
        public=step.public,
        already_copied=step.already_copied,
        entities=step.entities,
        stat_groups=step.stat_groups,
        stat_definitions=step.stat_definitions,
        information=step.information,
        attachments=step.attachments,
        dropped=[
            DroppedOut(kind=d.kind, source_id=d.source_id, reason=d.reason) for d in step.dropped
        ],
    )


def _plan_out(plan: Plan) -> CopyPlanOut:
    return CopyPlanOut(
        steps=[_step_out(s) for s in plan.steps],
        collisions=[
            CollisionOut(
                repository_id=c.repository_id,
                kind=c.kind,
                source_id=c.source_id,
                name=c.name,
                local_id=c.local_id,
                choices=c.choices,
            )
            for c in plan.collisions
        ],
    )


@router.get("/repositories/{repository_id}/copy-plan")
async def plan_repository_copy(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> CopyPlanOut:
    """What copying a granted, published repository would do, writing
    nothing (ADR 0119): its manifest - dependencies first, each with
    whether it's granted, published, and already copied here (ADR 0120) -
    how much each step brings in, and every collision that needs a choice.
    """
    plan = await plan_copy(
        session, tenant_id=tenant_id, repository_id=repository_id, user_id=user.id, resolutions=[]
    )
    return _plan_out(plan)


@router.post("/repositories/{repository_id}/copy", status_code=201)
async def copy_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    body: CopyRequest | None = None,
) -> CopyOut:
    """Copies a repository, and whatever of its dependencies this tenant
    hasn't copied yet, in one transaction (ADR 0119, 0120). Refused with
    `409` while a collision has no choice, a step lacks a grant or isn't
    published, or it's already been copied - unless `again` says to copy
    it afresh. `dry_run` does all of it, checks included, and rolls back,
    answering `200`. The copied rows are this tenant's own from then on;
    the tenant-admin tier, like authoring stat definitions.
    """
    dry_run = bool(body and body.dry_run)
    await _require_admin_unless_dry_run(session, tenant_id=tenant_id, user=user, dry_run=dry_run)
    again = body.again if body else None
    previous = None
    if again and await session.get(RepositoryCopy, (tenant_id, repository_id)) is not None:
        previous = await forget_copy(
            session,
            tenant_id=tenant_id,
            repository_id=repository_id,
            purge=again == "purge",
            user_id=user.id,
        )
    resolutions = [
        Resolution(kind=r.kind, source_id=r.source_id, action=r.action, name=r.name)
        for r in (body.resolutions if body and body.resolutions else [])
    ]
    plan = await plan_copy(
        session,
        tenant_id=tenant_id,
        repository_id=repository_id,
        user_id=user.id,
        resolutions=resolutions,
    )
    await apply_plan(session, plan, user_id=user.id)
    # A public repository is not granted to the library that copies it, so the copy grants it, and
    # every public repository it is built on, to the library, as its own (ADR 0287).
    await subscribe_to_public(
        session,
        tenant_id=tenant_id,
        repository_ids=[s.repository_id for s in plan.to_copy if s.public and not s.granted],
        user_id=user.id,
    )
    if dry_run:
        await session.rollback()
        response.status_code = 200
    else:
        await session.commit()
    return CopyOut(
        steps=[_step_out(s) for s in plan.to_copy],
        dry_run=dry_run,
        previous=(
            PreviousCopyOut(
                mode=previous.mode,
                entities=previous.entities,
                stat_groups=previous.stat_groups,
                stat_definitions=previous.stat_definitions,
                also_removed=previous.also_removed,
            )
            if previous
            else None
        ),
    )


# --- Updates (ADR 0121) ---------------------------------------------------------


def _collision_out(c: Any) -> CollisionOut | None:
    if c is None:
        return None
    return CollisionOut(
        repository_id=c.repository_id,
        kind=c.kind,
        source_id=c.source_id,
        name=c.name,
        local_id=c.local_id,
        choices=c.choices,
    )


def _notes_out(notes: Sequence[BreakingNote]) -> list[BreakingNoteOut]:
    return [
        BreakingNoteOut(
            reason=n.reason,
            detail=n.detail,
            release=ReleaseRefOut(id=n.release.id, number=n.release.number, label=n.release.label),
        )
        for n in notes
    ]


def _attachment_ref_out(a: AttachmentRef) -> AttachmentRefOut:
    return AttachmentRefOut(
        child_source_id=a.child_source_id,
        child_local_id=a.child_local_id,
        child_name=a.child_name,
        parent_source_id=a.parent_source_id,
        parent_local_id=a.parent_local_id,
        parent_name=a.parent_name,
    )


def _row_ref_out(r: RowRef) -> RowRefOut:
    return RowRefOut(
        kind=r.kind,
        source_id=r.source_id,
        local_id=r.local_id,
        name=r.name,
        state=r.state,
        breaking=_notes_out(r.breaking),
    )


def _attachment_change_out(a: AttachmentRef) -> AttachmentChangeOut:
    return AttachmentChangeOut(
        **_attachment_ref_out(a).model_dump(),
        state=a.state,
        breaking=_notes_out(a.breaking),
        warnings=_notes_out(a.warnings),
    )


@router.get("/repositories/{repository_id}/updates")
async def list_repository_updates(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
) -> UpdatesOut:
    """What a copied repository changed since this tenant copied or last
    synced it, row by row, beside this tenant's own copy (ADR 0121), and
    the parents it added to or took off its copies (ADR 0172). Reads the
    repository through the gated read, so it must still be granted and
    published."""
    updates = await compute_updates(session, tenant_id=tenant_id, repository_id=repository_id)
    return UpdatesOut(
        repository_id=repository_id,
        changed=[
            RowChangeOut(
                kind=row.kind,
                source_id=row.source_id,
                local_id=row.local_id,
                name=row.name,
                fields=[
                    FieldChangeOut(
                        field=f.field,
                        label=f.label,
                        state=f.state,
                        base=f.base,
                        upstream=f.upstream,
                        local=f.local,
                        added=f.added,
                        removed=f.removed,
                    )
                    for f in row.fields
                ],
                state=row.state,
                breaking=_notes_out(row.breaking),
            )
            for row in updates.changed
        ],
        removed=[_row_ref_out(r) for r in updates.removed],
        deleted_locally=[_row_ref_out(r) for r in updates.deleted_locally],
        added=[
            AddedOut(
                kind=a.kind,
                source_id=a.source_id,
                name=a.name,
                collision=_collision_out(a.collision),
                state=a.state,
                breaking=_notes_out(a.breaking),
            )
            for a in updates.added
        ],
        attachments_added=[
            AttachmentAddedOut(
                **_attachment_change_out(a).model_dump(), applicable=a.applicable, reason=a.reason
            )
            for a in updates.attachments_added
        ],
        attachments_removed=[_attachment_change_out(a) for a in updates.attachments_removed],
        attachments_deleted_locally=[
            _attachment_change_out(a) for a in updates.attachments_deleted_locally
        ],
        names=updates.names,
        release=(_readable(updates.release, current=True) if updates.release else None),
    )


@router.post("/repositories/{repository_id}/updates")
async def apply_repository_updates(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    body: ApplyUpdatesRequest,
    session: SessionDep,
    user: CurrentUser,
) -> ApplyUpdatesOut:
    """Applies the listed updates, row by row, in one transaction (ADR
    0121). Anything not listed stays as it is. `409` while a conflict is
    named in neither `keep_local` nor `take_upstream`. The `attachments`
    (ADR 0172) are applied after the actions, so one can point at a row an
    action adds; `422` for one that has nothing to add or detach.
    `dry_run` applies everything and rolls it back."""
    await _require_admin_unless_dry_run(
        session, tenant_id=tenant_id, user=user, dry_run=bool(body.dry_run)
    )
    actions = [
        UpdateAction(
            kind=a.kind,
            source_id=a.source_id,
            action=a.action,
            keep_local=a.keep_local or [],
            take_upstream=a.take_upstream or [],
            resolution=(
                Resolution(
                    kind=COLLISION_KIND[a.kind],
                    source_id=a.source_id,
                    action=a.resolution.action,
                    name=a.resolution.name,
                )
                if a.resolution
                else None
            ),
            confirm=bool(a.confirm),
        )
        for a in body.actions
    ]
    result = await apply_updates(
        session,
        tenant_id=tenant_id,
        repository_id=repository_id,
        user_id=user.id,
        actions=actions,
        attachments=[
            AttachmentAction(
                child_source_id=a.child_source_id,
                parent_source_id=a.parent_source_id,
                action=a.action.value,
            )
            for a in body.attachments or []
        ],
    )
    if body.dry_run:
        await session.rollback()
    else:
        await session.commit()
    return ApplyUpdatesOut(
        dry_run=bool(body.dry_run),
        applied=result.applied,
        added=result.added,
        detached=result.detached,
        attachments_added=result.attachments_added,
        attachments_detached=result.attachments_detached,
        not_applied=[
            NotAppliedOut(
                kind=n.kind,
                source_id=n.source_id,
                field=n.field,
                reason=n.reason,
                name=n.name,
                label=n.label,
            )
            for n in result.not_applied
        ],
    )
