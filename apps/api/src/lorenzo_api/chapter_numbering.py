"""Reader-scoped Chapter numbering, independent of prose (ADR 0380)."""

import hashlib
import uuid
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Chapter,
    Information,
    ManuscriptNumbering,
    ManuscriptPlacement,
    Payload,
)


class NumberingLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: Literal["decimal", "roman", "roman_lower", "alphabetic", "alphabetic_lower"] = "decimal"
    start: int = Field(default=1, ge=1, le=999999)
    restart_per_parent: bool = True
    include_parents: bool = True


class NumberingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    levels: list[NumberingLevel] = Field(
        default_factory=lambda: [NumberingLevel()], min_length=1, max_length=100
    )
    unnumbered: bool = False
    override: int | None = Field(default=None, ge=1, le=999999)
    restart: bool = False
    end: bool = False


def settings_version(settings: NumberingSettings) -> str:
    return '"' + hashlib.sha256(settings.model_dump_json().encode()).hexdigest() + '"'


def numeral(value: int, style: str) -> str:
    if style.startswith("roman") and value <= 3999:
        out = ""
        for amount, symbol in (
            (1000, "M"),
            (900, "CM"),
            (500, "D"),
            (400, "CD"),
            (100, "C"),
            (90, "XC"),
            (50, "L"),
            (40, "XL"),
            (10, "X"),
            (9, "IX"),
            (5, "V"),
            (4, "IV"),
            (1, "I"),
        ):
            while value >= amount:
                out += symbol
                value -= amount
    elif style.startswith("alphabetic"):
        out = ""
        while value:
            value, digit = divmod(value - 1, 26)
            out = chr(65 + digit) + out
    else:
        out = str(value)
    return out.lower() if style.endswith("_lower") else out


def calculate(
    root: uuid.UUID,
    chapters: set[uuid.UUID],
    ordered: dict[uuid.UUID, list[uuid.UUID]],
    settings: dict[uuid.UUID, NumberingSettings],
) -> dict[uuid.UUID, str]:
    policy = settings.get(root, NumberingSettings())
    if not policy.enabled:
        return {}
    labels: dict[uuid.UUID, str] = {}
    counters: dict[tuple[int, uuid.UUID | None], int | None] = {}
    pending: list[tuple[uuid.UUID, int, uuid.UUID | None, tuple[str, ...]]] = (
        [(root, 0, None, ())]
        if root in chapters
        else [(c, 0, root, ()) for c in reversed(ordered.get(root, []))]
    )
    visited: set[uuid.UUID] = set()
    while pending:
        child, level, parent, ancestors = pending.pop()
        if child in visited or child not in chapters:
            continue
        visited.add(child)
        rule = policy.levels[min(level, len(policy.levels) - 1)]
        own = settings.get(child, NumberingSettings())
        key = (level, parent if rule.restart_per_parent else None)
        number = counters.get(key, rule.start)
        if own.restart:
            number = rule.start
        if own.override is not None:
            number = own.override
        parts = ancestors
        if not own.unnumbered and number is not None and number <= 999999:
            part = numeral(number, rule.style)
            labels[child] = ".".join((*ancestors, part)) if rule.include_parents else part
            parts = (*ancestors, part)
            number += 1
        counters[key] = None if own.end else number
        pending.extend((c, level + 1, child, parts) for c in reversed(ordered.get(child, [])))
    return labels


async def projection(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    root: uuid.UUID,
    allowed: set[uuid.UUID],
    placements: list[ManuscriptPlacement],
) -> dict[uuid.UUID, str]:
    """Only an already authorized tree can influence labels or expose settings."""
    chapters = set(
        await session.scalars(
            select(Chapter.entity_id).where(
                Chapter.tenant_id == tenant_id, Chapter.entity_id.in_(allowed)
            )
        )
    )
    rows = await session.scalars(
        select(ManuscriptNumbering).where(
            ManuscriptNumbering.tenant_id == tenant_id, ManuscriptNumbering.entity_id.in_(allowed)
        )
    )
    settings = {r.entity_id: NumberingSettings.model_validate(r.settings) for r in rows}
    ordered = await composition_order(session, tenant_id, allowed, placements)
    return calculate(root, chapters, ordered, settings)


async def composition_order(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    allowed: set[uuid.UUID],
    placements: list[ManuscriptPlacement],
) -> dict[uuid.UUID, list[uuid.UUID]]:
    payloads = await session.execute(
        select(Payload.id, Payload.order)
        .join(Information, Information.id == Payload.information_id)
        .where(
            Payload.tenant_id == tenant_id,
            Information.entity_id.in_(allowed),
            Information.type == "manuscript",
        )
    )
    orders = {id: order for id, order in payloads.all()}
    links: dict[uuid.UUID, list[ManuscriptPlacement]] = defaultdict(list)
    for link in placements:
        if link.parent_entity_id in allowed and link.child_entity_id in allowed:
            links[link.parent_entity_id].append(link)
    ordered = {
        parent: [
            p.child_entity_id
            for p in sorted(
                children,
                key=lambda p: (
                    orders.get(p.before_payload_id, float("inf")),
                    p.position,
                    p.child_entity_id,
                ),
            )
        ]
        for parent, children in links.items()
    }
    return ordered
