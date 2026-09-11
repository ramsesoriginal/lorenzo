from __future__ import annotations

import uuid
from typing import Self

from pydantic import BaseModel

from lorenzo_api.models import Player
from lorenzo_api.schemas.characters import CharacterSummaryOut

__all__ = ["PlayerDetailOut", "PlayerOut", "PlayerSummaryOut"]


class PlayerSummaryOut(BaseModel):
    """Used by GET /me (RFC 0004) - a bare Player row alone (just ids)
    wouldn't answer anything useful there; a caller needs to know not just
    which campaigns they're in but which characters they play there.
    Carries its own tenant_id/campaign_id explicitly, unlike PlayerOut
    below - /me spans every tenant, so there's no URL scoping to infer
    them from the way a campaign-nested route already has both in its
    path.

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


class PlayerOut(BaseModel):
    """Campaign roster shape (GET .../campaigns/{id}/players) - no
    tenant_id/campaign_id, already in the path.

    RFC 0004's own shape also carries `created_by`/`updated_by` (ADR
    0029). Deliberately not included yet: `player.created_by`/`updated_by`
    don't land until user/player/character CRUD (ADR 0036/RFC 0007)
    actually writes to this table - matching the same deferral
    `schemas/tenants.py`'s roster entries make, for the same reason.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    characters: list[CharacterSummaryOut]

    @classmethod
    def from_player(cls, player: Player) -> Self:
        return cls(
            id=player.id,
            user_id=player.user_id,
            characters=[
                CharacterSummaryOut.from_character(link.character)
                for link in player.character_links
            ],
        )


class PlayerDetailOut(PlayerOut):
    """Identical shape to PlayerOut - Player has no columns the summary
    omits, unlike Entity's list/detail split (RFC 0004's own words). Kept
    as its own class anyway (rather than reusing PlayerOut as both list
    and detail response) since the RFC's endpoint table names it as its
    own schema, and a distinct name gives GET .../players/{id} its own
    OpenAPI schema rather than sharing one meant for a paginated list.
    """
