import uuid
from datetime import datetime

from pydantic import BaseModel

__all__ = ["KnowledgeEntryOut"]


class KnowledgeEntryOut(BaseModel):
    """GET /tenants/{tenant_id}/knowledge - see ADR 0085. One grant of one
    piece of information to one knower. Ids only, never content: this is an
    index of *who knows what* for export and audit, and reading the
    information itself still goes through its own visibility-filtered
    read. Exactly one of `knower_entity_id` (a character or group) and
    `knower_player_id` is set, mirroring `knowledge`'s own CHECK constraint
    (ADR 0028).
    """

    id: uuid.UUID
    information_id: uuid.UUID
    entity_id: uuid.UUID
    knower_entity_id: uuid.UUID | None
    knower_player_id: uuid.UUID | None
    created_at: datetime
