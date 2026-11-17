"""Audience preservation for manuscript restructuring."""

import uuid

from sqlalchemy import select, union

from lorenzo_api.dependencies import SessionDep
from lorenzo_api.exceptions import ManuscriptMoveConflictError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    CampaignGm,
    EntityAudience,
    EntityKnowledge,
    Information,
    Knowledge,
    Membership,
    Player,
)


async def require_no_new_readers(
    session: SessionDep,
    tenant: uuid.UUID,
    source: uuid.UUID,
    destination: uuid.UUID,
    source_info: Information | None,
    destination_info: Information | None,
) -> None:
    # Equal authored audiences need not mean equal access: GMs can have contextual
    # reach to one Chapter. Use the existing resolver for every current participant.
    people = await session.scalars(
        union(
            select(Membership.user_id).where(Membership.tenant_id == tenant),
            select(Player.user_id).where(Player.tenant_id == tenant),
            select(CampaignGm.user_id).where(CampaignGm.tenant_id == tenant),
        )
    )
    for person in people:
        vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=person)
        wider = vis.can_see_entry(destination) and not vis.can_see_entry(source)
        if source_info and not vis.can_see(source_info):
            if destination_info:
                wider |= vis.can_see(destination_info)
            else:
                # A newly created bundle keeps source grants/flags/authorship. Only
                # the new entry's contextual bypass can add access to those fields.
                wider |= vis.can_see_entry(destination) and (
                    destination in vis.gm_reachable_entity_ids
                    or destination in vis.author_entry_ids
                )
        if wider:
            raise ManuscriptMoveConflictError(
                detail="This would add readers through campaign access. Review sharing first."
            )


async def require_no_wider_manuscript_audience(
    session: SessionDep,
    tenant: uuid.UUID,
    source: uuid.UUID,
    destination: uuid.UUID,
    source_info: Information,
    destination_info: Information,
) -> None:
    """Include anonymous and future grant holders, not only today's participants."""
    source_outer = await session.get(EntityAudience, source)
    target_outer = await session.get(EntityAudience, destination)
    for (
        model,
        column,
        source_id,
        target_id,
        source_public,
        target_public,
        source_shared,
        target_shared,
    ) in (
        (
            EntityKnowledge,
            EntityKnowledge.entity_id,
            source,
            destination,
            source_outer.is_public if source_outer else True,
            target_outer.is_public if target_outer else True,
            source_outer.shared_with_participants if source_outer else False,
            target_outer.shared_with_participants if target_outer else False,
        ),
        (
            Knowledge,
            Knowledge.information_id,
            source_info.id,
            destination_info.id,
            source_info.is_public,
            destination_info.is_public,
            source_info.shared_with_participants,
            destination_info.shared_with_participants,
        ),
    ):
        if source_public:
            continue
        source_grants = set(
            await session.execute(
                select(model.knower_entity_id, model.knower_player_id).where(
                    model.tenant_id == tenant, column == source_id
                )
            )
        )
        target_grants = set(
            await session.execute(
                select(model.knower_entity_id, model.knower_player_id).where(
                    model.tenant_id == tenant, column == target_id
                )
            )
        )
        if target_public or (target_shared and not source_shared) or target_grants - source_grants:
            raise ManuscriptMoveConflictError(
                detail="These changes would widen the manuscript audience. Review sharing first."
            )
