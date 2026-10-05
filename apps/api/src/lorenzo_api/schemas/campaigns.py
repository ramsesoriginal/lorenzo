import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator

from lorenzo_api.models import CampaignGm

__all__ = ["CampaignCreate", "CampaignOut", "CampaignSummaryOut", "CampaignUpdate", "GmOut"]


class CampaignCreate(BaseModel):
    """POST /campaigns - see ADR 0034/RFC 0006. name/game_system/slug/
    description are all required, no defaults - RFC 0003's own no-default
    choice for `campaign` (no existing fixture call sites to spare, unlike
    `tenant`), extended here to the create body. Deliberately doesn't accept
    entity_id: the campaign's dedicated Entity is created server-side, in
    the same transaction as the campaign row - there's nothing meaningful a
    client could set on a brand-new, still-empty entity at creation time.
    """

    name: str
    game_system: str
    slug: str
    description: str
    secret: bool = False


class CampaignUpdate(BaseModel):
    """PATCH /campaigns/{id} - every field optional, applied via
    model_dump(exclude_unset=True) (ADR 0032's convention). Changing
    game_system mid-campaign is a real consequence (it changes which
    prototype variants every entity in the campaign resolves through on
    next read, ADR 0024) but not blocked - flagged here, not guarded.
    """

    name: str | None = None
    game_system: str | None = None
    slug: str | None = None
    description: str | None = None
    secret: bool | None = None
    # RFC 0034/ADR 0185. Not nullable: there is no "no setting" for a campaign.
    player_self_service: bool | None = None

    @field_validator("player_self_service")
    @classmethod
    def _not_null(cls, value: bool | None) -> bool | None:
        if value is None:
            raise ValueError("player_self_service cannot be null")
        return value


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
    player_self_service: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class GmOut(BaseModel):
    """One row of GET .../campaigns/{id}/gms - campaign_id/tenant_id are
    already in the path, no need to repeat them per row. See ADR 0031/RFC
    0004; fits here rather than a one-class module of its own, alongside
    campaign-roster concerns generally.

    Carries the GM's `nickname`/`display_name`/`user_color` (ADR 0176), the
    same three the tenant roster shows and never the email - a GM who joined
    by link (ADR 0177) holds no tenant-wide membership to be named through.
    Requires `campaign_gm.user` eager-loaded first (`lazy="raise_on_sql"`,
    ADR 0018).
    """

    user_id: uuid.UUID
    nickname: str | None
    display_name: str | None
    user_color: str | None

    @classmethod
    def from_campaign_gm(cls, campaign_gm: CampaignGm) -> Self:
        return cls(
            user_id=campaign_gm.user_id,
            nickname=campaign_gm.user.nickname,
            display_name=campaign_gm.user.display_name,
            user_color=campaign_gm.user.user_color,
        )
