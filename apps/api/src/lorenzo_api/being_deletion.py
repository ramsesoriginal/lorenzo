"""Permanent being deletion and inventory settlement (ADR 0302). No commit here."""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.author_guards import author_may_delete
from lorenzo_api.campaign_access import (
    campaign_ids_for_character,
    can_manage_every_campaign,
    can_manage_owner,
)
from lorenzo_api.change_feed import Change, holders, record_change
from lorenzo_api.entity_access import controlled_character_entity_ids
from lorenzo_api.exceptions import CharacterManagementForbiddenError
from lorenzo_api.models import (
    Being,
    Containment,
    Entity,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
    Tenant,
    TenantKind,
)
from lorenzo_api.routers.item_instances import _set_down_pieces


async def authorize_being_deletion(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    membership = await session.get(Membership, (tenant_id, user_id))
    tenant = await session.get_one(Tenant, tenant_id)
    if (
        membership is not None
        and membership.role is MembershipRole.AUTHOR
        and tenant.kind is TenantKind.REPOSITORY
    ):
        await author_may_delete(session, tenant_id=tenant_id, user_id=user_id, entity_id=entity_id)
        return
    controlled = await controlled_character_entity_ids(
        session, tenant_id=tenant_id, user_id=user_id
    )
    if entity_id in controlled:
        return
    campaigns = await campaign_ids_for_character(
        session, tenant_id=tenant_id, character_entity_id=entity_id
    )
    allowed = (
        await can_manage_every_campaign(
            session, tenant_id=tenant_id, user_id=user_id, campaign_ids=campaigns
        )
        if campaigns
        else await can_manage_owner(
            session, tenant_id=tenant_id, user_id=user_id, owner_entity_id=entity_id
        )
    )
    if not allowed:
        raise CharacterManagementForbiddenError(detail="Not authorized to delete this being")


async def _inventory_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, being_id: uuid.UUID
) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    # UNION makes this finite even for containment cycles. Another being is a carrying boundary:
    # carrying a passenger does not mean carrying (or deleting) that passenger's possessions.
    carried = (
        select(Containment.child_entity_id.label("id"))
        .where(Containment.tenant_id == tenant_id, Containment.parent_entity_id == being_id)
        .cte("being_carried", recursive=True)
    )
    carried = carried.union(
        select(Containment.child_entity_id)
        .join(carried, Containment.parent_entity_id == carried.c.id)
        .where(
            Containment.tenant_id == tenant_id,
            ~Containment.parent_entity_id.in_(
                select(Being.entity_id).where(Being.tenant_id == tenant_id)
            ),
        )
    )
    carried_ids = set(
        await session.scalars(
            select(ItemInstance.entity_id).where(
                ItemInstance.tenant_id == tenant_id,
                ItemInstance.entity_id.in_(select(carried.c.id)),
                ~ItemInstance.entity_id.in_(
                    select(Being.entity_id).where(Being.tenant_id == tenant_id)
                ),
            )
        )
    )
    owned_ids = set(
        await session.scalars(
            select(ItemInstance.entity_id)
            .join(Ownership, Ownership.owned_entity_id == ItemInstance.entity_id)
            .where(
                ItemInstance.tenant_id == tenant_id,
                Ownership.tenant_id == tenant_id,
                Ownership.owner_character_id == being_id,
                ItemInstance.entity_id != being_id,
            )
        )
    )
    return carried_ids, owned_ids


async def settle_inventory(
    session: AsyncSession, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, being_id: uuid.UUID
) -> None:
    # Re-read after locking: an item may have moved or changed owner while this request waited.
    # Expand the locked set until every item in the current inventory has been locked as well.
    entries: dict[uuid.UUID, Entity] = {}
    while True:
        carried_ids, owned_ids = await _inventory_ids(
            session, tenant_id=tenant_id, being_id=being_id
        )
        affected = carried_ids | owned_ids
        unlocked = affected - entries.keys()
        if not unlocked:
            break
        entries.update(
            {
                entry.id: entry
                for entry in await session.scalars(
                    select(Entity)
                    .where(Entity.tenant_id == tenant_id, Entity.id.in_(unlocked))
                    .order_by(Entity.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            }
        )
    removed = carried_ids & owned_ids
    affected = carried_ids | owned_ids
    if not affected:
        return
    before = {
        item_id: await holders(session, tenant_id=tenant_id, entity_id=item_id)
        for item_id in affected
    }
    changes: list[Change] = []
    # Clear owned-away instances before deleting their owner; this also frees bound items just as
    # the ownership FK does when its owner disappears. Other owners' links remain untouched.
    await session.execute(
        delete(Ownership).where(
            Ownership.tenant_id == tenant_id,
            Ownership.owned_entity_id.in_(owned_ids - removed),
            Ownership.owner_character_id == being_id,
        )
    )

    # Preserve survivor counts when deleting their container or setting down an owned-away item.
    # Contents of surviving containers stay together; only their outside link is removed.
    links = list(
        await session.scalars(
            select(Containment)
            .where(
                Containment.tenant_id == tenant_id,
                Containment.child_entity_id.in_(affected - removed),
            )
            .with_for_update()
        )
    )
    for link in links:
        if link.child_entity_id in owned_ids or link.parent_entity_id in removed | {being_id}:
            if link.quantity > 1:
                pieces = await _set_down_pieces(
                    session,
                    tenant_id=tenant_id,
                    stack_id=link.child_entity_id,
                    quantity=link.quantity,
                    actor_id=actor_id,
                )
                changes.extend(
                    Change(entity_id=p, before=frozenset(), both_kind=None) for p in pieces
                )
            await session.delete(link)
    for item_id in sorted(removed):
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="item_instance.deleted",
            target_type="item_instance",
            target_id=item_id,
            detail=f"being={being_id}",
        )
        await session.delete(entries[item_id])
    for item_id in affected - removed:
        entries[item_id].updated_by = actor_id
        entries[item_id].updated_at = func.now()
    await session.flush()
    changes.extend(
        Change(
            entity_id=item_id,
            before=before[item_id],
            both_kind="moved",
            deleted=item_id in removed,
            entity_name=entries[item_id].name,
        )
        for item_id in sorted(affected)
    )
    # Do this while the being's roster still exists, so its players can receive the feed rows.
    await record_change(session, tenant_id=tenant_id, actor_id=actor_id, changes=changes)
