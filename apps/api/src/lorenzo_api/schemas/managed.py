import uuid
from typing import Literal

from pydantic import BaseModel

from lorenzo_api.models import TenantKind

__all__ = ["ManagedCampaignOut", "ManagedScopeOut", "ManagedTenantOut"]


class ManagedCampaignOut(BaseModel):
    """One campaign in `GET /me/managed` - see ADR 0086. `is_gm` is true if
    the caller holds a `CampaignGm` row for it; a tenant administrator sees
    every campaign in their tenant, GM of it or not.
    """

    campaign_id: uuid.UUID
    name: str
    is_gm: bool


class ManagedTenantOut(BaseModel):
    """One tenant in `GET /me/managed`. `role` is the caller's tenant-wide
    Membership role, or `None` when they are here only because they GM a
    campaign in it.
    """

    tenant_id: uuid.UUID
    name: str
    slug: str
    role: Literal["owner", "orga"] | None
    # ADR 0118: a repository's authors run it too, but it has no campaigns.
    kind: TenantKind
    campaigns: list[ManagedCampaignOut]


class ManagedScopeOut(BaseModel):
    """`GET /me/managed` - an index of what the caller runs, to navigate
    from: not a dashboard, no counts or rosters (ADR 0086).
    """

    tenants: list[ManagedTenantOut]
