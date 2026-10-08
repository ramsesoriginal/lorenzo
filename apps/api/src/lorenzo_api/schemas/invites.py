import uuid
from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from lorenzo_api.invites import MAX_SHARED_INVITE_USES
from lorenzo_api.models import Invite, InviteKind, InviteRole, TenantKind

__all__ = [
    "InviteCreate",
    "InviteCreatedOut",
    "InviteOut",
    "InvitePreviewOut",
    "InviteRedeemIn",
    "InviteRedeemOut",
    "TenantInviteCreate",
]


class InviteCreate(BaseModel):
    """POST .../campaigns/{id}/invites - see ADR 0092. `expires_at` is
    required (a link always ends) and at most 30 days out; `max_uses` is
    optional - omit it for an unlimited link.

    `role` (ADR 0177) is `player` unless said otherwise. A `gm` link is
    single use - `max_uses` omitted or 1 - and its `expires_at` is at most 7
    days out, which the route checks. A campaign's links make a player or a GM, and
    nothing else (ADR 0211).
    """

    expires_at: AwareDatetime
    max_uses: int | None = Field(default=None, ge=1)
    role: InviteRole = InviteRole.PLAYER

    @model_validator(mode="after")
    def _a_campaign_link_makes_a_player_or_a_gm(self) -> Self:
        if self.role not in (InviteRole.PLAYER, InviteRole.GM):
            raise ValueError("a campaign link makes a player or a GM: role is player or gm")
        return self

    @model_validator(mode="after")
    def _a_gm_link_is_single_use(self) -> Self:
        if self.role is InviteRole.GM and self.max_uses not in (None, 1):
            raise ValueError("a GM link is single use: omit max_uses or set it to 1")
        return self


class TenantInviteCreate(BaseModel):
    """POST /tenants/{id}/invites - an Owner's link for their library or repository (ADR 0211).

    `kind` is `tenant_role`, which makes an Author or an Organizer of the tenant and takes a
    `role`, or `library_access`, which grants a repository to a library the redeemer owns and
    takes none. Never an Owner. Every one ends and is capped: `expires_at` left out is the
    default (3 days for a role link, 7 for a library link) and at most 7 days out for a role
    link, 30 for a library link; `max_uses` left out is 1, an Author link or a library link
    may be raised to a small ceiling, and an Organizer link is single use.
    """

    kind: InviteKind
    role: InviteRole | None = None
    expires_at: AwareDatetime | None = None
    max_uses: int | None = Field(default=None, ge=1, le=MAX_SHARED_INVITE_USES)

    @model_validator(mode="after")
    def _the_role_fits_the_kind(self) -> Self:
        if self.kind is InviteKind.CAMPAIGN:
            raise ValueError(
                "campaign links are made on the campaign: tenant_role or library_access"
            )
        if self.role not in (None, InviteRole.AUTHOR, InviteRole.ORGA):
            raise ValueError("a role link makes an Author or an Organizer: role is author or orga")
        if self.kind is InviteKind.TENANT_ROLE and self.role is None:
            raise ValueError("a role link says its role: author or orga")
        if self.kind is InviteKind.LIBRARY_ACCESS and self.role is not None:
            raise ValueError("a library link has no role")
        if self.role is InviteRole.ORGA and self.max_uses not in (None, 1):
            raise ValueError("an Organizer link is single use: omit max_uses or set it to 1")
        return self


class InviteOut(BaseModel):
    """An invite's metadata - never its token. `is_active` folds revocation,
    expiry and exhaustion into one flag for a management UI. `campaign_id` is null for a
    role or a library link, and `role` for a library link (ADR 0211).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: InviteKind
    campaign_id: uuid.UUID | None
    role: InviteRole | None
    created_by: uuid.UUID | None
    created_at: datetime
    expires_at: datetime
    max_uses: int | None
    use_count: int
    revoked_at: datetime | None
    is_active: bool

    @classmethod
    def from_invite(cls, invite: Invite, *, now: datetime) -> Self:
        is_active = (
            invite.revoked_at is None
            and invite.expires_at > now
            and (invite.max_uses is None or invite.use_count < invite.max_uses)
        )
        return cls(
            id=invite.id,
            kind=invite.kind,
            campaign_id=invite.campaign_id,
            role=invite.role,
            created_by=invite.created_by,
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            max_uses=invite.max_uses,
            use_count=invite.use_count,
            revoked_at=invite.revoked_at,
            is_active=is_active,
        )


class InviteCreatedOut(InviteOut):
    """The one response that carries the token: shown once, at creation,
    and unrecoverable afterwards (only its hash is stored).
    """

    token: str


class InvitePreviewOut(BaseModel):
    """GET /invites/{token} - unauthenticated. What the visitor is about to be asked and
    nothing more: the `kind`, the `name` of what it is for (a campaign, a library or a
    repository, the one a library link shares), its picture URL if it has one, and what
    redeeming makes them (`role`, null for a library link). `campaign_name` is the campaign's
    name for a campaign link, as before, and null for the other kinds. `tenant_kind` says
    whether `name` is a library (`play`) or a repository, null for a campaign. No tenant name
    of a campaign, no roster, nothing a holder of a leaked link couldn't already learn (ADR
    0092, 0211).
    """

    kind: InviteKind
    name: str
    campaign_name: str | None
    tenant_kind: TenantKind | None
    picture_url: str | None
    role: InviteRole | None


class InviteRedeemIn(BaseModel):
    """POST /invites/{token}/redeem. The body is for a library-access link only: the library
    (or, for a bridge, the repository) to share with, which the caller must own. It travels
    here and never in the path, with the token (ADR 0211)."""

    library_id: uuid.UUID | None = None


class InviteRedeemOut(BaseModel):
    """POST /invites/{token}/redeem. `already_joined` is true (and the
    response `200`, not `201`) when the caller already held what the link gives - the role
    in the campaign, any role in the tenant, the grant - no second seat, no use consumed.
    `player_id` is null for every kind but a player link. `campaign_id` is null for a role or
    a library link, and `role` for a library link. `library_id` is the library a library link
    shared its repository with (ADR 0211).
    """

    kind: InviteKind
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID | None
    role: InviteRole | None
    player_id: uuid.UUID | None
    library_id: uuid.UUID | None = None
    already_joined: bool
