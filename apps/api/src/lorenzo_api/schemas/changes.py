import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel

from lorenzo_api.models import EntityChange

__all__ = ["EntityChangeOut"]


class EntityChangeOut(BaseModel):
    """One row of `GET /me/changes` - see ADR 0099. `actor_user_id` is set
    only when the actor is visible to the recipient: another player, never
    a GM or tenant administrator. `entity_name` is the item's name when the
    change happened, so a row still reads correctly after a rename or
    deletion.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    character_entity_id: uuid.UUID
    entity_id: uuid.UUID
    entity_name: str
    kind: str
    detail: str | None
    actor_user_id: uuid.UUID | None
    occurred_at: datetime

    @classmethod
    def from_change(cls, change: EntityChange) -> Self:
        return cls(
            id=change.id,
            tenant_id=change.tenant_id,
            character_entity_id=change.character_entity_id,
            entity_id=change.entity_id,
            entity_name=change.entity_name,
            kind=change.kind,
            detail=change.detail,
            actor_user_id=change.actor_user_id if change.actor_visible else None,
            occurred_at=change.occurred_at,
        )
