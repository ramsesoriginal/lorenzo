"""Quotas on a repository: how many entries it holds, how many picture bytes in all, and how
large one picture can be - ADR 0298, RFC 0038 section 6.

They bound what the database holds for a repository other libraries read and copy, and only for a
tenant of kind `repository`: a play library is never limited. The limits are settings
(`repository_max_entries`, `repository_max_picture_bytes`, `repository_picture_max_bytes`).

Where it is enforced is one place for each way a row is made, not one call at every route:

- **A flush hook** on the ORM session looks at what a flush is about to insert: new `Entity`
  rows (every route that makes an entry, an inventory item, a being, a group, a character, a
  split or a pack's items, and the importer, Bench and the hub through them) and new or replaced
  `PayloadPicture` rows (every picture upload). It runs before the first statement of the flush,
  so a refused write has written nothing.
- **`check_rows`** is the same check for the copy and update engines, which insert whole tables
  of rows with Core statements the hook never sees (`repository_copying.write_rows`).

A write is refused only for what it adds: renaming, editing, deleting, and replacing a picture
with a smaller one are never blocked by a repository being over a limit that was lowered later.
The check counts with the tenant's own index (`ix_entity_tenant_id`) and takes no lock, so
writers in flight at the same moment can each see room that only one of them can have: a
repository can end up a few entries over, never more than the writes that were in flight.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history
from sqlalchemy.orm.base import PASSIVE_NO_INITIALIZE
from sqlalchemy.orm.unitofwork import UOWTransaction

from lorenzo_api.config import get_settings
from lorenzo_api.exceptions import (
    RepositoryEntryLimitError,
    RepositoryPictureTooLargeError,
    RepositoryPictureTotalLimitError,
)
from lorenzo_api.models import Entity, PayloadPicture, Tenant, TenantKind

__all__ = [
    "check_rows",
    "check_writes",
    "entries_held",
    "install",
    "picture_bytes_held",
    "shown_size",
]


def shown_size(size: int) -> str:
    """A size as a person reads it: `1.4 MB`, `250 kB`, `12 bytes` (decimal units, as the
    settings are written)."""
    if size >= 999_500:
        text = f"{size / 1_000_000:.1f}".removesuffix(".0")
        return f"{text} MB"
    if size >= 1_000:
        return f"{round(size / 1_000):,} kB"
    return f"{size:,} bytes"


def entries_held(session: Session, tenant_id: uuid.UUID) -> int:
    """The entries the tenant holds: the rows of `entity` of its id, by its own index."""
    return int(
        session.scalar(
            select(func.count()).select_from(Entity).where(Entity.tenant_id == tenant_id)
        )
        or 0
    )


def picture_bytes_held(session: Session, tenant_id: uuid.UUID) -> int:
    """The bytes of every picture on the tenant's entries (not its cover). `octet_length` of a
    stored picture is read from its header, so no picture is read in full."""
    return int(
        session.scalar(
            select(func.coalesce(func.sum(func.octet_length(PayloadPicture.data)), 0)).where(
                PayloadPicture.tenant_id == tenant_id
            )
        )
        or 0
    )


def _is_repository(session: Session, tenant_id: uuid.UUID) -> bool:
    tenant = session.get(Tenant, tenant_id)
    return tenant is not None and tenant.kind is TenantKind.REPOSITORY


def check_writes(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    new_entries: int = 0,
    removed_entries: int = 0,
    picture_sizes: Sequence[int] = (),
    picture_growth: int = 0,
) -> None:
    """Refuses what one flush or one engine write would add to the tenant, if it is a repository
    and the write would go past a limit; nothing otherwise.

    `new_entries` and `removed_entries` are entries inserted and deleted together (a flush that
    does both grows by the difference); `picture_sizes` the size of each picture written, new or
    replacing one, which is each held to the size of one picture; `picture_growth` what they add
    to the total over what they replace. Only growth is refused: a limit lowered under what a
    repository already holds never stops it from changing or shrinking.
    """
    settings = get_settings()
    if not (new_entries or picture_sizes):
        return
    if not _is_repository(session, tenant_id):
        return

    size_limit = settings.repository_picture_max_bytes
    if size_limit:
        for size in picture_sizes:
            if size > size_limit:
                raise RepositoryPictureTooLargeError(
                    detail=(
                        f"This picture is {shown_size(size)}, and a picture in a repository can "
                        f"be {shown_size(size_limit)} at most."
                    ),
                    quota="picture_size",
                    limit=size_limit,
                    size=size,
                )

    entries_limit = settings.repository_max_entries
    growth = new_entries - removed_entries
    if entries_limit and growth > 0:
        held = entries_held(session, tenant_id)
        if held + growth > entries_limit:
            if held == entries_limit and growth == 1:
                detail = (
                    f"This repository holds {held:,} entries, which is the most a repository "
                    "can have."
                )
            else:
                detail = (
                    f"This would make {held + growth:,} entries in this repository, and a "
                    f"repository can have {entries_limit:,} at most. It holds {held:,}."
                )
            raise RepositoryEntryLimitError(
                detail=detail, quota="entries", limit=entries_limit, holds=held, adding=growth
            )

    total_limit = settings.repository_max_picture_bytes
    if total_limit and picture_growth > 0:
        held_bytes = picture_bytes_held(session, tenant_id)
        if held_bytes + picture_growth > total_limit:
            raise RepositoryPictureTotalLimitError(
                detail=(
                    f"The pictures in this repository take up {shown_size(held_bytes)}, and "
                    f"this one would take them past {shown_size(total_limit)}, the most a "
                    "repository can hold."
                ),
                quota="picture_total",
                limit=total_limit,
                holds=held_bytes,
                adding=picture_growth,
            )


async def check_rows(session: Any, rows: dict[str, list[dict[str, Any]]]) -> None:
    """The check for rows an engine is about to insert with Core statements (a copy, an update's
    additions): the entries in `rows["entity"]` and the pictures in `rows["payload_picture"]`,
    each row naming its own tenant. `session` is the AsyncSession."""
    new_entries: Counter[uuid.UUID] = Counter(r["tenant_id"] for r in rows.get("entity", ()))
    sizes: dict[uuid.UUID, list[int]] = defaultdict(list)
    for row in rows.get("payload_picture", ()):
        sizes[row["tenant_id"]].append(len(row["data"]))
    for tenant_id in new_entries.keys() | sizes.keys():
        await session.run_sync(
            lambda sync, t=tenant_id: check_writes(
                sync,
                t,
                new_entries=new_entries[t],
                picture_sizes=sizes[t],
                picture_growth=sum(sizes[t]),
            )
        )


def _picture_change(picture: PayloadPicture) -> tuple[int, int] | None:
    """(new size, growth) of a picture whose bytes were replaced, or None when they were not."""
    history = get_history(picture, "data", PASSIVE_NO_INITIALIZE)
    if not history.added:
        return None
    new = len(history.added[0])
    old = len(history.deleted[0]) if history.deleted and history.deleted[0] is not None else 0
    return new, new - old


def _before_flush(session: Session, flush_context: UOWTransaction, instances: Any) -> None:
    new_entries: Counter[uuid.UUID] = Counter()
    removed_entries: Counter[uuid.UUID] = Counter()
    sizes: dict[uuid.UUID, list[int]] = defaultdict(list)
    growth: Counter[uuid.UUID] = Counter()

    for obj in session.new:
        if isinstance(obj, Entity) and obj.tenant_id is not None:
            new_entries[obj.tenant_id] += 1
    for obj in session.deleted:
        if isinstance(obj, Entity) and obj.tenant_id is not None:
            removed_entries[obj.tenant_id] += 1
    for obj in session.new:
        if isinstance(obj, PayloadPicture) and obj.tenant_id is not None and obj.data is not None:
            sizes[obj.tenant_id].append(len(obj.data))
            growth[obj.tenant_id] += len(obj.data)
    for obj in session.dirty:
        if isinstance(obj, PayloadPicture) and obj.tenant_id is not None:
            changed = _picture_change(obj)
            if changed is not None:
                sizes[obj.tenant_id].append(changed[0])
                growth[obj.tenant_id] += changed[1]

    for tenant_id in new_entries.keys() | sizes.keys():
        check_writes(
            session,
            tenant_id,
            new_entries=new_entries[tenant_id],
            removed_entries=removed_entries[tenant_id],
            picture_sizes=sizes[tenant_id],
            picture_growth=growth[tenant_id],
        )


def install() -> None:
    """Makes the flush hook live for every ORM session, once however often it is called."""
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
