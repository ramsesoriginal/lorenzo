"""The bulk write of relationships and their standings (ADR 0400): the writer of the matrix.

At most a hundred operations in one transaction. Each end and each relationship is resolved under
the writer's own visibility, a refusal of any operation refuses the request and writes nothing, and
the answer is the rows as written."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from rfc9457 import Problem
from sqlalchemy import select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
)
from lorenzo_api.entity_kinds import require_deletable
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import EntityNotFoundError
from lorenzo_api.library_counts import count_libraries, libraries_note
from lorenzo_api.models import Entity, EntityStat, Relationship, StatDefinition
from lorenzo_api.relationships import require_relationship_room
from lorenzo_api.routers.entity_stats import (
    _get_stat_definition_or_404,
    _touch,
    _validate_value,
    _write_own_value,
)
from lorenzo_api.routers.locations import require_manager
from lorenzo_api.routers.relationships import (
    RelationshipCreate,
    RelationshipOut,
    _after_write,
    _commit,
    add_relationship,
)

#: The most operations one request may hold.
MAX_OPERATIONS = 100
#: The most standings one created relationship may carry.
MAX_CREATE_STATS = 20

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["relationships"],
    dependencies=[Depends(get_tenant_or_404)],
)

_NOT_FOUND = "No such relationship in this library"


class StatWrite(BaseModel):
    """A standing to set on a relationship made in the same request."""

    model_config = ConfigDict(extra="forbid")
    stat_definition_id: uuid.UUID
    value: int | str | float | bool


class CreateOperation(RelationshipCreate):
    """Make a relationship, as `POST /relationships` does, with its standings."""

    op: Literal["create"]
    stats: list[StatWrite] = Field(default_factory=list, max_length=MAX_CREATE_STATS)


class SetOperation(BaseModel):
    """Set one own standing of a relationship; `if_match` is the relationship's ETag."""

    model_config = ConfigDict(extra="forbid")
    op: Literal["set"]
    relationship_id: uuid.UUID
    stat_definition_id: uuid.UUID
    value: int | str | float | bool
    if_match: str


class ClearOperation(BaseModel):
    """Remove one own standing of a relationship, keeping the relationship."""

    model_config = ConfigDict(extra="forbid")
    op: Literal["clear"]
    relationship_id: uuid.UUID
    stat_definition_id: uuid.UUID
    if_match: str


class DeleteOperation(BaseModel):
    """Delete a relationship."""

    model_config = ConfigDict(extra="forbid")
    op: Literal["delete"]
    relationship_id: uuid.UUID
    if_match: str


Operation = Annotated[
    CreateOperation | SetOperation | ClearOperation | DeleteOperation, Field(discriminator="op")
]


class RelationshipBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operations: list[Operation] = Field(min_length=1, max_length=MAX_OPERATIONS)


class BulkResult(BaseModel):
    index: int
    op: Literal["create", "set", "clear", "delete"]
    relationship_id: uuid.UUID
    # The relationship as written; null once it is deleted.
    relationship: RelationshipOut | None


class RelationshipBulkResponse(BaseModel):
    results: list[BulkResult]


async def _set_stat(
    session: SessionDep,
    user: CurrentUser,
    tenant: uuid.UUID,
    entity: Entity,
    stat_definition_id: uuid.UUID,
    value: int | str | float | bool,
    definitions: dict[uuid.UUID, StatDefinition],
) -> None:
    definition = definitions.get(stat_definition_id)
    if definition is None:
        definition = await _get_stat_definition_or_404(session, stat_definition_id, tenant)
        definitions[stat_definition_id] = definition
    await _validate_value(session, value, definition)
    await _write_own_value(
        session,
        entity=entity,
        user=user,
        tenant_id=tenant,
        entity_id=entity.id,
        stat_definition=definition,
        value=value,
        if_match=None,
        acquire_group=True,
    )


