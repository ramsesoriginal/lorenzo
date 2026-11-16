"""The grant rules of a library, and the prerequisites of a feature - ADR 0455, RFC 0054.

A rule hangs on a source entry and says which features a holder that has the entry as an ancestor
(or holds an active instance of it) is entitled to; a prerequisite is what a holder needs to have a
feature at all. Authoring is the vocabulary's tier, as the stats' and the templates': any member of
the library, an Author too, and a deletion an administrator's. Nothing here grants: that is the
apply of a later slice (ADR 0456).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_admin_context,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import unhidden
from lorenzo_api.exceptions import (
    FeatureNotFoundError,
    GrantRuleNotFoundError,
    InvalidGrantRuleError,
)
from lorenzo_api.features import usable_feature
from lorenzo_api.information_visibility import (
    InformationVisibility,
    resolve_information_visibility,
)
from lorenzo_api.models import (
    Entity,
    Feature,
    FeaturePrerequisite,
    GrantRule,
    GrantRuleCondition,
    GrantRuleOption,
    StatDefinition,
    StatValueType,
)
from lorenzo_api.routers.stats import _vocabulary_gate
from lorenzo_api.schemas.grant_rules import (
    ComparisonIn,
    ComparisonOut,
    ConditionIn,
    ConditionOut,
    GrantRuleIn,
    GrantRuleOut,
    GrantRuleUpdate,
    PrerequisitesIn,
    PrerequisitesOut,
    RuleOptionOut,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}/grant-rules",
    tags=["grant-rules"],
    dependencies=[Depends(_vocabulary_gate)],
)
prerequisites_router = APIRouter(
    prefix="/tenants/{tenant_id}/features/prototypes/{feature_id}/prerequisites",
    tags=["grant-rules"],
    dependencies=[Depends(_vocabulary_gate)],
)

HIDDEN_ENTRY = "a hidden entry"
_LOAD = (selectinload(GrantRule.conditions), selectinload(GrantRule.options))


async def _stat_names(
    session: SessionDep, tenant_id: uuid.UUID, ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await session.execute(
        select(StatDefinition.id, StatDefinition.name).where(
            StatDefinition.tenant_id == tenant_id, StatDefinition.id.in_(ids)
        )
    )
    return {stat_id: name for stat_id, name in rows.tuples()}


async def _entry_names(
    session: SessionDep, tenant_id: uuid.UUID, ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Entity.id, Entity.name).where(Entity.tenant_id == tenant_id, Entity.id.in_(ids))
    )
    return {entry_id: name for entry_id, name in rows.tuples()}


def _entry(
    entry_id: uuid.UUID, names: dict[uuid.UUID, str], visibility: InformationVisibility
) -> RuleOptionOut:
    if not visibility.can_see_entry(entry_id):
        return RuleOptionOut(id=None, name=HIDDEN_ENTRY, hidden=True)
    return RuleOptionOut(id=entry_id, name=names.get(entry_id, ""))


async def _outs(
    session: SessionDep, tenant_id: uuid.UUID, rules: Sequence[GrantRule], user: CurrentUser
) -> list[GrantRuleOut]:
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    stat_ids: set[uuid.UUID] = set()
    entry_ids: set[uuid.UUID] = set()
    for rule in rules:
        entry_ids.add(rule.entry_id)
        if rule.option_category_entry_id:
            entry_ids.add(rule.option_category_entry_id)
        if rule.count_stat_definition_id:
            stat_ids.add(rule.count_stat_definition_id)
        entry_ids.update(option.option_entry_id for option in rule.options)
        for condition in rule.conditions:
            stat_ids.add(condition.stat_definition_id)
            if condition.right_stat_definition_id:
                stat_ids.add(condition.right_stat_definition_id)
    stats = await _stat_names(session, tenant_id, stat_ids)
    names = await _entry_names(session, tenant_id, entry_ids)
    return [
        GrantRuleOut(
            id=rule.id,
            entry_id=rule.entry_id,
            entry_name=names.get(rule.entry_id, ""),
            label=rule.label,
            position=rule.position,
            mode=rule.mode,
            min_count=rule.min_count,
            max_count=rule.max_count,
            count_stat_definition_id=rule.count_stat_definition_id,
            count_stat_name=stats.get(rule.count_stat_definition_id)
            if rule.count_stat_definition_id
            else None,
            option_category=(
                _entry(rule.option_category_entry_id, names, visibility)
                if rule.option_category_entry_id
                else None
            ),
            options=[_entry(o.option_entry_id, names, visibility) for o in rule.options],
            lasts=rule.lasts,
            changeable=rule.changeable,
            conditions=[
                ConditionOut(
                    subject=c.subject,
                    **_comparison(c, stats).model_dump(),
                )
                for c in rule.conditions
            ],
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
        for rule in rules
    ]


def _comparison(
    row: GrantRuleCondition | FeaturePrerequisite, stats: dict[uuid.UUID, str]
) -> ComparisonOut:
    return ComparisonOut(
        stat_definition_id=row.stat_definition_id,
        stat_name=stats.get(row.stat_definition_id, ""),
        comparator=row.comparator,
        right_constant=row.right_constant,
        right_stat_definition_id=row.right_stat_definition_id,
        right_stat_name=(
            stats.get(row.right_stat_definition_id) if row.right_stat_definition_id else None
        ),
    )


async def _get_or_404(session: SessionDep, tenant_id: uuid.UUID, rule_id: uuid.UUID) -> GrantRule:
    rule = await session.scalar(
        select(GrantRule)
        .where(
            GrantRule.id == rule_id,
            GrantRule.tenant_id == tenant_id,
            await unhidden(session, tenant_id, GrantRule.entry_id),
        )
        .options(*_LOAD)
        .execution_options(populate_existing=True)
    )
    if rule is None:
        raise GrantRuleNotFoundError(
            detail=f"No grant rule with id {rule_id} in tenant {tenant_id}"
        )
    return rule


async def _check_stats(
    session: SessionDep,
    tenant_id: uuid.UUID,
    comparisons: Sequence[ComparisonIn],
    count: uuid.UUID | None,
) -> None:
    """Every stat a rule or a prerequisite reads is the library's and is not text: a comparison
    reads a number, a bool or an enum as a number, as the `comparison` formula does (ADR 0444), and
    a count is a number."""
    ids = {c.stat_definition_id for c in comparisons}
    ids |= {c.right_stat_definition_id for c in comparisons if c.right_stat_definition_id}
    if count is not None:
        ids.add(count)
    if not ids:
        return
    rows = await session.execute(
        select(StatDefinition.id, StatDefinition.value_type).where(
            StatDefinition.tenant_id == tenant_id, StatDefinition.id.in_(ids)
        )
    )
    types = {stat_id: value_type for stat_id, value_type in rows.tuples()}
    if missing := sorted(ids - set(types)):
        raise InvalidGrantRuleError(detail=f"{missing[0]} is not a stat of the library")
    text = sorted(
        stat_id for stat_id, value_type in types.items() if value_type is StatValueType.TEXT
    )
    if text:
        raise InvalidGrantRuleError(detail=f"{text[0]} is a text stat: a comparison reads a number")
    if count is not None and types[count] not in (StatValueType.INT, StatValueType.FLOAT):
        raise InvalidGrantRuleError(detail=f"{count} counts the picks and must be a number")


async def _validate(
    session: SessionDep, tenant_id: uuid.UUID, body: GrantRuleUpdate | GrantRuleIn
) -> None:
    """What a rule names is the library's (422): its options are features, its category an entry,
    its stats numbers. A hidden entry is answered as an unknown one (ADR 0437)."""
    if body.options:
        found = set(
            await session.scalars(
                select(Feature.entity_id).where(
                    Feature.tenant_id == tenant_id,
                    Feature.entity_id.in_(set(body.options)),
                    await unhidden(session, tenant_id, Feature.entity_id),
                )
            )
        )
        if missing := [o for o in body.options if o not in found]:
            raise InvalidGrantRuleError(
                detail=f"{missing[0]} is not a feature of tenant {tenant_id}"
            )
    if body.option_category_entry_id is not None and not await session.scalar(
        select(Entity.id).where(
            Entity.id == body.option_category_entry_id,
            Entity.tenant_id == tenant_id,
            await unhidden(session, tenant_id, Entity.id),
        )
    ):
        raise InvalidGrantRuleError(
            detail=f"{body.option_category_entry_id} is not an entry of tenant {tenant_id}"
        )
    await _check_stats(session, tenant_id, body.conditions, body.count_stat_definition_id)


async def _replace_parts(
    session: SessionDep,
    tenant_id: uuid.UUID,
    rule: GrantRule,
    conditions: Sequence[ConditionIn],
    options: Sequence[uuid.UUID],
) -> None:
    await session.execute(
        delete(GrantRuleCondition)
        .where(GrantRuleCondition.rule_id == rule.id, GrantRuleCondition.tenant_id == tenant_id)
        .execution_options(synchronize_session=False)
    )
    await session.execute(
        delete(GrantRuleOption)
        .where(GrantRuleOption.rule_id == rule.id, GrantRuleOption.tenant_id == tenant_id)
        .execution_options(synchronize_session=False)
    )
    for position, condition in enumerate(conditions):
        session.add(
            GrantRuleCondition(
                tenant_id=tenant_id,
                rule_id=rule.id,
                position=position,
                subject=condition.subject,
                stat_definition_id=condition.stat_definition_id,
                comparator=condition.comparator,
                right_constant=condition.right_constant,
                right_stat_definition_id=condition.right_stat_definition_id,
            )
        )
    for position, option in enumerate(options):
        session.add(
            GrantRuleOption(
                rule_id=rule.id, option_entry_id=option, tenant_id=tenant_id, position=position
            )
        )
    await session.flush()


def _apply_body(rule: GrantRule, body: GrantRuleUpdate | GrantRuleIn) -> None:
    rule.label = body.label
    rule.mode = body.mode
    rule.min_count = body.min_count
    rule.max_count = body.max_count
    rule.count_stat_definition_id = body.count_stat_definition_id
    rule.option_category_entry_id = body.option_category_entry_id
    rule.lasts = body.lasts
    rule.changeable = body.changeable


async def _place(
    session: SessionDep,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
    rule: GrantRule,
    position: int | None,
) -> None:
    """Gives the rule its place among its source's rules and numbers them 0, 1, 2...: at the end
    when `position` is not given (or is past it)."""
    others = list(
        await session.scalars(
            select(GrantRule)
            .where(
                GrantRule.tenant_id == tenant_id,
                GrantRule.entry_id == entry_id,
                GrantRule.id != rule.id,
            )
            .order_by(GrantRule.position, GrantRule.created_at, GrantRule.id)
        )
    )
    index = len(others) if position is None else min(position, len(others))
    ordered = [*others[:index], rule, *others[index:]]
    for place, item in enumerate(ordered):
        item.position = place
    await session.flush()


@router.get("")
async def list_grant_rules(
    tenant_id: uuid.UUID,
    session: SessionDep,
    params: ParamsDep,
    user: CurrentUser,
    entry_id: uuid.UUID | None = None,
) -> Page[GrantRuleOut]:
    """The library's rules by source entry (its name, then its id) and then in the order of the
    source, or those of one source. A rule on an entry the library hides is not one it can know of
    (ADR 0437)."""
    stmt = (
        select(GrantRule)
        .join(Entity, Entity.id == GrantRule.entry_id)
        .where(
            GrantRule.tenant_id == tenant_id,
            await unhidden(session, tenant_id, GrantRule.entry_id),
        )
        .options(*_LOAD)
    )
    if entry_id is not None:
        stmt = stmt.where(GrantRule.entry_id == entry_id)

    async def transform(rules: Sequence[GrantRule]) -> list[GrantRuleOut]:
        return await _outs(session, tenant_id, rules, user)

    page: Page[GrantRuleOut] = await apaginate(
        session,
        stmt.order_by(Entity.name, GrantRule.entry_id, GrantRule.position, GrantRule.id),
        params,
        transformer=transform,
    )
    return page


@router.post("", status_code=201)
async def create_grant_rule(
    tenant_id: uuid.UUID,
    body: GrantRuleIn,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> GrantRuleOut:
    """Makes a rule on a source entry (422 for an entry, option, category or stat that is not the
    library's, an option that is no feature, or a comparison of a text stat)."""
    if not await session.scalar(
        select(Entity.id).where(
            Entity.id == body.entry_id,
            Entity.tenant_id == tenant_id,
            await unhidden(session, tenant_id, Entity.id),
        )
    ):
        raise InvalidGrantRuleError(detail=f"{body.entry_id} is not an entry of tenant {tenant_id}")
    await _validate(session, tenant_id, body)
    rule = GrantRule(tenant_id=tenant_id, entry_id=body.entry_id, position=0)
    _apply_body(rule, body)
    session.add(rule)
    await session.flush()
    await _replace_parts(session, tenant_id, rule, body.conditions, body.options)
    await _place(session, tenant_id, body.entry_id, rule, body.position)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="grant_rule.created",
        target_type="grant_rule",
        target_id=rule.id,
        detail=f"entry={body.entry_id},mode={body.mode}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_grant_rule", tenant_id=tenant_id, rule_id=rule.id)
    )
    return (
        await _outs(session, tenant_id, [await _get_or_404(session, tenant_id, rule.id)], user)
    )[0]


