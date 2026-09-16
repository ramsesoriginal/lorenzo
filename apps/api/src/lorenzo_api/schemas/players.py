from __future__ import annotations

import uuid
from typing import Self

from pydantic import BaseModel

from lorenzo_api.models import Player
from lorenzo_api.schemas.characters import CharacterSummaryOut

__all__ = ["PlayerContextOut", "PlayerCreate", "PlayerOut", "PlayerSummaryOut"]


class PlayerCreate(BaseModel):
    """POST /tenants/{id}/campaigns/{id}/players - ADR 0036/RFC 0007.
    user_id must already be a real app_user row - this API has no email to
    invite by (ADR 0009's own boundary; see that RFC's "Invitation,
    honestly" for the full reasoning)."""

    user_id: uuid.UUID


class PlayerSummaryOut(BaseModel):
    """Campaign roster shape (GET .../campaigns/{id}/players, and the create-
    response shape for POST .../players) - no tenant_id/campaign_id, already
    in the path.

    Now carries `created_by`/`updated_by` (ADR 0029) - `player`'s
    attribution pair lands with user/player/character CRUD (ADR 0036/RFC
    0007), which is what actually writes to this table.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    characters: list[CharacterSummaryOut]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None

    @classmethod
    def from_player(cls, player: Player) -> Self:
        return cls(
            id=player.id,
            user_id=player.user_id,
            characters=[
                CharacterSummaryOut.from_character(link.character)
                for link in player.character_links
            ],
            created_by=player.created_by,
            updated_by=player.updated_by,
        )


class PlayerOut(PlayerSummaryOut):
    """GET .../players/{id} - identical shape to PlayerSummaryOut above,
    Player has no columns the summary omits, unlike Entity's list/detail
    split (RFC 0004's own words). Kept as its own class anyway (rather
    than reusing PlayerSummaryOut as both list and detail response) since
    the RFC's endpoint table names it as its own schema, and a distinct
    name gives this route its own OpenAPI schema rather than sharing one
    meant for a paginated list.
    """


class PlayerContextOut(BaseModel):
    """Used by GET /me and CharacterOut.players (RFC 0004) - a bare Player
    row alone (just ids) wouldn't answer anything useful in either place;
    a caller needs to know not just which campaigns a player row belongs
    to but which characters it plays there. Carries its own tenant_id/
    campaign_id explicitly, unlike PlayerSummaryOut/PlayerOut above -
    neither /me (spans every tenant) nor a character's own roster (spans
    every campaign that character is rostered into, ADR 0025's roster
    reuse) has a single campaign-nested URL to infer them from.

    Requires `player.character_links` (each with `.character.being.entity`)
    eager-loaded first (`lazy="raise_on_sql"`, ADR 0018).
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    characters: list[CharacterSummaryOut]

    @classmethod
    def from_player(cls, player: Player) -> Self:
        return cls(
            id=player.id,
            tenant_id=player.tenant_id,
            campaign_id=player.campaign_id,
            characters=[
                CharacterSummaryOut.from_character(link.character)
                for link in player.character_links
            ],
        )
