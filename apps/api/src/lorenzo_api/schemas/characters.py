from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel

from lorenzo_api.models import Character

if TYPE_CHECKING:
    from lorenzo_api.schemas.players import PlayerSummaryOut

__all__ = ["CharacterOut", "CharacterSummaryOut"]


class CharacterSummaryOut(BaseModel):
    """Identity/roster shape, not the fuller narrative view `v_character`
    exists for - see ADR 0031/RFC 0004. `name` is plain `Entity.name` (the
    internal/reference name, ADR 0012), not `v_character.title` - reaching
    for the view here would just be a second, unnecessary join. `is_pc` is
    RFC 0001/0002's derived fact (`owner_player_id IS NOT NULL`), computed
    here, not stored.

    Requires `character.being.entity` eager-loaded first (`lazy=
    "raise_on_sql"`, ADR 0018) - raises rather than silently lazy-loading
    if the caller forgot.
    """

    entity_id: uuid.UUID
    name: str
    is_pc: bool

    @classmethod
    def from_character(cls, character: Character) -> Self:
        return cls(
            entity_id=character.entity_id,
            name=character.being.entity.name,
            is_pc=character.owner_player_id is not None,
        )


class CharacterOut(BaseModel):
    """GET /tenants/{id}/characters/{id} - see ADR 0031/RFC 0004.
    `created_by`/`updated_by` are this row's own (ADR 0029) - who
    *promoted* this being into a tracked character, not who created the
    underlying `being` (that's `entity.created_by`, a different, also
    meaningful fact - ADR 0029's own open question).

    `players` reuses `PlayerSummaryOut` whole (RFC 0004's own accepted
    minor redundancy: each returned player entry redundantly re-includes
    the very character being viewed, among any others that player
    controls - not worth a fourth schema variant to trim).

    `PlayerSummaryOut` (schemas/players.py) needs `CharacterSummaryOut`
    right back - a genuine two-way schema reference, not an accident.
    Broken here the standard way: `PlayerSummaryOut` only appears under
    `TYPE_CHECKING` (so this module never really imports players.py,
    which itself really imports this one for `CharacterSummaryOut` above
    - a real cycle either direction if both were real imports), and
    `from_character` below imports it locally, deferred until actually
    called. Whatever first imports `routers/characters.py` calls
    `CharacterOut.model_rebuild(...)` to make the forward reference
    resolvable - see that module.
    """

    entity_id: uuid.UUID
    name: str
    is_pc: bool
    owner_player_id: uuid.UUID | None
    players: list[PlayerSummaryOut]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None

    @classmethod
    def from_character(cls, character: Character) -> Self:
        from lorenzo_api.schemas.players import PlayerSummaryOut

        return cls(
            entity_id=character.entity_id,
            name=character.being.entity.name,
            is_pc=character.owner_player_id is not None,
            owner_player_id=character.owner_player_id,
            players=[PlayerSummaryOut.from_player(link.player) for link in character.player_links],
            created_by=character.created_by,
            updated_by=character.updated_by,
        )
