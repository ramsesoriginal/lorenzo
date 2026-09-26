import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from lorenzo_api.models import StatValueType

__all__ = [
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
    "RepositoryEntityOut",
    "RepositoryStatDefinitionOut",
    "RepositoryStatGroupOut",
    "RepositorySummaryOut",
    "SubscriberOut",
    "SubscriptionOut",
]

EntityKindName = Literal["item", "item_instance", "being", "character"]


class SubscriberOut(BaseModel):
    """A tenant granted a repository, as its owners see it - ADR 0118."""

    tenant_id: uuid.UUID
    name: str
    slug: str
    granted_at: datetime
    granted_by: uuid.UUID | None


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
    origin id. `clean`: the tenant hasn't changed it, so it can simply be
    taken; `conflict`: the tenant changed it too; `not_applicable`: shown,
    but changed by hand. Sets (`prototypes`, `stat_groups`, `enum_values`)
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


class UpdatesOut(BaseModel):
    """`GET .../repositories/{id}/updates` - ADR 0121. `removed` rows are
    gone upstream and only ever detached, never deleted here;
    `deleted_locally` rows are ones this tenant deleted itself."""

    repository_id: uuid.UUID
    changed: list[RowChangeOut]
    removed: list[RowRefOut]
    deleted_locally: list[RowRefOut]
    added: list[AddedOut]


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


class ApplyUpdatesRequest(BaseModel):
    """`dry_run` applies everything and rolls it back (ADR 0121)."""

    actions: list[UpdateActionIn]
    dry_run: bool | None = None


class NotAppliedOut(BaseModel):
    """A field that couldn't be applied, and why. It keeps being offered."""

    kind: str
    source_id: uuid.UUID
    field: str
    reason: str


class ApplyUpdatesOut(BaseModel):
    dry_run: bool
    applied: int
    added: int
    detached: int
    not_applied: list[NotAppliedOut]
