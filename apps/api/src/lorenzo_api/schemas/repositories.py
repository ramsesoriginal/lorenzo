import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel

from lorenzo_api.models import StatValueType

__all__ = [
    "AttachmentActionIn",
    "AttachmentActionName",
    "AttachmentAddedOut",
    "AttachmentRefOut",
    "ContributionCountsOut",
    "ContributionOut",
    "PreviousCopyOut",
    "AddedOut",
    "ApplyUpdatesOut",
    "ApplyUpdatesRequest",
    "FieldChangeOut",
    "NotAppliedOut",
    "RowChangeOut",
    "RowRefOut",
    "UpdateActionIn",
    "UpdatesOut",
    "CollisionOut",
    "CopyOut",
    "CopyPlanOut",
    "CopyRequest",
    "CopyStepOut",
    "DroppedOut",
    "EntityKindName",
    "ResolutionIn",
    "RepositoryDependencyOut",
    "RepositoryEntityOut",
    "RepositoryStatDefinitionOut",
    "RepositoryStatGroupOut",
    "RepositorySummaryOut",
    "SubscriberOut",
    "SubscriptionOut",
]

EntityKindName = Literal["item", "item_instance", "being", "character"]


class SubscriberOut(BaseModel):
    """A tenant granted a repository or holding a copy of it, as its owners
    see it - ADR 0118, 0204. `granted_at` is null for one whose invitation is
    gone and whose copy stays; `copied_at` and `synced_at` are null until it
    copies."""

    tenant_id: uuid.UUID
    name: str
    slug: str
    granted_at: datetime | None
    granted_by: uuid.UUID | None
    copied_at: datetime | None
    synced_at: datetime | None


class RepositorySummaryOut(BaseModel):
    """A repository as a tenant granted it sees it - ADR 0118."""

    id: uuid.UUID
    name: str
    slug: str
    description: str
    published_at: datetime | None


class ContributionCountsOut(BaseModel):
    """What a copy contributed that's still here (ADR 0119)."""

    entities: int
    stat_groups_copied: int
    stat_groups_merged: int
    stat_definitions_copied: int
    stat_definitions_merged: int
    # The parents it added to rows copied from elsewhere, taken with it (ADR 0172).
    attachments: int


class SubscriptionOut(BaseModel):
    """One repository granted to or copied by a tenant - `GET
    .../repositories`, ADR 0118/0119. `granted_at` is null once the grant
    is gone; `copied_at`/`synced_at`/`contributed` until it's copied.
    `repository.published_at` later than `synced_at` means it has
    published since (ADR 0121). A repository deleted since it was copied
    shows the name it had, and no slug."""

    repository: RepositorySummaryOut
    granted_at: datetime | None
    copied_at: datetime | None
    synced_at: datetime | None
    contributed: ContributionCountsOut | None


class ContributionOut(BaseModel):
    """One row a copy contributed (ADR 0119). `local_id` is null if this
    tenant deleted it; `mode` is `copied` or `merged` for a stat group or
    definition, null for an entity."""

    kind: Literal["entity", "stat_group", "stat_definition"]
    local_id: uuid.UUID | None
    source_id: uuid.UUID
    name: str
    mode: Literal["copied", "merged"] | None


class RepositoryDependencyOut(BaseModel):
    """A repository another one is built on, with the asking library's state
    of it (ADR 0198): who it is, never what it holds."""

    id: uuid.UUID
    name: str
    slug: str
    # The asking library holds an invitation to it / has copied it.
    invited: bool
    copied: bool
    published: bool


class RepositoryEntityOut(BaseModel):
    """An entity in a repository, as browsed before copying: structure,
    not text (ADR 0118)."""

    id: uuid.UUID
    name: str
    kinds: list[EntityKindName]
    prototype_ids: list[uuid.UUID]


class RepositoryStatDefinitionOut(BaseModel):
    id: uuid.UUID
    name: str
    value_type: StatValueType
    enum_values: list[str]


class RepositoryStatGroupOut(BaseModel):
    """A repository's stat group with its definitions, as browsed before
    copying (ADR 0118)."""

    id: uuid.UUID
    name: str
    priority: int
    mandatory: bool
    definitions: list[RepositoryStatDefinitionOut]


