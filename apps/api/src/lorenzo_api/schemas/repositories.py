import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from lorenzo_api.models import StatValueType

__all__ = [
    "EntityKindName",
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
    0118."""

    repository: RepositorySummaryOut
    granted_at: datetime


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
