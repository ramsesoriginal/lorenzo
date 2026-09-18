from __future__ import annotations

import uuid
from typing import Self

from pydantic import BaseModel

from lorenzo_api.models import Being

__all__ = ["BeingSummaryOut"]


class BeingSummaryOut(BaseModel):
    """GET /tenants/{id}/beings - see ADR 0078. A superset of
    CharacterSummaryOut: every Being, not just ones with a Character row.

    `name` is plain Entity.name (the internal/reference name, ADR 0012),
    matching CharacterSummaryOut's own precedent - not any narrative
    title. `is_pc` is genuinely three-valued, unlike
    CharacterSummaryOut.is_pc (always a real bool, since that schema only
    ever describes rows that already have a Character): `None` means no
    Character row exists at all, distinct from `False` (a Character row
    exists, but owner_player_id is unset).

    Requires `being.entity` and `being.character` eager-loaded first
    (`lazy="raise_on_sql"`, ADR 0018) - raises rather than silently
    lazy-loading if the caller forgot.
    """

    entity_id: uuid.UUID
    name: str
    is_pc: bool | None

    @classmethod
    def from_being(cls, being: Being) -> Self:
        return cls(
            entity_id=being.entity_id,
            name=being.entity.name,
            is_pc=(being.character.owner_player_id is not None)
            if being.character is not None
            else None,
        )
