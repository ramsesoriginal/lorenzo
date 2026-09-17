import uuid
from typing import Annotated, Self

from fastapi import Request
from pydantic import BaseModel, Field

from lorenzo_api.models import CampaignGm, Membership, Player, User
from lorenzo_api.schemas.campaigns import CampaignSummaryOut
from lorenzo_api.schemas.players import PlayerContextOut

_USER_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class MembershipOut(BaseModel):
    """A tenant-wide administrative access grant - see ADR 0022/0023."""

    tenant_id: uuid.UUID
    role: str

    @classmethod
    def from_membership(cls, membership: Membership) -> Self:
        return cls(tenant_id=membership.tenant_id, role=membership.role.value)


class MeOut(BaseModel):
    """The caller's own identity, tenant-wide memberships, campaign
    memberships, and GM grants - see ADR 0023/0031. `players`/
    `campaign_gm_grants` (ADR 0031/RFC 0004) are the concrete answer to
    "user -> owner|orga|member of tenant -> [player(campaign) ->
    character | GM(campaign)]" for the caller's own identity - the single
    place a client reads "everything I am, everywhere."
    """

    id: uuid.UUID
    authgear_subject_id: str
    email: str | None
    nickname: str | None
    # ADR 0056 - a fuller profile.
    display_name: str | None
    pronouns: str | None
    bio: str | None
    locales: list[str]
    user_color: str | None
    # Always a constructed URL, not conditional on a picture actually
    # existing - the same "hand back the URL, let the resource itself
    # 404/redirect" precedent PayloadPictureOut.url already established
    # (ADR 0020) - GET /users/{id}/picture (ADR 0052) resolves to the
    # uploaded picture, a Gravatar redirect, or 404, entirely on its own.
    picture_url: str
    memberships: list[MembershipOut]
    players: list[PlayerContextOut]
    campaign_gm_grants: list[CampaignSummaryOut]

    @classmethod
    def from_user(
        cls,
        user: User,
        *,
        request: Request,
        players: list[Player],
        campaign_gms: list[CampaignGm],
    ) -> Self:
        """`players`/`campaign_gms` are passed in explicitly rather than
        read off `user.players`/`user.campaign_gms` - resolving them needs
        a tenant-by-tenant query loop the router does itself (see
        routers/users.py's own docstring for why: RLS on what these
        reference has no single-tenant-context escape hatch the way
        `Player`/`CampaignGm` rows themselves do), not a plain eager load.
        """
        return cls(
            id=user.id,
            authgear_subject_id=user.authgear_subject_id,
            email=user.email,
            nickname=user.nickname,
            display_name=user.display_name,
            pronouns=user.pronouns,
            bio=user.bio,
            locales=user.locales,
            user_color=user.user_color,
            picture_url=str(request.url_for("get_user_picture", user_id=user.id)),
            memberships=[MembershipOut.from_membership(m) for m in user.memberships],
            players=[PlayerContextOut.from_player(p) for p in players],
            campaign_gm_grants=[
                CampaignSummaryOut.model_validate(gm.campaign) for gm in campaign_gms
            ],
        )


class UserRefOut(BaseModel):
    """A minimal, deliberately-thin reference to a user - see ADR 0051.
    Returned by the by-email/by-nickname lookup routes so a client can
    resolve an identifier it already knows into the user_id the existing
    invite-shaped endpoints (POST .../memberships, player creation) still
    take. Never echoes email back - the caller already supplied it.
    `display_name` (ADR 0056) is included as a friendlier label while
    resolving who you're about to invite - not `user_color`, which is for
    shared UI rendering, not a lookup result.
    """

    id: uuid.UUID
    nickname: str | None
    display_name: str | None

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(id=user.id, nickname=user.nickname, display_name=user.display_name)


class ProfileUpdate(BaseModel):
    """PATCH /me - see ADR 0050/0056. Replaces the narrower NicknameUpdate:
    every field is optional and independently omittable (`exclude_unset`
    semantics, matching `TenantUpdate`/`CampaignUpdate`'s own established
    PATCH convention) - a client updating just `bio` no longer has to
    resend every other field to avoid wiping them. An explicitly-sent
    `null` still clears a field (`nickname`'s own pre-existing behavior,
    ADR 0050); omitting the key entirely leaves it untouched.

    `nickname`, given, must be non-empty (`min_length=1`) - an empty
    string would still pass the column's own partial unique index (it
    only excludes NULL), letting the *first* user to "clear" it this way
    silently block everyone else from ever doing the same. `user_color`,
    given, must be a `#RRGGBB` hex string - format-checked here, not
    enforced as meaningful beyond that shape (ADR 0056).
    """

    nickname: Annotated[str, Field(min_length=1)] | None = None
    display_name: str | None = None
    pronouns: str | None = None
    bio: str | None = None
    locales: list[str] | None = None
    user_color: Annotated[str, Field(pattern=_USER_COLOR_PATTERN)] | None = None
