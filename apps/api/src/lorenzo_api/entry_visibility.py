"""The existence/name gate, separate from an information audience (ADR 0305)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, exists, or_, select, text, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, aliased

from lorenzo_api.entity_access import entity_id_among
from lorenzo_api.models import (
    CalendarObservance,
    CalendarPeriod,
    EntityAudience,
    EntityKnowledge,
    Relationship,
    RepositoryCopyLinkEntity,
    Tenant,
)

if TYPE_CHECKING:
    from lorenzo_api.information_visibility import InformationVisibility


def shown_clause(
    vis: InformationVisibility,
    entity_id: ColumnElement[uuid.UUID] | InstrumentedAttribute[uuid.UUID],
) -> ColumnElement[bool]:
    """Whether the entry is not hidden by the repository it came with (ADR 0437): the copy link of
    a row the library hides says so. Nobody is let past it, an Owner or an Author included, which is
    why it is not an audience: those are the library's own and are bypassed by its administrators.
    A tenant that hides nothing (`vis.hides_entries`) asks nothing."""
    if not vis.hides_entries:
        return true()
    return ~exists().where(
        RepositoryCopyLinkEntity.entity_id == entity_id, RepositoryCopyLinkEntity.hidden.is_(True)
    )


def _own_visible_entry_clause(
    vis: InformationVisibility,
    entity_id: ColumnElement[uuid.UUID] | InstrumentedAttribute[uuid.UUID],
) -> ColumnElement[bool]:
    if vis.is_admin or vis.author_sees_all:
        return shown_clause(vis, entity_id)
    recipients = []
    if vis.player_ids:
        recipients.append(entity_id_among(EntityKnowledge.knower_player_id, vis.player_ids))
    if vis.knower_entity_ids:
        recipients.append(entity_id_among(EntityKnowledge.knower_entity_id, vis.knower_entity_ids))
    allowed: list[ColumnElement[bool]] = [EntityAudience.is_public.is_(True)]
    if vis.session_reader_ids:
        allowed.append(entity_id_among(EntityAudience.entity_id, vis.session_reader_ids))
    if vis.participant_event_ids:
        allowed.append(
            EntityAudience.shared_with_participants.is_(True)
            & entity_id_among(EntityAudience.entity_id, vis.participant_event_ids)
        )
    if vis.own_entry_ids:
        allowed.append(entity_id_among(EntityAudience.entity_id, vis.own_entry_ids))
    if vis.gm_reachable_entity_ids:
        allowed.append(entity_id_among(EntityAudience.entity_id, vis.gm_reachable_entity_ids))
    if vis.author_entry_ids:
        allowed.append(entity_id_among(EntityAudience.entity_id, vis.author_entry_ids))
    if recipients:
        allowed.append(
            exists().where(EntityKnowledge.entity_id == EntityAudience.entity_id, or_(*recipients))
        )
    return shown_clause(vis, entity_id) & ~exists().where(
        EntityAudience.entity_id == entity_id, ~or_(*allowed)
    )


def visible_entry_clause(
    vis: InformationVisibility,
    entity_id: ColumnElement[uuid.UUID] | InstrumentedAttribute[uuid.UUID],
) -> ColumnElement[bool]:
    """The entries a reader may see. A relationship is also read only with both its ends (ADR
    0399), so the rule is here, in the clause every entry read applies, and no read has to
    remember it. An end is never itself a relationship, so the ends are tested by the gate alone
    and the clause does not recurse."""
    if (vis.is_admin or vis.author_sees_all) and not vis.hides_entries:
        return true()
    tie = aliased(Relationship)
    return _entry_gate(vis, entity_id) & ~exists().where(
        tie.entity_id == entity_id,
        ~(_entry_gate(vis, tie.end_a) & _entry_gate(vis, tie.end_b)),
    )


def _entry_gate(
    vis: InformationVisibility,
    entity_id: ColumnElement[uuid.UUID] | InstrumentedAttribute[uuid.UUID],
) -> ColumnElement[bool]:
    privileged = vis.is_admin or vis.author_sees_all
    if privileged and not vis.hides_entries:
        return true()
    period = aliased(CalendarPeriod)
    observance = aliased(CalendarObservance)
    own = _own_visible_entry_clause(vis, entity_id)
    if vis.session_entry_ids and not privileged:
        own = own & (
            ~entity_id_among(entity_id, vis.session_entry_ids)
            | entity_id_among(entity_id, vis.session_reader_ids)
        )
    from lorenzo_api.models import SceneAppearance

    appearance = aliased(SceneAppearance)
    return (
        ~exists().where(
            appearance.entity_id == entity_id,
            ~_own_visible_entry_clause(vis, appearance.scene_entity_id),
        )
        & own
        & ~exists().where(
            period.entity_id == entity_id,
            ~_own_visible_entry_clause(vis, period.calendar_entity_id),
        )
        & ~exists().where(
            observance.entity_id == entity_id,
            ~_own_visible_entry_clause(vis, observance.calendar_entity_id),
        )
    )


async def require_visible_entry(
    session: AsyncSession,
    *,
    entity_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> None:
    # Internal copy/planning reads have no caller and retain the repository read contract.
    if user_id is not None:
        session.info["entry_reader_user_id"] = user_id
    user_id = user_id or session.info.get("entry_reader_user_id")
    checked = session.info.setdefault("visible_entry_checks", set())
    key = (tenant_id, entity_id, user_id)
    if key in checked:
        return
    if await hidden_by_source(session, tenant_id=tenant_id, entity_id=entity_id):
        from lorenzo_api.exceptions import EntityNotFoundError

        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    from lorenzo_api.models import SceneAppearance, StorySession

    planning_cache = session.info.setdefault("planning_entry_checks", {})
    result = (
        await session.execute(
            select(
                EntityAudience.entity_id,
                exists().where(StorySession.entity_id == EntityAudience.entity_id),
                exists().where(SceneAppearance.entity_id == EntityAudience.entity_id),
            ).where(
                EntityAudience.entity_id == entity_id,
                EntityAudience.tenant_id == tenant_id,
                or_(
                    EntityAudience.is_public.is_(False),
                    exists().where(CalendarPeriod.entity_id == entity_id),
                    exists().where(CalendarObservance.entity_id == entity_id),
                    exists().where(Relationship.entity_id == entity_id),
                ),
            )
        )
    ).first()
    gate = result[0] if result else None
    planning_cache[(tenant_id, entity_id)] = bool(result and (result[1] or result[2]))
    if gate is None:
        checked.add(key)
        return
    if user_id is None:
        raw = await session.scalar(text("SELECT current_setting('app.user_id', true)"))
        if not raw:
            return
        user_id = uuid.UUID(raw)
    from lorenzo_api.exceptions import EntityNotFoundError
    from lorenzo_api.information_visibility import resolve_information_visibility

    vis = await resolve_information_visibility(session, user_id=user_id, tenant_id=tenant_id)
    if entity_id in vis.hidden_entry_ids:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    checked.add(key)


async def hides_entries(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Whether the tenant hides any entry (`tenant.hides_entries`, ADR 0437). The tenant row is the
    one the request already holds, so this is not a statement."""
    tenant = await session.get(Tenant, tenant_id)
    return bool(tenant is not None and tenant.hides_entries)


