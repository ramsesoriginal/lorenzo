"""What a holder is entitled to and has been given: the grants read, and apply with picks
(ADR 0456, RFC 0054 section 4).

`GET .../entities/{holder}/grants` computes and writes nothing; `POST .../grants/apply` makes the
automatic grants that are due, records the holder's picks and revokes what is orphaned, in one
transaction. The holder's controller applies, and any GM; only a GM overrides a limit.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from fastapi import APIRouter, Depends
from sqlalchemy import select

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_entity_or_404,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import can_self_manage_entity
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    GrantApplyForbiddenError,
    GrantOverrideForbiddenError,
)
from lorenzo_api.features import holder_kind, manages_holder, require_holder
from lorenzo_api.grants import (
    Applied,
    Computed,
    DueGrant,
    OpenChoice,
    Orphan,
    PickSpec,
    Revoked,
    apply_grants,
    compute,
)
from lorenzo_api.information_visibility import InformationVisibility, resolve_information_visibility
from lorenzo_api.models import (
    Entity,
    FeatureInstance,
    GrantRecord,
    GrantRule,
    ItemInstance,
)
from lorenzo_api.routers.features import _may_read
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.grant_rules import RuleOptionOut
from lorenzo_api.schemas.grants import (
    ApplyIn,
    ApplyOut,
    DueGrantOut,
    GrantSourceOut,
    GrantsOut,
    HeldGrantOut,
    OpenChoiceOut,
    OrphanOut,
    RevokedOut,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}/entities/{entity_id}/grants",
    tags=["grants"],
    dependencies=[Depends(get_tenant_or_404)],
)


class _Names:
    """The names a grants response uses, read once: entries, and the label of each rule."""

    def __init__(self, visibility: InformationVisibility) -> None:
        self.visibility = visibility
        self.entries: dict[uuid.UUID, str] = {}
        self.labels: dict[uuid.UUID, str | None] = {}
        self.instances: set[uuid.UUID] = set()

    async def load(
        self,
        session: SessionDep,
        tenant_id: uuid.UUID,
        entry_ids: Iterable[uuid.UUID],
        rule_ids: Iterable[uuid.UUID],
    ) -> None:
        wanted = set(entry_ids)
        if wanted:
            rows = await session.execute(
                select(Entity.id, Entity.name).where(
                    Entity.tenant_id == tenant_id, Entity.id.in_(wanted)
                )
            )
            self.entries = {entry_id: name for entry_id, name in rows.tuples()}
            for model in (FeatureInstance, ItemInstance):
                self.instances |= set(
                    await session.scalars(
                        select(model.entity_id).where(
                            model.tenant_id == tenant_id, model.entity_id.in_(wanted)
                        )
                    )
                )
        rules = set(rule_ids)
        if rules:
            label_rows = await session.execute(
                select(GrantRule.id, GrantRule.label).where(
                    GrantRule.tenant_id == tenant_id, GrantRule.id.in_(rules)
                )
            )
            self.labels = {rule_id: label for rule_id, label in label_rows.tuples()}

    def named(self, entry_id: uuid.UUID) -> RuleOptionOut:
        if not self.visibility.can_see_entry(entry_id):
            return RuleOptionOut(id=None, name="a hidden entry", hidden=True)
        return RuleOptionOut(id=entry_id, name=self.entries.get(entry_id, ""))

    def source(self, ref_id: uuid.UUID, kind: str | None = None) -> GrantSourceOut:
        named = self.named(ref_id)
        return GrantSourceOut(
            id=named.id,
            name=named.name,
            kind=kind or ("instance" if ref_id in self.instances else "ancestor"),
            hidden=named.hidden,
        )

    def label(self, rule_id: uuid.UUID | None) -> str | None:
        return self.labels.get(rule_id) if rule_id is not None else None


def _entries_of(
    found: Computed, extra: Iterable[GrantRecord] = ()
) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    entries: set[uuid.UUID] = {found.holder_id}
    rules: set[uuid.UUID] = set()
    for record in [*found.active, *extra]:
        entries |= {record.feature_id}
        if record.source_ref_id:
            entries.add(record.source_ref_id)
        if record.rule_id:
            rules.add(record.rule_id)
    for due in found.due:
        entries |= {due.feature_id, due.standing.ref_id}
        rules.add(due.standing.rule.id)
    for choice in found.open_choices:
        entries |= {choice.standing.ref_id, *choice.picked, *choice.offered}
        rules.add(choice.standing.rule.id)
    return entries, rules


def _held(record: GrantRecord, names: _Names) -> HeldGrantOut:
    assert record.feature_instance_id is not None
    return HeldGrantOut(
        record_id=record.id,
        instance_id=record.feature_instance_id,
        feature=EntitySummary(id=record.feature_id, name=names.entries.get(record.feature_id, "")),
        rule_id=record.rule_id,
        label=names.label(record.rule_id),
        source=names.source(record.source_ref_id) if record.source_ref_id else None,
        created_at=record.created_at,
    )


def _due(due: DueGrant, names: _Names) -> DueGrantOut:
    return DueGrantOut(
        rule_id=due.standing.rule.id,
        label=due.standing.rule.label,
        source=names.source(due.standing.ref_id, due.standing.kind),
        feature=names.named(due.feature_id),
    )


def _open(choice: OpenChoice, names: _Names) -> OpenChoiceOut:
    return OpenChoiceOut(
        rule_id=choice.standing.rule.id,
        label=choice.standing.rule.label,
        source=names.source(choice.standing.ref_id, choice.standing.kind),
        minimum=choice.minimum,
        maximum=choice.maximum,
        picked=[names.named(f) for f in choice.picked],
        options=[names.named(f) for f in choice.offered if f in choice.passing],
        changeable=choice.standing.rule.changeable,
    )


def _orphan(orphan: Orphan, names: _Names) -> OrphanOut:
    record = orphan.record
    return OrphanOut(
        record_id=record.id,
        rule_id=record.rule_id,
        label=names.label(record.rule_id),
        feature=names.named(record.feature_id),
        instance_id=record.feature_instance_id,
        reason=orphan.reason,
    )


def _revoked(revoked: Revoked, names: _Names) -> RevokedOut:
    return RevokedOut(
        record_id=revoked.record_id,
        rule_id=revoked.rule_id,
        label=names.label(revoked.rule_id),
        feature=names.named(revoked.feature_id),
        instance_id=revoked.instance_id,
        reason=revoked.reason,
    )


@router.get("")
async def get_grants(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> GrantsOut:
    """What the holder has through rules and awards, what is due (automatic grants whose
    conditions hold and that have no record), the open choices (a rule's minimum, maximum, what is
    picked and the options that pass their prerequisites) and what is orphaned. A read never
    writes. Readable as the holder's features are: whoever reaches it, and its managers."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    holder = await get_entity_or_404(session, entity_id, tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    kind = await holder_kind(session, tenant_id=tenant_id, entity_id=entity_id)
    if not await _may_read(
        session,
        tenant_id=tenant_id,
        user=user,
        visibility=visibility,
        holder_id=entity_id,
        kind=kind,
    ):
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    await require_holder(session, tenant_id=tenant_id, entity_id=entity_id)
    found = await compute(session, tenant_id, entity_id)
    entries, rules = _entries_of(found, [o.record for o in found.orphans])
    names = _Names(visibility)
    await names.load(session, tenant_id, entries, rules)
    return GrantsOut(
        holder=EntitySummary.from_entity(holder),
        held=[_held(r, names) for r in found.active],
        due=[_due(d, names) for d in found.due],
        open_choices=[_open(c, names) for c in found.open_choices],
        orphaned=[_orphan(o, names) for o in found.orphans],
    )


