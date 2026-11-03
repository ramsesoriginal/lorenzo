"""Authorized structural contents, with no generated manuscript text (ADR 0381)."""

import hashlib
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.chapter_numbering import composition_order, projection
from lorenzo_api.models import (
    Chapter,
    Entity,
    ManuscriptContents,
    ManuscriptPlacement,
    ManuscriptRedirect,
)


class ContentsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    depth: int = Field(default=3, ge=1, le=100)
    template: str = Field(default="{number} {title}", min_length=1, max_length=120)
    included: bool = True
    role: Literal["chapter", "contents", "index", "glossary"] = "chapter"

    @field_validator("template")
    @classmethod
    def valid_template(cls, value: str) -> str:
        rest = value.replace("{title}", "").replace("{number}", "")
        if value.count("{title}") != 1 or value.count("{number}") > 1 or "{" in rest or "}" in rest:
            raise ValueError(
                "Use {title} once and {number} at most once; other placeholders are not supported."
            )
        return value


def contents_version(settings: ContentsSettings) -> str:
    return '"' + hashlib.sha256(settings.model_dump_json().encode()).hexdigest() + '"'


class ContentsRow(BaseModel):
    id: uuid.UUID
    label: str
    depth: int


async def contents_tree(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    root: uuid.UUID,
    allowed: set[uuid.UUID],
    placements: list[ManuscriptPlacement],
) -> tuple[dict[uuid.UUID, ContentsSettings], list[ContentsRow]]:
    settings = {
        row.entity_id: ContentsSettings.model_validate(row.settings)
        for row in await session.scalars(
            select(ManuscriptContents).where(
                ManuscriptContents.tenant_id == tenant_id, ManuscriptContents.entity_id.in_(allowed)
            )
        )
    }
    policy = settings.get(root, ContentsSettings())
    names = {
        id: name
        for id, name in await session.execute(
            select(Entity.id, Entity.name)
            .join(Chapter, Chapter.entity_id == Entity.id)
            .where(Entity.tenant_id == tenant_id, Entity.id.in_(allowed))
        )
    }
    joined = set(
        await session.scalars(
            select(ManuscriptRedirect.source_id).where(
                ManuscriptRedirect.tenant_id == tenant_id, ManuscriptRedirect.source_id.in_(allowed)
            )
        )
    )
    ordered = await composition_order(session, tenant_id, allowed, placements)
    numbers = await projection(session, tenant_id, root, allowed, placements)
    rows = []
    pending = [(id, 1) for id in reversed(ordered.get(root, []))]
    seen = {root}
    while pending:
        id, depth = pending.pop()
        if id in seen or id not in names or id in joined:
            continue
        seen.add(id)
        if depth <= policy.depth and settings.get(id, ContentsSettings()).included:
            label = (
                policy.template.replace("{number}", numbers.get(id, ""))
                .replace("{title}", names[id])
                .strip()
            )
            rows.append(ContentsRow(id=id, label=label, depth=depth))
        pending.extend((child, depth + 1) for child in reversed(ordered.get(id, [])))
    return {id: value for id, value in settings.items() if id in seen}, rows


def visible_contents(
    root: uuid.UUID,
    id: uuid.UUID,
    settings: dict[uuid.UUID, ContentsSettings],
    rows: list[ContentsRow],
) -> list[ContentsRow] | None:
    own = settings.get(id, ContentsSettings())
    if (id == root and own.enabled) or own.role == "contents":
        return [row for row in rows if row.id != id]
    return None
