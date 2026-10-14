"""Looking at a repository before copying it, and the Owner's showcase - ADR 0293, RFC 0038 §5.

What a reader may look at of the entries is the Owner's `preview` switch and whether the reader is a
holder (a library with access) or a visitor (anyone else signed in): `repository_preview.rules_for`.
Two forms of each read, as everywhere in ADR 0118 and 0287: `/repositories/{id}/...` for a user
with no library (always a visitor), and `/tenants/{tenant_id}/repositories/{id}/...` for a library
(a holder if it holds access to the repository, else a visitor).

The Owner's side, `GET`/`PUT /tenants/{id}/showcase`, says which entries are featured.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    PublicReader,
    SessionDep,
    get_tenant_context,
)
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    RepositoryNotFoundError,
    ShowcaseInvalidError,
)
from lorenzo_api.models import Entity, RepositoryShowcase
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_preview import (
    SHOWCASE_MAX,
    Rules,
    entity_out,
    picture_of,
    preview_of,
    read_content,
    rules_for,
    showcase_ids,
)
from lorenzo_api.routers.repositories import _require_owner, _require_repository, is_holder
from lorenzo_api.schemas.repository_preview import (
    PreviewEntityOut,
    PreviewOut,
    ShowcaseEntryOut,
    ShowcaseOut,
    ShowcaseUpdate,
)

visitor_router = APIRouter(prefix="/repositories", tags=["repositories"])
library_router = APIRouter(prefix="/tenants/{tenant_id}/repositories", tags=["repositories"])
owner_router = APIRouter(prefix="/tenants/{tenant_id}", tags=["repositories"])

NotFound = Callable[[], RepositoryNotFoundError]


def _no_entry(entity_id: uuid.UUID) -> EntityNotFoundError:
    return EntityNotFoundError(detail=f"There is no entry {entity_id} to look at")


async def _may_look(
    session: AsyncSession, repository_id: uuid.UUID, entity_id: uuid.UUID, rules: Rules
) -> tuple[bool, bool]:
    """Whether the entry may be looked at at all, and whether its text may be, for these rules:
    its name is visible to all, or if it is featured; its text to all, or if it is featured and
    the rules say the featured ones. Inside the gated read."""
    featured = (
        set(await showcase_ids(session, repository_id))
        if "showcase"
        in (
            rules.names,
            rules.text,
        )
        else set()
    )
    named = rules.names == "all" or (rules.names == "showcase" and entity_id in featured)
    text = rules.text == "all" or (rules.text == "showcase" and entity_id in featured)
    return named or text, text


async def preview_view(
    session: AsyncSession, repository_id: uuid.UUID, *, holder: bool, not_found: NotFound
) -> PreviewOut:
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise not_found()
        switch = await preview_of(session, repository_id)
        rules = rules_for(switch, holder=holder)
        entries: list[PreviewEntityOut] = []
        if rules.text != "none":
            content = await read_content(session, repository_id)
            for entity_id in await showcase_ids(session, repository_id):
                shown = entity_out(content, entity_id, text=True, featured=True)
                if shown is not None:
                    entries.append(shown)
    return PreviewOut(preview=switch, entries=entries)


async def entry_view(
    session: AsyncSession,
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    *,
    holder: bool,
    not_found: NotFound,
) -> PreviewEntityOut:
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise not_found()
        rules = rules_for(await preview_of(session, repository_id), holder=holder)
        may, text = await _may_look(session, repository_id, entity_id, rules)
        if not may:
            raise _no_entry(entity_id)
        content = await read_content(session, repository_id)
        featured = entity_id in set(await showcase_ids(session, repository_id))
        shown = entity_out(content, entity_id, text=text, featured=featured)
    if shown is None:
        raise _no_entry(entity_id)
    return shown


async def picture_view(
    session: AsyncSession,
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload_id: uuid.UUID,
    *,
    holder: bool,
    not_found: NotFound,
) -> Response:
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise not_found()
        rules = rules_for(await preview_of(session, repository_id), holder=holder)
        may, text = await _may_look(session, repository_id, entity_id, rules)
        if not (may and text):
            raise _no_entry(entity_id)
        picture = picture_of(await read_content(session, repository_id), entity_id, payload_id)
    if picture is None:
        raise _no_entry(entity_id)
    data, file_type = picture
    return Response(content=data, media_type=file_type)


# --- A user with no library: a visitor -----------------------------------------------------------


def _public_not_found(repository_id: uuid.UUID) -> RepositoryNotFoundError:
    return RepositoryNotFoundError(detail=f"No public repository {repository_id}")


@visitor_router.get("/{repository_id}/preview")
async def get_public_preview(
    repository_id: uuid.UUID, session: SessionDep, user: PublicReader
) -> PreviewOut:
    """The entries the Owner of a public repository features, with their text, as far as its
    preview switch lets a visitor look: none while it is `off`."""
    return await preview_view(
        session, repository_id, holder=False, not_found=lambda: _public_not_found(repository_id)
    )


@visitor_router.get("/{repository_id}/entities/{entity_id}")
async def get_public_entry(
    repository_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: PublicReader
) -> PreviewEntityOut:
    """One entry of a public repository as a visitor may look at it: `404` for one the preview
    switch does not show them, whatever it is, the same as for one that does not exist."""
    return await entry_view(
        session,
        repository_id,
        entity_id,
        holder=False,
        not_found=lambda: _public_not_found(repository_id),
    )


@visitor_router.get("/{repository_id}/entities/{entity_id}/pictures/{payload_id}")
async def get_public_entry_picture(
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload_id: uuid.UUID,
    session: SessionDep,
    user: PublicReader,
) -> Response:
    """A picture on a row of Everyone's text of an entry a visitor may read the text of."""
    return await picture_view(
        session,
        repository_id,
        entity_id,
        payload_id,
        holder=False,
        not_found=lambda: _public_not_found(repository_id),
    )


