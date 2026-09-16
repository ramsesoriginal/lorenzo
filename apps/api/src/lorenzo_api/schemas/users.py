import uuid
from typing import Annotated, Self

from pydantic import BaseModel, Field

from lorenzo_api.models import CampaignGm, Membership, Player, User
from lorenzo_api.schemas.campaigns import CampaignSummaryOut
from lorenzo_api.schemas.players import PlayerContextOut


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
    memberships: list[MembershipOut]
    players: list[PlayerContextOut]
    campaign_gm_grants: list[CampaignSummaryOut]

    @classmethod
    def from_user(
        cls, user: User, *, players: list[Player], campaign_gms: list[CampaignGm]
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
    """

    id: uuid.UUID
    nickname: str | None

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(id=user.id, nickname=user.nickname)


class NicknameUpdate(BaseModel):
    """PATCH /me - see ADR 0050. `None` clears the nickname; a given value
    must be non-empty (`min_length=1`) - an empty string would still pass
    the column's own partial unique index (it only excludes NULL), letting
    the *first* user to "clear" it this way silently block everyone else
    from ever doing the same.
    """

    nickname: Annotated[str, Field(min_length=1)] | None