@router.post("/apply")
async def apply_grants_route(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: ApplyIn,
    session: SessionDep,
    user: CurrentUser,
) -> ApplyOut:
    """Makes the automatic grants that are due, records the picks and revokes what is orphaned,
    and repeats until nothing more is due, since a granted feature is itself a source. A pick is
    refused (`422`) outside the rule's options, with no open choice behind it, below the minimum
    where the apply carries picks for it, above the maximum or past a prerequisite, and `409` for
    a feature the holder has and that is not repeatable; a GM's `override` lifts the three limits.
    `dry_run` reports what would happen and writes nothing. The holder's controller applies, and
    any GM (`403` otherwise); `override` is a GM's alone."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await get_entity_or_404(session, entity_id, tenant_id)
    kind = await require_holder(session, tenant_id=tenant_id, entity_id=entity_id)
    manager = await manages_holder(
        session, tenant_id=tenant_id, user_id=user.id, holder_id=entity_id, kind=kind
    )
    if not manager and not await can_self_manage_entity(
        session, entity_id=entity_id, user_id=user.id, tenant_id=tenant_id
    ):
        raise GrantApplyForbiddenError(detail=f"Not authorized to apply the grants of {entity_id}")
    if body.override and not manager:
        raise GrantOverrideForbiddenError(detail="Only a GM of this holder can override a limit.")
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    applied = await apply_grants(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        holder_id=entity_id,
        picks=[PickSpec(p.rule_id, p.source_id, p.options) for p in body.picks],
        override=body.override,
    )
    out = await _applied_out(session, tenant_id, entity_id, applied, visibility, body.dry_run)
    if body.dry_run:
        await session.rollback()
    else:
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return out


async def _applied_out(
    session: SessionDep,
    tenant_id: uuid.UUID,
    holder_id: uuid.UUID,
    applied: Applied,
    visibility: InformationVisibility,
    dry_run: bool,
) -> ApplyOut:
    found = await compute(session, tenant_id, holder_id)
    created = list(
        await session.scalars(
            select(GrantRecord).where(
                GrantRecord.tenant_id == tenant_id,
                GrantRecord.id.in_([g.record.id for g in applied.created]),
            )
        )
    )
    entries, rules = _entries_of(found, created)
    for revoked in applied.revoked:
        entries.add(revoked.feature_id)
        if revoked.rule_id:
            rules.add(revoked.rule_id)
    names = _Names(visibility)
    await names.load(session, tenant_id, entries, rules)
    return ApplyOut(
        created=[_held(r, names) for r in created],
        revoked=[_revoked(r, names) for r in applied.revoked],
        open_choices=[_open(c, names) for c in found.open_choices],
        dry_run=dry_run,
        truncated=applied.truncated,
    )
