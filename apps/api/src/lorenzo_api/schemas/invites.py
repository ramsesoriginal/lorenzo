import uuid
from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from lorenzo_api.models import InviteRole

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

    `role` (ADR 0177) is `player` unless said otherwise. A `gm` link is
    single use - `max_uses` omitted or 1 - and its `expires_at` is at most 7
    days out, which the route checks.
    """

    expires_at: AwareDatetime
    max_uses: int | None = Field(default=None, ge=1)
    role: InviteRole = InviteRole.PLAYER

    @model_validator(mode="after")
    def _a_gm_link_is_single_use(self) -> Self:
        if self.role is InviteRole.GM and self.max_uses not in (None, 1):
            raise ValueError("a GM link is single use: omit max_uses or set it to 1")
        return self


class InviteOut(BaseModel):
    """An invite's metadata - never its token. `is_active` folds revocation,
    expiry and exhaustion into one flag for a management UI.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    role: InviteRole
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
    already learn: no tenant name, no roster. `role` (ADR 0177) says what
    redeeming it makes them, so the page can ask before they log in: it is
    not a secret from someone holding the link.
    """

    campaign_name: str
    picture_url: str | None
    role: InviteRole


class InviteRedeemOut(BaseModel):
    """POST /invites/{token}/redeem. `already_joined` is true (and the
    response `200`, not `201`) when the caller already held this role in this
    campaign - no second seat, no use consumed. `player_id` is null for a GM
    link (ADR 0177): redeeming it makes a GM, not a player.
    """

    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    role: InviteRole
    player_id: uuid.UUID | None
    already_joined: bool
