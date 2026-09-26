"""Copying repositories into a tenant - ADR 0119 (the copy) and ADR 0120
(bridges and their dependency manifests).

`plan_copy` reads everything a copy needs, each repository through the
gated read (ADR 0118), and works out in Python what would be written:
fresh ids, re-targeted references, collisions, and rows it has to drop.
`apply_plan` writes it, as the copying tenant, with no repository read
open. Only a repository's *own* rows are copied; a reference to a row it
copied from elsewhere is re-targeted through the origin both copies share
(RFC 0024 amendment A8), so a bridge's edges land on the subscriber's own
copies of its dependencies.
"""

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import delete, exists, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.description_payloads import reference_values
from lorenzo_api.exceptions import (
    InvalidRepositoryCopyChoiceError,
    RepositoryAlreadyCopiedError,
    RepositoryCopyFormulaCycleError,
    RepositoryCopyNeedsChoicesError,
    RepositoryCopyNeedsGrantsError,
    RepositoryNotFoundError,
)
from lorenzo_api.models import (
    Being,
    Character,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatLinear,
    Containment,
    ContentReference,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    GroupMember,
    Information,
    Item,
    ItemInstance,
    Knowledge,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    RepositorySubscription,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    Tenant,
    TenantKind,
)
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import (
    Content,
    Links,
    entity_snapshot,
    index_entities,
    load_content,
    load_links,
    origin_namer,
    stat_definition_snapshot,
    stat_group_snapshot,
)

CollisionKind = Literal["stat_group", "stat_definition", "slug"]
Action = Literal["rename", "merge", "skip"]

# ADR 0107's slug grammar (schemas.common.Slug).
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_MAX_SLUG = 100


@dataclass(frozen=True)
class Resolution:
    kind: CollisionKind
    source_id: uuid.UUID
    action: Action
    name: str | None = None


@dataclass
class Collision:
    repository_id: uuid.UUID
    kind: CollisionKind
    source_id: uuid.UUID
    name: str
    local_id: uuid.UUID | None
    choices: list[Action]

    def as_json(self) -> dict[str, Any]:
        return {
            "repository_id": str(self.repository_id),
            "kind": self.kind,
            "source_id": str(self.source_id),
            "name": self.name,
            "local_id": str(self.local_id) if self.local_id else None,
            "choices": self.choices,
        }


@dataclass
class Dropped:
    kind: str
    source_id: uuid.UUID
    reason: str


@dataclass
class Step:
    """One repository in a copy's manifest (ADR 0120)."""

    repository_id: uuid.UUID
    name: str
    granted: bool
    published: bool
    already_copied: bool
    content: Content | None = None
    entities: int = 0
    stat_groups: int = 0
    stat_definitions: int = 0
    information: int = 0
    dropped: list[Dropped] = field(default_factory=list)


@dataclass
class Plan:
    tenant_id: uuid.UUID
    steps: list[Step]
    collisions: list[Collision] = field(default_factory=list)
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))

    @property
    def missing(self) -> list[Step]:
        return [s for s in self.steps if not s.already_copied and not (s.granted and s.published)]

    @property
    def to_copy(self) -> list[Step]:
        return [s for s in self.steps if not s.already_copied]


# --- The manifest (ADR 0120) ---------------------------------------------------


async def _step(
    session: AsyncSession, tenant_id: uuid.UUID, repository_id: uuid.UUID, copied: set[uuid.UUID]
) -> Step:
    repository = await session.get(Tenant, repository_id)
    granted = (await session.get(RepositorySubscription, (repository_id, tenant_id))) is not None
    return Step(
        repository_id=repository_id,
        name=repository.name if repository else "",
        granted=granted,
        published=bool(
            repository
            and repository.kind is TenantKind.REPOSITORY
            and repository.published_at is not None
        ),
        already_copied=repository_id in copied,
    )


