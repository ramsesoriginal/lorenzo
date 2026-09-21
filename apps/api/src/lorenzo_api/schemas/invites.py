import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

__all__ = [
    "InviteCreate",
    "InviteCreatedOut",
    "InviteOut",
    "InvitePreviewOut",
    "InviteRedeemOut",
]


class InviteCreate(BaseModel):
    """POST .../campaigns/{id}/invites - see ADR 0092. `expires_at` is
    required (a link always ends) and at most 30 days out; `max_uses` is
    optional - omit it for an unlimited link.
    """

    expires_at: AwareDatetime
    max_uses: int | None = Field(default=None, ge=1)


class InviteOut(BaseModel):
    """An invite's metadata - never its token. `is_active` folds revocation,
    expiry and exhaustion into one flag for a management UI.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    created_by: uuid.UUID | None
    created_at: datetime
    expires_at: datetime
    max_uses: int | None
    use_count: int
    revoked_at: datetime | None
    is_active: bool


class InviteCreatedOut(InviteOut):
    """The one response that carries the token: shown once, at creation,
    and unrecoverable afterwards (only its hash is stored).
    """

    token: str


class InvitePreviewOut(BaseModel):
    """GET /invites/{token} - unauthenticated. The campaign's name and, if
    it has one, its picture URL. Nothing a holder of a leaked link couldn't
    already learn: no tenant name, no roster.
    """

    campaign_name: str
    picture_url: str | None


class InviteRedeemOut(BaseModel):
    """POST /invites/{token}/redeem. `already_joined` is true (and the
    response `200`, not `201`) when the caller was already a player in this
    campaign - no second seat, no use consumed.
    """

    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    player_id: uuid.UUID
    already_joined: bool
