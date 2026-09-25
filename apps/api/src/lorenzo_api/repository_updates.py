"""Repository updates and re-sync - ADR 0121.

Every copy link holds a snapshot of what was copied, in origin ids (ADR
0119). An update compares three versions of each copied row: that
snapshot (base), the repository's row now (upstream), and the tenant's
copy now (local). A field upstream changed is *clean* while the local copy
still matches the base, and a *conflict* once the tenant changed it too;
sets (prototypes, stat groups, enum values) merge element by element and
never conflict. Nothing is applied except row by row, on request, and a
conflict is never resolved without being named.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.exceptions import (
    InvalidRepositoryUpdateError,
    RepositoryCopyNeedsChoicesError,
    RepositoryNotCopiedError,
    RepositoryNotFoundError,
    RepositoryUpdateNeedsChoicesError,
)
from lorenzo_api.models import (
    ComputedStat,
    ComputedStatComparison,
    ComputedStatLinear,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    Item,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
)
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import (
    Content,
    Namer,
    entity_snapshot,
    index_entities,
    load_content,
    origin_namer,
    stat_definition_snapshot,
    stat_group_snapshot,
)
from lorenzo_api.repository_copying import (
    Collision,
    Resolution,
    Step,
    _Planner,
    check_formula_cycles,
    write_rows,
)

RowKind = Literal["entity", "stat_group", "stat_definition"]
_ROW_KINDS: tuple[RowKind, ...] = ("entity", "stat_group", "stat_definition")
# Groups before definitions before entities: the order additions need.
_ADD_ORDER: tuple[RowKind, ...] = ("stat_group", "stat_definition", "entity")
State = Literal["clean", "conflict", "not_applicable"]

_SETS = {"prototypes", "stat_groups", "enum_values"}
_KEYED = {"stats", "formulas"}
# Shown when they change, never applied: converting every value is a
# person's job.
_NOT_APPLICABLE = {"value_type"}
# Not compared: an entity's kinds are what it is, not content that drifts.
_IGNORED = {"kinds"}

_LINK_MODELS: dict[str, Any] = {
    "entity": (RepositoryCopyLinkEntity, RepositoryCopyLinkEntity.entity_id),
    "stat_group": (RepositoryCopyLinkStatGroup, RepositoryCopyLinkStatGroup.stat_group_id),
    "stat_definition": (
        RepositoryCopyLinkStatDefinition,
        RepositoryCopyLinkStatDefinition.stat_definition_id,
    ),
}
# What an added row of each kind can collide on (ADR 0119).
COLLISION_KIND: dict[str, Any] = {
    "entity": "slug",
    "stat_group": "stat_group",
    "stat_definition": "stat_definition",
}


@dataclass
class FieldChange:
    field: str
    label: str | None
    state: State
    base: Any
    upstream: Any
    local: Any
    added: list[Any] | None = None
    removed: list[Any] | None = None


@dataclass
class RowChange:
    kind: RowKind
    source_id: uuid.UUID
    local_id: uuid.UUID
    name: str
    fields: list[FieldChange]
    base: dict[str, Any]
    upstream: dict[str, Any]


@dataclass
class RowRef:
    kind: RowKind
    source_id: uuid.UUID
    local_id: uuid.UUID | None
    name: str


@dataclass
class Added:
    kind: RowKind
    source_id: uuid.UUID
    name: str
    collision: Collision | None


@dataclass
class Updates:
    repository_id: uuid.UUID
    changed: list[RowChange] = field(default_factory=list)
    removed: list[RowRef] = field(default_factory=list)
    deleted_locally: list[RowRef] = field(default_factory=list)
    added: list[Added] = field(default_factory=list)
    upstream: Content | None = None
    local: Content | None = None


# --- Finding updates -------------------------------------------------------------


def _scalar(name: str, label: str | None, base: Any, upstream: Any, local: Any) -> FieldChange:
    if name in _NOT_APPLICABLE:
        state: State = "not_applicable"
    elif local in (base, upstream):
        state = "clean"
    else:
        state = "conflict"
    return FieldChange(name, label, state, base, upstream, local)


def diff(
    base: dict[str, Any], upstream: dict[str, Any], local: dict[str, Any], labels: dict[str, str]
) -> list[FieldChange]:
    """Every field upstream changed since the base, with the local value
    beside it. Keyed fields (stats, formulas) are one scalar per stat,
    named `stats:<origin id>`."""
    changes: list[FieldChange] = []
    for key in sorted(set(base) | set(upstream)):
        if key in _IGNORED:
            continue
        b, u, loc = base.get(key), upstream.get(key), local.get(key)
        if key in _SETS:
            bs, us, ls = set(b or []), set(u or []), set(loc or [])
            # Nothing to do once the local copy already has upstream's change.
            if bs != us and not (us - bs <= ls and not (bs - us) & ls):
                changes.append(
                    FieldChange(
                        key,
                        None,
                        "clean",
                        sorted(bs),
                        sorted(us),
                        sorted(ls),
                        added=sorted(us - bs),
                        removed=sorted(bs - us),
                    )
                )
        elif key in _KEYED:
            bd, ud, ld = b or {}, u or {}, loc or {}
            for sub in sorted(set(bd) | set(ud)):
                if bd.get(sub) != ud.get(sub) and ld.get(sub) != ud.get(sub):
                    changes.append(
                        _scalar(
                            f"{key}:{sub}", labels.get(sub), bd.get(sub), ud.get(sub), ld.get(sub)
                        )
                    )
        elif b != u and loc != u:
            changes.append(_scalar(key, None, b, u, loc))
    return changes


def _local_namer(local: Content, repository_id: uuid.UUID) -> Namer:
    """Names the tenant's own rows the way the repository's snapshot does:
    a copied row by its origin, anything else by a marker no origin can
    equal."""

    def name(kind: str, local_id: uuid.UUID) -> str:
        origin = getattr(local.links, kind).get(local_id)
        return str(origin) if origin is not None else f"local:{local_id}"

    return name


def _snapshot(
    content: Content, kind: str, row_id: uuid.UUID, namer: Namer, index: Any
) -> dict[str, Any]:
    if kind == "entity":
        return entity_snapshot(content, index, row_id, namer)
    if kind == "stat_group":
        return stat_group_snapshot(content, row_id)
    return stat_definition_snapshot(content, row_id, namer)


def _rows(content: Content, kind: str) -> dict[uuid.UUID, Any]:
    rows: dict[str, dict[uuid.UUID, Any]] = {
        "entity": content.entities,
        "stat_group": content.groups,
        "stat_definition": content.definitions,
    }
    return rows[kind]


def _row_name(content: Content, kind: str, row_id: uuid.UUID) -> str:
    row = _rows(content, kind)[row_id]
    return str(row) if kind == "entity" else str(row["name"])


async def compute_updates(
    session: AsyncSession, *, tenant_id: uuid.UUID, repository_id: uuid.UUID
) -> Updates:
    if await session.get(RepositoryCopy, (tenant_id, repository_id)) is None:
        raise RepositoryNotCopiedError(detail=f"Copy repository {repository_id} first")
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise RepositoryNotFoundError(
                detail=f"No published repository {repository_id} is granted to tenant {tenant_id}"
            )
        upstream = await load_content(session, repository_id)
    local = await load_content(session, tenant_id)
    links = local.links
    updates = Updates(repository_id=repository_id, upstream=upstream, local=local)
    up_namer, local_namer = origin_namer(upstream), _local_namer(local, repository_id)
    up_index, local_index = index_entities(upstream), index_entities(local)
    labels = {
        str(upstream.origin("stat_definition", d)): definition["name"]
        for d, definition in upstream.definitions.items()
    }

    for kind in _ROW_KINDS:
        for local_id, origin in getattr(links, kind).items():
            if links.origin_tenant.get(origin) != repository_id or origin in links.merged:
                continue
            if origin not in _rows(upstream, kind) or not upstream.own(kind, origin):
                updates.removed.append(
                    RowRef(kind, origin, local_id, _row_name(local, kind, local_id))
                )
                continue
            base = links.snapshots[origin]
            upstream_snapshot = _snapshot(upstream, kind, origin, up_namer, up_index)
            local_snapshot = _snapshot(local, kind, local_id, local_namer, local_index)
            changes = diff(base, upstream_snapshot, local_snapshot, labels)
            if changes:
                updates.changed.append(
                    RowChange(
                        kind,
                        origin,
                        local_id,
                        _row_name(local, kind, local_id),
                        changes,
                        base,
                        upstream_snapshot,
                    )
                )
        for origin in sorted(links.deleted.get(kind, ()), key=str):
            if links.origin_tenant.get(origin) == repository_id:
                updates.deleted_locally.append(
                    RowRef(kind, origin, None, str(links.snapshots[origin].get("name", "")))
                )

    # Added upstream: the repository's own rows this tenant has no link for.
    local_group_names = {g["name"] for g in local.groups.values()}
    local_def_names = {d["name"] for d in local.definitions.values()}
    local_slugs = set(local.slugs.values())
    for kind in _ADD_ORDER:
        for row_id in _rows(upstream, kind):
            if not upstream.own(kind, row_id) or row_id in links.snapshots:
                continue
            name = _row_name(upstream, kind, row_id)
            collision = None
            if kind == "stat_group" and name in local_group_names:
                collision = Collision(
                    repository_id, "stat_group", row_id, name, None, ["rename", "merge", "skip"]
                )
            elif kind == "stat_definition" and name in local_def_names:
                collision = Collision(
                    repository_id,
                    "stat_definition",
                    row_id,
                    name,
                    None,
                    ["rename", "merge", "skip"],
                )
            elif kind == "entity" and upstream.slugs.get(row_id) in local_slugs:
                collision = Collision(
                    repository_id, "slug", row_id, upstream.slugs[row_id], None, ["rename", "skip"]
                )
            updates.added.append(Added(kind, row_id, name, collision))
    return updates


# --- Applying ----------------------------------------------------------------------


@dataclass
class UpdateAction:
    kind: RowKind
    source_id: uuid.UUID
    action: Literal["apply", "add", "detach"]
    keep_local: list[str] = field(default_factory=list)
    take_upstream: list[str] = field(default_factory=list)
    resolution: Resolution | None = None


@dataclass
class NotApplied:
    kind: str
    source_id: uuid.UUID
    field: str
    reason: str


@dataclass
class ApplyResult:
    applied: int = 0
    added: int = 0
    detached: int = 0
    not_applied: list[NotApplied] = field(default_factory=list)


class _Applier:
    """Writes the chosen fields of changed rows onto the tenant's copies."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, local: Content) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.local = local
        self.origin_to_local = {
            kind: local.links.local_of(kind) for kind in ("entity", "stat_group", "stat_definition")
        }
        self.value_types = {d: row["value_type"] for d, row in local.definitions.items()}
        self.result = ApplyResult()

    def resolve(self, kind: str, origin: str) -> uuid.UUID | None:
        if origin.startswith("local:"):
            return uuid.UUID(origin.removeprefix("local:"))
        origin_id = uuid.UUID(origin)
        local = self.origin_to_local[kind].get(origin_id)
        if local is not None:
            return local
        # The tenant's own row, which the repository copied from it (ADR 0120).
        return origin_id if origin_id in _rows(self.local, kind) else None

    def skip(self, row: RowChange, name: str, reason: str) -> None:
        self.result.not_applied.append(NotApplied(row.kind, row.source_id, name, reason))

    async def apply(self, row: RowChange, chosen: list[FieldChange]) -> set[str]:
        """Applies `chosen`; returns the fields it couldn't apply."""
        failed: set[str] = set()
        for change in chosen:
            ok = await getattr(self, f"_{row.kind}")(row, change)
            if not ok:
                failed.add(change.field)
        return failed

    # entity ---------------------------------------------------------------

    async def _entity(self, row: RowChange, change: FieldChange) -> bool:
        e, t, s = row.local_id, self.tenant_id, self.session
        name = change.field
        if name == "name":
            await s.execute(
                update(Entity)
                .where(Entity.id == e, Entity.tenant_id == t)
                .values(name=change.upstream)
            )
            return True
        if name == "in_public_catalog":
            await s.execute(
                update(Item)
                .where(Item.entity_id == e, Item.tenant_id == t)
                .values(in_public_catalog=bool(change.upstream))
            )
            return True
        if name == "slug":
            await s.execute(
                delete(EntitySlug).where(EntitySlug.entity_id == e, EntitySlug.tenant_id == t)
            )
            if change.upstream is None:
                return True
            taken = await s.scalar(
                select(EntitySlug.entity_id).where(
                    EntitySlug.tenant_id == t, EntitySlug.slug == change.upstream
                )
            )
            if taken is not None:
                self.skip(row, name, f"the slug {change.upstream!r} is taken here")
                return False
            await s.execute(
                insert(EntitySlug).values(entity_id=e, tenant_id=t, slug=change.upstream)
            )
            return True
        if name in ("prototypes", "stat_groups"):
            kind = "entity" if name == "prototypes" else "stat_group"
            model, column = (
                (EntityPrototype, EntityPrototype.prototype_id)
                if name == "prototypes"
                else (EntityStatGroup, EntityStatGroup.stat_group_id)
            )
            ok = True
            for origin in change.removed or []:
                target = self.resolve(kind, origin)
                if target is not None:
                    await s.execute(
                        delete(model).where(
                            model.entity_id == e, column == target, model.tenant_id == t
                        )
                    )
            for origin in change.added or []:
                target = self.resolve(kind, origin)
                if target is None:
                    self.skip(row, name, f"{origin} wasn't copied here")
                    ok = False
                    continue
                exists = await s.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.entity_id == e, column == target, model.tenant_id == t)
                )
                if not exists:
                    values = {"entity_id": e, "tenant_id": t, column.key: target}
                    await s.execute(insert(model).values(**values))
            return ok
        prefix, _, key = name.partition(":")
        definition = self.resolve("stat_definition", key)
        if definition is None:
            self.skip(row, name, "its stat wasn't copied here")
            return False
        if prefix == "stats":
            await s.execute(
                delete(EntityStat).where(
                    EntityStat.entity_id == e,
                    EntityStat.stat_definition_id == definition,
                    EntityStat.tenant_id == t,
                )
            )
            if change.upstream is None:
                return True
            await s.execute(
                delete(ComputedStat).where(
                    ComputedStat.entity_id == e,
                    ComputedStat.stat_definition_id == definition,
                    ComputedStat.tenant_id == t,
                )
            )
            value_column = _value_column(self.value_types.get(definition))
            await s.execute(
                insert(EntityStat).values(
                    entity_id=e,
                    stat_definition_id=definition,
                    tenant_id=t,
                    **{value_column: change.upstream},
                )
            )
            return True
        # formulas
        formula = change.upstream
        inputs: dict[str, uuid.UUID | None] = {}
        if formula is not None:
            for role in ("source", "left", "right"):
                if formula.get(role):
                    inputs[role] = self.resolve("stat_definition", formula[role])
            if None in inputs.values():
                self.skip(row, name, "a stat its formula uses wasn't copied here")
                return False
        await s.execute(
            delete(ComputedStat).where(
                ComputedStat.entity_id == e,
                ComputedStat.stat_definition_id == definition,
                ComputedStat.tenant_id == t,
            )
        )
        if formula is None:
            return True
        await s.execute(
            delete(EntityStat).where(
                EntityStat.entity_id == e,
                EntityStat.stat_definition_id == definition,
                EntityStat.tenant_id == t,
            )
        )
        keys = {"entity_id": e, "stat_definition_id": definition, "tenant_id": t}
        await s.execute(insert(ComputedStat).values(**keys))
        if formula["kind"] == "linear":
            await s.execute(
                insert(ComputedStatLinear).values(
                    **keys,
                    source_stat_definition_id=inputs["source"],
                    multiplier=formula["multiplier"],
                    offset=formula["offset"],
                    round_mode=formula["round_mode"],
                )
            )
        else:
            await s.execute(
                insert(ComputedStatComparison).values(
                    **keys,
                    left_stat_definition_id=inputs["left"],
                    comparator=formula["comparator"],
                    right_stat_definition_id=inputs.get("right"),
                    right_constant=formula["right_constant"],
                    true_value=formula["true_value"],
                    false_value=formula["false_value"],
                )
            )
        return True

    # stat group -------------------------------------------------------------

    async def _stat_group(self, row: RowChange, change: FieldChange) -> bool:
        g, t, s = row.local_id, self.tenant_id, self.session
        if change.field == "name":
            taken = await s.scalar(
                select(StatGroup.id).where(
                    StatGroup.tenant_id == t, StatGroup.name == change.upstream, StatGroup.id != g
                )
            )
            if taken is not None:
                self.skip(row, "name", f"{change.upstream!r} is taken here")
                return False
        await s.execute(
            update(StatGroup)
            .where(StatGroup.id == g, StatGroup.tenant_id == t)
            .values(**{change.field: change.upstream})
        )
        return True

    # stat definition --------------------------------------------------------

    async def _stat_definition(self, row: RowChange, change: FieldChange) -> bool:
        d, t, s = row.local_id, self.tenant_id, self.session
        if change.field == "name":
            taken = await s.scalar(
                select(StatDefinition.id).where(
                    StatDefinition.tenant_id == t,
                    StatDefinition.name == change.upstream,
                    StatDefinition.id != d,
                )
            )
            if taken is not None:
                self.skip(row, "name", f"{change.upstream!r} is taken here")
                return False
            await s.execute(
                update(StatDefinition)
                .where(StatDefinition.id == d, StatDefinition.tenant_id == t)
                .values(name=change.upstream)
            )
            return True
        if change.field == "stat_group":
            group = self.resolve("stat_group", change.upstream)
            if group is None:
                self.skip(row, "stat_group", "that stat group wasn't copied here")
                return False
            await s.execute(
                update(StatDefinition)
                .where(StatDefinition.id == d, StatDefinition.tenant_id == t)
                .values(stat_group_id=group)
            )
            return True
        # enum_values
        ok = True
        for value in change.removed or []:
            in_use = await s.scalar(
                select(func.count())
                .select_from(EntityStat)
                .where(
                    EntityStat.stat_definition_id == d,
                    EntityStat.tenant_id == t,
                    EntityStat.value_text == value,
                )
            )
            if in_use:
                self.skip(row, "enum_values", f"{value!r} is still in use here")
                ok = False
                continue
            await s.execute(
                delete(StatDefinitionEnumValue).where(
                    StatDefinitionEnumValue.stat_definition_id == d,
                    StatDefinitionEnumValue.tenant_id == t,
                    StatDefinitionEnumValue.value == value,
                )
            )
        existing = set(
            await s.scalars(
                select(StatDefinitionEnumValue.value).where(
                    StatDefinitionEnumValue.stat_definition_id == d,
                    StatDefinitionEnumValue.tenant_id == t,
                )
            )
        )
        for value in change.added or []:
            if value not in existing:
                await s.execute(
                    insert(StatDefinitionEnumValue).values(
                        tenant_id=t, stat_definition_id=d, value=value
                    )
                )
        return ok


