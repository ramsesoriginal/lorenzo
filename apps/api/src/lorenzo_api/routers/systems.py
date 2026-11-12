"""The game systems of a library - ADR 0448, RFC 0052.

A system is a vocabulary's own: any member who may author the stat vocabulary may make one and
edit it, and deleting one is an administrator's, as deleting from the vocabulary is (ADR 0219).
Reading is for any participant of the tenant, since a sheet needs to say which system a stat
belongs to.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import func, select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_admin_context,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    InvalidSystemError,
    SystemInUseError,
    SystemNotFoundError,
    SystemSlugInUseError,
    SystemSlugTakenError,
)
from lorenzo_api.models import Entity, StatGroup, System
from lorenzo_api.routers.stats import _vocabulary_gate
from lorenzo_api.schemas.systems import SystemCreate, SystemOut, SystemUpdate

router = APIRouter(
    prefix="/tenants/{tenant_id}/systems",
    tags=["systems"],
    dependencies=[Depends(_vocabulary_gate)],
)


async def _get_system_or_404(
    session: SessionDep, tenant_id: uuid.UUID, system_id: uuid.UUID
) -> System:
    system = (
        await session.execute(
            select(System).where(System.id == system_id, System.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if system is None:
        raise SystemNotFoundError(detail=f"No system with id {system_id} in tenant {tenant_id}")
    return system


async def _check_root(session: SessionDep, tenant_id: uuid.UUID, root_entry_id: uuid.UUID) -> None:
    found = await session.scalar(
        select(Entity.id).where(Entity.id == root_entry_id, Entity.tenant_id == tenant_id)
    )
    if found is None:
        raise InvalidSystemError(detail=f"{root_entry_id} is not an entry of tenant {tenant_id}")


async def _check_slug_free(
    session: SessionDep, tenant_id: uuid.UUID, slug: str, *, own_id: uuid.UUID | None = None
) -> None:
    taken = await session.scalar(
        select(System.id).where(
            System.tenant_id == tenant_id,
            System.slug == slug,
            *([System.id != own_id] if own_id is not None else []),
        )
    )
    if taken is not None:
        raise SystemSlugTakenError(
            detail=f"Another system in tenant {tenant_id} already has the slug {slug!r}"
        )


async def _groups_of(session: SessionDep, tenant_id: uuid.UUID, system_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(StatGroup)
            .where(StatGroup.tenant_id == tenant_id, StatGroup.system_id == system_id)
        )
        or 0
    )


@router.post("", status_code=201)
async def create_system(
    tenant_id: uuid.UUID,
    body: SystemCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SystemOut:
    """Makes a game system (409 for a slug the library has, 422 for a root entry that is not
    one of its entries)."""
    await _check_slug_free(session, tenant_id, body.slug)
    if body.root_entry_id is not None:
        await _check_root(session, tenant_id, body.root_entry_id)
    system = System(
        tenant_id=tenant_id, slug=body.slug, name=body.name, root_entry_id=body.root_entry_id
    )
    session.add(system)
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="system.created",
        target_type="system",
        target_id=system.id,
        detail=f"slug={body.slug}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_system", tenant_id=tenant_id, system_id=system.id)
    )
    return SystemOut.model_validate(await _get_system_or_404(session, tenant_id, system.id))


@router.get("")
async def list_systems(
    tenant_id: uuid.UUID, session: SessionDep, params: ParamsDep
) -> Page[SystemOut]:
    """The library's systems, by slug (ADR 0085's page)."""
    page: Page[SystemOut] = await apaginate(
        session,
        select(System).where(System.tenant_id == tenant_id).order_by(System.slug, System.id),
        params,
        transformer=lambda rows: [SystemOut.model_validate(row) for row in rows],
    )
    return page


@router.get("/{system_id}")
async def get_system(tenant_id: uuid.UUID, system_id: uuid.UUID, session: SessionDep) -> SystemOut:
    return SystemOut.model_validate(await _get_system_or_404(session, tenant_id, system_id))


@router.patch("/{system_id}")
async def update_system(
    tenant_id: uuid.UUID, system_id: uuid.UUID, body: SystemUpdate, session: SessionDep
) -> SystemOut:
    """Edits a system's name, root entry (or clears it) or slug. The slug cannot change while a
    stat group belongs to the system, since the names of its stats start with it (409); a slug
    another system has is a 409 too. Not logged: naming, not structure (ADR 0084)."""
    system = await _get_system_or_404(session, tenant_id, system_id)
    changes = body.model_dump(exclude_unset=True)
    if "slug" in changes and changes["slug"] != system.slug:
        if await _groups_of(session, tenant_id, system_id):
            raise SystemSlugInUseError(
                detail=f"The slug of {system.slug!r} cannot change while a stat group belongs to "
                "it: the names of its stats start with it"
            )
        await _check_slug_free(session, tenant_id, changes["slug"], own_id=system_id)
    if changes.get("root_entry_id") is not None:
        await _check_root(session, tenant_id, changes["root_entry_id"])
    for field, value in changes.items():
        setattr(system, field, value)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return SystemOut.model_validate(await _get_system_or_404(session, tenant_id, system_id))


@router.delete("/{system_id}", status_code=204, dependencies=[Depends(get_tenant_admin_context)])
async def delete_system(
    tenant_id: uuid.UUID, system_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    """Deletes a system nothing uses (409 while a stat group belongs to it)."""
    system = await _get_system_or_404(session, tenant_id, system_id)
    if await _groups_of(session, tenant_id, system_id):
        raise SystemInUseError(detail=f"A stat group still belongs to system {system.slug!r}")
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="system.deleted",
        target_type="system",
        target_id=system_id,
        detail=f"slug={system.slug}",
    )
    await session.delete(system)
    await session.commit()
