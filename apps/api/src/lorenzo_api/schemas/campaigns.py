import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import CampaignGm

__all__ = ["CampaignOut", "CampaignSummaryOut", "GmOut"]


class CampaignSummaryOut(BaseModel):
    """One row of `GET /tenants/{id}/campaigns` - lean on purpose, matching
    every other *SummaryOut shape in this API (ADR 0020). See ADR 0030/RFC
    0003."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    game_system: str
    secret: bool


class CampaignOut(BaseModel):
    """GET /tenants/{id}/campaigns/{id} - the full detail shape.
    Deliberately doesn't expose entity_id: it's an internal attachment
    point for Information/Knowledge, not something a client addresses
    directly yet (ADR 0030/RFC 0003). created_by/updated_by are bare
    user_ids (ADR 0029) - resolving one to a display name is a client
    concern this API doesn't store data for.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    slug: str
    name: str
    description: str
    game_system: str
    secret: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class GmOut(BaseModel):
    """One row of GET .../campaigns/{id}/gms - campaign_id/tenant_id are
    already in the path, no need to repeat them per row. See ADR 0031/RFC
    0004; fits here rather than a one-class module of its own, alongside
    campaign-roster concerns generally.
    """

    user_id: uuid.UUID

    @classmethod
    def from_campaign_gm(cls, campaign_gm: CampaignGm) -> Self:
        return cls(user_id=campaign_gm.user_id)
