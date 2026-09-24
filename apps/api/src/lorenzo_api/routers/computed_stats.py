"""Authoring computed stats - see ADR 0104/RFC 0016.

Tenant-admin tier (get_tenant_context), like stat definitions: a formula
defines what a stat *means* for every entity that inherits it, not a
per-character edit.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_entity_or_404,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    ComputedStatConflictError,
    ComputedStatCycleError,
    ComputedStatNotFoundError,
    InvalidComputedStatError,
    StatDefinitionNotFoundError,
)
from lorenzo_api.models import (
    ComputedStat,
    ComputedStatComparison,
    ComputedStatLinear,
    EntityStat,
    RoundMode,
    StatDefinition,
    StatValueType,
    VEffectiveStat,
)
from lorenzo_api.schemas.computed_stats import (
    ComparisonFormulaBody,
    ComputedStatDependentOut,
    ComputedStatOut,
    ComputedStatPreviewIn,
    ComputedStatPreviewOut,
    FormulaBody,
    LinearFormulaBody,
    PreviewInputOut,
)
from lorenzo_api.stat_evaluation import (
    ComparisonFormula,
    Formula,
    LinearFormula,
    evaluate,
    formula_of,
    input_ids,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["computed-stats"],
    dependencies=[Depends(get_tenant_context)],
)

_NUMERIC = (StatValueType.INT, StatValueType.FLOAT)


async def _get_stat_definition_or_404(
    session: SessionDep, stat_definition_id: uuid.UUID, tenant_id: uuid.UUID
) -> StatDefinition:
    stmt = (
        select(StatDefinition)
        .where(StatDefinition.id == stat_definition_id, StatDefinition.tenant_id == tenant_id)
        .options(selectinload(StatDefinition.enum_values))
    )
    stat_definition = (await session.execute(stmt)).scalar_one_or_none()
    if stat_definition is None:
        raise StatDefinitionNotFoundError(
            detail=f"No stat definition with id {stat_definition_id} in tenant {tenant_id}"
        )
    return stat_definition


async def _get_own_formula(
    session: SessionDep, *, entity_id: uuid.UUID, stat_definition_id: uuid.UUID
) -> ComputedStat | None:
    stmt = (
        select(ComputedStat)
        .where(
            ComputedStat.entity_id == entity_id,
            ComputedStat.stat_definition_id == stat_definition_id,
        )
        .options(selectinload(ComputedStat.linear), selectinload(ComputedStat.comparison))
        # updated_at is set by the database on write; a re-read in the same
        # session must replace the identity-map copy.
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _check_types(
    formula: Formula, target: StatDefinition, inputs: dict[uuid.UUID, StatDefinition]
) -> None:
    """ADR 0104's type rules for each kind."""

    def invalid(detail: str) -> InvalidComputedStatError:
        return InvalidComputedStatError(detail=f"Stat {target.name!r}: {detail}")

    if isinstance(formula, LinearFormula):
        source = inputs[formula.source_stat_definition_id]
        if source.value_type not in _NUMERIC:
            raise invalid(f"a linear formula reads a number, and {source.name!r} isn't one")
        if target.value_type not in _NUMERIC:
            raise invalid("a linear formula produces a number, so the stat must be int or float")
        if target.value_type is StatValueType.INT and formula.round_mode is RoundMode.NONE:
            raise invalid("an int stat needs a rounding mode other than 'none'")
        return

    if (formula.right_stat_definition_id is None) == (formula.right_constant is None):
        raise invalid(
            "a comparison needs exactly one of right_stat_definition_id or right_constant"
        )
    for operand_id in input_ids(formula):
        operand = inputs[operand_id]
        if operand.value_type not in _NUMERIC:
            raise invalid(f"a comparison reads numbers, and {operand.name!r} isn't one")
    if target.value_type is StatValueType.BOOL:
        if formula.true_value is not None or formula.false_value is not None:
            raise invalid("a bool stat takes the comparison's outcome; leave the result values out")
        return
    if target.value_type not in (StatValueType.TEXT, StatValueType.ENUM):
        raise invalid("a comparison produces a bool, text, or enum value")
    if formula.true_value is None or formula.false_value is None:
        raise invalid("a text or enum stat needs both true_value and false_value")
    if target.value_type is StatValueType.ENUM:
        allowed = {row.value for row in target.enum_values}
        for result in (formula.true_value, formula.false_value):
            if result not in allowed:
                raise invalid(f"{result!r} is not one of its allowed values")


