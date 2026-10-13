"""An entry's own parents, replaced as a set - the one write path both PUT /items/{id}/prototypes
(ADR 0072) and PUT /entities/{id}/parents (ADR 0216) go through, so every kind of entry follows
the same rules: not itself, every id an entry of the tenant, no loop. A parent is the API's
`prototype`: an entity_prototype row, which is what "inherits from" means.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import EntityPrototypeCycleError, InvalidPrototypeError
from lorenzo_api.models import Entity, EntityPrototype


async def replace_parents(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity: Entity,
    parent_ids: Sequence[uuid.UUID],
    user_id: uuid.UUID,
) -> bool:
    """Makes `parent_ids` the complete list of the entry's direct parents, in that order (a
    repeated id counts once, at its first place), and says whether that changed anything. The
    order matters: at equal distance and priority the earlier parent wins a stat (ADR 0266). A
    list already equal, in the same order, is left alone: nothing is written, so the entry's
    version (its ETag) does not move. A change touches `updated_by` and `updated_at`: the parents
    are part of what the entry is, since they decide its resolved stats (ADR 0037/0039).

    Raises EntityPrototypeCycleError for the entry itself or a loop (the BEFORE INSERT trigger of
    ADR 0015 finds a transitive one) and InvalidPrototypeError for an id that is not an entry of
    this tenant. The flush happens here, so the caller's commit is the only thing left to do.
    """
    entity_id = entity.id
    ordered = list(dict.fromkeys(parent_ids))
    wanted = set(ordered)
    if entity_id in wanted:
        raise EntityPrototypeCycleError(detail=f"Entry {entity_id} cannot be its own parent")
    if wanted:
        found = set(
            (
                await session.execute(
                    select(Entity.id).where(Entity.id.in_(wanted), Entity.tenant_id == tenant_id)
                )
            )
            .scalars()
            .all()
        )
        if missing := wanted - found:
            raise InvalidPrototypeError(
                detail=(
                    f"Parent id(s) {sorted(str(i) for i in missing)} do not exist "
                    f"in tenant {tenant_id}"
                )
            )

    current = list(
        (
            await session.execute(
                select(EntityPrototype.prototype_id)
                .where(
                    EntityPrototype.entity_id == entity_id, EntityPrototype.tenant_id == tenant_id
                )
                .order_by(EntityPrototype.position, EntityPrototype.prototype_id)
            )
        )
        .scalars()
        .all()
    )
    if ordered == current:
        return False

    if removed := set(current) - wanted:
        await session.execute(
            delete(EntityPrototype).where(
                EntityPrototype.entity_id == entity_id,
                EntityPrototype.tenant_id == tenant_id,
                EntityPrototype.prototype_id.in_(removed),
            )
        )
    kept = set(current) & wanted
    for position, parent_id in enumerate(ordered):
        if parent_id in kept:
            await session.execute(
                update(EntityPrototype)
                .where(
                    EntityPrototype.entity_id == entity_id,
                    EntityPrototype.tenant_id == tenant_id,
                    EntityPrototype.prototype_id == parent_id,
                )
                .values(position=position)
            )
        else:
            session.add(
                EntityPrototype(
                    entity_id=entity_id,
                    prototype_id=parent_id,
                    tenant_id=tenant_id,
                    position=position,
                )
            )
    entity.updated_by = user_id
    # Also set when updated_by is already this user, so the ETag moves whoever writes.
    entity.updated_at = func.now()
    try:
        await session.flush()
    except DBAPIError as exc:
        # entity_prototype's BEFORE INSERT trigger (ADR 0015): the only way a transitive loop
        # reaches the database. Translated rather than left as a 500.
        raise EntityPrototypeCycleError(
            detail=f"Replacing entry {entity_id}'s parents would create an inheritance cycle"
        ) from exc
    return True
