import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

__all__ = ["CampaignOut", "CampaignSummaryOut"]


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
