from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["SYSTEM_SLUG_PATTERN", "SystemCreate", "SystemOut", "SystemUpdate"]

# A short lowercase word: it is the prefix of the names of the system's stats (ADR 0448).
SYSTEM_SLUG_PATTERN = r"^[a-z][a-z0-9]{0,31}$"


class SystemCreate(BaseModel):
    """POST /systems - a game system the library holds the vocabulary of (ADR 0448, RFC 0052).
    The slug is a short lowercase word (letters and digits, no underscore), the prefix of its
    stats' names, and does not change once a stat group uses it. The name is for people. The
    root entry is the system root of ADR 0181, optional."""

    slug: str = Field(pattern=SYSTEM_SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    root_entry_id: uuid.UUID | None = None


class SystemUpdate(BaseModel):
    """PATCH /systems/{id} - merge-patch (`exclude_unset`). The slug cannot change while a stat
    group uses it (409). Only the root entry may be cleared; the slug and the name cannot be
    null."""

    slug: str | None = Field(default=None, pattern=SYSTEM_SLUG_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    root_entry_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _no_nulls(self) -> SystemUpdate:
        for field in ("slug", "name"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class SystemOut(BaseModel):
    """A game system of the library (ADR 0448)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    root_entry_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
