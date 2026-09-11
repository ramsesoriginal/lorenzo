import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from lorenzo_api.models import CampaignGm, Membership, Player, Tenant
from lorenzo_api.schemas.characters import CharacterSummaryOut

__all__ = [
    "GmRosterEntryOut",
    "MembershipRosterEntryOut",
    "PlayerRosterEntryOut",
    "TenantOut",
    "TenantRole",
    "TenantRosterEntryOut",
    "TenantSummaryOut",
]

TenantRole = Literal["owner", "orga", "participant"]


class TenantSummaryOut(BaseModel):
    """One row of `GET /tenants` - every tenant the caller belongs to in
    any capacity. `role` is derived, not a plain column, so this needs an
    explicit constructor rather than `from_attributes=True` alone (ADR
    0020's own precedent for anything needing data beyond a bare ORM
    attribute copy). See ADR 0030/RFC 0003.
    """

    id: uuid.UUID
    slug: str
    name: str
    role: TenantRole

    @classmethod
    def from_tenant(cls, tenant: Tenant, *, role: TenantRole) -> Self:
        return cls(id=tenant.id, slug=tenant.slug, name=tenant.name, role=role)


class TenantOut(BaseModel):
    """GET /tenants/{id} - the full detail shape. No role here: the caller
    already knows they're at least a tenant-wide member, since
    get_tenant_context gates this route."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str


class MembershipRosterEntryOut(BaseModel):
    """One row of GET /tenants/{id}/memberships' broadened roster (ADR
    0031/RFC 0004) - see TenantRosterEntryOut below for why this is a
    discriminated union rather than one schema with sometimes-meaningful
    fields, matching the PayloadOut precedent (ADR 0020).

    RFC 0004's own shape also carries `created_by`/`updated_by`.
    Deliberately not included yet: per ADR 0029's phased table,
    `membership`'s attribution pair doesn't land until user/player/
    character CRUD (ADR 0036/RFC 0007) actually writes to this table -
    add it here as a small follow-up once that lands.
    """

    kind: Literal["membership"] = "membership"
    user_id: uuid.UUID
    role: str

    @classmethod
    def from_membership(cls, membership: Membership) -> Self:
        return cls(user_id=membership.user_id, role=membership.role.value)


class PlayerRosterEntryOut(BaseModel):
    """Sourced the same way `is_tenant_participant` (ADR 0030) already
    queries every Player row where Player.tenant_id matches - already
    denormalized, no join through Campaign needed.

    Same attribution deferral as MembershipRosterEntryOut above -
    `player.created_by`/`updated_by` don't exist until ADR 0036/RFC 0007.
    """

    kind: Literal["player"] = "player"
    user_id: uuid.UUID
    campaign_id: uuid.UUID
    characters: list[CharacterSummaryOut]

    @classmethod
    def from_player(cls, player: Player) -> Self:
        return cls(
            user_id=player.user_id,
            campaign_id=player.campaign_id,
            characters=[
                CharacterSummaryOut.from_character(link.character)
                for link in player.character_links
            ],
        )


class GmRosterEntryOut(BaseModel):
    """One row per CampaignGm row in the tenant. No `characters` field -
    GM-ing isn't tied to any character; a GM who also plays a PC already
    gets their own separate player-kind row for that.

    RFC 0004's own shape also carries `created_by` (matching
    `campaign_gm`'s eventual lighter, create-only attribution shape - no
    `updated_by`, since a grant is never "updated," only made or revoked).
    Deliberately not included yet: per ADR 0029's phased table,
    `campaign_gm.created_by` itself doesn't land until campaign CRUD (ADR
    0034/RFC 0006) actually writes to this table - exposing a column that
    doesn't exist would be building ahead of that slice, not this one.
    Add it here as a small, natural follow-up once ADR 0034 lands.
    """

    kind: Literal["gm"] = "gm"
    user_id: uuid.UUID
    campaign_id: uuid.UUID

    @classmethod
    def from_campaign_gm(cls, campaign_gm: CampaignGm) -> Self:
        return cls(user_id=campaign_gm.user_id, campaign_id=campaign_gm.campaign_id)


TenantRosterEntryOut = Annotated[
    MembershipRosterEntryOut | PlayerRosterEntryOut | GmRosterEntryOut, Field(discriminator="kind")
]
