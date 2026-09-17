from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel

from lorenzo_api.models import Character

if TYPE_CHECKING:
    from lorenzo_api.schemas.players import PlayerContextOut

__all__ = [
    "CharacterCreate",
    "CharacterOut",
    "CharacterPromote",
    "CharacterSummaryOut",
    "CharacterUpdate",
]


class CharacterCreate(BaseModel):
    """POST /tenants/{id}/characters - ADR 0036/RFC 0007. owner_player_id is
    automatically added to player_ids too, if given and not already present
    - a primary owner who isn't also in the piloting roster would be a
    strange, easy-to-hit-by-accident state."""

    name: str
    owner_player_id: uuid.UUID | None = None
    player_ids: list[uuid.UUID] = []


class CharacterPromote(BaseModel):
    """PUT /tenants/{id}/characters/{id} - promotes an existing `being` into
    a character (ADR 0036/RFC 0007). Deliberately no `player_ids` list,
    unlike CharacterCreate - the roster sub-resource endpoints already own
    adding players one at a time; reintroducing a wholesale list here would
    undercut the exact race-avoidance reasoning that kept `character_player`
    off CharacterUpdate below in the first place. If given, owner_player_id
    is added to the roster automatically too, matching creation's own
    behavior."""

    owner_player_id: uuid.UUID | None = None


class CharacterUpdate(BaseModel):
    """PATCH /tenants/{id}/characters/{id} - ADR 0036/RFC 0007. Both fields
    optional; `owner_player_id` is re-checked for authorization against its
    *new* value if given, not just the character's current state - see
    routers/characters.py."""

    name: str | None = None
    owner_player_id: uuid.UUID | None = None


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

    `players` reuses `PlayerContextOut` whole (RFC 0004's own accepted
    minor redundancy: each returned player entry redundantly re-includes
    the very character being viewed, among any others that player
    controls - not worth a fourth schema variant to trim).

    `PlayerContextOut` (schemas/players.py) needs `CharacterSummaryOut`
    right back - a genuine two-way schema reference, not an accident.
    Broken here the standard way: `PlayerContextOut` only appears under
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
    players: list[PlayerContextOut]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None

    @classmethod
    def from_character(cls, character: Character) -> Self:
        from lorenzo_api.schemas.players import PlayerContextOut

        return cls(
            entity_id=character.entity_id,
            name=character.being.entity.name,
            is_pc=character.owner_player_id is not None,
            owner_player_id=character.owner_player_id,
            players=[PlayerContextOut.from_player(link.player) for link in character.player_links],
            created_by=character.created_by,
            updated_by=character.updated_by,
        )
