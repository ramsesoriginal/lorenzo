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

from sqlalchemy import delete, exists, func, insert, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.copyable_tables import COPIED_TABLES, COPY_LINKS, LINK_MODELS, PURGE_COUNTED
from lorenzo_api.description_payloads import reference_values
from lorenzo_api.exceptions import (
    EntityKindInUseError,
    InvalidRepositoryCopyChoiceError,
    InvalidRepositoryUpdateError,
    RepositoryAlreadyCopiedError,
    RepositoryCopyFormulaCycleError,
    RepositoryCopyNeedsChoicesError,
    RepositoryCopyNeedsGrantsError,
    RepositoryNotFoundError,
)
from lorenzo_api.models import (
    Calendar,
    CalendarObservance,
    CalendarPeriod,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatContents,
    ComputedStatLinear,
    ComputedStatSumTerm,
    Containment,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    EntryCalendarPeriod,
    EventLearning,
    EventParticipant,
    EventRelationship,
    GroupMember,
    Information,
    Knowledge,
    Ownership,
    RepositoryCopy,
    RepositoryCopyLinkAttachment,
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
from lorenzo_api.models.fact import EntityKnowledge, FactAbout
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import (
    Content,
    Links,
    attachments_of,
    entity_snapshot,
    index_entities,
    load_links,
    origin_namer,
    stat_definition_snapshot,
    stat_group_snapshot,
)
from lorenzo_api.repository_upstream import is_public, load_upstream, upstream_copies

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
    # Readable without a grant, because the repository is public (ADR 0287).
    public: bool = False
    content: Content | None = None
    # The release the repository is read at when it is planned, its current one: what the copy
    # records as taken (ADR 0207, 0286).
    release_id: uuid.UUID | None = None
    entities: int = 0
    stat_groups: int = 0
    stat_definitions: int = 0
    information: int = 0
    # The attachment edges the step writes (ADR 0172).
    attachments: int = 0
    dropped: list[Dropped] = field(default_factory=list)

    @property
    def readable(self) -> bool:
        """Whether the copying tenant may read it: it is published, and the tenant holds a grant
        or it is public (ADR 0287)."""
        return self.published and (self.granted or self.public)


LOOP_REASON = "it would make a prototype loop here"


@dataclass
class PlannedAttachment:
    """A parent a repository added to one of its copies, with its two ends found
    in the copying tenant (ADR 0172). `edge` is false where the tenant already has
    the parent, so only the link is recorded."""

    step: Step
    child: uuid.UUID
    parent: uuid.UUID
    child_source_id: uuid.UUID
    parent_source_id: uuid.UUID
    edge: bool


@dataclass
class Plan:
    tenant_id: uuid.UUID
    steps: list[Step]
    collisions: list[Collision] = field(default_factory=list)
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    attachments: list[PlannedAttachment] = field(default_factory=list)

    @property
    def missing(self) -> list[Step]:
        return [s for s in self.steps if not s.already_copied and not s.readable]

    @property
    def to_copy(self) -> list[Step]:
        return [s for s in self.steps if not s.already_copied]


# --- The manifest (ADR 0120) ---------------------------------------------------


async def _step(
    session: AsyncSession,
    tenant_id: uuid.UUID | None,
    repository_id: uuid.UUID,
    copied: set[uuid.UUID],
) -> Step:
    """One repository as `tenant_id` stands with it (a user with no library: `None`)."""
    repository = await session.get(Tenant, repository_id)
    granted = (
        tenant_id is not None
        and (await session.get(RepositorySubscription, (repository_id, tenant_id))) is not None
    )
    # A delisted repository reads as unpublished to everyone but its own members (ADR 0303).
    published = bool(
        repository
        and repository.kind is TenantKind.REPOSITORY
        and repository.published_at is not None
        and repository.delisted_at is None
    )
    public = False
    if published:
        async with reading_repository(session, repository_id) as readable:
            public = readable and await is_public(session, repository_id)
    return Step(
        repository_id=repository_id,
        name=repository.name if repository else "",
        granted=granted,
        published=published,
        already_copied=repository_id in copied,
        public=public,
    )


async def _copied_by(session: AsyncSession, tenant_id: uuid.UUID) -> set[uuid.UUID]:
    """The repositories `tenant_id` has copied: its own copy records, nothing
    of what they brought in."""
    return set(
        await session.scalars(
            select(RepositoryCopy.repository_tenant_id).where(RepositoryCopy.tenant_id == tenant_id)
        )
    )


async def _dependencies(session: AsyncSession, repository_id: uuid.UUID) -> set[uuid.UUID] | None:
    """The repositories `repository_id` has copied, read through the gated
    read; None if this tenant can't read it."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            return None
        return await upstream_copies(session, repository_id)


async def manifest(
    session: AsyncSession, *, tenant_id: uuid.UUID | None, repository_id: uuid.UUID
) -> list[Step]:
    """`repository_id`'s dependencies in dependency order, then itself
    (ADR 0120). A dependency's own dependencies are already among the
    repository's: it had to copy them first. The copying tenant is never a
    step, even if it's somebody's dependency - its rows are the origins.
    """
    copied = await _copied_by(session, tenant_id) if tenant_id is not None else set()
    top = await _step(session, tenant_id, repository_id, copied)
    if not top.readable:
        raise RepositoryNotFoundError(
            detail=f"No published repository {repository_id} is granted to tenant {tenant_id}"
            if tenant_id is not None
            else f"No public repository {repository_id}"
        )
    deps = (await _dependencies(session, repository_id) or set()) - {tenant_id, repository_id}
    steps = {d: await _step(session, tenant_id, d, copied) for d in deps}
    # Order the dependencies among themselves by what each one copied.
    edges: dict[uuid.UUID, set[uuid.UUID]] = {}
    for d, step in steps.items():
        edges[d] = ((await _dependencies(session, d) or set()) & deps) if step.readable else set()
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


async def dependencies_of(
    session: AsyncSession, *, tenant_id: uuid.UUID | None, repository_id: uuid.UUID
) -> list[Step]:
    """What `repository_id` is built on, in the manifest's order (ADR 0198):
    its steps without itself, each carrying `tenant_id`'s own state of it
    (`granted`, `already_copied`) and whether it is published. Reads no
    content, only copy records, and refuses as the manifest does, with
    `RepositoryNotFoundError`, unless `tenant_id` holds a grant to the
    repository, or it is public, and it is published. `tenant_id` is `None` for a user with no
    library, who can read only what is public (ADR 0287)."""
    return (await manifest(session, tenant_id=tenant_id, repository_id=repository_id))[:-1]


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
        # The tenant's prototype edges as (entity, prototype), then every one
        # this plan writes: what an attachment finds already there (ADR 0172).
        self.edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.attachments: list[PlannedAttachment] = []

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
        self.edges = {
            (entity_id, prototype_id)
            for entity_id, prototype_id in await session.execute(
                select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
                    EntityPrototype.tenant_id == t
                )
            )
        }
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
        fresh: dict[uuid.UUID, uuid.UUID] = {}
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
                    "unit": definition["unit"],
                    "adjustable_in_play": definition["adjustable_in_play"],
                    "pin": definition["pin"],
                    "signed": definition["signed"],
                    "position": definition["position"],
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
            fresh[d] = new

        # Hints link definitions to each other, so they go in once all of them have ids: a hint
        # whose target wasn't copied (skipped, dropped) is left unset (ADR 0280).
        for d, new in fresh.items():
            hints = {
                f"{key}_id": self._local(c, "stat_definition", hinted)
                for key, hinted in c.definitions[d]["hints"].items()
                if hinted is not None
            }
            hints = {key: target for key, target in hints.items() if target is not None}
            if hints:
                self.rows["stat_definition_hint"].append(
                    {"id": new, "tenant_id": tenant_id} | hints
                )

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
            if "event" in kinds:
                self.rows["story_event"].append({"entity_id": new, "tenant_id": tenant_id})
            if "calendar" in kinds:
                self.rows["calendar"].append(
                    {"entity_id": new, "tenant_id": tenant_id, "definition": c.calendars[e]}
                )
            if "fact" in kinds:
                self.rows["fact"].append({"entity_id": new, "tenant_id": tenant_id})
            if (
                e in c.entry_audiences
                or "fact" in kinds
                or "calendar" in kinds
                or "calendar_period" in kinds
                or "event" in kinds
                or "observance" in kinds
            ):
                self.rows["entity_audience"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "is_public": c.entry_audiences.get(e, False),
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

        placed: dict[uuid.UUID, int] = defaultdict(int)
        for e, p in c.prototypes:
            if copies("entity", e):
                target = self._local(c, "entity", p)
                if target is None:
                    drop("entity_prototype", e, "its prototype wasn't copied")
                    continue
                self.edges.add((self.local["entity"][e], target))
                self.rows["entity_prototype"].append(
                    {
                        "entity_id": self.local["entity"][e],
                        "prototype_id": target,
                        "tenant_id": tenant_id,
                        # c.prototypes is in each entry's order; the copy keeps it (ADR 0266).
                        "position": placed[e],
                    }
                )
                placed[e] += 1
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
            elif formula.kind == "contents":
                assert formula.source is not None
                self.rows["computed_stat_contents"].append(
                    key | {"source_stat_definition_id": inputs[formula.source]}
                )
            elif formula.kind == "sum":
                assert formula.terms is not None
                self.rows["computed_stat_sum"].append(
                    key | {"offset": formula.offset, "round_mode": formula.round_mode}
                )
                self.rows["computed_stat_sum_term"].extend(
                    key
                    | {
                        "source_stat_definition_id": inputs[source],
                        "coefficient": coefficient,
                        "position": position,
                    }
                    for position, (source, coefficient) in enumerate(formula.terms)
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
        for e, knower in c.entry_knowledge:
            if copies("entity", e):
                target = self._local(c, "entity", knower)
                if target is None:
                    drop("entity_knowledge", e, "its knower wasn't copied")
                else:
                    self.rows["entity_knowledge"].append(
                        {
                            "tenant_id": tenant_id,
                            "entity_id": self.local["entity"][e],
                            "knower_entity_id": target,
                        }
                    )
        for e, subject in c.fact_about:
            if copies("entity", e):
                target = self._local(c, "entity", subject)
                if target is None:
                    drop("fact_about", e, "its subject wasn't copied")
                else:
                    self.rows["fact_about"].append(
                        {
                            "tenant_id": tenant_id,
                            "fact_entity_id": self.local["entity"][e],
                            "subject_entity_id": target,
                        }
                    )
        # Structural parents first, then their children. A missing calendar/parent is an
        # explicit refusal instead of an orphaned period or silent change of kind.
        for e, period in sorted(
            c.calendar_periods.items(),
            key=lambda pair: (pair[1]["segment"] is not None, pair[1]["day"] is not None),
        ):
            if copies("entity", e):
                calendar_id = self._local(c, "entity", period["calendar"])
                parent_id = self._local(c, "entity", period["parent"]) if period["parent"] else None
                if calendar_id is None or period["parent"] and parent_id is None:
                    raise InvalidRepositoryUpdateError(
                        detail="Copy the calendar and its parent periods before this period."
                    )
                self.rows["calendar_period"].append(
                    {
                        "entity_id": self.local["entity"][e],
                        "tenant_id": tenant_id,
                        "calendar_entity_id": calendar_id,
                        "year": period["year"],
                        "segment": period["segment"],
                        "day": period["day"],
                        "parent_entity_id": parent_id,
                    }
                )
        for e, observance in c.observances.items():
            if copies("entity", e):
                calendar_id = self._local(c, "entity", observance["calendar"])
                if calendar_id is None:
                    raise InvalidRepositoryUpdateError(
                        detail="Copy the calendar before its observance."
                    )
                self.rows["calendar_observance"].append(
                    {
                        "entity_id": self.local["entity"][e],
                        "tenant_id": tenant_id,
                        "calendar_entity_id": calendar_id,
                        "rule": observance["rule"],
                    }
                )
        for event, being, information in c.event_learning:
            if copies("entity", event):
                target = self._local(c, "entity", being)
                local_info_id = local_information.get(information)
                if target is None or local_info_id is None:
                    drop("event_learning", event, "its being or Information was not copied")
                else:
                    self.rows["event_learning"].append(
                        {
                            "tenant_id": tenant_id,
                            "event_entity_id": self.local["entity"][event],
                            "being_entity_id": target,
                            "information_id": local_info_id,
                        }
                    )
        for event, being in c.event_participants:
            if copies("entity", event):
                target = self._local(c, "entity", being)
                if target is None:
                    drop("event_participant", event, "its participating being was not copied")
                else:
                    self.rows["event_participant"].append(
                        {
                            "tenant_id": tenant_id,
                            "event_entity_id": self.local["entity"][event],
                            "being_entity_id": target,
                        }
                    )
        for source, target, kind in c.event_relationships:
            if copies("entity", source):
                local_target = self._local(c, "entity", target)
                if local_target is None:
                    drop("event_relationship", source, "its target Event was not copied")
                else:
                    self.rows["event_relationship"].append(
                        {
                            "tenant_id": tenant_id,
                            "from_event_id": self.local["entity"][source],
                            "to_event_id": local_target,
                            "kind": kind,
                        }
                    )
        for e, period_id in c.entry_dates:
            if copies("entity", e):
                target = self._local(c, "entity", period_id)
                if target is None:
                    drop("entry_calendar_period", e, "its calendar period was not copied")
                else:
                    self.rows["entry_calendar_period"].append(
                        {
                            "entity_id": self.local["entity"][e],
                            "period_entity_id": target,
                            "tenant_id": tenant_id,
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

        if only is None:
            self._plan_attachments(step)

        if record_copy:
            self.rows["repository_copy"].append(
                {
                    "tenant_id": tenant_id,
                    "repository_tenant_id": repository_id,
                    "repository_name": step.name,
                    "copied_by": user_id,
                    "synced_release_id": step.release_id,
                }
            )

    def _plan_attachments(self, step: Step) -> None:
        """Plans the parents the repository added to its copies of other rows
        (ADR 0172), after its own rows, so a parent that is the repository's own
        entity is found among the ones this step copies. Each end is found through
        the origin it shares with the tenant's own copy, and one that isn't here is
        dropped and reported, as any row whose target is missing is."""
        c = step.content
        assert c is not None
        for a in attachments_of(c):
            child = self._local(c, "entity", a.child)
            if child is None:
                step.dropped.append(
                    Dropped("attachment", a.child_source_id, "the item it attaches to isn't here")
                )
                continue
            parent = self._local(c, "entity", a.parent)
            if parent is None:
                step.dropped.append(
                    Dropped("attachment", a.child_source_id, "the prototype it attaches isn't here")
                )
                continue
            edge = (child, parent) not in self.edges
            self.edges.add((child, parent))
            self.attachments.append(
                PlannedAttachment(step, child, parent, a.child_source_id, a.parent_source_id, edge)
            )
            step.attachments += edge

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
            upstream = await load_upstream(session, step.repository_id)
            step.content = upstream.content
            step.release_id = upstream.release.id if upstream.release else None
        planner.plan_step(step)
    plan.collisions = planner.collisions
    plan.rows = planner.rows
    plan.attachments = planner.attachments
    for definition_id, values in planner.enum_additions.items():
        for value in sorted(values):
            plan.rows["stat_definition_enum_value"].append(
                {"tenant_id": tenant_id, "stat_definition_id": definition_id, "value": value}
            )
    return plan


# --- Writing -------------------------------------------------------------------

# What a copy writes, and in what order, is the registry of copyable tables (ADR 0218).
_TABLES = COPIED_TABLES
_LINKS = COPY_LINKS


async def write_rows(session: AsyncSession, rows: dict[str, list[dict[str, Any]]]) -> None:
    """Inserts a plan's rows in dependency order. Shared with ADR 0121's
    updates, which add rows the same way."""
    # Acquire the graph lock before any row locks or insert snapshots, also for copy/update.
    from lorenzo_api.event_order_lock import lock_event_order

    for tenant_id in sorted({r["tenant_id"] for r in rows.get("event_relationship", [])}):
        await lock_event_order(session, tenant_id)
    bound_rows = rows.get("calendar_period", []) + rows.get("calendar_observance", [])
    calendars = {(r["tenant_id"], r["calendar_entity_id"]) for r in bound_rows}
    for tenant_id, calendar_id in sorted(calendars, key=lambda pair: (str(pair[0]), str(pair[1]))):
        await session.execute(
            select(Entity.id)
            .where(Entity.id == calendar_id, Entity.tenant_id == tenant_id)
            .with_for_update()
        )
    # Not held to the quotas of ADR 0298: a bridge's size is its upstream's (see there).
    for key, model in _TABLES:
        if rows.get(key):
            await session.execute(insert(model), rows[key])
        if key == "stat_definition":
            for hint in rows.get("stat_definition_hint", []):
                await session.execute(
                    update(StatDefinition)
                    .where(
                        StatDefinition.id == hint["id"],
                        StatDefinition.tenant_id == hint["tenant_id"],
                    )
                    .values({k: v for k, v in hint.items() if k.endswith("_hint_id")})
                )
    if calendars:
        from lorenzo_calendar import CalendarDefinition

        from lorenzo_api.calendar_periods import validate_materialized_periods

        for tenant_id, calendar_id in calendars:
            definition = await session.scalar(
                select(Calendar.definition).where(
                    Calendar.entity_id == calendar_id, Calendar.tenant_id == tenant_id
                )
            )
            assert definition is not None
            await validate_materialized_periods(
                session, tenant_id, calendar_id, CalendarDefinition.model_validate(definition)
            )
    for key, model, local in _LINKS:
        if rows.get(key):
            await session.execute(
                insert(model),
                [{local if k == "local_id" else k: v for k, v in r.items()} for r in rows[key]],
            )


async def write_attachments(
    session: AsyncSession, tenant_id: uuid.UUID, attachments: list[PlannedAttachment]
) -> list[PlannedAttachment]:
    """Writes attachment edges, one at a time and each in a savepoint, because
    `entity_prototype`'s trigger refuses a loop (ADR 0015) with a prototype the
    tenant has of its own. Records a link for every attachment taken, the edge
    written here or already there (ADR 0172). Returns the ones refused, which have
    neither."""
    refused: list[PlannedAttachment] = []
    refused_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    links: list[dict[str, Any]] = []
    for a in attachments:
        if (a.child, a.parent) in refused_pairs:
            refused.append(a)
            continue
        if a.edge:
            try:
                async with session.begin_nested():
                    await session.execute(
                        insert(EntityPrototype).values(
                            entity_id=a.child, prototype_id=a.parent, tenant_id=tenant_id
                        )
                    )
            except DBAPIError:
                refused.append(a)
                refused_pairs.add((a.child, a.parent))
                continue
        links.append(
            {
                "tenant_id": tenant_id,
                "source_tenant_id": a.step.repository_id,
                "child_source_id": a.child_source_id,
                "parent_source_id": a.parent_source_id,
            }
        )
    if links:
        await session.execute(
            pg_insert(RepositoryCopyLinkAttachment).on_conflict_do_nothing(), links
        )
    return refused


async def check_formula_cycles(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """The tenant's formula graph, whole, after a copy or update wrote
    formulas: an edge from each formula's stat to each stat of the same
    entity it reads (ADR 0104) - a contents formula reads a level down and
    adds none (ADR 0127). Merging definitions is the only way a copy can
    close a loop."""
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
    for target, source in await session.execute(
        select(
            ComputedStatSumTerm.stat_definition_id, ComputedStatSumTerm.source_stat_definition_id
        ).where(ComputedStatSumTerm.tenant_id == tenant_id)
    ):
        edges[target].add(source)
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
                    "public": s.public,
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
    for a in await write_attachments(session, plan.tenant_id, plan.attachments):
        a.step.attachments -= a.edge
        a.step.dropped.append(Dropped("attachment", a.child_source_id, LOOP_REASON))
    await check_formula_cycles(session, plan.tenant_id)
    for step in plan.to_copy:
        reported_dropped = sum(
            d.kind not in ("event_relationship", "event_participant", "event_learning")
            for d in step.dropped
        )
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
                f"attachments={step.attachments},"
                f"dropped={reported_dropped}"
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
    and counts what of the tenant's own goes with them, the parents the
    repository's attachments gave to other rows included (ADR 0172). Doesn't
    commit."""
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
    links = await load_links(session, t)
    pairs = sorted(links.attachments.get(repository_id, ()))

    if purge:
        from lorenzo_api.event_order_lock import lock_event_order

        await lock_event_order(session, t)
        # Serialize with materialization and date edits before inspecting local references.
        await session.execute(
            select(Entity.id)
            .where(Entity.tenant_id == t, Entity.id.in_(entities))
            .order_by(Entity.id)
            .with_for_update()
        )
        local_period = await session.scalar(
            select(
                exists().where(
                    CalendarPeriod.tenant_id == t,
                    CalendarPeriod.entity_id.not_in(entities),
                    or_(
                        CalendarPeriod.calendar_entity_id.in_(entities),
                        CalendarPeriod.parent_entity_id.in_(entities),
                    ),
                )
            )
        )
        local_date = await session.scalar(
            select(
                exists().where(
                    EntryCalendarPeriod.tenant_id == t,
                    EntryCalendarPeriod.entity_id.not_in(entities),
                    EntryCalendarPeriod.period_entity_id.in_(entities),
                )
            )
        )
        local_rule = await session.scalar(
            select(
                exists().where(
                    CalendarObservance.tenant_id == t,
                    CalendarObservance.entity_id.not_in(entities),
                    CalendarObservance.calendar_entity_id.in_(entities),
                )
            )
        )
        if local_period or local_date or local_rule:
            raise EntityKindInUseError(
                detail="Local dated material still references this copy. Resolve it before purging."
            )
        # The edges the attachments recorded that no deleted row takes with it. One
        # whose parent a purge deletes goes with that entity, and is counted below
        # as it always was. A parent that isn't a copy is the tenant's own row, which
        # the repository copied from it (ADR 0120): its origin is its id.
        local_entities = links.local_of("entity")
        recorded = [
            (local_entities.get(child, child), local_entities.get(parent, parent))
            for child, parent in pairs
        ]
        attached_edges = (
            [
                (child, parent)
                for child, parent in await session.execute(
                    select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
                        EntityPrototype.tenant_id == t,
                        tuple_(EntityPrototype.entity_id, EntityPrototype.prototype_id).in_(
                            recorded
                        ),
                    )
                )
                if child not in entities and parent not in entities
            ]
            if recorded
            else []
        )
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
            exists().where(
                ComputedStatSumTerm.entity_id == ComputedStat.entity_id,
                ComputedStatSumTerm.stat_definition_id == ComputedStat.stat_definition_id,
                ComputedStatSumTerm.source_stat_definition_id.in_(all_definitions),
            ),
            exists().where(
                ComputedStatContents.entity_id == ComputedStat.entity_id,
                ComputedStatContents.stat_definition_id == ComputedStat.stat_definition_id,
                ComputedStatContents.source_stat_definition_id.in_(all_definitions),
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
            "attachment": len(attached_edges),
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
            "entity_knowledge": await _count(
                session,
                EntityKnowledge,
                EntityKnowledge.tenant_id == t,
                EntityKnowledge.knower_entity_id.in_(entities),
                EntityKnowledge.entity_id.not_in(entities),
            ),
            "event_learning": await _count(
                session,
                EventLearning,
                EventLearning.tenant_id == t,
                or_(
                    EventLearning.event_entity_id.in_(entities),
                    EventLearning.being_entity_id.in_(entities),
                    EventLearning.information_id.in_(
                        select(Information.id).where(
                            Information.tenant_id == t, Information.entity_id.in_(entities)
                        )
                    ),
                ),
            ),
            "event_participant": await _count(
                session,
                EventParticipant,
                EventParticipant.tenant_id == t,
                or_(
                    EventParticipant.event_entity_id.in_(entities)
                    & EventParticipant.being_entity_id.not_in(entities),
                    EventParticipant.being_entity_id.in_(entities)
                    & EventParticipant.event_entity_id.not_in(entities),
                ),
            ),
            "event_relationship": await _count(
                session,
                EventRelationship,
                EventRelationship.tenant_id == t,
                or_(
                    EventRelationship.to_event_id.in_(entities)
                    & EventRelationship.from_event_id.not_in(entities),
                    EventRelationship.from_event_id.in_(entities)
                    & EventRelationship.to_event_id.not_in(entities),
                ),
            ),
            "fact_about": await _count(
                session,
                FactAbout,
                FactAbout.tenant_id == t,
                FactAbout.subject_entity_id.in_(entities),
                FactAbout.fact_entity_id.not_in(entities),
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
        # The counts above are hand-written; the registry says which tables they are for.
        assert set(also) == PURGE_COUNTED, set(also) ^ PURGE_COUNTED
        previous.also_removed = {kind: n for kind, n in also.items() if n}
        # Formula inputs don't cascade (ADR 0104), so the tenant's own
        # formulas reading a purged definition go first; everything else
        # cascades from the rows themselves.
        await session.execute(delete(ComputedStat).where(own_formulas, uses_definition))
        if attached_edges:
            await session.execute(
                delete(EntityPrototype).where(
                    EntityPrototype.tenant_id == t,
                    tuple_(EntityPrototype.entity_id, EntityPrototype.prototype_id).in_(
                        attached_edges
                    ),
                )
            )
        if pairs:
            # Another repository that attached the same parent has lost it too,
            # and its next update offers it again (ADR 0172).
            await session.execute(
                delete(RepositoryCopyLinkAttachment).where(
                    RepositoryCopyLinkAttachment.tenant_id == t,
                    tuple_(
                        RepositoryCopyLinkAttachment.child_source_id,
                        RepositoryCopyLinkAttachment.parent_source_id,
                    ).in_(pairs),
                )
            )
        await session.execute(
            delete(EventLearning).where(
                EventLearning.tenant_id == t,
                or_(
                    EventLearning.event_entity_id.in_(entities),
                    EventLearning.being_entity_id.in_(entities),
                    EventLearning.information_id.in_(
                        select(Information.id).where(
                            Information.tenant_id == t, Information.entity_id.in_(entities)
                        )
                    ),
                ),
            )
        )
        await session.execute(
            delete(EventParticipant).where(
                EventParticipant.tenant_id == t,
                or_(
                    EventParticipant.event_entity_id.in_(entities),
                    EventParticipant.being_entity_id.in_(entities),
                ),
            )
        )
        # These are deliberately NO ACTION for individual Event deletion.
        # A reviewed repository purge explicitly removes the incident assertions first.
        await session.execute(
            delete(EventRelationship).where(
                EventRelationship.tenant_id == t,
                or_(
                    EventRelationship.from_event_id.in_(entities),
                    EventRelationship.to_event_id.in_(entities),
                ),
            )
        )
        await session.execute(delete(Entity).where(Entity.tenant_id == t, Entity.id.in_(entities)))
        await session.execute(
            delete(StatDefinition).where(
                StatDefinition.tenant_id == t, StatDefinition.id.in_(all_definitions)
            )
        )
        await session.execute(
            delete(StatGroup).where(StatGroup.tenant_id == t, StatGroup.id.in_(groups))
        )

    for model in LINK_MODELS:
        await session.execute(
            delete(model).where(model.tenant_id == t, model.source_tenant_id == repository_id)
        )
    await session.execute(
        delete(RepositoryCopy).where(
            RepositoryCopy.tenant_id == t, RepositoryCopy.repository_tenant_id == repository_id
        )
    )
    reported_removed = sum(
        count
        for kind, count in previous.also_removed.items()
        if kind not in ("event_relationship", "event_participant", "event_learning")
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
            f"also_removed={reported_removed}"
        ),
    )
    return previous