@router.get("/{rule_id}")
async def get_grant_rule(
    tenant_id: uuid.UUID, rule_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> GrantRuleOut:
    return (
        await _outs(session, tenant_id, [await _get_or_404(session, tenant_id, rule_id)], user)
    )[0]


@router.put("/{rule_id}")
async def replace_grant_rule(
    tenant_id: uuid.UUID,
    rule_id: uuid.UUID,
    body: GrantRuleUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> GrantRuleOut:
    """Replaces the rule: everything but its source. A change reaches a holder at its next apply;
    what was granted is not touched here (ADR 0456 decides what a grant outlives)."""
    rule = await _get_or_404(session, tenant_id, rule_id)
    await _validate(session, tenant_id, body)
    _apply_body(rule, body)
    await session.flush()
    await _replace_parts(session, tenant_id, rule, body.conditions, body.options)
    if body.position is not None:
        await _place(session, tenant_id, rule.entry_id, rule, body.position)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="grant_rule.updated",
        target_type="grant_rule",
        target_id=rule_id,
        detail=f"entry={rule.entry_id},mode={body.mode}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return (
        await _outs(session, tenant_id, [await _get_or_404(session, tenant_id, rule_id)], user)
    )[0]


@router.delete("/{rule_id}", status_code=204, dependencies=[Depends(get_tenant_admin_context)])
async def delete_grant_rule(
    tenant_id: uuid.UUID, rule_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    rule = await _get_or_404(session, tenant_id, rule_id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="grant_rule.deleted",
        target_type="grant_rule",
        target_id=rule_id,
        detail=f"entry={rule.entry_id}",
    )
    await session.delete(rule)
    await session.commit()


# --- the prerequisites of a feature --------------------------------------------------------


async def _feature_or_404(session: SessionDep, tenant_id: uuid.UUID, feature_id: uuid.UUID) -> None:
    if await usable_feature(session, tenant_id=tenant_id, feature_id=feature_id) is None:
        raise FeatureNotFoundError(detail=f"No feature with id {feature_id} in tenant {tenant_id}")


async def _prerequisites_out(
    session: SessionDep, tenant_id: uuid.UUID, feature_id: uuid.UUID
) -> PrerequisitesOut:
    rows = list(
        await session.scalars(
            select(FeaturePrerequisite)
            .where(
                FeaturePrerequisite.tenant_id == tenant_id,
                FeaturePrerequisite.feature_id == feature_id,
            )
            .order_by(FeaturePrerequisite.position)
        )
    )
    ids = {r.stat_definition_id for r in rows} | {
        r.right_stat_definition_id for r in rows if r.right_stat_definition_id
    }
    stats = await _stat_names(session, tenant_id, ids)
    return PrerequisitesOut(
        feature_id=feature_id, prerequisites=[_comparison(r, stats) for r in rows]
    )


@prerequisites_router.get("")
async def get_prerequisites(
    tenant_id: uuid.UUID, feature_id: uuid.UUID, session: SessionDep
) -> PrerequisitesOut:
    """What a holder needs to have the feature, in order; all of it must hold."""
    await _feature_or_404(session, tenant_id, feature_id)
    return await _prerequisites_out(session, tenant_id, feature_id)


@prerequisites_router.put("")
async def put_prerequisites(
    tenant_id: uuid.UUID,
    feature_id: uuid.UUID,
    body: PrerequisitesIn,
    session: SessionDep,
    user: CurrentUser,
) -> PrerequisitesOut:
    """Replaces the list (empty clears it): comparisons on the holder of the feature, which every
    rule that offers it respects. 422 for a stat that is not the library's or is text."""
    await _feature_or_404(session, tenant_id, feature_id)
    await _check_stats(session, tenant_id, body.prerequisites, None)
    await session.execute(
        delete(FeaturePrerequisite)
        .where(
            FeaturePrerequisite.tenant_id == tenant_id,
            FeaturePrerequisite.feature_id == feature_id,
        )
        .execution_options(synchronize_session=False)
    )
    for position, comparison in enumerate(body.prerequisites):
        session.add(
            FeaturePrerequisite(
                tenant_id=tenant_id,
                feature_id=feature_id,
                position=position,
                stat_definition_id=comparison.stat_definition_id,
                comparator=comparison.comparator,
                right_constant=comparison.right_constant,
                right_stat_definition_id=comparison.right_stat_definition_id,
            )
        )
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="feature.prerequisites_set",
        target_type="entity",
        target_id=feature_id,
        detail=f"count={len(body.prerequisites)}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _prerequisites_out(session, tenant_id, feature_id)