def _value_column(value_type: StatValueType | None) -> str:
    return {
        StatValueType.INT: "value_int",
        StatValueType.FLOAT: "value_float",
        StatValueType.BOOL: "value_bool",
    }.get(value_type, "value_text")  # type: ignore[arg-type]


def _next_snapshot(row: RowChange, failed: set[str], kept: set[str]) -> dict[str, Any]:
    """The upstream version, except where a field couldn't be applied: that
    keeps its base, so it's still offered next time. A field kept local
    takes the upstream value too - the difference was seen and decided."""
    snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in row.upstream.items()}
    for name in failed - kept:
        key, _, sub = name.partition(":")
        if sub:
            base = row.base.get(key, {})
            if sub in base:
                snapshot[key][sub] = base[sub]
            else:
                snapshot[key].pop(sub, None)
        else:
            snapshot[key] = row.base.get(key)
    return snapshot


async def apply_updates(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
    actions: list[UpdateAction],
) -> ApplyResult:
    """Applies the listed actions in one transaction (doesn't commit)."""
    updates = await compute_updates(session, tenant_id=tenant_id, repository_id=repository_id)
    assert updates.local is not None and updates.upstream is not None
    changed = {(c.kind, c.source_id): c for c in updates.changed}
    removed = {(r.kind, r.source_id): r for r in updates.removed}
    added = {(a.kind, a.source_id): a for a in updates.added}

    unnamed: list[dict[str, Any]] = []
    for action in actions:
        key = (action.kind, action.source_id)
        pools: dict[str, Mapping[tuple[RowKind, uuid.UUID], Any]] = {
            "apply": changed,
            "add": added,
            "detach": removed,
        }
        pool = pools[action.action]
        if key not in pool:
            raise InvalidRepositoryUpdateError(
                detail=f"{action.kind} {action.source_id} has nothing to {action.action}"
            )
        if action.action == "apply":
            named = set(action.keep_local) | set(action.take_upstream)
            unnamed += [
                {"kind": action.kind, "source_id": str(action.source_id), "field": f.field}
                for f in changed[key].fields
                if f.state == "conflict" and f.field not in named
            ]
    if unnamed:
        raise RepositoryUpdateNeedsChoicesError(
            detail="Name each conflicting field in keep_local or take_upstream", conflicts=unnamed
        )

    result = ApplyResult()
    # Additions first, so an applied change can point at a row added in the
    # same call; then the tenant's content again, with them in it.
    additions = [a for a in actions if a.action == "add"]
    local = updates.local
    if additions:
        await _add(session, updates, tenant_id, user_id, additions)
        result.added = len(additions)
        local = await load_content(session, tenant_id)

    applier = _Applier(session, tenant_id, local)
    applier.result = result
    for action in actions:
        key = (action.kind, action.source_id)
        model, _ = _LINK_MODELS[action.kind]
        if action.action == "detach":
            await session.execute(
                delete(model).where(
                    model.tenant_id == tenant_id, model.source_id == action.source_id
                )
            )
            result.detached += 1
        elif action.action == "apply":
            row = changed[key]
            kept = set(action.keep_local)
            chosen = [f for f in row.fields if f.state != "not_applicable" and f.field not in kept]
            failed = await applier.apply(row, chosen)
            # A field changed only by hand keeps its base, so it's shown
            # until the local copy matches.
            failed |= {f.field for f in row.fields if f.state == "not_applicable"}
            await session.execute(
                update(model)
                .where(model.tenant_id == tenant_id, model.source_id == row.source_id)
                .values(snapshot=_next_snapshot(row, failed, kept))
            )
            result.applied += 1

    await session.execute(
        update(RepositoryCopy)
        .where(
            RepositoryCopy.tenant_id == tenant_id,
            RepositoryCopy.repository_tenant_id == repository_id,
        )
        .values(synced_at=datetime.now(UTC))
    )
    await check_formula_cycles(session, tenant_id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user_id,
        action="repository.synced",
        target_type="tenant",
        target_id=repository_id,
        detail=(
            f"applied={result.applied},added={result.added},detached={result.detached},"
            f"not_applied={len(result.not_applied)}"
        ),
    )
    return result


