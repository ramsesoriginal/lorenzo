import uuid
from datetime import datetime

from pydantic import BaseModel

from lorenzo_api.schemas.entities import EntityKind, InformationOut


class EntityExportStatOut(BaseModel):
    """One value an entry holds itself (ADR 0262), by the id of its definition: what
    `PUT .../stats/{stat_definition_id}` writes, and nothing inherited or computed. A tag is a
    stat whose value is a bool. `updated_at` is the stat's own version, the source of its
    `If-Match` (ADR 0225)."""

    stat_definition_id: uuid.UUID
    value: int | str | float | bool
    updated_at: datetime


class EntityExportOut(BaseModel):
    """One entry of GET .../entities/export, as much of it as a mirror needs to be written back
    from (ADR 0262): not `EntityDetailOut`, which has effective values by name and the
    containment tree, and no definition ids. `updated_at` is the entry's version (its `ETag` and
    `If-Match`). `information` is what the caller may read of the entry's information, the rows
    and payloads `GET .../entities/{id}` shows it, picture payloads as `url`s, never as bytes."""

    id: uuid.UUID
    name: str
    slug: str | None
    kinds: list[EntityKind]
    parent_ids: list[uuid.UUID]
    stat_group_ids: list[uuid.UUID]
    stats: list[EntityExportStatOut]
    information: list[InformationOut]
    created_at: datetime
    updated_at: datetime


class EntityExportPage(BaseModel):
    """A page of GET .../entities/export, entries in id order. `revision` is the token inside
    the `ETag` of the response: the same on every page of one export. `next_cursor` is null on the
    last page, otherwise what to send as `cursor` for the next."""

    revision: str
    items: list[EntityExportOut]
    next_cursor: str | None