async def _dependencies(session: AsyncSession, repository_id: uuid.UUID) -> set[uuid.UUID] | None:
    """The repositories `repository_id` has copied, read through the gated
    read; None if this tenant can't read it."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            return None
        return set(
            await session.scalars(
                select(RepositoryCopy.repository_tenant_id).where(
                    RepositoryCopy.tenant_id == repository_id
                )
            )
        )


async def manifest(
    session: AsyncSession, *, tenant_id: uuid.UUID, repository_id: uuid.UUID
) -> list[Step]:
    """`repository_id`'s dependencies in dependency order, then itself
    (ADR 0120). A dependency's own dependencies are already among the
    repository's: it had to copy them first. The copying tenant is never a
    step, even if it's somebody's dependency - its rows are the origins.
    """
    copied = (await load_links(session, tenant_id)).copies
    top = await _step(session, tenant_id, repository_id, copied)
    if not (top.granted and top.published):
        raise RepositoryNotFoundError(
            detail=f"No published repository {repository_id} is granted to tenant {tenant_id}"
        )
    deps = (await _dependencies(session, repository_id) or set()) - {tenant_id, repository_id}
    steps = {d: await _step(session, tenant_id, d, copied) for d in deps}
    # Order the dependencies among themselves by what each one copied.
    edges: dict[uuid.UUID, set[uuid.UUID]] = {}
    for d, step in steps.items():
        readable = step.granted and step.published
        edges[d] = ((await _dependencies(session, d) or set()) & deps) if readable else set()
    ordered: list[uuid.UUID] = []
    state: dict[uuid.UUID, int] = {}

    def visit(node: uuid.UUID) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            return  # two repositories copied each other: either order works
        state[node] = 1
        for successor in sorted(edges[node], key=str):
            visit(successor)
        state[node] = 2
        ordered.append(node)

    for d in sorted(deps, key=lambda d: (steps[d].name, str(d))):
        visit(d)
    return [steps[d] for d in ordered] + [top]


# --- Planning (ADR 0119) --------------------------------------------------------


class _Planner:
    """Works out a copy step by step. The names, slugs, and origin maps it
    carries between steps are what makes two repositories in one manifest
    collide with each other, and a bridge's references land on copies made
    earlier in the same call."""

    def __init__(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        links: Links,
        resolutions: dict[tuple[str, uuid.UUID], Resolution],
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.resolutions = resolutions
        self.collisions: list[Collision] = []
        self.rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # Origin id -> local id, per kind: the tenant's links, then every
        # row this plan copies or merges.
        self.local = {
            kind: links.local_of(kind) for kind in ("entity", "stat_group", "stat_definition")
        }
        self.group_names: dict[str, uuid.UUID] = {}
        self.definitions: dict[str, tuple[uuid.UUID, Any, set[str]]] = {}
        self.slugs: set[str] = set()
        # The tenant's own row ids, per kind, for a repository that copied
        # this tenant (ADR 0120: the tenant's rows are then the origins).
        self.existing: dict[str, set[uuid.UUID]] = {}
        self.enum_additions: dict[uuid.UUID, set[str]] = defaultdict(set)

    async def load_local_names(self, session: AsyncSession) -> None:
        t = self.tenant_id
        for group_id, name in await session.execute(
            select(StatGroup.id, StatGroup.name).where(StatGroup.tenant_id == t)
        ):
            self.group_names[name] = group_id
        vocab: dict[uuid.UUID, set[str]] = defaultdict(set)
        for def_id, value in await session.execute(
            select(StatDefinitionEnumValue.stat_definition_id, StatDefinitionEnumValue.value).where(
                StatDefinitionEnumValue.tenant_id == t
            )
        ):
            vocab[def_id].add(value)
        for def_id, name, value_type in await session.execute(
            select(StatDefinition.id, StatDefinition.name, StatDefinition.value_type).where(
                StatDefinition.tenant_id == t
            )
        ):
            self.definitions[name] = (def_id, value_type, vocab[def_id])
        self.slugs = set(
            await session.scalars(select(EntitySlug.slug).where(EntitySlug.tenant_id == t))
        )
        self.existing = {
            "entity": set(await session.scalars(select(Entity.id).where(Entity.tenant_id == t))),
            "stat_group": set(self.group_names.values()),
            "stat_definition": {d for d, _, _ in self.definitions.values()},
        }

    def _resolve(
        self,
        step: Step,
        kind: CollisionKind,
        source_id: uuid.UUID,
        name: str,
        local_id: uuid.UUID | None,
        choices: list[Action],
    ) -> Resolution | None:
        resolution = self.resolutions.get((kind, source_id))
        if resolution is None:
            self.collisions.append(
                Collision(step.repository_id, kind, source_id, name, local_id, choices)
            )
            return None
        if resolution.action not in choices:
            raise InvalidRepositoryCopyChoiceError(
                detail=f"{name!r} can be resolved with {', '.join(choices)}, "
                f"not {resolution.action}"
            )
        return resolution

    def _local(self, content: Content, kind: str, source_id: uuid.UUID) -> uuid.UUID | None:
        """Where one of a repository's rows lives in the copying tenant, if
        anywhere: through the origin both copies share (ADR 0120)."""
        origin = content.origin(kind, source_id)
        local = self.local[kind].get(origin)
        if local is not None:
            return local
        if content.links.origin_tenant.get(origin) == self.tenant_id:
            # The copying tenant's own row, copied into this repository.
            return origin if origin in self.existing[kind] else None
        return None

    def plan_step(
        self,
        step: Step,
        *,
        only: dict[str, set[uuid.UUID]] | None = None,
        record_copy: bool = True,
    ) -> None:
        """Plans copying one repository's own rows. `only` narrows it to the
        rows named, per kind - ADR 0121's additions, where everything else
        was copied before and resolves through the tenant's links."""
        c = step.content
        assert c is not None

        def copies(kind: str, row_id: uuid.UUID) -> bool:
            return c.own(kind, row_id) and (only is None or row_id in only.get(kind, set()))

        repository_id, tenant_id, user_id = step.repository_id, self.tenant_id, self.user_id

        def drop(kind: str, source_id: uuid.UUID, reason: str) -> None:
            step.dropped.append(Dropped(kind, source_id, reason))

        # Stat groups.
        for g in sorted(
            (g for g in c.groups if copies("stat_group", g)), key=lambda g: c.groups[g]["name"]
        ):
            group = c.groups[g]
            name = group["name"]
            if name in self.group_names:
                choice = self._resolve(
                    step, "stat_group", g, name, self.group_names[name], ["rename", "merge", "skip"]
                )
                if choice is None:
                    # Unresolved: plan it as if renamed, so its definitions'
                    # own collisions show too.
                    self.local["stat_group"][g] = uuid.uuid4()
                    continue
                if choice.action == "skip":
                    continue
                if choice.action == "merge":
                    self.local["stat_group"][g] = self.group_names[name]
                    self.rows["link_stat_group"].append(
                        self._link(
                            repository_id,
                            g,
                            self.group_names[name],
                            stat_group_snapshot(c, g),
                            "merged",
                        )
                    )
                    continue
                name = self._new_name(choice, taken=self.group_names)
            new = uuid.uuid4()
            self.local["stat_group"][g] = new
            self.group_names[name] = new
            self.rows["stat_group"].append(
                {
                    "id": new,
                    "tenant_id": tenant_id,
                    "name": name,
                    "priority": group["priority"],
                    "mandatory": group["mandatory"],
                }
            )
            self.rows["link_stat_group"].append(
                self._link(repository_id, g, new, stat_group_snapshot(c, g), "copied")
            )
            step.stat_groups += 1

        # Stat definitions.
        namer = origin_namer(c)
        for d in sorted(
            (d for d in c.definitions if copies("stat_definition", d)),
            key=lambda d: c.definitions[d]["name"],
        ):
            definition = c.definitions[d]
            local_group = self._local(c, "stat_group", definition["group"])
            if local_group is None:
                drop("stat_definition", d, "its stat group wasn't copied")
                continue
            name = definition["name"]
            values = {v for v, _ in c.enum_values.get(d, [])}
            if name in self.definitions:
                existing, value_type, vocab = self.definitions[name]
                choices: list[Action] = ["rename", "skip"]
                if value_type is definition["value_type"]:
                    choices.insert(1, "merge")
                choice = self._resolve(step, "stat_definition", d, name, existing, choices)
                if choice is None:
                    self.local["stat_definition"][d] = uuid.uuid4()
                    continue
                if choice.action == "skip":
                    continue
                if choice.action == "merge":
                    self.local["stat_definition"][d] = existing
                    self.enum_additions[existing] |= values - vocab
                    vocab |= values
                    self.rows["link_stat_definition"].append(
                        self._link(
                            repository_id,
                            d,
                            existing,
                            stat_definition_snapshot(c, d, namer),
                            "merged",
                        )
                    )
                    continue
                name = self._new_name(choice, taken=self.definitions)
            new = uuid.uuid4()
            self.local["stat_definition"][d] = new
            self.definitions[name] = (new, definition["value_type"], set(values))
            self.rows["stat_definition"].append(
                {
                    "id": new,
                    "tenant_id": tenant_id,
                    "stat_group_id": local_group,
                    "name": name,
                    "value_type": definition["value_type"],
                }
            )
            for value, sort_order in c.enum_values.get(d, []):
                self.rows["stat_definition_enum_value"].append(
                    {
                        "tenant_id": tenant_id,
                        "stat_definition_id": new,
                        "value": value,
                        "sort_order": sort_order,
                    }
                )
            self.rows["link_stat_definition"].append(
                self._link(repository_id, d, new, stat_definition_snapshot(c, d, namer), "copied")
            )
            step.stat_definitions += 1

        # Entities, and everything that belongs to one.
        own = [e for e in c.entities if copies("entity", e)]
        for e in own:
            self.local["entity"][e] = uuid.uuid4()
        index = index_entities(c)
        for e in own:
            new = self.local["entity"][e]
            self.rows["entity"].append(
                {
                    "id": new,
                    "tenant_id": tenant_id,
                    "name": c.entities[e],
                    "created_by": user_id,
                    "updated_by": user_id,
                }
            )
            kinds = c.kinds.get(e, set())
            if "item" in kinds:
                self.rows["item"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "in_public_catalog": c.in_public_catalog.get(e, False),
                    }
                )
            if "item_instance" in kinds:
                self.rows["item_instance"].append({"entity_id": new, "tenant_id": tenant_id})
            if "being" in kinds:
                self.rows["being"].append({"entity_id": new, "tenant_id": tenant_id})
            if "character" in kinds:
                self.rows["character"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "owner_player_id": None,
                        "created_by": user_id,
                        "updated_by": user_id,
                    }
                )
            slug = c.slugs.get(e)
            if slug is not None and slug in self.slugs:
                choice = self._resolve(step, "slug", e, slug, None, ["rename", "skip"])
                slug = None if choice is None or choice.action == "skip" else self._new_slug(choice)
            if slug is not None:
                self.slugs.add(slug)
                self.rows["entity_slug"].append(
                    {"entity_id": new, "tenant_id": tenant_id, "slug": slug}
                )
            self.rows["link_entity"].append(
                self._link(repository_id, e, new, entity_snapshot(c, index, e, namer))
            )
            step.entities += 1

        for e, p in c.prototypes:
            if copies("entity", e):
                target = self._local(c, "entity", p)
                if target is None:
                    drop("entity_prototype", e, "its prototype wasn't copied")
                    continue
                self.rows["entity_prototype"].append(
                    {
                        "entity_id": self.local["entity"][e],
                        "prototype_id": target,
                        "tenant_id": tenant_id,
                    }
                )
        for e, g in c.entity_groups:
            if not copies("entity", e):
                continue
            target = self._local(c, "stat_group", g)
            if target is None:
                drop("entity_stat_group", e, "its stat group wasn't copied")
                continue
            self.rows["entity_stat_group"].append(
                {
                    "entity_id": self.local["entity"][e],
                    "stat_group_id": target,
                    "tenant_id": tenant_id,
                }
            )
        for (e, d), stat_value in c.stats.items():
            if not copies("entity", e):
                continue
            target = self._local(c, "stat_definition", d)
            if target is None:
                drop("entity_stat", e, "its stat definition wasn't copied")
                continue
            self.rows["entity_stat"].append(
                {
                    "entity_id": self.local["entity"][e],
                    "stat_definition_id": target,
                    "tenant_id": tenant_id,
                    "value_int": stat_value.value_int,
                    "value_text": stat_value.value_text,
                    "value_float": stat_value.value_float,
                    "value_bool": stat_value.value_bool,
                }
            )
        for (e, d), formula in c.formulas.items():
            if not copies("entity", e):
                continue
            target = self._local(c, "stat_definition", d)
            inputs = {i: self._local(c, "stat_definition", i) for i in formula.inputs()}
            if target is None or None in inputs.values():
                drop("computed_stat", e, "a stat its formula uses wasn't copied")
                continue
            local_entity = self.local["entity"][e]
            key = {"entity_id": local_entity, "stat_definition_id": target, "tenant_id": tenant_id}
            self.rows["computed_stat"].append(dict(key))
            if formula.kind == "linear":
                assert formula.source is not None
                self.rows["computed_stat_linear"].append(
                    key
                    | {
                        "source_stat_definition_id": inputs[formula.source],
                        "multiplier": formula.multiplier,
                        "offset": formula.offset,
                        "round_mode": formula.round_mode,
                    }
                )
            else:
                assert formula.left is not None
                self.rows["computed_stat_comparison"].append(
                    key
                    | {
                        "left_stat_definition_id": inputs[formula.left],
                        "comparator": formula.comparator,
                        "right_stat_definition_id": (
                            inputs[formula.right] if formula.right else None
                        ),
                        "right_constant": formula.right_constant,
                        "true_value": formula.true_value,
                        "false_value": formula.false_value,
                    }
                )
        for child, (parent, quantity) in c.containment.items():
            if not copies("entity", child):
                continue
            target = self._local(c, "entity", parent)
            if target is None:
                drop("containment", child, "its container wasn't copied")
                continue
            self.rows["containment"].append(
                {
                    "child_entity_id": self.local["entity"][child],
                    "parent_entity_id": target,
                    "tenant_id": tenant_id,
                    "quantity": quantity,
                }
            )
        for owned, owner in c.ownership.items():
            if not copies("entity", owned):
                continue
            target = self._local(c, "entity", owner)
            if target is None:
                drop("ownership", owned, "its owner wasn't copied")
                continue
            self.rows["ownership"].append(
                {
                    "owned_entity_id": self.local["entity"][owned],
                    "owner_character_id": target,
                    "tenant_id": tenant_id,
                }
            )
        for group_entity, member in c.group_members:
            if not copies("entity", group_entity):
                continue
            target = self._local(c, "entity", member)
            if target is None:
                drop("group_member", group_entity, "a member wasn't copied")
                continue
            self.rows["group_member"].append(
                {
                    "group_entity_id": self.local["entity"][group_entity],
                    "character_entity_id": target,
                    "tenant_id": tenant_id,
                }
            )

        # Information, its payloads, and who knows it.
        local_information: dict[uuid.UUID, uuid.UUID] = {}
        for info_id, info in c.information.items():
            if not copies("entity", info.entity_id):
                continue
            new = uuid.uuid4()
            local_information[info_id] = new
            self.rows["information"].append(
                {
                    "id": new,
                    "tenant_id": tenant_id,
                    "entity_id": self.local["entity"][info.entity_id],
                    "title": info.title,
                    "type": info.type,
                    "is_public": info.is_public,
                    "order": info.order,
                    "created_by": user_id,
                }
            )
            step.information += 1
        for payload in c.payloads.values():
            local_info = local_information.get(payload.information_id)
            if local_info is None:
                continue
            new = uuid.uuid4()
            self.rows["payload"].append(
                {
                    "id": new,
                    "tenant_id": tenant_id,
                    "information_id": local_info,
                    "order": payload.order,
                }
            )
            self.rows[f"payload_{payload.kind}"].append(
                {"payload_id": new, "tenant_id": tenant_id} | payload.fields
            )
            if payload.kind == "description":
                for position, (kind, hint, target_text) in enumerate(
                    reference_values(payload.fields["content"])
                ):
                    self.rows["content_reference"].append(
                        {
                            "payload_id": new,
                            "position": position,
                            "tenant_id": tenant_id,
                            "kind": kind,
                            "hint": hint,
                            "target": target_text,
                        }
                    )
        for info_id, knower in c.knowledge:
            known = local_information.get(info_id)
            if known is None:
                continue
            target = self._local(c, "entity", knower)
            if target is None:
                drop("knowledge", info_id, "its knower wasn't copied")
                continue
            self.rows["knowledge"].append(
                {"tenant_id": tenant_id, "knower_entity_id": target, "information_id": known}
            )

        if record_copy:
            self.rows["repository_copy"].append(
                {
                    "tenant_id": tenant_id,
                    "repository_tenant_id": repository_id,
                    "repository_name": step.name,
                    "copied_by": user_id,
                }
            )

    def _link(
        self,
        repository_id: uuid.UUID,
        source_id: uuid.UUID,
        local_id: uuid.UUID,
        snapshot: dict[str, Any],
        mode: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "tenant_id": self.tenant_id,
            "local_id": local_id,
            "source_tenant_id": repository_id,
            "source_id": source_id,
            "snapshot": snapshot,
        }
        if mode is not None:
            row["mode"] = mode
        return row

    @staticmethod
    def _new_name(choice: Resolution, *, taken: dict[str, Any]) -> str:
        name = (choice.name or "").strip()
        if not name:
            raise InvalidRepositoryCopyChoiceError(detail="A rename needs a new name")
        if name in taken:
            raise InvalidRepositoryCopyChoiceError(detail=f"{name!r} is taken here too")
        return name

    def _new_slug(self, choice: Resolution) -> str:
        slug = (choice.name or "").strip()
        if not _SLUG.match(slug) or len(slug) > _MAX_SLUG:
            raise InvalidRepositoryCopyChoiceError(detail=f"{slug!r} isn't a valid slug")
        if slug in self.slugs:
            raise InvalidRepositoryCopyChoiceError(detail=f"The slug {slug!r} is taken here too")
        return slug