async def _apply(
    session: SessionDep,
    user: CurrentUser,
    tenant: uuid.UUID,
    operation: CreateOperation | SetOperation | ClearOperation | DeleteOperation,
    *,
    seen: dict[uuid.UUID, Entity],
    versions: dict[uuid.UUID, Any],
    definitions: dict[uuid.UUID, StatDefinition],
) -> uuid.UUID:
    """One operation, in the writer's transaction. Returns the relationship it was about."""
    if isinstance(operation, CreateOperation):
        entity = await add_relationship(
            session,
            user,
            tenant,
            RelationshipCreate(**operation.model_dump(exclude={"op", "stats"})),
        )
        for stat in operation.stats:
            await _set_stat(
                session, user, tenant, entity, stat.stat_definition_id, stat.value, definitions
            )
        return entity.id
    target = seen.get(operation.relationship_id)
    if target is None:
        raise EntityNotFoundError(detail=_NOT_FOUND)
    check_if_match(operation.if_match, updated_at=versions[target.id])
    if isinstance(operation, SetOperation):
        await _set_stat(
            session,
            user,
            tenant,
            target,
            operation.stat_definition_id,
            operation.value,
            definitions,
        )
    elif isinstance(operation, ClearOperation):
        await _get_stat_definition_or_404(session, operation.stat_definition_id, tenant)
        existing = await session.get(EntityStat, (target.id, operation.stat_definition_id))
        if existing is not None:
            await session.delete(existing)
            _touch(target, user)
    else:
        kinds = await require_deletable(session, tenant_id=tenant, entity_id=target.id)
        await record_activity(
            session,
            tenant_id=tenant,
            actor_id=user.id,
            action="entity.deleted",
            target_type="entity",
            target_id=target.id,
            detail=f"kinds={'+'.join(sorted(kinds)) or 'none'}"
            + libraries_note(await count_libraries(session, tenant, "entity", target.id)),
        )
        await session.delete(target)
    return operation.relationship_id


@router.post("/relationships/bulk")
async def write_relationships(
    tenant_id: uuid.UUID,
    body: RelationshipBulkRequest,
    session: SessionDep,
    user: CurrentUser,
) -> RelationshipBulkResponse:
    """Makes, sets, clears and deletes up to a hundred things at once, or none of them (ADR 0400).

    An operation that is refused refuses the request with that operation's own problem (its status
    and type) and its position as `operation`, and nothing is written. A relationship is addressed
    by the ETag it was read at; a request holds every operation to that version, so two standings
    of one relationship can go in together."""
    vis = await require_manager(session, user, tenant_id)
    creating = sum(1 for operation in body.operations if isinstance(operation, CreateOperation))
    if creating:
        await require_relationship_room(session, tenant_id=tenant_id, adding=creating)
    wanted = {
        operation.relationship_id
        for operation in body.operations
        if not isinstance(operation, CreateOperation)
    }
    seen: dict[uuid.UUID, Entity] = {}
    versions: dict[uuid.UUID, Any] = {}
    if wanted:
        found = await session.scalars(
            select(Entity)
            .join(Relationship, Relationship.entity_id == Entity.id)
            .where(
                Entity.tenant_id == tenant_id,
                Entity.id.in_(wanted),
                visible_entry_clause(vis, Entity.id),
            )
        )
        for entity in found:
            seen[entity.id] = entity
            versions[entity.id] = entity.updated_at
    definitions: dict[uuid.UUID, StatDefinition] = {}
    written: list[uuid.UUID] = []
    for index, operation in enumerate(body.operations):
        try:
            written.append(
                await _apply(
                    session,
                    user,
                    tenant_id,
                    operation,
                    seen=seen,
                    versions=versions,
                    definitions=definitions,
                )
            )
        except Problem as problem:
            raise Problem(
                title=problem.title,
                type_=problem.type,
                detail=f"Operation {index}: {problem.detail}",
                status=problem.status,
                headers=problem.headers,
                operation=index,
            ) from problem
    await _commit(session, tenant_id)
    results: list[BulkResult] = []
    for index, (operation, identity) in enumerate(zip(body.operations, written, strict=True)):
        deleted = isinstance(operation, DeleteOperation)
        results.append(
            BulkResult(
                index=index,
                op=operation.op,
                relationship_id=identity,
                relationship=None
                if deleted
                else await _after_write(session, vis, tenant_id, identity),
            )
        )
    return RelationshipBulkResponse(results=results)
