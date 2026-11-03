import uuid

from pydantic import BaseModel

from lorenzo_api.schemas.common import EntitySummary

__all__ = ["EffectiveStatOut", "EntryEffectiveStatsOut"]


class EffectiveStatOut(BaseModel):
    """One stat of one entry in GET .../entities/effective-stats - ADR 0387: the effective value,
    formulas evaluated (as `EntityStatValueOut.value`), whether the entry holds it itself, the
    entry it is inherited from (null when it holds it, or when the caller may not see the
    source) and whether a formula decided it."""

    stat_definition_id: uuid.UUID
    value: int | str | float | bool
    own: bool
    from_entity: EntitySummary | None = None
    computed: bool


class EntryEffectiveStatsOut(BaseModel):
    """One row of GET .../entities/effective-stats: an entry and the requested stats it has a
    value for, in the order asked. A stat it has none of is left out."""

    id: uuid.UUID
    name: str
    stats: list[EffectiveStatOut]