async def plan_copy(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    repository_id: uuid.UUID,
    user_id: uuid.UUID,
    resolutions: list[Resolution],
) -> Plan:
    """Everything a copy would do, without writing. Raises nothing about
    collisions or grants: the plan carries them, for `copy-plan` to show
    and `apply_plan` to refuse."""
    steps = await manifest(session, tenant_id=tenant_id, repository_id=repository_id)
    plan = Plan(tenant_id=tenant_id, steps=steps)
    if steps[-1].already_copied or plan.missing:
        return plan
    links = await load_links(session, tenant_id)
    planner = _Planner(tenant_id, user_id, links, {(r.kind, r.source_id): r for r in resolutions})
    await planner.load_local_names(session)
    for step in plan.to_copy:
        async with reading_repository(session, step.repository_id) as allowed:
            assert allowed  # manifest already checked grant and publication
            step.content = await load_content(session, step.repository_id)
        planner.plan_step(step)
    plan.collisions = planner.collisions
    plan.rows = planner.rows
    for definition_id, values in planner.enum_additions.items():
        for value in sorted(values):
            plan.rows["stat_definition_enum_value"].append(
                {"tenant_id": tenant_id, "stat_definition_id": definition_id, "value": value}
            )
    return plan


# --- Writing -------------------------------------------------------------------