async def hidden_by_source(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> bool:
    """Whether the entry is hidden by the repository it came with, for everyone (ADR 0437). The
    engines that write what a library hides (the copy, the update and the removal of a copy) are the
    only readers that may see it: they set `session.info["sees_hidden"]` for their own reads."""
    if session.info.get("sees_hidden") or not await hides_entries(session, tenant_id):
        return False
    return bool(
        await session.scalar(
            select(
                exists().where(
                    RepositoryCopyLinkEntity.tenant_id == tenant_id,
                    RepositoryCopyLinkEntity.entity_id == entity_id,
                    RepositoryCopyLinkEntity.hidden.is_(True),
                )
            )
        )
    )


async def hidden_by_source_ids(session: AsyncSession, tenant_id: uuid.UUID) -> frozenset[uuid.UUID]:
    """The entries the tenant hides (ADR 0437), and the relationships that tie one of them: a
    relationship is read only with both its ends (ADR 0399). The other ties of a hidden entry are
    found by the gate itself, which asks of an entry whether what it hangs on is hidden."""
    hidden = frozenset(
        entity_id
        for entity_id in await session.scalars(
            select(RepositoryCopyLinkEntity.entity_id).where(
                RepositoryCopyLinkEntity.tenant_id == tenant_id,
                RepositoryCopyLinkEntity.hidden.is_(True),
                RepositoryCopyLinkEntity.entity_id.is_not(None),
            )
        )
        if entity_id is not None
    )
    if not hidden:
        return hidden
    tied = frozenset(
        await session.scalars(
            select(Relationship.entity_id).where(
                Relationship.tenant_id == tenant_id,
                or_(Relationship.end_a.in_(hidden), Relationship.end_b.in_(hidden)),
            )
        )
    )
    return hidden | tied


async def unhidden(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: ColumnElement[Any] | InstrumentedAttribute[Any],
) -> ColumnElement[bool]:
    """The clause for a read of one kind of entry that has no audience gate of its own (the typed
    lists: items, beings, characters, groups, item instances): the entry is not hidden by the
    repository it came with (ADR 0437). `true()` for a tenant that hides nothing."""
    if not await hides_entries(session, tenant_id):
        return true()
    return ~exists().where(
        RepositoryCopyLinkEntity.tenant_id == tenant_id,
        RepositoryCopyLinkEntity.entity_id == entity_id,
        RepositoryCopyLinkEntity.hidden.is_(True),
    )
