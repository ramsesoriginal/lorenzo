"""Audience preservation for manuscript restructuring."""

import uuid

from sqlalchemy import select, union

from lorenzo_api.dependencies import SessionDep
from lorenzo_api.exceptions import ManuscriptMoveConflictError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import CampaignGm, Information, Membership, Player


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
