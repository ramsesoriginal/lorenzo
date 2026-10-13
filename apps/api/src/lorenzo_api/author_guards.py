"""What an Author may do to an entry (RFC 0040, ADR 0219), where a route is open to every member
who edits and the entry decides: the routes that make, change the kinds or the parents of, and
delete any entry (ADR 0215 to 0217).

An administrator (an Owner or an Organizer) is never held back here. An Author's reach is a
repository's every entry and a library's catalog items (`entry_in_author_reach`); in a library
they make and change items, not beings, characters or what a campaign owns. Deleting an entry
other entries inherit from is an administrator's: what would be lost is not the Author's.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.campaign_access import entry_in_author_reach, is_tenant_admin
from lorenzo_api.exceptions import (
    AuthorEntryForbiddenError,
    InheritedEntryDeletionForbiddenError,
)
from lorenzo_api.models import EntityPrototype, Tenant, TenantKind

# The kinds an Author gives to an entry of a library: the catalog's.
LIBRARY_AUTHOR_KINDS = frozenset({"item"})


async def _is_library(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    tenant = await session.get(Tenant, tenant_id)
    return tenant is not None and tenant.kind is not TenantKind.REPOSITORY


async def author_may_use_kinds(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, kinds: Iterable[str]
) -> None:
    """403 for an Author who gives an entry of a library a kind that is not the catalog's, or none:
    a bare entry is not a catalog item."""
    if await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id):
        return
    given = set(kinds)
    if await _is_library(session, tenant_id) and (not given or not given <= LIBRARY_AUTHOR_KINDS):
        raise AuthorEntryForbiddenError(
            detail="An Author makes and changes items in a library; beings and characters stay "
            "with an Owner or an Organizer"
        )


async def author_may_touch(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    """403 for an Author who changes an entry that is not in their reach."""
    if await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id):
        return
    if not await entry_in_author_reach(session, tenant_id=tenant_id, entity_id=entity_id):
        raise AuthorEntryForbiddenError(
            detail=f"Entry {entity_id} is not one an Author changes in this library"
        )


async def author_may_delete(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    """403 for an Author who deletes an entry that is not in their reach, or one that other
    entries inherit from."""
    if await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id):
        return
    await author_may_touch(session, tenant_id=tenant_id, user_id=user_id, entity_id=entity_id)
    inherited = await session.execute(
        select(EntityPrototype.entity_id)
        .where(EntityPrototype.prototype_id == entity_id, EntityPrototype.tenant_id == tenant_id)
        .limit(1)
    )
    if inherited.first() is not None:
        raise InheritedEntryDeletionForbiddenError(
            detail=f"Other entries inherit from entry {entity_id}; an Owner or an Organizer can"
            " delete it"
        )