async def _check_no_cycle(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    target_id: uuid.UUID,
    new_inputs: list[uuid.UUID],
) -> None:
    """ADR 0104: the graph is tenant-wide at the stat-definition level -
    an edge from each formula's stat to each stat it reads, across every
    entity. Conservative (it can reject formulas on unrelated entities that
    could never meet at runtime) but sound: any runtime cycle needs one
    here. A separate graph from entity_prototype's, which keeps its own
    trigger (ADR 0015).
    """
    stmt = (
        select(ComputedStat)
        .where(ComputedStat.tenant_id == tenant_id)
        .options(selectinload(ComputedStat.linear), selectinload(ComputedStat.comparison))
    )
    edges: dict[uuid.UUID, set[uuid.UUID]] = {}
    for row in (await session.execute(stmt)).scalars():
        if row.entity_id == entity_id and row.stat_definition_id == target_id:
            continue  # the formula being replaced
        edges.setdefault(row.stat_definition_id, set()).update(row.source_stat_definition_ids())
    edges.setdefault(target_id, set()).update(new_inputs)

    # Depth-first from the target: reaching it again closes a cycle.
    stack: list[tuple[uuid.UUID, list[uuid.UUID]]] = [(target_id, [target_id])]
    seen: set[uuid.UUID] = set()
    while stack:
        node, path = stack.pop()
        for successor in edges.get(node, ()):
            if successor == target_id:
                result = await session.execute(
                    select(StatDefinition.id, StatDefinition.name).where(
                        StatDefinition.id.in_([*path, target_id])
                    )
                )
                names = {row_id: name for row_id, name in result.tuples()}
                chain = " -> ".join(names.get(step, str(step)) for step in [*path, target_id])
                raise ComputedStatCycleError(detail=f"Formula dependencies would loop: {chain}")
            if successor not in seen:
                seen.add(successor)
                stack.append((successor, [*path, successor]))


async def _validate(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    target: StatDefinition,
    formula: Formula,
) -> dict[uuid.UUID, StatDefinition]:
    """Every write-time check (ADR 0104), shared by PUT and preview.
    Returns the input stat definitions by id."""
    ids = input_ids(formula)
    if target.id in ids:
        raise InvalidComputedStatError(detail=f"Stat {target.name!r} can't read itself")
    rows = (
        await session.execute(
            select(StatDefinition).where(
                StatDefinition.id.in_(ids), StatDefinition.tenant_id == tenant_id
            )
        )
    ).scalars()
    inputs = {row.id: row for row in rows}
    missing = [str(i) for i in ids if i not in inputs]
    if missing:
        raise InvalidComputedStatError(
            detail=f"Not a stat definition in this tenant: {', '.join(missing)}"
        )
    _check_types(formula, target, inputs)

    direct = await session.get(EntityStat, (entity_id, target.id))
    if direct is not None:
        raise ComputedStatConflictError(
            detail=(
                f"Entity {entity_id} has a direct value for {target.name!r}; "
                "clear it before giving it a formula"
            )
        )
    await _check_no_cycle(
        session, tenant_id=tenant_id, entity_id=entity_id, target_id=target.id, new_inputs=ids
    )
    return inputs


def _formula_from_body(body: LinearFormulaBody | ComparisonFormulaBody) -> Formula:
    return body.to_formula()


