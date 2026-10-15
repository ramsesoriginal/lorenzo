"""Discover, the listing and the storefront - ADR 0292, RFC 0038 section 4."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from lorenzo_api.schemas.repository_profiles import RepositoryProfileOut

__all__ = [
    "DiscoverFacetOut",
    "DiscoverFacetsOut",
    "DiscoverItemOut",
    "DiscoverPageOut",
    "DiscoverReleaseOut",
    "DiscoverSort",
    "PublisherOut",
    "StorefrontOut",
]

DiscoverSort = Literal["name", "released"]


class PublisherOut(BaseModel):
    """Who published a repository, as its Owners' accounts say it (ADR 0299, RFC 0038 section 6):
    an account's display name, else its nickname, and never a field the repository writes about
    itself. An Owner whose account has neither is "A Lorenzo account"."""

    display_name: str


class DiscoverReleaseOut(BaseModel):
    """The latest release of a listed repository: its label and when it was made."""

    label: str
    released_at: datetime


class DiscoverItemOut(BaseModel):
    """One repository in the listing: what it says of itself and how big it is, never what it
    holds. `has_cover` says `GET /repositories/{id}/profile/cover` has a picture."""

    id: uuid.UUID
    name: str
    slug: str
    summary: str
    tags: list[str]
    system: str | None
    languages: list[str]
    has_cover: bool
    release: DiscoverReleaseOut
    entries: int | None
    stat_definitions: int | None
    # Its Owners' account names, in the order they became Owners, at most five (ADR 0299).
    publishers: list[PublisherOut]


class DiscoverPageOut(BaseModel):
    """A page of the listing, in the shape of every page of the API (`items`, `total`, `page`,
    `size`, `pages`), built by hand: Discover caps a page at 50 whatever is asked, where the
    paging library would refuse only past 100."""

    items: list[DiscoverItemOut]
    total: int
    page: int
    size: int
    pages: int


class StorefrontOut(BaseModel):
    """A repository's page (ADR 0292): its listing entry, the long description, and the whole of
    its profile (licence, credits, the preview switch). Its releases, what it is built on and
    what may be looked at before copying are their own routes."""

    item: DiscoverItemOut
    description: str
    profile: RepositoryProfileOut
    # A `mailto:` to the deployment's report address with the repository's name and id in the
    # subject, for the page's "Report this repository" link; null where no address is set
    # (ADR 0299). The address is the deployment's, so every storefront says the same one.
    report_mailto: str | None


class DiscoverFacetOut(BaseModel):
    """A value a listing can be narrowed by, and how many listed repositories have it."""

    value: str
    count: int


class DiscoverFacetsOut(BaseModel):
    """The tags, systems and languages in use among the listed repositories, the most used
    first, at most a hundred of each (ADR 0292). `enabled` is whether this deployment accepts
    public repositories at all (ADR 0290): a client shows Discover only when it does."""

    enabled: bool
    tags: list[DiscoverFacetOut]
    systems: list[DiscoverFacetOut]
    languages: list[DiscoverFacetOut]
