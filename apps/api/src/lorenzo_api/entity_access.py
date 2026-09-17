"""Ownership/containment reachability - the shared walk RFC 0005's
self-or-managed item-instance authorization and RFC 0009's GM-reachable-set
both need, per each RFC's own text naming this as one shared module rather
than two independent copies of the identical traversal. Mirrors
campaign_access.py/information_visibility.py's own precedent: a plain,
directly-testable domain-rule module with no HTTP-specific concerns.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CTE, any_, func, select
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import CharacterPlayer, Containment, Ownership, Player

# Bounds the cost of a recursive container traversal on a legitimately deep
# (but acyclic) containment tree - see routers/item_instances.py's original
# _MAX_CONTAINMENT_DEPTH, moved here so both this module's reachability walk
# and that router's own container-filtered listing share one definition.
_MAX_CONTAINMENT_DEPTH = 50


async def controlled_character_entity_ids(
    session: AsyncSession, *, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """Every character the caller directly controls via their own Player
    rows - the same Player -> CharacterPlayer resolution
    information_visibility.resolve_information_visibility already does for
    its own knower_entity_ids set, extracted here so RFC 0005's
    self-or-managed check can reuse it without re-deriving character
    control from scratch.
    """
    player_ids = (
        (
            await session.execute(
                select(Player.id).where(Player.user_id == user_id, Player.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )
    if not player_ids:
        return frozenset()
    character_ids = (
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
    return frozenset(character_ids)


def recursive_descendants_cte(root_entity_ids: frozenset[uuid.UUID], tenant_id: uuid.UUID) -> CTE:
    """Every entity transitively contained in any of root_entity_ids,
    cycle-safe - generalized from routers/item_instances.py's own
    single-container version (RFC 0005's own flagged follow-up: "extracting
    it into the shared entity_access.py") to start from a *set* of roots at
    once, since reachable_entity_ids below needs to walk from every entity
    a character owns simultaneously, not just one container. Not private
    (no leading underscore) - routers/item_instances.py's own
    container-filtered listing imports and reuses this directly rather than
    keeping a second copy.

    containment's PK is child_entity_id alone (ADR 0016: at most one parent
    per entity, globally), so a parent->child traversal can never
    diamond-merge - a node can only reappear via an actual cycle, which
    makes a path-array guard alone provably sufficient here (see
    item_instances.py's own docstring for the empirical verification this
    reasoning was originally checked against).
    """
    base = select(
        Containment.child_entity_id.label("child_entity_id"),
        pg_array([Containment.parent_entity_id, Containment.child_entity_id]).label("path"),
    ).where(
        Containment.parent_entity_id.in_(root_entity_ids),
        Containment.tenant_id == tenant_id,
    )
    cte = base.cte("entity_access_contained", recursive=True)
    recursive_term = (
        select(
            Containment.child_entity_id.label("child_entity_id"),
            (cte.c.path.op("||")(Containment.child_entity_id)).label("path"),
        )
        .select_from(cte.join(Containment, Containment.parent_entity_id == cte.c.child_entity_id))
        .where(
            Containment.tenant_id == tenant_id,
            ~(Containment.child_entity_id == any_(cte.c.path)),
            func.array_length(cte.c.path, 1) < _MAX_CONTAINMENT_DEPTH,
        )
    )
    return cte.union_all(recursive_term)


def _containing_ancestors_cte(entity_ids: frozenset[uuid.UUID], tenant_id: uuid.UUID) -> CTE:
    """Every entity that transitively CONTAINS any of entity_ids - the exact
    mirror of recursive_descendants_cte's downward walk (child -> parent
    here, instead of parent -> child), same cycle-safe path-array guard
    technique, see ADR 0046.
    """
    base = select(
        Containment.parent_entity_id.label("parent_entity_id"),
        pg_array([Containment.child_entity_id, Containment.parent_entity_id]).label("path"),
    ).where(
        Containment.child_entity_id.in_(entity_ids),
        Containment.tenant_id == tenant_id,
    )
    cte = base.cte("entity_access_containers", recursive=True)
    recursive_term = (
        select(
            Containment.parent_entity_id.label("parent_entity_id"),
            (cte.c.path.op("||")(Containment.parent_entity_id)).label("path"),
        )
        .select_from(cte.join(Containment, Containment.child_entity_id == cte.c.parent_entity_id))
        .where(
            Containment.tenant_id == tenant_id,
            ~(Containment.parent_entity_id == any_(cte.c.path)),
            func.array_length(cte.c.path, 1) < _MAX_CONTAINMENT_DEPTH,
        )
    )
    return cte.union_all(recursive_term)


async def containing_ancestors_ids(
    session: AsyncSession, *, entity_ids: frozenset[uuid.UUID], tenant_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """Every entity that transitively contains any of entity_ids (ADR 0046)
    - the room a character is standing in, the building that room is in,
    and so on up the containment chain. Ancestors only, not entity_ids
    themselves - matching reachable_entity_ids' own convention of taking
    the "plus itself" step at the call site rather than inside the
    traversal helper.
    """
    if not entity_ids:
        return frozenset()
    cte = _containing_ancestors_cte(entity_ids, tenant_id)
    return frozenset((await session.execute(select(cte.c.parent_entity_id))).scalars().all())


async def reachable_entity_ids(
    session: AsyncSession, *, root_entity_ids: frozenset[uuid.UUID], tenant_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """root_entity_ids themselves, plus everything Ownership-owned by one of
    them, plus everything reachable from either of those via Containment,
    recursively - RFC 0009's own three-step GM-reachable-set walk ("start
    from the campaign's characters; extend through ownership; extend
    through containment"), reused as-is for RFC 0005's self-or-managed
    check: an item instance is self-service exactly when its entity_id is
    in this set, computed with the caller's own controlled characters as
    root_entity_ids.
    """
    if not root_entity_ids:
        return frozenset()

    owned_ids = frozenset(
        (
            await session.execute(
                select(Ownership.owned_entity_id).where(
                    Ownership.owner_character_id.in_(root_entity_ids),
                    Ownership.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    start = root_entity_ids | owned_ids

    cte = recursive_descendants_cte(start, tenant_id)
    contained_ids = frozenset(
        (await session.execute(select(cte.c.child_entity_id))).scalars().all()
    )

    return start | contained_ids


async def can_self_manage_entity(
    session: AsyncSession, *, entity_id: uuid.UUID, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> bool:
    """RFC 0005's self-service check: is entity_id reachable from one of the
    caller's own characters - owned directly, or transitively contained
    within something one of them owns? Moving your own sword from your own
    backpack into your own chest, or giving it to a party member's
    character, is all just "acting on your own stuff," regardless of where
    it ends up - checked against the entity's *current* state, not its
    state after the write.
    """
    characters = await controlled_character_entity_ids(
        session, user_id=user_id, tenant_id=tenant_id
    )
    if not characters:
        return False
    reachable = await reachable_entity_ids(session, root_entity_ids=characters, tenant_id=tenant_id)
    return entity_id in reachable