CollisionKindName = Literal["stat_group", "stat_definition", "slug"]
ActionName = Literal["rename", "merge", "skip"]


class ResolutionIn(BaseModel):
    """A choice for one collision (ADR 0119). `name` is the new name, or
    the new slug, for `rename`."""

    kind: CollisionKindName
    source_id: uuid.UUID
    action: ActionName
    name: str | None = None


class CopyRequest(BaseModel):
    """`dry_run` does everything, checks included, and rolls it back.
    `again` copies an already-copied repository afresh: `keep` leaves the
    earlier copy as unlinked local rows, `purge` deletes what it created
    first (ADR 0119)."""

    resolutions: list[ResolutionIn] | None = None
    dry_run: bool | None = None
    again: Literal["keep", "purge"] | None = None


class CollisionOut(BaseModel):
    """Something a copy would bring in whose name or slug is taken here -
    `local_id` is the stat group or definition it collides with, if any."""

    repository_id: uuid.UUID
    kind: CollisionKindName
    source_id: uuid.UUID
    name: str
    local_id: uuid.UUID | None
    choices: list[ActionName]


class DroppedOut(BaseModel):
    """A row a copy leaves out, because something it points at wasn't
    copied (usually by the tenant's own choice to skip it)."""

    kind: str
    source_id: uuid.UUID
    reason: str


class CopyStepOut(BaseModel):
    """One repository in a copy's manifest (ADR 0120): its dependencies in
    order, then the repository itself."""

    repository_id: uuid.UUID
    name: str
    granted: bool
    published: bool
    already_copied: bool
    entities: int
    stat_groups: int
    stat_definitions: int
    information: int
    # Parents added to entities copied elsewhere, that this step writes (ADR 0172).
    attachments: int
    dropped: list[DroppedOut]


class CopyPlanOut(BaseModel):
    """What `POST .../copy` would do, with nothing written (ADR 0119)."""

    steps: list[CopyStepOut]
    collisions: list[CollisionOut]


class PreviousCopyOut(BaseModel):
    """What copying again did to the earlier copy. `also_removed` counts,
    per kind, rows of the tenant's own that went with a purge."""

    mode: Literal["keep", "purge"]
    entities: int
    stat_groups: int
    stat_definitions: int
    also_removed: dict[str, int]


class CopyOut(BaseModel):
    """What a copy did, or with `dry_run`, would have done: one entry per
    repository it copied."""

    steps: list[CopyStepOut]
    dry_run: bool
    previous: PreviousCopyOut | None


# --- Updates (ADR 0121) ---------------------------------------------------------

RowKindName = Literal["entity", "stat_group", "stat_definition"]


class FieldChangeOut(BaseModel):
    """One field the repository changed since this tenant copied or last
    synced it. `field` is its name, or `stats:<id>`/`formulas:<id>` for one
    stat, `label` then naming the stat. Values name other rows by their
    origin id, and the response's `names` has each one's name (ADR 0197).
    `clean`: the tenant hasn't changed it, so it can simply be taken;
    `conflict`: the tenant changed it too; `not_applicable`: shown, but
    changed by hand. Sets (`prototypes`, `stat_groups`, `enum_values`)
    list what upstream `added` and `removed`, and are always clean."""

    field: str
    label: str | None
    state: Literal["clean", "conflict", "not_applicable"]
    base: Any
    upstream: Any
    local: Any
    added: list[Any] | None
    removed: list[Any] | None


class RowChangeOut(BaseModel):
    kind: RowKindName
    source_id: uuid.UUID
    local_id: uuid.UUID
    name: str
    fields: list[FieldChangeOut]


class RowRefOut(BaseModel):
    kind: RowKindName
    source_id: uuid.UUID
    local_id: uuid.UUID | None
    name: str


class AddedOut(BaseModel):
    """A row the repository added since, with the collision copying it
    would hit, if any."""

    kind: RowKindName
    source_id: uuid.UUID
    name: str
    collision: CollisionOut | None


