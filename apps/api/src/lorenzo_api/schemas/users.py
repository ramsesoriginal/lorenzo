import uuid
from typing import Self

from pydantic import BaseModel

from lorenzo_api.models import CampaignGm, Membership, Player, User
from lorenzo_api.schemas.campaigns import CampaignSummaryOut
from lorenzo_api.schemas.players import PlayerSummaryOut


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
    memberships: list[MembershipOut]
    players: list[PlayerSummaryOut]
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
            memberships=[MembershipOut.from_membership(m) for m in user.memberships],
            players=[PlayerSummaryOut.from_player(p) for p in players],
            campaign_gm_grants=[
                CampaignSummaryOut.model_validate(gm.campaign) for gm in campaign_gms
            ],
        )
