import uuid
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from lorenzo_api.models import CampaignGm, Membership, Player, Tenant
from lorenzo_api.schemas.characters import CharacterSummaryOut

__all__ = [
    "GmRosterEntryOut",
    "MembershipCreate",
    "MembershipRoleName",
    "MembershipRosterEntryOut",
    "MembershipUpdate",
    "PlayerRosterEntryOut",
    "TenantCreate",
    "TenantOut",
    "TenantRole",
    "TenantRosterEntryOut",
    "TenantSummaryOut",
    "TenantUpdate",
]

TenantRole = Literal["owner", "orga", "participant"]

# Membership.role only ever holds one of these two (MembershipRole, ADR
# 0022) - narrower than TenantRole above, which also admits "participant"
# for a caller with no Membership row at all, never a valid *input* value.
MembershipRoleName = Literal["owner", "orga"]

# Basic format only (lowercase alphanumeric segments joined by single
# hyphens, no leading/trailing/doubled hyphen) - RFC 0012's own "Open
# questions" explicitly leaves a reserved-word blocklist, profanity
# filtering, and length limits undesigned; this is just enough to keep an
# explicitly-given slug usable in a URL path segment.
_SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class TenantCreate(BaseModel):
    """POST /tenants - see ADR 0033/RFC 0012. `name` required - the
    column's own "Unnamed Tenant" server default exists only for
    pre-existing test fixtures (ADR 0022), not for a fresh create endpoint
    to ever produce. `slug`, left unset, is derived from `name` and
    auto-suffixed on collision; given explicitly, it's validated (format,
    above) and checked for uniqueness with *no* auto-suffix (409
    SlugConflictError if taken) - creating a tenant never fails just
    because someone else already picked a similar name, but silently
    rewriting a slug the caller explicitly chose would be the wrong failure
    mode. `description` defaults to `''` (the column's own existing server
    default) when omitted.
    """

    name: str
    slug: Annotated[str | None, Field(pattern=_SLUG_PATTERN)] = None
    description: str | None = None


class TenantUpdate(BaseModel):
    """PATCH /tenants/{id} - all fields optional. Renaming never
    regenerates `slug` - the two are independent once a tenant exists.
    Changing `slug` here goes through the same explicit-collision-check
    path POST uses (no auto-suffix): a specific new slug is being asked for
    by name, not merely omitted.
    """

    name: str | None = None
    slug: Annotated[str | None, Field(pattern=_SLUG_PATTERN)] = None
    description: str | None = None


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
    get_tenant_context gates this route.

    `created_by`/`updated_by` (ADR 0033/RFC 0012): `tenant` moves from
    excluded to covered by ADR 0029's attribution pair now that POST/PATCH
    /tenants actually write it - same shape as `campaign`/`membership`/
    `player`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None


class MembershipCreate(BaseModel):
    """POST /tenants/{id}/memberships - ADR 0036/RFC 0007. user_id must
    already be a real app_user row - as with PlayerCreate, this API has no
    email to invite by (ADR 0009's own boundary)."""

    user_id: uuid.UUID
    role: MembershipRoleName


class MembershipUpdate(BaseModel):
    """PATCH /tenants/{id}/memberships/{user_id} - ADR 0036/RFC 0007. Just
    the one field the RFC's own endpoint table names - no `exclude_unset`
    dance needed, unlike CampaignUpdate/TenantUpdate's multi-field bodies.
    """

    role: MembershipRoleName


class MembershipRosterEntryOut(BaseModel):
    """One row of GET /tenants/{id}/memberships' broadened roster (ADR
    0031/RFC 0004), also POST/PATCH's own create/update-response shape - see
    TenantRosterEntryOut below for why this is a discriminated union rather
    than one schema with sometimes-meaningful fields, matching the
    PayloadOut precedent (ADR 0020).

    Now carries `created_by`/`updated_by` (ADR 0029) - `membership`'s
    attribution pair lands with user/player/character CRUD (ADR 0036/RFC
    0007), which is what actually writes to this table.
    """

    kind: Literal["membership"] = "membership"
    user_id: uuid.UUID
    nickname: str | None
    role: str
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None

    @classmethod
    def from_membership(cls, membership: Membership, *, nickname: str | None) -> Self:
        return cls(
            user_id=membership.user_id,
            nickname=nickname,
            role=membership.role.value,
            created_by=membership.created_by,
            updated_by=membership.updated_by,
        )


class PlayerRosterEntryOut(BaseModel):
    """Sourced the same way `is_tenant_participant` (ADR 0030) already
    queries every Player row where Player.tenant_id matches - already
    denormalized, no join through Campaign needed.

    Now carries `created_by`/`updated_by` too, same as
    MembershipRosterEntryOut above (ADR 0036/RFC 0007).
    """

    kind: Literal["player"] = "player"
    user_id: uuid.UUID
    nickname: str | None
    campaign_id: uuid.UUID
    characters: list[CharacterSummaryOut]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None

    @classmethod
    def from_player(cls, player: Player, *, nickname: str | None) -> Self:
        return cls(
            user_id=player.user_id,
            nickname=nickname,
            campaign_id=player.campaign_id,
            characters=[
                CharacterSummaryOut.from_character(link.character)
                for link in player.character_links
            ],
            created_by=player.created_by,
            updated_by=player.updated_by,
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
    nickname: str | None
    campaign_id: uuid.UUID

    @classmethod
    def from_campaign_gm(cls, campaign_gm: CampaignGm, *, nickname: str | None) -> Self:
        return cls(
            user_id=campaign_gm.user_id, nickname=nickname, campaign_id=campaign_gm.campaign_id
        )


TenantRosterEntryOut = Annotated[
    MembershipRosterEntryOut | PlayerRosterEntryOut | GmRosterEntryOut, Field(discriminator="kind")
]