_TABLES: list[tuple[str, Any]] = [
    ("stat_group", StatGroup),
    ("stat_definition", StatDefinition),
    ("stat_definition_enum_value", StatDefinitionEnumValue),
    ("entity", Entity),
    ("item", Item),
    ("item_instance", ItemInstance),
    ("being", Being),
    ("character", Character),
    ("entity_slug", EntitySlug),
    ("entity_prototype", EntityPrototype),
    ("entity_stat_group", EntityStatGroup),
    ("entity_stat", EntityStat),
    ("computed_stat", ComputedStat),
    ("computed_stat_linear", ComputedStatLinear),
    ("computed_stat_comparison", ComputedStatComparison),
    ("containment", Containment),
    ("ownership", Ownership),
    ("group_member", GroupMember),
    ("information", Information),
    ("payload", Payload),
    ("payload_description", PayloadDescription),
    ("payload_number", PayloadNumber),
    ("payload_picture", PayloadPicture),
    ("payload_document", PayloadDocument),
    ("knowledge", Knowledge),
    ("content_reference", ContentReference),
    ("repository_copy", RepositoryCopy),
]
_LINKS: list[tuple[str, Any, str]] = [
    ("link_entity", RepositoryCopyLinkEntity, "entity_id"),
    ("link_stat_group", RepositoryCopyLinkStatGroup, "stat_group_id"),
    ("link_stat_definition", RepositoryCopyLinkStatDefinition, "stat_definition_id"),
]


