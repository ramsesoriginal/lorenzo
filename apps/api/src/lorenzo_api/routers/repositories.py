"""Repositories - RFC 0024, ADR 0118 onward.

A repository is a tenant of kind `repository`: a reusable setting other
tenants are granted access to and copy from. This router holds what's
repository-specific; authoring a repository's content goes through the
same routes as any other tenant's.

Two sides, both under /tenants/{tenant_id}: the repository's own
(`/published`, `/subscribers`), and a granted tenant's (`/repositories`).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import is_tenant_owner
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    InvalidSubscriberError,
    NotARepositoryError,
    RepositoryManagementForbiddenError,
    RepositoryNotFoundError,
    SubscriptionNotFoundError,
    TenantNotFoundError,
)
from lorenzo_api.models import (
    Being,
    Character,
    Entity,
    EntityPrototype,
    Item,
    ItemInstance,
    RepositoryCopy,
    RepositorySubscription,
    StatDefinition,
    StatGroup,
    Tenant,
    TenantKind,
)
from lorenzo_api.notifications import create_tenant_members_notification
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_copying import Plan, Resolution, Step, apply_plan, plan_copy
from lorenzo_api.schemas.repositories import (
    CollisionOut,
    CopyOut,
    CopyPlanOut,
    CopyRequest,
    CopyStepOut,
    DroppedOut,
    EntityKindName,
    RepositoryEntityOut,
    RepositoryStatDefinitionOut,
    RepositoryStatGroupOut,
    RepositorySummaryOut,
    SubscriberOut,
    SubscriptionOut,
)
from lorenzo_api.schemas.tenants import TenantOut

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["repositories"])


async def _require_owner(session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser) -> None:
    if not await is_tenant_owner(session, tenant_id=tenant_id, user_id=user.id):
        raise RepositoryManagementForbiddenError(
            detail=f"Only an owner of tenant {tenant_id} can do this"
        )


async def _require_repository(session: SessionDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = await session.get_one(Tenant, tenant_id)
    if tenant.kind is not TenantKind.REPOSITORY:
        raise NotARepositoryError(detail=f"Tenant {tenant_id} is for play, not a repository")
    return tenant


async def _notify_members_of(
    session: SessionDep,
    *,
    recipient_tenant_ids: Sequence[uuid.UUID],
    current_tenant_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    user: CurrentUser,
) -> None:
    """Tells each tenant's members, reading each one's Membership under its
    own RLS context, then puts the current tenant's context back. Flushes
    first: anything still pending belongs to the current tenant, and would
    fail RLS if autoflush wrote it under another tenant's context.
    """
    await session.flush()
    for recipient in recipient_tenant_ids:
        await set_tenant_rls_context(session, recipient)
        await create_tenant_members_notification(
            session, tenant_id=recipient, type=type, title=title, body=body, created_by=user.id
        )
    await set_tenant_rls_context(session, current_tenant_id)


# --- The repository's own side ----------------------------------------------


@router.put("/published")
async def publish_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
) -> TenantOut:
    """Publishes a repository, or announces an update to one already
    published: either way `published_at` becomes now, and every granted
    tenant's members are told (ADR 0118). Until the first publish, no
    subscriber can see anything of it.
    """
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    was_published = tenant.published_at is not None
    tenant.published_at = datetime.now(UTC)
    tenant.updated_by = user.id
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.published",
        target_type="tenant",
        target_id=tenant_id,
    )
    subscribers = (
        await session.scalars(
            select(RepositorySubscription.subscriber_tenant_id).where(
                RepositorySubscription.repository_tenant_id == tenant_id
            )
        )
    ).all()
    await _notify_members_of(
        session,
        recipient_tenant_ids=subscribers,
        current_tenant_id=tenant_id,
        type="repository_updated" if was_published else "repository_published",
        title=(
            f"{tenant.name} has published an update"
            if was_published
            else f"{tenant.name} is published"
        ),
        body=(
            "Check its updates to see what changed."
            if was_published
            else "You can browse it and copy it into your tenant."
        ),
        user=user,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return TenantOut.model_validate(await session.get_one(Tenant, tenant_id))


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


def _subscriber_out(subscription: RepositorySubscription, tenant: Tenant) -> SubscriberOut:
    return SubscriberOut(
        tenant_id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        granted_at=subscription.created_at,
        granted_by=subscription.created_by,
    )


@router.get("/subscribers")
async def list_subscribers(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[SubscriberOut]:
    """The tenants this repository is granted to, for any of its members."""
    await _require_repository(session, tenant_id)
    stmt = (
        select(RepositorySubscription, Tenant)
        .join(Tenant, Tenant.id == RepositorySubscription.subscriber_tenant_id)
        .where(RepositorySubscription.repository_tenant_id == tenant_id)
        .order_by(Tenant.name, Tenant.id)
    )

    def _rows_out(rows: Sequence[tuple[RepositorySubscription, Tenant]]) -> list[SubscriberOut]:
        return [_subscriber_out(subscription, tenant) for subscription, tenant in rows]

    return cast(
        Page[SubscriberOut],
        await apaginate(session, stmt, params, transformer=_rows_out, unique=False),
    )


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
    Its members are told.
    """
    await _require_owner(session, tenant_id=tenant_id, user=user)
    repository = await _require_repository(session, tenant_id)
    if subscriber_tenant_id == tenant_id:
        raise InvalidSubscriberError(detail="A repository can't be granted to itself")
    subscriber = await session.get(Tenant, subscriber_tenant_id)
    if subscriber is None:
        raise TenantNotFoundError(detail=f"No tenant with id {subscriber_tenant_id}")
    subscription = await session.get(RepositorySubscription, (tenant_id, subscriber_tenant_id))
    if subscription is not None:
        return _subscriber_out(subscription, subscriber)

    session.add(
        RepositorySubscription(
            repository_tenant_id=tenant_id,
            subscriber_tenant_id=subscriber_tenant_id,
            created_by=user.id,
        )
    )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.granted",
        target_type="tenant",
        target_id=subscriber_tenant_id,
    )
    await _notify_members_of(
        session,
        recipient_tenant_ids=[subscriber_tenant_id],
        current_tenant_id=tenant_id,
        type="repository_granted",
        title=f"{repository.name} is available to {subscriber.name}",
        body=(
            "You can browse it and copy it into your tenant."
            if repository.published_at is not None
            else "It isn't published yet. You'll be told when it is."
        ),
        user=user,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.status_code = 201
    return _subscriber_out(
        await session.get_one(RepositorySubscription, (tenant_id, subscriber_tenant_id)),
        subscriber,
    )


@router.delete("/subscribers/{subscriber_tenant_id}", status_code=204)
async def revoke_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    subscriber_tenant_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Revokes a grant. What the tenant already copied stays theirs (RFC
    0024 §6)."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    await _require_repository(session, tenant_id)
    subscription = await session.get(RepositorySubscription, (tenant_id, subscriber_tenant_id))
    if subscription is None:
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
    await session.commit()


# --- A granted tenant's side --------------------------------------------------


@router.get("/repositories")
async def list_repositories(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[SubscriptionOut]:
    """The repositories granted to this tenant, published or not, for any
    of its members."""
    stmt = (
        select(RepositorySubscription, Tenant, RepositoryCopy)
        .join(Tenant, Tenant.id == RepositorySubscription.repository_tenant_id)
        .outerjoin(
            RepositoryCopy,
            (RepositoryCopy.tenant_id == tenant_id)
            & (RepositoryCopy.repository_tenant_id == Tenant.id),
        )
        .where(RepositorySubscription.subscriber_tenant_id == tenant_id)
        .order_by(Tenant.name, Tenant.id)
    )

    def _rows_out(
        rows: Sequence[tuple[RepositorySubscription, Tenant, RepositoryCopy | None]],
    ) -> list[SubscriptionOut]:
        return [
            SubscriptionOut(
                repository=RepositorySummaryOut(
                    id=repository.id,
                    name=repository.name,
                    slug=repository.slug,
                    description=repository.description,
                    published_at=repository.published_at,
                ),
                granted_at=subscription.created_at,
                copied_at=copy.copied_at if copy else None,
                synced_at=copy.synced_at if copy else None,
            )
            for subscription, repository, copy in rows
        ]

    return cast(
        Page[SubscriptionOut],
        await apaginate(session, stmt, params, transformer=_rows_out, unique=False),
    )


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
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise _not_found(tenant_id, repository_id)
        stmt = select(Entity).where(Entity.tenant_id == repository_id)
        if q is not None:
            stmt = stmt.where(Entity.name.ilike(f"%{q}%"))
        stmt = stmt.order_by(Entity.name, Entity.id)

        async def _entities_out(entities: Sequence[Entity]) -> list[RepositoryEntityOut]:
            ids = [e.id for e in entities]
            kinds: dict[uuid.UUID, list[EntityKindName]] = {i: [] for i in ids}
            kind_tables: list[
                tuple[EntityKindName, type[Item | ItemInstance | Being | Character]]
            ] = [
                ("item", Item),
                ("item_instance", ItemInstance),
                ("being", Being),
                ("character", Character),
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
                )
                .order_by(EntityPrototype.prototype_id)
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


@router.get("/repositories/{repository_id}/stat-groups")
async def browse_repository_stat_groups(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
) -> list[RepositoryStatGroupOut]:
    """A granted, published repository's stat groups and their definitions,
    before copying (ADR 0118)."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise _not_found(tenant_id, repository_id)
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


# --- Copying (ADR 0119, 0120) ---------------------------------------------------


def _step_out(step: Step) -> CopyStepOut:
    return CopyStepOut(
        repository_id=step.repository_id,
        name=step.name,
        granted=step.granted,
        published=step.published,
        already_copied=step.already_copied,
        entities=step.entities,
        stat_groups=step.stat_groups,
        stat_definitions=step.stat_definitions,
        information=step.information,
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
    session: SessionDep,
    user: CurrentUser,
    body: CopyRequest | None = None,
) -> CopyOut:
    """Copies a repository, and whatever of its dependencies this tenant
    hasn't copied yet, in one transaction (ADR 0119, 0120). Refused with
    `409` while a collision has no choice, a step lacks a grant or isn't
    published, or it's already been copied. The copied rows are this
    tenant's own from then on; the tenant-admin tier, like authoring stat
    definitions.
    """
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
    await session.commit()
    return CopyOut(steps=[_step_out(s) for s in plan.to_copy])