def _concrete_row(
    formula: Formula, *, entity_id: uuid.UUID, stat_definition_id: uuid.UUID, tenant_id: uuid.UUID
) -> ComputedStatLinear | ComputedStatComparison:
    key = {
        "entity_id": entity_id,
        "stat_definition_id": stat_definition_id,
        "tenant_id": tenant_id,
    }
    if isinstance(formula, LinearFormula):
        return ComputedStatLinear(
            **key,
            source_stat_definition_id=formula.source_stat_definition_id,
            multiplier=formula.multiplier,
            offset=formula.offset,
            round_mode=formula.round_mode.value,
        )
    assert isinstance(formula, ComparisonFormula)
    return ComputedStatComparison(
        **key,
        left_stat_definition_id=formula.left_stat_definition_id,
        comparator=formula.comparator.value,
        right_stat_definition_id=formula.right_stat_definition_id,
        right_constant=formula.right_constant,
        true_value=formula.true_value,
        false_value=formula.false_value,
    )


def _out(row: ComputedStat) -> ComputedStatOut:
    formula = formula_of(row)
    assert formula is not None
    return ComputedStatOut.from_row(row, formula)


@router.get("/entities/{entity_id}/computed-stats")
async def list_entity_computed_stats(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep
) -> list[ComputedStatOut]:
    """The formulas this entity holds itself - not inherited ones (ADR
    0104). Unpaginated: bounded by the tenant's stat definitions."""
    await get_entity_or_404(session, entity_id, tenant_id)
    stmt = (
        select(ComputedStat)
        .where(ComputedStat.entity_id == entity_id, ComputedStat.tenant_id == tenant_id)
        .options(selectinload(ComputedStat.linear), selectinload(ComputedStat.comparison))
        .order_by(ComputedStat.stat_definition_id)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_out(row) for row in rows if formula_of(row) is not None]


