"""The reviewed bounded import contract (ADR 0311)."""

from __future__ import annotations

import uuid
from typing import Literal

from lorenzo_calendar import Key
from lorenzo_calendar.document import CalendarDocument
from pydantic import BaseModel, ConfigDict, Field


class CalendarImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: CalendarDocument
    accepted_warnings: list[Key] = Field(default_factory=list, max_length=100)
    resolutions: dict[str, Literal["keep_local", "take_source"]] = Field(
        default_factory=dict, max_length=1001
    )


class CalendarImportApply(CalendarImportRequest):
    token: str = Field(pattern=r"^[a-f0-9]{64}$")


class CalendarImportChange(BaseModel):
    key: str
    action: Literal["create", "unchanged", "conflict", "retained"]
    reason: str | None = None
    resolution: Literal["keep_local", "take_source"] | None = None


class CalendarImportPlan(BaseModel):
    source_key: str
    calendar_entity_id: uuid.UUID
    token: str
    changes: list[CalendarImportChange]
    unaccepted_warnings: list[str]
    ready: bool


class CalendarImportReceipt(BaseModel):
    source_key: str
    calendar_entity_id: uuid.UUID
    created: list[str]
    changed: list[str]
    unchanged: list[str]
    kept_local: list[str]
    retained: list[str]