# --- A library: a holder if it holds access, else a visitor ---------------------------------------


def _library_not_found(tenant_id: uuid.UUID, repository_id: uuid.UUID) -> RepositoryNotFoundError:
    return RepositoryNotFoundError(
        detail=f"No published repository {repository_id} is granted to tenant {tenant_id}"
    )


@library_router.get("/{repository_id}/preview")
async def get_preview(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
) -> PreviewOut:
    """The featured entries with their text, as far as the Owner's preview switch lets this
    library look: a holder at `showcase` and `public`, a visitor as `/repositories/{id}/preview`."""
    return await preview_view(
        session,
        repository_id,
        holder=await is_holder(session, tenant_id, repository_id),
        not_found=lambda: _library_not_found(tenant_id, repository_id),
    )


@library_router.get("/{repository_id}/entities/{entity_id}")
async def get_entry(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
) -> PreviewEntityOut:
    """One entry as this library may look at it: a holder sees its name, kinds and parents and,
    when the preview switch says, its Everyone's text, pictures and stat values."""
    return await entry_view(
        session,
        repository_id,
        entity_id,
        holder=await is_holder(session, tenant_id, repository_id),
        not_found=lambda: _library_not_found(tenant_id, repository_id),
    )


@library_router.get("/{repository_id}/entities/{entity_id}/pictures/{payload_id}")
async def get_entry_picture(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    payload_id: uuid.UUID,
    session: SessionDep,
) -> Response:
    """A picture on a row of Everyone's text of an entry this library may read the text of."""
    return await picture_view(
        session,
        repository_id,
        entity_id,
        payload_id,
        holder=await is_holder(session, tenant_id, repository_id),
        not_found=lambda: _library_not_found(tenant_id, repository_id),
    )


# --- The Owner's showcase ------------------------------------------------------------------------


async def _showcase(session: AsyncSession, repository_id: uuid.UUID) -> ShowcaseOut:
    rows = await session.execute(
        select(Entity.id, Entity.name)
        .join(
            RepositoryShowcase,
            (RepositoryShowcase.entity_id == Entity.id)
            & (RepositoryShowcase.tenant_id == Entity.tenant_id),
        )
        .where(Entity.tenant_id == repository_id)
        .order_by(RepositoryShowcase.position, Entity.id)
    )
    return ShowcaseOut(
        limit=SHOWCASE_MAX, entries=[ShowcaseEntryOut(id=i, name=n) for i, n in rows.all()]
    )


@owner_router.get("/showcase")
async def get_showcase(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)], session: SessionDep
) -> ShowcaseOut:
    """The entries featured in the repository's preview, in order, for any of its members (the
    entry names as they are now; what a visitor reads is the current release's)."""
    await _require_repository(session, tenant_id)
    return await _showcase(session, tenant_id)


@owner_router.put("/showcase")
async def put_showcase(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    body: ShowcaseUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ShowcaseOut:
    """Features these entries, in this order, instead of the ones there: at most 12, each an entry
    of this repository, none twice (`422 showcase-invalid`). Owner only. An entry added after the
    last release is featured from the release that has it."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    await _require_repository(session, tenant_id)
    ids = body.entity_ids
    if len(ids) > SHOWCASE_MAX:
        raise ShowcaseInvalidError(detail=f"At most {SHOWCASE_MAX} entries can be featured")
    if len(set(ids)) != len(ids):
        raise ShowcaseInvalidError(detail="An entry can be featured once")
    known = set(
        await session.scalars(
            select(Entity.id).where(Entity.tenant_id == tenant_id, Entity.id.in_(ids))
        )
    )
    missing = [i for i in ids if i not in known]
    if missing:
        raise ShowcaseInvalidError(
            detail=f"{len(missing)} of these are not entries of this repository"
        )
    await session.execute(
        RepositoryShowcase.__table__.delete().where(  # type: ignore[attr-defined]
            RepositoryShowcase.tenant_id == tenant_id
        )
    )
    session.add_all(
        RepositoryShowcase(tenant_id=tenant_id, entity_id=entity_id, position=position)
        for position, entity_id in enumerate(ids)
    )
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.showcase_changed",
        target_type="tenant",
        target_id=tenant_id,
        detail=f"entries={len(ids)}",
    )
    out = await _showcase(session, tenant_id)
    await session.commit()
    return out