class AttachmentRefOut(BaseModel):
    """A parent the repository added to an entity it holds a copy of - ADR
    0172. Both ends are named by their origin id, `*_source_id`; the `*_local_id`
    is this tenant's own row for it, null where it has none."""

    child_source_id: uuid.UUID
    child_local_id: uuid.UUID | None
    child_name: str
    parent_source_id: uuid.UUID
    parent_local_id: uuid.UUID | None
    parent_name: str


class AttachmentAddedOut(AttachmentRefOut):
    """An attachment this tenant has no record of taking. `applicable`: both
    ends are here, so it can be taken now; otherwise `reason` says which isn't.
    It becomes applicable once the end is here, whether an update brings it or
    this call adds it."""

    applicable: bool
    reason: str | None


class UpdatesOut(BaseModel):
    """`GET .../repositories/{id}/updates` - ADR 0121. `removed` rows are
    gone upstream and only ever detached, never deleted here;
    `deleted_locally` rows are ones this tenant deleted itself. The
    `attachments_*` lists are the same for the parents the repository added to
    its copies (ADR 0172): `attachments_removed` are ones it no longer has, which
    are only detached, and `attachments_deleted_locally` are ones whose edge this
    tenant removed. `names` maps every id the changed fields mention (an origin id,
    or `local:<id>` for one of this tenant's own rows) to its name, the repository's
    row as it is now, else this tenant's, else the one it was copied as, so a row
    gone upstream or deleted here still reads (ADR 0197). An id nobody has a name for
    is not in it, and a client says "an entry that is gone", never the id."""

    repository_id: uuid.UUID
    changed: list[RowChangeOut]
    removed: list[RowRefOut]
    deleted_locally: list[RowRefOut]
    added: list[AddedOut]
    attachments_added: list[AttachmentAddedOut]
    attachments_removed: list[AttachmentRefOut]
    attachments_deleted_locally: list[AttachmentRefOut]
    names: dict[str, str]


class UpdateResolutionIn(BaseModel):
    action: ActionName
    name: str | None = None


class UpdateActionIn(BaseModel):
    """One row's update. `apply` takes every clean field, and each
    conflicting field named in `take_upstream`; one named in `keep_local`
    stays. Every conflict must be named in one or the other. `add` copies
    an added row, with `resolution` for its collision; `detach` drops a
    removed row's link."""

    kind: RowKindName
    source_id: uuid.UUID
    action: Literal["apply", "add", "detach"]
    keep_local: list[str] | None = None
    take_upstream: list[str] | None = None
    resolution: UpdateResolutionIn | None = None


class AttachmentActionName(StrEnum):
    """A named type rather than an inline `Literal`, so the generated clients keep
    naming the other actions the way they did."""

    ADD = "add"
    DETACH = "detach"


class AttachmentActionIn(BaseModel):
    """One attachment's update (ADR 0172), named by its two origin ids. `add`
    takes an added attachment: the edge, if this tenant hasn't it, and the record
    of having taken it. `detach` drops a removed attachment's record and leaves the
    parent where it is."""

    child_source_id: uuid.UUID
    parent_source_id: uuid.UUID
    action: AttachmentActionName


class ApplyUpdatesRequest(BaseModel):
    """`dry_run` applies everything and rolls it back (ADR 0121). The
    `attachments` are applied after the `actions`, so one can point at a row
    those add."""

    actions: list[UpdateActionIn]
    attachments: list[AttachmentActionIn] | None = None
    dry_run: bool | None = None


class NotAppliedOut(BaseModel):
    """A field that couldn't be applied, and why. It keeps being offered. `name` is the
    row it is about and `label` the stat or parent its `field` names, in words (ADR 0197)."""

    kind: str
    source_id: uuid.UUID
    field: str
    reason: str
    name: str | None
    label: str | None


class ApplyUpdatesOut(BaseModel):
    """An attachment that couldn't be added is a `not_applied` entry of kind
    `attachment`, its `source_id` the child's origin and its `field`
    `prototypes`."""

    dry_run: bool
    applied: int
    added: int
    detached: int
    attachments_added: int
    attachments_detached: int
    not_applied: list[NotAppliedOut]