async def write_rows(session: AsyncSession, rows: dict[str, list[dict[str, Any]]]) -> None:
    """Inserts a plan's rows in dependency order. Shared with ADR 0121's
    updates, which add rows the same way."""
    for key, model in _TABLES:
        if rows.get(key):
            await session.execute(insert(model), rows[key])
    for key, model, local in _LINKS:
        if rows.get(key):
            await session.execute(
                insert(model),
                [{local if k == "local_id" else k: v for k, v in r.items()} for r in rows[key]],
            )


async def check_formula_cycles(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """The tenant's formula graph, whole, after a copy or update wrote
    formulas: an edge from each formula's stat to each stat it reads
    (ADR 0104). Merging definitions is the only way a copy can close a
    loop."""
    edges: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for target, source in await session.execute(
        select(
            ComputedStatLinear.stat_definition_id, ComputedStatLinear.source_stat_definition_id
        ).where(ComputedStatLinear.tenant_id == tenant_id)
    ):
        edges[target].add(source)
    for target, left, right in await session.execute(
        select(
            ComputedStatComparison.stat_definition_id,
            ComputedStatComparison.left_stat_definition_id,
            ComputedStatComparison.right_stat_definition_id,
        ).where(ComputedStatComparison.tenant_id == tenant_id)
    ):
        edges[target].add(left)
        if right is not None:
            edges[target].add(right)
    state: dict[uuid.UUID, int] = {}
    for start in list(edges):
        if state.get(start):
            continue
        stack: list[tuple[uuid.UUID, list[uuid.UUID]]] = [(start, list(edges[start]))]
        state[start] = 1
        while stack:
            node, pending = stack[-1]
            if not pending:
                state[node] = 2
                stack.pop()
                continue
            successor = pending.pop()
            if state.get(successor) == 1:
                raise RepositoryCopyFormulaCycleError(
                    detail="Merged stats would make formulas depend on each other in a loop"
                )
            if not state.get(successor):
                state[successor] = 1
                stack.append((successor, list(edges.get(successor, ()))))


async def apply_plan(session: AsyncSession, plan: Plan, *, user_id: uuid.UUID) -> None:
    """Writes a plan, or refuses it. Doesn't commit."""
    if plan.steps[-1].already_copied:
        raise RepositoryAlreadyCopiedError(
            detail="Its later changes come in through its updates, not another copy"
        )
    if plan.missing:
        raise RepositoryCopyNeedsGrantsError(
            detail="Ask each one's owners for access, or to publish it",
            missing=[
                {
                    "repository_id": str(s.repository_id),
                    "name": s.name,
                    "granted": s.granted,
                    "published": s.published,
                }
                for s in plan.missing
            ],
        )
    if plan.collisions:
        raise RepositoryCopyNeedsChoicesError(
            detail="Choose rename, merge, or skip for each one, and send them as resolutions",
            collisions=[c.as_json() for c in plan.collisions],
        )
    await write_rows(session, plan.rows)
    await check_formula_cycles(session, plan.tenant_id)
    for step in plan.to_copy:
        await record_activity(
            session,
            tenant_id=plan.tenant_id,
            actor_id=user_id,
            action="repository.copied",
            target_type="tenant",
            target_id=step.repository_id,
            detail=(
                f"entities={step.entities},stat_groups={step.stat_groups},"
                f"stat_definitions={step.stat_definitions},information={step.information},"
                f"dropped={len(step.dropped)}"
            ),
        )


# --- Copying again (ADR 0119) ----------------------------------------------------


@dataclass
class Previous:
    """What happened to an earlier copy before copying again."""

    mode: Literal["keep", "purge"]
    entities: int
    stat_groups: int
    stat_definitions: int
    # Rows of the tenant's own that went with a purge, per kind.
    also_removed: dict[str, int] = field(default_factory=dict)


async def _count(session: AsyncSession, model: Any, *where: Any) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


async def forget_copy(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    repository_id: uuid.UUID,
    purge: bool,
    user_id: uuid.UUID,
) -> Previous:
    """Drops the tenant's copy record and links for a repository, so it can
    be copied afresh. With `purge`, first deletes the rows the copy
    created - entities, and groups and definitions linked as `copied` -
    and counts what of the tenant's own goes with them. Doesn't commit."""
    t = tenant_id

    async def local_ids(model: Any, column: Any, copied_only: bool) -> set[uuid.UUID]:
        stmt = select(column).where(
            model.tenant_id == t, model.source_tenant_id == repository_id, column.is_not(None)
        )
        if copied_only:
            stmt = stmt.where(model.mode == "copied")
        return set(await session.scalars(stmt))

    entities = await local_ids(RepositoryCopyLinkEntity, RepositoryCopyLinkEntity.entity_id, False)
    groups = await local_ids(
        RepositoryCopyLinkStatGroup, RepositoryCopyLinkStatGroup.stat_group_id, True
    )
    definitions = await local_ids(
        RepositoryCopyLinkStatDefinition, RepositoryCopyLinkStatDefinition.stat_definition_id, True
    )
    previous = Previous("purge" if purge else "keep", len(entities), len(groups), len(definitions))

    if purge:
        # The tenant's own definitions inside a purged group go with it.
        own_definitions = set(
            await session.scalars(
                select(StatDefinition.id).where(
                    StatDefinition.tenant_id == t,
                    StatDefinition.stat_group_id.in_(groups),
                    StatDefinition.id.not_in(definitions),
                )
            )
        )
        all_definitions = definitions | own_definitions
        uses_definition = or_(
            ComputedStat.stat_definition_id.in_(all_definitions),
            exists().where(
                ComputedStatLinear.entity_id == ComputedStat.entity_id,
                ComputedStatLinear.stat_definition_id == ComputedStat.stat_definition_id,
                ComputedStatLinear.source_stat_definition_id.in_(all_definitions),
            ),
            exists().where(
                ComputedStatComparison.entity_id == ComputedStat.entity_id,
                ComputedStatComparison.stat_definition_id == ComputedStat.stat_definition_id,
                or_(
                    ComputedStatComparison.left_stat_definition_id.in_(all_definitions),
                    ComputedStatComparison.right_stat_definition_id.in_(all_definitions),
                ),
            ),
        )
        own_formulas = (ComputedStat.tenant_id == t) & ComputedStat.entity_id.not_in(entities)
        also = {
            "stat_definition": len(own_definitions),
            "entity_stat": await _count(
                session,
                EntityStat,
                EntityStat.tenant_id == t,
                EntityStat.stat_definition_id.in_(all_definitions),
                EntityStat.entity_id.not_in(entities),
            ),
            "computed_stat": await _count(session, ComputedStat, own_formulas, uses_definition),
            "entity_stat_group": await _count(
                session,
                EntityStatGroup,
                EntityStatGroup.tenant_id == t,
                EntityStatGroup.stat_group_id.in_(groups),
                EntityStatGroup.entity_id.not_in(entities),
            ),
            "entity_prototype": await _count(
                session,
                EntityPrototype,
                EntityPrototype.tenant_id == t,
                EntityPrototype.prototype_id.in_(entities),
                EntityPrototype.entity_id.not_in(entities),
            ),
            "containment": await _count(
                session,
                Containment,
                Containment.tenant_id == t,
                Containment.parent_entity_id.in_(entities),
                Containment.child_entity_id.not_in(entities),
            ),
            "ownership": await _count(
                session,
                Ownership,
                Ownership.tenant_id == t,
                Ownership.owner_character_id.in_(entities),
                Ownership.owned_entity_id.not_in(entities),
            ),
            "group_member": await _count(
                session,
                GroupMember,
                GroupMember.tenant_id == t,
                GroupMember.character_entity_id.in_(entities),
                GroupMember.group_entity_id.not_in(entities),
            ),
            "knowledge": await _count(
                session,
                Knowledge,
                Knowledge.tenant_id == t,
                Knowledge.knower_entity_id.in_(entities),
                Knowledge.information_id.in_(
                    select(Information.id).where(
                        Information.tenant_id == t, Information.entity_id.not_in(entities)
                    )
                ),
            ),
        }
        previous.also_removed = {kind: n for kind, n in also.items() if n}
        # Formula inputs don't cascade (ADR 0104), so the tenant's own
        # formulas reading a purged definition go first; everything else
        # cascades from the rows themselves.
        await session.execute(delete(ComputedStat).where(own_formulas, uses_definition))
        await session.execute(delete(Entity).where(Entity.tenant_id == t, Entity.id.in_(entities)))
        await session.execute(
            delete(StatDefinition).where(
                StatDefinition.tenant_id == t, StatDefinition.id.in_(all_definitions)
            )
        )
        await session.execute(
            delete(StatGroup).where(StatGroup.tenant_id == t, StatGroup.id.in_(groups))
        )

    for model in (
        RepositoryCopyLinkEntity,
        RepositoryCopyLinkStatGroup,
        RepositoryCopyLinkStatDefinition,
    ):
        await session.execute(
            delete(model).where(model.tenant_id == t, model.source_tenant_id == repository_id)
        )
    await session.execute(
        delete(RepositoryCopy).where(
            RepositoryCopy.tenant_id == t, RepositoryCopy.repository_tenant_id == repository_id
        )
    )
    await record_activity(
        session,
        tenant_id=t,
        actor_id=user_id,
        action="repository.copy_purged" if purge else "repository.copy_forgotten",
        target_type="tenant",
        target_id=repository_id,
        detail=(
            f"entities={previous.entities},stat_groups={previous.stat_groups},"
            f"stat_definitions={previous.stat_definitions},"
            f"also_removed={sum(previous.also_removed.values())}"
        ),
    )
    return previous
