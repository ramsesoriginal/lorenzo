"""Scene and Session reference rules (ADR 0317)."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import EntityKindInUseError
from lorenzo_api.models import (
    Being,
    Fact,
    SceneBeing,
    SceneEvent,
    SceneFact,
    SceneTelling,
    SessionEvent,
    SessionFact,
    StoryEvent,
)


@dataclass(frozen=True)
class ReferenceBinding:
    model: Any
    target_model: Any
    source: str
    target: str


SCENE_REFERENCES = {
    "facts": ReferenceBinding(SceneFact, Fact, "scene_entity_id", "fact_entity_id"),
    "events": ReferenceBinding(SceneEvent, StoryEvent, "scene_entity_id", "event_entity_id"),
    "beings": ReferenceBinding(SceneBeing, Being, "scene_entity_id", "being_entity_id"),
}
SESSION_REFERENCES = {
    "facts": ReferenceBinding(SessionFact, Fact, "session_entity_id", "fact_entity_id"),
    "events": ReferenceBinding(SessionEvent, StoryEvent, "session_entity_id", "event_entity_id"),
}


async def require_no_context_references(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    from lorenzo_api.models import EventPresentation

    if (
        await session.scalar(
            select(EventPresentation.id)
            .where(
                EventPresentation.tenant_id == tenant_id,
                EventPresentation.event_entity_id == entity_id,
            )
            .limit(1)
        )
        is not None
    ):
        raise EntityKindInUseError(
            detail="This entry has references that prevent deletion or kind removal."
        )
    if await session.scalar(
        select(SceneTelling.entity_id)
        .where(
            SceneTelling.tenant_id == tenant_id,
            (SceneTelling.scene_entity_id == entity_id)
            | (SceneTelling.viewpoint_entity_id == entity_id),
        )
        .limit(1)
    ):
        raise EntityKindInUseError(detail="Remove the Scene telling reference first.")
    for binding in [*SCENE_REFERENCES.values(), *SESSION_REFERENCES.values()]:
        if (
            await session.scalar(
                select(getattr(binding.model, binding.target))
                .where(
                    binding.model.tenant_id == tenant_id,
                    getattr(binding.model, binding.target) == entity_id,
                )
                .limit(1)
            )
            is not None
        ):
            raise EntityKindInUseError(
                detail="This entry has references that prevent deletion or kind removal"
            )
