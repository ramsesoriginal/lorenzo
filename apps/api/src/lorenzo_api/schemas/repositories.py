import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from lorenzo_api.models import StatValueType

__all__ = [
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


class SubscriptionOut(BaseModel):
    """One repository granted to a tenant - `GET .../repositories`, ADR
    0118. `copied_at`/`synced_at` are null until it's copied (ADR 0119);
    `repository.published_at` later than `synced_at` means it has
    published since (ADR 0121)."""

    repository: RepositorySummaryOut
    granted_at: datetime
    copied_at: datetime | None
    synced_at: datetime | None


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
    resolutions: list[ResolutionIn] | None = None


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


class CopyOut(BaseModel):
    """What a copy did: one entry per repository it copied."""

    steps: list[CopyStepOut]
