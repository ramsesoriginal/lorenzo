"""Reviewed calendar imports in one caller-owned transaction (ADR 0311).

No helper commits. Provenance stays local; imported entries are ordinary world content.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from lorenzo_calendar import CalendarDate, CalendarDefinition, segment_for, validate_recurrence
from lorenzo_calendar.document import Annotation, CalendarDocument, DocumentWarning
from sqlalchemy import Select, delete, func, select, text

from lorenzo_api.activity_log import record_activity
from lorenzo_api.author_guards import author_may_use_kinds
from lorenzo_api.calendar_periods import validate_materialized_periods
from lorenzo_api.client_ids import insert_with_client_id
from lorenzo_api.dependencies import CurrentUser, SessionDep
from lorenzo_api.description_payloads import write_description
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import require_visible_entry
from lorenzo_api.exceptions import (
    CalendarImportReviewRequiredError,
    ClientIdUnavailableError,
    PreconditionFailedError,
)
from lorenzo_api.models import (
    Calendar,
    CalendarImport,
    CalendarObservance,
    CalendarPeriod,
    Entity,
    EntityAudience,
    EntityKnowledge,
    EntryCalendarPeriod,
    Fact,
    Information,
    Knowledge,
    Payload,
    StoryEvent,
)
from lorenzo_api.routers.calendar_periods import PeriodCreate, materialize
from lorenzo_api.routers.calendars import read_calendar
from lorenzo_api.routers.entities import (
    authorize_entity_write,
    authorize_information_edit,
    get_information_or_404,
)
from lorenzo_api.schemas.calendar_imports import (
    CalendarImportApply,
    CalendarImportChange,
    CalendarImportPlan,
    CalendarImportReceipt,
    CalendarImportRequest,
)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            default=str,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def chosen_id(tenant_id: uuid.UUID, source: str, key: str) -> uuid.UUID:
    return uuid.uuid5(tenant_id, f"calendar-import:{source}:{key}")


def units_of(request: CalendarImportRequest) -> dict[str, list[Annotation]]:
    units: dict[str, list[Annotation]] = {}
    for annotation in request.document.annotations:
        key = annotation.classification + ":" + (annotation.group or annotation.key)
        units.setdefault(key, []).append(annotation)
    for values in units.values():
        values.sort(key=lambda a: a.key)
    return units


async def state_for(
    session: SessionDep, tenant_id: uuid.UUID, source_key: str
) -> CalendarImport | None:
    return cast(
        CalendarImport | None,
        await session.scalar(
            select(CalendarImport)
            .where(CalendarImport.tenant_id == tenant_id, CalendarImport.source_key == source_key)
            .execution_options(populate_existing=True)
        ),
    )


async def lock_source(session: SessionDep, tenant_id: uuid.UUID, source_key: str) -> None:
    lock = int.from_bytes(
        hashlib.sha256(f"{tenant_id}:{source_key}".encode()).digest()[:8], signed=True
    )
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})


async def period_ids(
    session: SessionDep, tenant_id: uuid.UUID, calendar_id: uuid.UUID
) -> set[uuid.UUID]:
    return set(
        await session.scalars(
            select(CalendarPeriod.entity_id).where(
                CalendarPeriod.tenant_id == tenant_id,
                CalendarPeriod.calendar_entity_id == calendar_id,
            )
        )
    )


async def authorize_state(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, state: CalendarImport | None
) -> None:
    if state is None:
        return
    await read_calendar(session, user, tenant_id, state.calendar_entity_id)
    await authorize_entity_write(
        session, entity_id=state.calendar_entity_id, tenant_id=tenant_id, user=user
    )
    for binding in state.bindings.values():
        entity_id = uuid.UUID(binding["entity"])
        await require_visible_entry(
            session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id
        )
        await authorize_entity_write(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
        dates = await session.scalars(
            select(EntryCalendarPeriod.period_entity_id).where(
                EntryCalendarPeriod.entity_id == entity_id,
                EntryCalendarPeriod.tenant_id == tenant_id,
            )
        )
        for date_id in dates:
            await require_visible_entry(
                session, entity_id=date_id, tenant_id=tenant_id, user_id=user.id
            )
        for annotation in binding.get("annotations", {}).values():
            information = await get_information_or_404(
                session, uuid.UUID(annotation["information"]), tenant_id
            )
            await authorize_information_edit(
                session, information=information, tenant_id=tenant_id, user=user
            )


async def fingerprint(session: SessionDep, tenant_id: uuid.UUID, binding: dict[str, Any]) -> str:
    entity_id = uuid.UUID(binding["entity"])
    info_ids = [uuid.UUID(a["information"]) for a in binding.get("annotations", {}).values()]
    values: dict[str, Any] = {}
    queries: dict[str, Select[Any]] = {
        "entry": select(Entity.id, Entity.name, Entity.updated_at).where(
            Entity.id == entity_id, Entity.tenant_id == tenant_id
        ),
        "audience": select(EntityAudience.is_public, EntityAudience.updated_at).where(
            EntityAudience.entity_id == entity_id, EntityAudience.tenant_id == tenant_id
        ),
        "grants": select(
            EntityKnowledge.id, EntityKnowledge.knower_entity_id, EntityKnowledge.knower_player_id
        )
        .where(EntityKnowledge.entity_id == entity_id, EntityKnowledge.tenant_id == tenant_id)
        .order_by(EntityKnowledge.id),
        "information": select(
            Information.id,
            Information.entity_id,
            Information.title,
            Information.type,
            Information.order,
            Information.is_public,
            Information.updated_at,
        )
        .where(Information.id.in_(info_ids), Information.tenant_id == tenant_id)
        .order_by(Information.id),
        "payloads": select(Payload.id, Payload.order, Payload.updated_at)
        .where(Payload.information_id.in_(info_ids), Payload.tenant_id == tenant_id)
        .order_by(Payload.id),
        "knowledge": select(
            Knowledge.id,
            Knowledge.knower_entity_id,
            Knowledge.knower_player_id,
            Knowledge.updated_at,
        )
        .where(Knowledge.information_id.in_(info_ids), Knowledge.tenant_id == tenant_id)
        .order_by(Knowledge.id),
        "dates": select(EntryCalendarPeriod.period_entity_id)
        .where(
            EntryCalendarPeriod.entity_id == entity_id, EntryCalendarPeriod.tenant_id == tenant_id
        )
        .order_by(EntryCalendarPeriod.period_entity_id),
        "calendar": select(Calendar.definition, Calendar.updated_at).where(
            Calendar.entity_id == entity_id, Calendar.tenant_id == tenant_id
        ),
        "rule": select(CalendarObservance.rule).where(
            CalendarObservance.entity_id == entity_id, CalendarObservance.tenant_id == tenant_id
        ),
    }
    for key, query in queries.items():
        values[key] = [list(row) for row in (await session.execute(query)).all()]
    return digest(values)


@dataclass
class Prepared:
    state: CalendarImport | None
    units: dict[str, list[Annotation]]
    plan: CalendarImportPlan
    request_hash: str
    actual: dict[str, str]


async def prepare(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, request: CalendarImportRequest
) -> Prepared:
    await author_may_use_kinds(session, tenant_id=tenant_id, user_id=user.id, kinds=["calendar"])
    state = await state_for(session, tenant_id, request.document.source_key)
    await authorize_state(session, user, tenant_id, state)
    calendar_id = (
        state.calendar_entity_id
        if state
        else chosen_id(tenant_id, request.document.source_key, "calendar")
    )
    units = units_of(request)
    bindings = state.bindings if state else {}
    expected_keys = {"$calendar", *units}
    if set(request.resolutions) - expected_keys:
        raise CalendarImportReviewRequiredError(
            detail="Resolve only changes named by this import plan"
        )
    desired = {
        "$calendar": digest(
            {
                "name": request.document.name,
                "definition": request.document.definition.model_dump(mode="json"),
                "is_public": request.document.is_public,
                "period_is_public": request.document.period_is_public,
            }
        )
    }
    desired.update(
        {
            key: digest([a.model_dump(mode="json") for a in annotations])
            for key, annotations in units.items()
        }
    )
    actual = {
        key: await fingerprint(session, tenant_id, binding) for key, binding in bindings.items()
    }
    changes = []
    old_annotation_units = {
        a: key for key, binding in bindings.items() for a in binding.get("annotations", {})
    }
    for key, wanted in desired.items():
        binding = bindings.get(key)
        if binding is None:
            reclassified = key in units and any(a.key in old_annotation_units for a in units[key])
            changes.append(
                CalendarImportChange(
                    key=key,
                    action="conflict" if reclassified else "create",
                    reason="Classification/grouping changed; taking the source creates new "
                    "material and retains the former entries"
                    if reclassified
                    else None,
                    resolution=request.resolutions.get(key),
                )
            )
        elif wanted != binding["desired"] or actual[key] != binding["fingerprint"]:
            changes.append(
                CalendarImportChange(
                    key=key,
                    action="conflict",
                    reason="Source or local authored material changed",
                    resolution=request.resolutions.get(key),
                )
            )
        else:
            changes.append(CalendarImportChange(key=key, action="unchanged"))
    changes.extend(
        CalendarImportChange(
            key=key,
            action="retained",
            reason="Omitted source material is retained; import never deletes it",
        )
        for key in bindings
        if key not in desired
    )
    calendar_change = next(c for c in changes if c.key == "$calendar")
    effective = request.document.definition
    if state:
        current_calendar, _ = await read_calendar(session, user, tenant_id, calendar_id)
        if calendar_change.action == "conflict" and calendar_change.resolution == "take_source":
            await validate_materialized_periods(session, tenant_id, calendar_id, effective)
        else:
            effective = CalendarDefinition.model_validate(current_calendar.definition)
    for change in changes:
        if (
            change.key not in units
            or change.action in {"retained", "unchanged"}
            or change.resolution == "keep_local"
        ):
            continue
        for annotation in units[change.key]:
            try:
                segment_for(effective, annotation.date)
                if annotation.recurrence is not None:
                    validate_recurrence(effective, annotation.recurrence)
            except ValueError:
                change.action = "conflict"
                change.resolution = None
                change.reason = (
                    "This annotation does not fit the effective local definition; "
                    "revise it or keep the existing material"
                )
    warnings = sorted({w.key for w in request.document.warnings} - set(request.accepted_warnings))
    request_hash = digest(request.model_dump(mode="json", exclude={"token"}))
    token = digest(
        {
            "tenant": str(tenant_id),
            "calendar": str(calendar_id),
            "request": request_hash,
            "actual": actual,
            "periods": sorted(str(p) for p in await period_ids(session, tenant_id, calendar_id)),
            "revision": str(state.updated_at) if state else None,
        }
    )
    plan = CalendarImportPlan(
        source_key=request.document.source_key,
        calendar_entity_id=calendar_id,
        token=token,
        changes=changes,
        unaccepted_warnings=warnings,
        ready=not warnings
        and not any(c.action == "conflict" and c.resolution is None for c in changes),
    )
    return Prepared(state, units, plan, request_hash, actual)


async def lock_current(session: SessionDep, tenant_id: uuid.UUID, prepared: Prepared) -> None:
    calendar_id = prepared.plan.calendar_entity_id
    existing_periods = await period_ids(session, tenant_id, calendar_id)
    bindings = prepared.state.bindings if prepared.state else {}
    entities = {
        calendar_id,
        *existing_periods,
        *(uuid.UUID(b["entity"]) for b in bindings.values()),
    }
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant_id, Entity.id.in_(entities))
        .order_by(Entity.id)
        .with_for_update()
    )
    await session.execute(
        select(Calendar.entity_id)
        .where(Calendar.tenant_id == tenant_id, Calendar.entity_id == calendar_id)
        .with_for_update()
    )
    infos = [
        uuid.UUID(a["information"])
        for b in bindings.values()
        for a in b.get("annotations", {}).values()
    ]
    await session.execute(
        select(Information.id)
        .where(Information.tenant_id == tenant_id, Information.id.in_(infos))
        .order_by(Information.id)
        .with_for_update()
    )
    await session.execute(
        select(Payload.id)
        .where(Payload.tenant_id == tenant_id, Payload.information_id.in_(infos))
        .order_by(Payload.id)
        .with_for_update()
    )
    if existing_periods != await period_ids(session, tenant_id, calendar_id):
        raise PreconditionFailedError(
            detail="Recorded periods changed while reviewing the import; plan it again"
        )


async def write_information(
    session: SessionDep,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    entity_id: uuid.UUID,
    source_key: str,
    unit: str,
    annotation: Annotation,
    binding: dict[str, Any] | None,
) -> dict[str, str]:
    info_id = (
        uuid.UUID(binding["information"])
        if binding
        else chosen_id(tenant_id, source_key, f"{unit}:{annotation.key}:information")
    )
    payload_id = (
        uuid.UUID(binding["payload"])
        if binding
        else chosen_id(tenant_id, source_key, f"{unit}:{annotation.key}:payload")
    )
    if binding:
        information = await get_information_or_404(session, info_id, tenant_id)
        payload = next((p for p in information.payloads if p.id == payload_id), None)
        if payload is None or payload.description is None:
            raise CalendarImportReviewRequiredError(
                detail="An original imported text payload was removed; "
                "resolve it in the entry before reimporting"
            )
        if information.entity_id != entity_id:
            last = await session.scalar(
                select(func.max(Information.order)).where(
                    Information.entity_id == entity_id, Information.tenant_id == tenant_id
                )
            )
            information.order = (last if last is not None else -1) + 1
            information.entity_id = entity_id
        information.title = annotation.title or "Imported note"
        information.is_public = annotation.information_is_public
        information.updated_at = datetime.now(UTC)
    else:
        information = Information(
            id=info_id,
            tenant_id=tenant_id,
            entity_id=entity_id,
            title=annotation.title or "Imported note",
            type="note",
            is_public=annotation.information_is_public,
            created_by=user.id,
        )
        await insert_with_client_id(session, information)
        payload = Payload(id=payload_id, tenant_id=tenant_id, information_id=info_id)
        await write_description(session, payload=payload, content=annotation.text, locale="und")
        await insert_with_client_id(session, payload)
    await write_description(session, payload=payload, content=annotation.text, locale="und")
    await session.flush()
    return {"information": str(info_id), "payload": str(payload_id)}


async def write_unit(
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    request: CalendarImportRequest,
    calendar_id: uuid.UUID,
    key: str,
    annotations: list[Annotation],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    first = annotations[0]
    periods = {}
    if first.classification != "observance":
        for annotation in annotations:
            period, _ = await materialize(
                session,
                user,
                tenant_id,
                calendar_id,
                PeriodCreate(
                    **annotation.date.model_dump(), is_public=request.document.period_is_public
                ),
            )
            periods[annotation.key] = period.entity_id
    if first.classification == "note":
        entity_id = periods[first.key]
    elif previous:
        entity_id = uuid.UUID(previous["entity"])
    else:
        entity_id = chosen_id(tenant_id, request.document.source_key, key)
        if await session.get(Entity, entity_id) is not None:
            raise ClientIdUnavailableError(detail="That id is not available")
        created_entry = await create_entry(
            session,
            tenant_id=tenant_id,
            user_id=user.id,
            name=first.title or first.text.strip().splitlines()[0][:200],
            slug=None,
            kinds=[],
            parents=[],
            in_public_catalog=False,
            entity_id=entity_id,
        )
        assert first.classification != "observance" or first.recurrence is not None
        marker = (
            Fact(entity_id=entity_id, tenant_id=tenant_id)
            if first.classification == "fact"
            else StoryEvent(entity_id=entity_id, tenant_id=tenant_id)
            if first.classification == "event"
            else CalendarObservance(
                entity_id=entity_id,
                tenant_id=tenant_id,
                calendar_entity_id=calendar_id,
                rule=first.recurrence.model_dump(mode="json")
                if first.recurrence is not None
                else {},
            )
        )
        session.add_all(
            [
                marker,
                EntityAudience(
                    entity_id=created_entry.id, tenant_id=tenant_id, is_public=first.is_public
                ),
            ]
        )
        await session.flush()
    session.info.pop("visible_entry_checks", None)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    if first.classification != "note":
        entry = await session.get(Entity, entity_id)
        assert entry is not None
        entry.name = first.title or first.text.strip().splitlines()[0][:200]
        entry.updated_at = datetime.now(UTC)
        entry.updated_by = user.id
        audience = await session.get(EntityAudience, entity_id)
        assert audience is not None
        audience.is_public = first.is_public
        if first.classification == "observance":
            observance = await session.get(CalendarObservance, entity_id)
            assert observance is not None and first.recurrence is not None
            observance.rule = first.recurrence.model_dump(mode="json")
        else:
            await session.execute(
                delete(EntryCalendarPeriod).where(
                    EntryCalendarPeriod.entity_id == entity_id,
                    EntryCalendarPeriod.tenant_id == tenant_id,
                )
            )
            session.add_all(
                [
                    EntryCalendarPeriod(
                        entity_id=entity_id, period_entity_id=p, tenant_id=tenant_id
                    )
                    for p in set(periods.values())
                ]
            )
    result: dict[str, Any] = {
        "entity": str(entity_id),
        "annotations": dict(previous.get("annotations", {})) if previous else {},
    }
    for annotation in annotations:
        old = previous.get("annotations", {}).get(annotation.key) if previous else None
        result["annotations"][annotation.key] = await write_information(
            session, tenant_id, user, entity_id, request.document.source_key, key, annotation, old
        )
    await session.flush()
    return result


async def apply_import(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, request: CalendarImportApply
) -> CalendarImportReceipt:
    await lock_source(session, tenant_id, request.document.source_key)
    prepared = await prepare(session, user, tenant_id, request)
    await lock_current(session, tenant_id, prepared)
    session.info.pop("visible_entry_checks", None)
    prepared = await prepare(session, user, tenant_id, request)
    state = prepared.state
    if (
        state
        and state.last_token == request.token
        and state.last_request_hash == prepared.request_hash
    ):
        return CalendarImportReceipt.model_validate(state.receipt)
    if request.token != prepared.plan.token:
        raise PreconditionFailedError(
            detail="The import plan is stale; read the file and local changes again"
        )
    if not prepared.plan.ready:
        raise CalendarImportReviewRequiredError(
            detail="Acknowledge warnings and resolve each conflict in the import plan"
        )
    bindings = {key: dict(value) for key, value in state.bindings.items()} if state else {}
    receipt = CalendarImportReceipt(
        source_key=request.document.source_key,
        calendar_entity_id=prepared.plan.calendar_entity_id,
        created=[],
        changed=[],
        unchanged=[],
        kept_local=[],
        retained=[],
    )
    calendar_id = receipt.calendar_entity_id
    calendar_change = next(c for c in prepared.plan.changes if c.key == "$calendar")
    if calendar_change.action == "create":
        if await session.get(Entity, calendar_id) is not None:
            raise ClientIdUnavailableError(detail="That id is not available")
        entry = await create_entry(
            session,
            tenant_id=tenant_id,
            user_id=user.id,
            name=request.document.name,
            slug=None,
            kinds=[],
            parents=[],
            in_public_catalog=False,
            entity_id=calendar_id,
        )
        session.add_all(
            [
                Calendar(
                    entity_id=calendar_id,
                    tenant_id=tenant_id,
                    definition=request.document.definition.model_dump(mode="json"),
                ),
                EntityAudience(
                    entity_id=calendar_id, tenant_id=tenant_id, is_public=request.document.is_public
                ),
            ]
        )
        await session.flush()
        session.info.pop("visible_entry_checks", None)
        await require_visible_entry(
            session, entity_id=calendar_id, tenant_id=tenant_id, user_id=user.id
        )
        bindings["$calendar"] = {"entity": str(calendar_id), "annotations": {}}
    elif calendar_change.action == "conflict" and calendar_change.resolution == "take_source":
        calendar, entry = await read_calendar(session, user, tenant_id, calendar_id, lock=True)
        await validate_materialized_periods(
            session, tenant_id, calendar_id, request.document.definition
        )
        calendar.definition = request.document.definition.model_dump(mode="json")
        calendar.updated_at = datetime.now(UTC)
        entry.name = request.document.name
        entry.updated_at = calendar.updated_at
        entry.updated_by = user.id
        audience = await session.get(EntityAudience, calendar_id)
        assert audience is not None
        audience.is_public = request.document.is_public
    for change in prepared.plan.changes:
        if change.action == "retained":
            receipt.retained.append(change.key)
            continue
        if change.action == "conflict" and change.resolution == "keep_local":
            receipt.kept_local.append(change.key)
        elif change.action == "unchanged":
            receipt.unchanged.append(change.key)
        else:
            if change.key != "$calendar":
                bindings[change.key] = await write_unit(
                    session,
                    user,
                    tenant_id,
                    request,
                    calendar_id,
                    change.key,
                    prepared.units[change.key],
                    bindings.get(change.key),
                )
            (receipt.created if change.action == "create" else receipt.changed).append(change.key)
        if change.key == "$calendar":
            bindings[change.key]["desired"] = digest(
                {
                    "name": request.document.name,
                    "definition": request.document.definition.model_dump(mode="json"),
                    "is_public": request.document.is_public,
                    "period_is_public": request.document.period_is_public,
                }
            )
        else:
            # A newly reclassified unit kept local stays absent; a future take_source can create it.
            if change.key not in bindings:
                continue
            bindings[change.key]["desired"] = digest(
                [a.model_dump(mode="json") for a in prepared.units[change.key]]
            )
    await session.flush()
    for binding in bindings.values():
        binding["fingerprint"] = await fingerprint(session, tenant_id, binding)
    if state is None:
        state = CalendarImport(
            tenant_id=tenant_id,
            source_key=request.document.source_key,
            calendar_entity_id=calendar_id,
            document={},
            bindings={},
            receipt={},
        )
        session.add(state)
    state.document = request.document.model_dump(mode="json")
    state.bindings = bindings
    state.last_token = request.token
    state.last_request_hash = prepared.request_hash
    state.receipt = receipt.model_dump(mode="json")
    state.updated_at = datetime.now(UTC)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="calendar.imported",
        target_type="entity",
        target_id=calendar_id,
    )
    await session.flush()
    return receipt


async def export_document(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, source_key: str
) -> CalendarDocument:
    from lorenzo_api.exceptions import EntityNotFoundError

    state = await state_for(session, tenant_id, source_key)
    if state is None:
        raise EntityNotFoundError(detail="No calendar import with that source key in this library")
    await authorize_state(session, user, tenant_id, state)
    document = CalendarDocument.model_validate(state.document)
    calendar, entry = await read_calendar(session, user, tenant_id, state.calendar_entity_id)
    definition = CalendarDefinition.model_validate(calendar.definition)
    annotations = []
    source_units = units_of(CalendarImportRequest(document=document))
    for key, source_annotations in source_units.items():
        binding = state.bindings.get(key)
        if binding is None:
            raise CalendarImportReviewRequiredError(
                detail="Resolve pending classifications before exporting this source"
            )
        if source_annotations[0].classification in {"event", "fact"}:
            dates = (
                await session.scalars(
                    select(CalendarPeriod)
                    .join(
                        EntryCalendarPeriod,
                        EntryCalendarPeriod.period_entity_id == CalendarPeriod.entity_id,
                    )
                    .where(
                        EntryCalendarPeriod.entity_id == uuid.UUID(binding["entity"]),
                        EntryCalendarPeriod.tenant_id == tenant_id,
                    )
                )
            ).all()
            actual_dates = {(p.year, p.segment, p.day) for p in dates}
            expected = {(a.date.year, a.date.segment, a.date.day) for a in source_annotations}
            if actual_dates != expected:
                raise CalendarImportReviewRequiredError(
                    detail="Date associations changed outside this source; "
                    "review their mapping before exporting"
                )
        for annotation in source_annotations:
            linked = binding.get("annotations", {}).get(annotation.key)
            if linked is None:
                raise CalendarImportReviewRequiredError(
                    detail="A source annotation has no local information binding"
                )
            information = await get_information_or_404(
                session, uuid.UUID(linked["information"]), tenant_id
            )
            if len(information.payloads) != 1 or information.payloads[0].description is None:
                raise CalendarImportReviewRequiredError(
                    detail="This source export supports its single text payloads; "
                    "preserve expanded bundles separately"
                )
            payload = information.payloads[0].description
            assert payload is not None
            value = annotation.model_dump(mode="json")
            value.update(text=payload.content, information_is_public=information.is_public)
            if annotation.classification == "note":
                period = await session.get(CalendarPeriod, information.entity_id)
                if period is None or period.segment is None or period.day is None:
                    raise CalendarImportReviewRequiredError(
                        detail="A dated note no longer belongs to a day period"
                    )
                value["date"] = CalendarDate(
                    year=period.year, segment=period.segment, day=period.day
                ).model_dump(mode="json")
                value["title"] = (
                    None
                    if annotation.title is None and information.title == "Imported note"
                    else information.title
                )
            else:
                target = await session.get(Entity, uuid.UUID(binding["entity"]))
                assert target is not None
                audience = await session.get(EntityAudience, target.id)
                assert audience is not None
                title = (
                    None
                    if annotation.title is None
                    and target.name == annotation.text.strip().splitlines()[0][:200]
                    else target.name
                )
                value.update(title=title, is_public=audience.is_public)
                if annotation.classification == "observance":
                    observance = await session.get(CalendarObservance, target.id)
                    assert observance is not None
                    value["recurrence"] = observance.rule
            annotations.append(Annotation.model_validate(value))
    source = dict(document.source)
    source["export_scope"] = (
        "Managed import annotations only; omitted/extra local material is retained in the library"
    )
    warnings = {w.key: w for w in document.warnings}
    if set(state.bindings) - {"$calendar", *source_units}:
        warnings["retained-material"] = DocumentWarning(
            key="retained-material",
            message="This file covers active managed annotations; formerly imported "
            "material remains in the original library.",
        )
    audience = await session.get(EntityAudience, calendar.entity_id)
    assert audience is not None
    return CalendarDocument(
        source_key=document.source_key,
        name=entry.name,
        definition=definition,
        annotations=tuple(annotations),
        source=source,
        warnings=tuple(warnings.values()),
        is_public=audience.is_public,
        period_is_public=document.period_is_public,
    )