async def _add(
    session: AsyncSession,
    updates: Updates,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    additions: list[UpdateAction],
) -> None:
    """Copies rows added upstream exactly as a first copy would (ADR 0119),
    everything else resolving through the tenant's links."""
    assert updates.local is not None and updates.upstream is not None
    resolutions = {
        (COLLISION_KIND[a.kind], a.source_id): Resolution(
            kind=COLLISION_KIND[a.kind],
            source_id=a.source_id,
            action=a.resolution.action,
            name=a.resolution.name,
        )
        for a in additions
        if a.resolution is not None
    }
    planner = _Planner(tenant_id, user_id, updates.local.links, resolutions)
    await planner.load_local_names(session)
    only: dict[str, set[uuid.UUID]] = {
        "entity": set(),
        "stat_group": set(),
        "stat_definition": set(),
    }
    for a in additions:
        only[a.kind].add(a.source_id)
    step = Step(
        repository_id=updates.repository_id,
        name="",
        granted=True,
        published=True,
        already_copied=True,
        content=updates.upstream,
    )
    planner.plan_step(step, only=only, record_copy=False)
    if planner.collisions:
        raise RepositoryCopyNeedsChoicesError(
            detail="Choose rename, merge, or skip for each one, as the addition's resolution",
            collisions=[c.as_json() for c in planner.collisions],
        )
    for definition_id, values in planner.enum_additions.items():
        for value in sorted(values):
            planner.rows["stat_definition_enum_value"].append(
                {"tenant_id": tenant_id, "stat_definition_id": definition_id, "value": value}
            )
    await write_rows(session, planner.rows)
