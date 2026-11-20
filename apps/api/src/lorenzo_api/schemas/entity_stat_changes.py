import uuid
from datetime import datetime

from pydantic import BaseModel

__all__ = ["EntityStatChangeOut"]


class EntityStatChangeOut(BaseModel):
    """One step of GET .../entities/{id}/stat-changes (ADR 0525): a stat's own value went from
    `old` to `new`, by `actor_name` at `created_at`. `old` is null when the entry had no own value
    before, `new` when the value was removed. `actor_name` is the person's nickname or display
    name, null when the account is gone."""

    id: uuid.UUID
    stat_definition_id: uuid.UUID
    stat_name: str
    old: bool | int | float | str | None
    new: bool | int | float | str | None
    actor_id: uuid.UUID | None
    actor_name: str | None
    created_at: datetime
