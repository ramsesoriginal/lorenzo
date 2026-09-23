"""The player-facing change feed's write side - see ADR 0099.

Core mechanics only, no auth and no commit, like `activity_log`: each
item-instance write path takes a `snapshot` of the affected items' holders
before it mutates, then calls `record_change` afterwards, before its own
commit.

A character *holds* an item if it owns it, contains it at any depth, or owns
something that contains it at any depth. A change is recorded for every
holder before or after it: holders only after get `received`, only before
get `given_away`, both get the change's own kind (or nothing, for kinds that
don't concern someone who kept the item). Rows go to every user controlling
a holder, except the user who made the change.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.entity_access import containing_ancestors_ids
from lorenzo_api.models import (
    CampaignGm,
    Character,
    CharacterPlayer,
    Entity,
    EntityChange,
    Membership,
    Ownership,
    Player,
)

# Rows older than this are pruned when their recipient reads the feed.
RETENTION_DAYS = 90


async def holders(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """The characters that currently hold `entity_id` (see module docstring)."""
    ancestors = await containing_ancestors_ids(
        session, entity_ids=frozenset({entity_id}), tenant_id=tenant_id
    )
    chain = ancestors | {entity_id}
    owners = set(
        (
            await session.execute(
                select(Ownership.owner_character_id).where(
                    Ownership.owned_entity_id.in_(chain), Ownership.tenant_id == tenant_id
                )
            )
        ).scalars()
    )
    candidates = owners | set(ancestors)
    if not candidates:
        return frozenset()
    # Owners and containers can be any entity; only characters count.
    return frozenset(
        (
            await session.execute(
                select(Character.entity_id).where(
                    Character.entity_id.in_(candidates), Character.tenant_id == tenant_id
                )
            )
        ).scalars()
    )


@dataclass(frozen=True, slots=True)
class Change:
    """One item's change. `before` is its holders from before the mutation
    (from `holders`, or an empty set for a new item); `both_kind` is what a
    holder who kept the item is told, or None to tell them nothing."""

    entity_id: uuid.UUID
    before: frozenset[uuid.UUID]
    both_kind: str | None
    detail: str | None = None
    # A deleted item has no holders afterwards, and its holders are told
    # `deleted` rather than `given_away`.
    deleted: bool = False
    # For a deleted item, which can no longer be looked up.
    entity_name: str | None = None


async def _actor_visible(
    session: AsyncSession, *, tenant_id: uuid.UUID, actor_id: uuid.UUID
) -> bool:
    """Hidden if the actor holds any GM grant or tenant-wide membership in
    this tenant (every MembershipRole is administrative) - ADR 0099."""
    if await session.get(Membership, (tenant_id, actor_id)) is not None:
        return False
    gm = await session.execute(
        select(CampaignGm.campaign_id)
        .where(CampaignGm.user_id == actor_id, CampaignGm.tenant_id == tenant_id)
        .limit(1)
    )
    return gm.first() is None


async def _users_by_character(
    session: AsyncSession, *, tenant_id: uuid.UUID, character_ids: set[uuid.UUID]
) -> dict[uuid.UUID, set[uuid.UUID]]:
    rows = await session.execute(
        select(CharacterPlayer.character_entity_id, Player.user_id)
        .join(Player, Player.id == CharacterPlayer.player_id)
        .where(
            CharacterPlayer.character_entity_id.in_(character_ids),
            CharacterPlayer.tenant_id == tenant_id,
        )
    )
    by_character: dict[uuid.UUID, set[uuid.UUID]] = {}
    for character_id, user_id in rows:
        by_character.setdefault(character_id, set()).add(user_id)
    return by_character


async def record_change(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    changes: list[Change],
) -> None:
    """Writes the feed rows for `changes`. Call after the mutation (the
    after-holders are computed now, from current state) and before the
    route's commit, while its tenant context is still set."""
    if not changes:
        return
    plans: list[tuple[Change, str, dict[uuid.UUID, str]]] = []
    for change in changes:
        after = (
            frozenset()
            if change.deleted
            else await holders(session, tenant_id=tenant_id, entity_id=change.entity_id)
        )
        kinds: dict[uuid.UUID, str] = {}
        for character_id in change.before | after:
            if change.deleted:
                kinds[character_id] = "deleted"
            elif character_id in after and character_id not in change.before:
                kinds[character_id] = "received"
            elif character_id in change.before and character_id not in after:
                kinds[character_id] = "given_away"
            elif change.both_kind is not None:
                kinds[character_id] = change.both_kind
        if not kinds:
            continue
        name = change.entity_name
        if name is None:
            name = (
                await session.execute(select(Entity.name).where(Entity.id == change.entity_id))
            ).scalar_one()
        plans.append((change, name, kinds))
    if not plans:
        return

    users = await _users_by_character(
        session,
        tenant_id=tenant_id,
        character_ids={c for _, _, kinds in plans for c in kinds},
    )
    visible = await _actor_visible(session, tenant_id=tenant_id, actor_id=actor_id)
    now = datetime.now(tz=UTC)
    for change, name, kinds in plans:
        for character_id, kind in kinds.items():
            for user_id in users.get(character_id, set()) - {actor_id}:
                session.add(
                    EntityChange(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        user_id=user_id,
                        character_entity_id=character_id,
                        entity_id=change.entity_id,
                        kind=kind,
                        entity_name=name,
                        detail=change.detail,
                        actor_user_id=actor_id,
                        actor_visible=visible,
                        occurred_at=now,
                    )
                )
