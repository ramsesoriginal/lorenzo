"""Read-time resolution of "what can this user see" for Information rows -
ADR 0028's own named-but-deferred follow-up. Mirrors campaign_access.py's
precedent: a plain, directly-testable domain-rule module with no
HTTP-specific concerns, not folded into dependencies.py - kept a plain
function rather than a FastAPI dependency for the same reason
can_access_campaign still is: exactly one consuming route exists today.

Deliberately campaign-independent for the knower_entity_id half only: a
Being has no single fixed campaign (roster reuse, ADR 0025/RFC 0002), and
Knowledge.knower_entity_id references the character/group entity directly
with no per-campaign qualifier - a character's knowledge holds regardless
of which campaign session is active, exactly like its inventory.

The knower_player_id half is NOT campaign-independent in that same sense -
Player is UniqueConstraint(campaign_id, user_id): a user gets a fresh
Player row per campaign, on purpose, which is exactly why character_player
had to exist as its own separate roster-reuse mechanism. Unioning
player_ids across every campaign in the tenant here is a deliberate
widening this route's total lack of a campaign parameter forces, not
something structurally proven safe the way the character side is - see
ADR 0028's addendum. It can let a player-level fact meant for one campaign
surface while viewing an entity shared with an unrelated campaign in the
same tenant; accepted as a named, residual limitation.

Resolved via plain column-scoped select() statements against id columns
only, matching can_access_campaign's own idiom - never by loading
Player/Being/CharacterPlayer/GroupMember as ORM objects, since only their
ids are needed here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    CharacterPlayer,
    GroupMember,
    Information,
    Membership,
    MembershipRole,
    OrgaCampaignOptOut,
    Player,
)


@dataclass(frozen=True, slots=True)
class InformationVisibility:
    """What one user can see in one tenant, outside any specific campaign.
    Pure Python, no DB access - can_see is directly unit-testable against
    hand-built Information/Knowledge objects with no session at all.
    """

    is_orga: bool
    player_ids: frozenset[uuid.UUID]
    knower_entity_ids: frozenset[uuid.UUID]

    def can_see(self, info: Information) -> bool:
        """info.knowledge_links must already be eager-loaded (raise_on_sql,
        ADR 0018). Reads only the plain knower_entity_id/knower_player_id
        FK columns off each Knowledge row, never the knower_entity/
        knower_player relationship objects - so no further eager-load
        chain is needed beyond selectinload(knowledge_links) itself.
        Several distinct Knowledge rows can legitimately share the same
        information_id (the "visible to a subset" case), so this checks
        all of them, not just the first.
        """
        if self.is_orga or info.is_public:
            return True
        return any(
            link.knower_player_id in self.player_ids
            or link.knower_entity_id in self.knower_entity_ids
            for link in info.knowledge_links
        )


async def resolve_information_visibility(
    session: AsyncSession, *, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> InformationVisibility:
    """Three short-circuiting queries: every Player row this user holds in
    this tenant (Player.tenant_id is denormalized - ADR 0024 - so this
    skips a join through campaign); every character (Being.entity_id) one
    of those players controls (CharacterPlayer's roster-reuse join, ADR
    0025); every group one of those characters belongs to (GroupMember,
    ADR 0028 - one level only, the schema's bipartite shape forecloses
    multi-hop cycles, so no recursion is needed). Each step is skipped
    once its input set is empty, mirroring can_access_campaign's own
    short-circuiting order.

    is_orga is suppressed if the user has any active OrgaCampaignOptOut
    row anywhere in this tenant - coarser than that row's own per-campaign
    shape, forced by this route having no campaign parameter to check
    against; see the module docstring and ADR 0028's addendum.
    """
    player_ids: set[uuid.UUID] = set(
        (
            await session.execute(
                select(Player.id).where(Player.user_id == user_id, Player.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )

    character_ids: set[uuid.UUID] = set()
    if player_ids:
        character_ids = set(
            (
                await session.execute(
                    select(CharacterPlayer.character_entity_id).where(
                        CharacterPlayer.player_id.in_(player_ids),
                        CharacterPlayer.tenant_id == tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    group_ids: set[uuid.UUID] = set()
    if character_ids:
        group_ids = set(
            (
                await session.execute(
                    select(GroupMember.group_entity_id).where(
                        GroupMember.character_entity_id.in_(character_ids),
                        GroupMember.tenant_id == tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    membership = await session.get(Membership, (tenant_id, user_id))
    is_orga = membership is not None and membership.role is MembershipRole.ORGA
    if is_orga:
        has_opt_out = (
            await session.execute(
                select(OrgaCampaignOptOut.campaign_id)
                .where(
                    OrgaCampaignOptOut.tenant_id == tenant_id,
                    OrgaCampaignOptOut.user_id == user_id,
                )
                .limit(1)
            )
        ).first() is not None
        is_orga = not has_opt_out

    return InformationVisibility(
        is_orga=is_orga,
        player_ids=frozenset(player_ids),
        knower_entity_ids=frozenset(character_ids | group_ids),
    )