@router.put("/entities/{entity_id}/computed-stats/{stat_definition_id}")
async def set_computed_stat(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    body: Annotated[FormulaBody, Body()],
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ComputedStatOut:
    """Creates or replaces this entity's formula for one stat - ADR 0104.
    Check order: entity and stat definition (404), If-Match against the
    existing formula (412), then the formula itself - inputs, types, the
    direct-value conflict (409), and cycles (422). A kind change replaces
    the concrete row.
    """
    await get_entity_or_404(session, entity_id, tenant_id)
    target = await _get_stat_definition_or_404(session, stat_definition_id, tenant_id)
    existing = await _get_own_formula(
        session, entity_id=entity_id, stat_definition_id=stat_definition_id
    )
    if existing is not None:
        check_if_match(if_match, updated_at=existing.updated_at)
    formula = _formula_from_body(body)
    await _validate(
        session, tenant_id=tenant_id, entity_id=entity_id, target=target, formula=formula
    )

    concrete = _concrete_row(
        formula, entity_id=entity_id, stat_definition_id=stat_definition_id, tenant_id=tenant_id
    )
    if existing is None:
        existing = ComputedStat(
            entity_id=entity_id, stat_definition_id=stat_definition_id, tenant_id=tenant_id
        )
        session.add(existing)
        await session.flush()
    else:
        # Remove the old concrete row first: the new one reuses its key.
        existing.linear = None
        existing.comparison = None
        await session.flush()
        existing.updated_at = func.now()
    session.add(concrete)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="computed_stat.set",
        target_type="entity",
        target_id=entity_id,
        detail=f"stat_definition={stat_definition_id}, kind={body.kind}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)

    saved = await _get_own_formula(
        session, entity_id=entity_id, stat_definition_id=stat_definition_id
    )
    assert saved is not None
    response.headers["ETag"] = etag_for(saved.updated_at)
    return _out(saved)


@router.delete("/entities/{entity_id}/computed-stats/{stat_definition_id}", status_code=204)
async def delete_computed_stat(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Removes this entity's own formula; the stat is inherited (or
    unset) again - ADR 0104. Check the dependents lookup first: other
    formulas may read this stat."""
    await get_entity_or_404(session, entity_id, tenant_id)
    existing = await _get_own_formula(
        session, entity_id=entity_id, stat_definition_id=stat_definition_id
    )
    if existing is None:
        raise ComputedStatNotFoundError(
            detail=f"Entity {entity_id} has no formula of its own for {stat_definition_id}"
        )
    check_if_match(if_match, updated_at=existing.updated_at)
    await session.delete(existing)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="computed_stat.deleted",
        target_type="entity",
        target_id=entity_id,
        detail=f"stat_definition={stat_definition_id}",
    )
    await session.commit()


@router.post("/entities/{entity_id}/computed-stats/{stat_definition_id}/preview")
async def preview_computed_stat(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat_definition_id: uuid.UUID,
    session: SessionDep,
    body: ComputedStatPreviewIn | None = None,
) -> ComputedStatPreviewOut:
    """Evaluates a stat on this entity without saving anything - ADR 0104.
    With a formula, every write-time check runs first, then the unsaved
    formula is evaluated in place of whatever would otherwise resolve.
    Without one, it reports whatever currently resolves.
    """
    await get_entity_or_404(session, entity_id, tenant_id)
    target = await _get_stat_definition_or_404(session, stat_definition_id, tenant_id)
    stats = (
        (
            await session.execute(
                select(VEffectiveStat)
                .where(VEffectiveStat.entity_id == entity_id)
                .options(
                    selectinload(VEffectiveStat.stat_definition),
                    selectinload(VEffectiveStat.computed_stat).selectinload(ComputedStat.linear),
                    selectinload(VEffectiveStat.computed_stat).selectinload(
                        ComputedStat.comparison
                    ),
                )
            )
        )
        .scalars()
        .all()
    )

    formula: Formula | None
    if body is not None and body.formula is not None:
        formula = _formula_from_body(body.formula)
        await _validate(
            session, tenant_id=tenant_id, entity_id=entity_id, target=target, formula=formula
        )
        values = evaluate(stats, overrides={target.id: (formula, target.value_type)})
    else:
        values = evaluate(stats)
        winner = next((s for s in stats if s.stat_definition_id == target.id), None)
        if winner is None:
            return ComputedStatPreviewOut(
                stat_definition_id=target.id, value=None, source="unset", inputs=[]
            )
        if winner.computed_entity_id is None:
            return ComputedStatPreviewOut(
                stat_definition_id=target.id,
                value=values.get(target.id),
                source="direct",
                inputs=[],
            )
        formula = formula_of(winner.computed_stat) if winner.computed_stat else None

    inputs: list[PreviewInputOut] = []
    if formula is not None:
        ids = input_ids(formula)
        result = await session.execute(
            select(StatDefinition.id, StatDefinition.name).where(StatDefinition.id.in_(ids))
        )
        names = {row_id: name for row_id, name in result.tuples()}
        inputs = [
            PreviewInputOut(stat_definition_id=i, name=names.get(i, str(i)), value=values.get(i))
            for i in ids
        ]
    return ComputedStatPreviewOut(
        stat_definition_id=target.id,
        value=values.get(target.id),
        source="computed",
        inputs=inputs,
    )


@router.get("/stat-definitions/{stat_definition_id}/dependents")
async def list_stat_dependents(
    tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, session: SessionDep
) -> list[ComputedStatDependentOut]:
    """Every formula in the tenant that reads this stat - check before
    changing or removing it (ADR 0104, after ADR 0073's prototype reverse
    lookup)."""
    await _get_stat_definition_or_404(session, stat_definition_id, tenant_id)
    linear = (
        await session.execute(
            select(ComputedStatLinear.entity_id, ComputedStatLinear.stat_definition_id).where(
                ComputedStatLinear.source_stat_definition_id == stat_definition_id,
                ComputedStatLinear.tenant_id == tenant_id,
            )
        )
    ).tuples()
    comparison = (
        await session.execute(
            select(
                ComputedStatComparison.entity_id, ComputedStatComparison.stat_definition_id
            ).where(
                (ComputedStatComparison.left_stat_definition_id == stat_definition_id)
                | (ComputedStatComparison.right_stat_definition_id == stat_definition_id),
                ComputedStatComparison.tenant_id == tenant_id,
            )
        )
    ).tuples()
    dependents = [
        ComputedStatDependentOut(entity_id=e, stat_definition_id=s, kind="linear")
        for e, s in linear
    ] + [
        ComputedStatDependentOut(entity_id=e, stat_definition_id=s, kind="comparison")
        for e, s in comparison
    ]
    return sorted(dependents, key=lambda d: (str(d.entity_id), str(d.stat_definition_id)))
