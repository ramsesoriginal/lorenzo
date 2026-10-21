"""Resolve LorenzoScript dates without reading or creating period entries (ADR 0313)."""

import uuid

from fastapi import APIRouter, Depends
from lorenzo_calendar import CalendarDefinition
from lorenzo_calendar.references import parse_reference, resolve_reference
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_or_404
from lorenzo_api.models import Calendar
from lorenzo_api.routers.entities import resolve_slugs

router = APIRouter(
    prefix="/tenants/{tenant_id}/calendar-references",
    tags=["calendars"],
    dependencies=[Depends(get_tenant_or_404)],
)


class CalendarReferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expressions: list[str] = Field(min_length=1, max_length=100)


class CalendarReferenceOut(BaseModel):
    expression: str
    calendar_entity_id: uuid.UUID
    calendar_slug: str
    text: str
    year: int
    segment: str | None = None
    day: int | None = None


@router.post("/resolve")
async def resolve_calendar_references(
    tenant_id: uuid.UUID, body: CalendarReferencesIn, session: SessionDep, user: CurrentUser
) -> list[CalendarReferenceOut]:
    references = {}
    for expression in dict.fromkeys(body.expressions):
        if len(expression) > 1000:
            continue
        try:
            references[expression] = parse_reference(expression)
        except ValueError:
            continue
    # The existing resolver applies the combined existence/name audience gate.
    # It is called even for an invalid batch, to enforce membership consistently.
    found = await resolve_slugs(
        tenant_id=tenant_id,
        slug=list({r.calendar for r in references.values()}),
        session=session,
        user=user,
        home=None,
    )
    calendars = {e.slug: e for e in found if "calendar" in e.kinds}
    definitions = dict(
        (
            await session.execute(
                select(Calendar.entity_id, Calendar.definition).where(
                    Calendar.tenant_id == tenant_id,
                    Calendar.entity_id.in_([e.entity_id for e in calendars.values()]),
                )
            )
        )
        .tuples()
        .all()
    )
    result = []
    for expression, reference in references.items():
        calendar = calendars.get(reference.calendar)
        if calendar is None or calendar.entity_id not in definitions:
            continue
        try:
            segment, text = resolve_reference(
                CalendarDefinition.model_validate(definitions[calendar.entity_id]),
                reference,
            )
        except ValueError:
            continue
        result.append(
            CalendarReferenceOut(
                expression=expression,
                calendar_entity_id=calendar.entity_id,
                calendar_slug=calendar.slug,
                text=text,
                year=reference.year,
                segment=segment,
                day=reference.day,
            )
        )
    return result
