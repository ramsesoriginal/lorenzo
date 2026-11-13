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
from decimal import Decimal
from typing import Any, Literal

from lorenzo_map import (
    MapDocumentError,
    keep_theme_hint,
    validate_calibration,
    validate_opacity,
    validate_placement,
)
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
    RepositoryProtectedError,
)
from lorenzo_api.frames import AXES
from lorenzo_api.models import (
    Calendar,
    CalendarObservance,
    CalendarPeriod,
    CalendarReckoning,
    CarrierCoverage,
    ClockRelationship,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatContents,
    ComputedStatExtremumInput,
    ComputedStatLinear,
    ComputedStatProductFactor,
    ComputedStatRatio,
    ComputedStatSelect,
    ComputedStatSelectStep,
    ComputedStatSumTerm,
    Containment,
    Entity,
    EntityFrame,
    EntityLocation,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    EntryCalendarPeriod,
    EventClockReading,
    EventLearning,
    EventParticipant,
    EventRelationship,
    FeaturePrerequisite,
    GrantRule,
    GrantRuleCondition,
    GroupMember,
    Information,
    Knowledge,
    LivedBefore,
    LocationPart,
    MapPlacement,
    Ownership,
    Payload,
    RelationshipThrough,
    RepositoryCopy,
    RepositoryCopyLinkAttachment,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    RepositorySubscription,
    Scene,
    SceneAppearance,
    SceneTelling,
    SocialWebEntry,
    SocialWebType,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StorySession,
    System,
    Template,
    TemplateSlot,
    TemplateSlotExclusion,
    TemplateSlotStat,
    Tenant,
    TenantKind,
)
from lorenzo_api.models.fact import EntityKnowledge, FactAbout
from lorenzo_api.models.manuscript import Edition, ManuscriptPlacement
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import (
    Content,
    Links,
    assert_acyclic,
    attachments_of,
    entity_snapshot,
    index_entities,
    load_links,
    origin_namer,
    stat_definition_snapshot,
    stat_group_snapshot,
)
from lorenzo_api.repository_deprecation import copy_refusal
from lorenzo_api.repository_hiding import carries_of, refresh_hidden
from lorenzo_api.repository_reach import PROTECTED_NAME
from lorenzo_api.repository_upstream import load_upstream, upstream_copies, visibility_of
from lorenzo_api.svg_lint import SvgRefused, check_svg

CollisionKind = Literal["stat_group", "stat_definition", "stat_role", "slug"]
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
class ScaleWarning:
    """A stat the copy merges into the library's own whose unit or bounds differ: the library's
    stay, so a value written in the other unit would be read as the library's (ADR 0453). `library`
    and `incoming` are each {unit, min_value, max_value}."""

    repository_id: uuid.UUID
    source_id: uuid.UUID
    local_id: uuid.UUID
    name: str
    library: dict[str, Any]
    incoming: dict[str, Any]


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
    # Readable because the repository is protected and the copy goes through a public repository
    # whose current release lists it, or the library was invited to it (ADR 0434). Its name is not
    # given to a library that was not invited: no view of a library names a protected repository.
    protected: bool = False
    # Whether the library holds a grant row of any source to it, `protected` included: what a copy
    # that writes its own grant must not write twice. `granted` is a grant that reads it alone.
    held: bool = False
    # Retired by its Owner (ADR 0384): a library that holds it keeps it and its updates, and cannot
    # copy it again, nor take it in as a dependency it has not copied.
    deprecated: bool = False
    deprecated_message: str | None = None
    content: Content | None = None
    # The release the repository is read at when it is planned, its current one: what the copy
    # records as taken (ADR 0207, 0286).
    release_id: uuid.UUID | None = None
    # The repository the copy is of: its entries are brought for itself, and never hidden by what
    # another repository says of it (ADR 0437).
    head: bool = False
    entities: int = 0
    stat_groups: int = 0
    stat_definitions: int = 0
    # The game systems the library did not have and the templates this step makes (ADR 0453).
    systems: int = 0
    templates: int = 0
    information: int = 0
    # The attachment edges the step writes (ADR 0172).
    attachments: int = 0
    dropped: list[Dropped] = field(default_factory=list)

    @property
    def readable(self) -> bool:
        """Whether the copying tenant may read it: it is published, and the tenant holds a grant
        or it is public (ADR 0287), or it is protected and the copy goes through a repository that
        lists it (ADR 0434)."""
        return self.published and (self.granted or self.public or self.protected)


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
    warnings: list[ScaleWarning] = field(default_factory=list)

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
    via: uuid.UUID | None = None,
) -> Step:
    """One repository as `tenant_id` stands with it (a user with no library: `None`). `via` is the
    repository the copy goes through, the head of the manifest: a protected repository is readable
    through it and through nothing else but an invitation (ADR 0434)."""
    repository = await session.get(Tenant, repository_id)
    row = (
        await session.get(RepositorySubscription, (repository_id, tenant_id))
        if tenant_id is not None
        else None
    )
    # A protected row is how a library lists what it holds through another repository; it never
    # reads anything alone, so it is not a grant (ADR 0434).
    granted = row is not None and row.source != "protected"
    # A delisted repository reads as unpublished to everyone but its own members (ADR 0303).
    published = bool(
        repository
        and repository.kind is TenantKind.REPOSITORY
        and repository.published_at is not None
        and repository.delisted_at is None
    )
    visibility = None
    if published:
        async with reading_repository(
            session, repository_id, via=via if tenant_id is not None else None
        ) as readable:
            if readable:
                visibility = await visibility_of(session, repository_id)
    protected = visibility == "protected"
    return Step(
        repository_id=repository_id,
        # Nothing a library reads names a protected repository it was not invited to.
        name=(
            PROTECTED_NAME if protected and not granted else repository.name if repository else ""
        ),
        granted=granted,
        published=published,
        already_copied=repository_id in copied,
        public=visibility == "public",
        protected=protected,
        held=row is not None,
        deprecated=bool(repository and repository.deprecated_at is not None),
        deprecated_message=repository.deprecated_message if repository else None,
    )


def _protected_alone() -> RepositoryProtectedError:
    return RepositoryProtectedError(
        detail="This repository is protected: it comes with the repositories built on it and is "
        "not copied on its own. Copy one of those, or build a repository of your own on it with "
        "its Owner's invitation."
    )


async def _holds_protected(
    session: AsyncSession, tenant_id: uuid.UUID | None, repository_id: uuid.UUID
) -> bool:
    """Whether the tenant holds the repository through another: the row it wrote for itself when
    it copied a repository that brings it (ADR 0434)."""
    if tenant_id is None:
        return False
    row = await session.get(RepositorySubscription, (repository_id, tenant_id))
    return row is not None and row.source == "protected"


async def _is_repository(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    tenant = await session.get(Tenant, tenant_id)
    return tenant is not None and tenant.kind is TenantKind.REPOSITORY


async def _copied_by(session: AsyncSession, tenant_id: uuid.UUID) -> set[uuid.UUID]:
    """The repositories `tenant_id` has copied: its own copy records, nothing
    of what they brought in."""
    return set(
        await session.scalars(
            select(RepositoryCopy.repository_tenant_id).where(RepositoryCopy.tenant_id == tenant_id)
        )
    )


async def _dependencies(
    session: AsyncSession, repository_id: uuid.UUID, via: uuid.UUID | None = None
) -> set[uuid.UUID] | None:
    """The repositories `repository_id` has copied, read through the gated
    read; None if this tenant can't read it. `via` as for `_step`."""
    async with reading_repository(session, repository_id, via=via) as allowed:
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
        # A library that holds a repository only through another is told it is protected and
        # copied with the repository that brings it (ADR 0434); anybody else, that it is not there.
        if await _holds_protected(session, tenant_id, repository_id):
            raise _protected_alone()
        raise RepositoryNotFoundError(
            detail=f"No published repository {repository_id} is granted to tenant {tenant_id}"
            if tenant_id is not None
            else f"No public repository {repository_id}"
        )
    # Every other step is read through the head: a protected one is readable through it and
    # through nothing else but an invitation (ADR 0434).
    deps = (await _dependencies(session, repository_id) or set()) - {tenant_id, repository_id}
    steps = {d: await _step(session, tenant_id, d, copied, via=repository_id) for d in deps}
    # Order the dependencies among themselves by what each one copied.
    edges: dict[uuid.UUID, set[uuid.UUID]] = {}
    for d, step in steps.items():
        edges[d] = (
            ((await _dependencies(session, d, via=repository_id) or set()) & deps)
            if step.readable
            else set()
        )
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
        *,
        strict_units: bool = False,
    ) -> None:
        self.tenant_id = tenant_id
        # With `strict_units` a stat whose unit or bounds differ from the library's is not merged
        # without being told: merge is not among its choices (ADR 0453).
        self.strict_units = strict_units
        self.warnings: list[ScaleWarning] = []
        self.scales: dict[uuid.UUID, dict[str, Any]] = {}
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
        # The library's game systems by slug, then every one this plan makes, and the names of its
        # templates (ADR 0453).
        self.system_ids: dict[str, uuid.UUID] = {}
        self.template_names: set[str] = set()
        # The library's id for each grant rule this plan makes, by the repository's (ADR 0456).
        self.rule_ids: dict[uuid.UUID, uuid.UUID] = {}
        self.definitions: dict[str, tuple[uuid.UUID, Any, set[str]]] = {}
        # Who holds each role in the library, and what the stat holders are (ADR 0449): the
        # library's own, then every one this plan gives a role to.
        self.group_roles: dict[str, uuid.UUID] = {}
        self.definition_roles: dict[str, uuid.UUID] = {}
        self.type_and_values: dict[uuid.UUID, tuple[Any, set[str]]] = {}
        self.slugs: set[str] = set()
        # The tenant's own row ids, per kind, for a repository that copied
        # this tenant (ADR 0120: the tenant's rows are then the origins).
        self.existing: dict[str, set[uuid.UUID]] = {}
        self.enum_additions: dict[uuid.UUID, set[str]] = defaultdict(set)
        # The tenant's prototype edges as (entity, prototype), then every one
        # this plan writes: what an attachment finds already there (ADR 0172).
        self.edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.attachments: list[PlannedAttachment] = []
        self.participations: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def load_local_names(self, session: AsyncSession) -> None:
        t = self.tenant_id
        self.participations = {
            (e, b)
            for e, b in await session.execute(
                select(EventParticipant.event_entity_id, EventParticipant.being_entity_id).where(
                    EventParticipant.tenant_id == t
                )
            )
        }
        for group_id, name, group_role in await session.execute(
            select(StatGroup.id, StatGroup.name, StatGroup.role).where(StatGroup.tenant_id == t)
        ):
            self.group_names[name] = group_id
            if group_role is not None:
                self.group_roles[group_role] = group_id
        vocab: dict[uuid.UUID, set[str]] = defaultdict(set)
        for def_id, value in await session.execute(
            select(StatDefinitionEnumValue.stat_definition_id, StatDefinitionEnumValue.value).where(
                StatDefinitionEnumValue.tenant_id == t
            )
        ):
            vocab[def_id].add(value)
        for def_id, name, value_type, definition_role, unit, low, high in await session.execute(
            select(
                StatDefinition.id,
                StatDefinition.name,
                StatDefinition.value_type,
                StatDefinition.role,
                StatDefinition.unit,
                StatDefinition.min_value,
                StatDefinition.max_value,
            ).where(StatDefinition.tenant_id == t)
        ):
            self.scales[def_id] = {"unit": unit, "min_value": low, "max_value": high}
            self.definitions[name] = (def_id, value_type, vocab[def_id])
            self.type_and_values[def_id] = (value_type, vocab[def_id])
            if definition_role is not None:
                self.definition_roles[definition_role] = def_id
        self.slugs = set(
            await session.scalars(select(EntitySlug.slug).where(EntitySlug.tenant_id == t))
        )
        self.system_ids = {
            slug: system_id
            for system_id, slug in await session.execute(
                select(System.id, System.slug).where(System.tenant_id == t)
            )
        }
        self.template_names = set(
            await session.scalars(select(Template.name).where(Template.tenant_id == t))
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

        # Game systems are joined by slug when the library has one (its name and root stay) and
        # made when it has not; a repository added to by an update brings none (ADR 0453). The
        # rows come once the entries have ids, since a system's root is an entry.
        new_systems: list[tuple[uuid.UUID, dict[str, Any]]] = []
        if only is None:
            for system_id in sorted(c.systems, key=lambda s: c.systems[s]["slug"]):
                system = c.systems[system_id]
                if system["slug"] not in self.system_ids:
                    self.system_ids[system["slug"]] = uuid.uuid4()
                    new_systems.append((self.system_ids[system["slug"]], system))
                    step.systems += 1

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
            # The role comes along when the library has no group holding it (ADR 0449).
            group_role = group.get("role")
            if group_role is not None and group_role in self.group_roles:
                group_role = None
            if group_role is not None:
                self.group_roles[group_role] = new
            self.rows["stat_group"].append(
                {
                    "id": new,
                    "tenant_id": tenant_id,
                    "name": name,
                    "priority": group["priority"],
                    "mandatory": group["mandatory"],
                    "role": group_role,
                    "system_id": self._system_of(c, group),
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
                if value_type is definition["value_type"] and not self._blocked(
                    existing, definition
                ):
                    choices.insert(1, "merge")
                choice = self._resolve(step, "stat_definition", d, name, existing, choices)
                if choice is None:
                    self.local["stat_definition"][d] = uuid.uuid4()
                    continue
                if choice.action == "skip":
                    continue
                if choice.action == "merge":
                    self.local["stat_definition"][d] = existing
                    self._note_scale(step, d, name, existing, definition)
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
            # A role is held once in a library (ADR 0449): a stat that holds one the library's
            # own stat already holds is a collision of its own - merge into the holder when the
            # types agree, or skip.
            role = definition.get("role")
            if role is not None and role in self.definition_roles:
                holder = self.definition_roles[role]
                holder_type, holder_vocab = self.type_and_values[holder]
                role_choices: list[Action] = ["skip"]
                if holder_type is definition["value_type"] and not self._blocked(
                    holder, definition
                ):
                    role_choices.insert(0, "merge")
                role_choice = self._resolve(step, "stat_role", d, name, holder, role_choices)
                if role_choice is None:
                    self.local["stat_definition"][d] = uuid.uuid4()
                    continue
                if role_choice.action == "skip":
                    continue
                self.local["stat_definition"][d] = holder
                self._note_scale(step, d, name, holder, definition)
                self.enum_additions[holder] |= values - holder_vocab
                holder_vocab |= values
                self.rows["link_stat_definition"].append(
                    self._link(
                        repository_id,
                        d,
                        holder,
                        stat_definition_snapshot(c, d, namer),
                        "merged",
                    )
                )
                continue
            new = uuid.uuid4()
            self.local["stat_definition"][d] = new
            self.definitions[name] = (new, definition["value_type"], set(values))
            self.type_and_values[new] = (definition["value_type"], set(values))
            self.scales[new] = self._scale(definition)
            if role is not None:
                self.definition_roles[role] = new
            self.rows["stat_definition"].append(
                {
                    "id": new,
                    "tenant_id": tenant_id,
                    "stat_group_id": local_group,
                    "name": name,
                    "role": role,
                    "value_type": definition["value_type"],
                    "unit": definition["unit"],
                    "adjustable_in_play": definition["adjustable_in_play"],
                    "pin": definition["pin"],
                    "signed": definition["signed"],
                    "position": definition["position"],
                    "min_value": definition["min_value"],
                    "max_value": definition["max_value"],
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
        for system_id, system in new_systems:
            root = system["root"]
            self.rows["system"].append(
                {
                    "id": system_id,
                    "tenant_id": tenant_id,
                    "slug": system["slug"],
                    "name": system["name"],
                    "root_entry_id": self._local(c, "entity", root) if root else None,
                }
            )
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
                        "starts_inactive": c.starts_inactive.get(e, False),
                    }
                )
            if "item_instance" in kinds:
                # A copy makes a new instance, which starts as its prototypes say (ADR 0447).
                self.rows["item_instance"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "active": not any(
                            c.starts_inactive.get(p, False) for p in index.prototypes.get(e, [])
                        ),
                    }
                )
            if "feature" in kinds:
                self.rows["feature"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "repeatable": c.repeatable.get(e, False),
                        "starts_inactive": c.starts_inactive.get(e, False),
                    }
                )
            if "feature_instance" in kinds:
                # Like an item instance (ADR 0447), it starts as its feature says (ADR 0454).
                self.rows["feature_instance"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "active": not any(
                            c.starts_inactive.get(p, False) for p in index.prototypes.get(e, [])
                        ),
                    }
                )
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
            if e in c.writing_biographies:
                self.rows["writing_biography"].append({"entity_id": new, "tenant_id": tenant_id})
            if "scene_telling" in kinds:
                telling = c.tellings[e]
                scene = self._local(c, "entity", telling["scene"])
                viewpoint = (
                    self._local(c, "entity", telling["viewpoint"]) if telling["viewpoint"] else None
                )
                if scene is None or (telling["viewpoint"] and viewpoint is None):
                    raise InvalidRepositoryUpdateError(
                        detail="Copy this telling together with its Scene and viewpoint."
                    )
                self.rows["scene_telling"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "scene_entity_id": scene,
                        "viewpoint_entity_id": viewpoint,
                        "uses_scene_manuscript": telling["shared"],
                    }
                )
            for kind in ("book", "chapter", "carrier"):
                if kind in kinds:
                    self.rows[kind].append({"entity_id": new, "tenant_id": tenant_id})
            if "edition" in kinds:
                book = self._local(c, "entity", c.editions[e])
                if book is None:
                    raise InvalidRepositoryUpdateError(detail="Copy the Book before its Edition.")
                self.rows["edition"].append(
                    {"entity_id": new, "tenant_id": tenant_id, "book_entity_id": book}
                )
            if "scene" in kinds:
                source_period = c.scenes.get(e)
                target_period = self._local(c, "entity", source_period) if source_period else None
                if source_period and target_period is None:
                    raise InvalidRepositoryUpdateError(
                        detail="Copy the calendar period before its Scene"
                    )
                self.rows["scene"].append(
                    {"entity_id": new, "tenant_id": tenant_id, "period_entity_id": target_period}
                )
            if "event" in kinds:
                self.rows["story_event"].append({"entity_id": new, "tenant_id": tenant_id})
            if "clock" in kinds:
                self.rows["clock"].append(
                    {"entity_id": new, "tenant_id": tenant_id, "ticking": c.clocks[e]}
                )
            if "location" in kinds:
                self.rows["location"].append({"entity_id": new, "tenant_id": tenant_id})
            if "map" in kinds:
                subject = c.maps[e]["subject"]
                self.rows["map"].append(
                    {
                        "entity_id": new,
                        "tenant_id": tenant_id,
                        "system": c.maps[e]["system"],
                        "theme_hint": keep_theme_hint(c.maps[e]["theme"]),
                        "view": c.maps[e]["view"],
                        "subject_entity_id": None
                        if subject is None
                        else self._local(c, "entity", subject),
                    }
                )
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
                        "shared_with_participants": e in c.participant_entry_audiences,
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
                    "dice_count": stat_value.dice_count,
                    "dice_sides": stat_value.dice_sides,
                    "dice_drop_mode": stat_value.dice_drop_mode,
                    "dice_drop_count": stat_value.dice_drop_count,
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
            if formula.kind == "select":
                assert formula.source is not None and formula.steps is not None
                other = formula.otherwise
                self.rows["computed_stat_select"].append(
                    key
                    | {
                        "source_stat_definition_id": inputs[formula.source],
                        "mode": formula.select_mode,
                        "otherwise_number": None if other is None else other.number,
                        "otherwise_text": None if other is None else other.text,
                        "otherwise_bool": None if other is None else other.flag,
                        "otherwise_stat_definition_id": (
                            inputs[other.stat] if other is not None and other.stat else None
                        ),
                    }
                )
                self.rows["computed_stat_select_step"].extend(
                    key
                    | {
                        "position": position,
                        "threshold": step.threshold,
                        "match_value": step.match_value,
                        "result_number": step.result.number,
                        "result_text": step.result.text,
                        "result_bool": step.result.flag,
                        "result_stat_definition_id": (
                            inputs[step.result.stat] if step.result.stat else None
                        ),
                    }
                    for position, step in enumerate(formula.steps)
                )
            elif formula.kind == "product":
                assert formula.operands is not None
                self.rows["computed_stat_product"].append(
                    key
                    | {
                        "multiplier": formula.multiplier,
                        "offset": formula.offset,
                        "round_mode": formula.round_mode,
                    }
                )
                self.rows["computed_stat_product_factor"].extend(
                    key | {"position": position, "source_stat_definition_id": inputs[stat]}
                    for position, (stat, _) in enumerate(formula.operands)
                    if stat is not None
                )
            elif formula.kind == "ratio":
                assert formula.left is not None
                self.rows["computed_stat_ratio"].append(
                    key
                    | {
                        "numerator_stat_definition_id": inputs[formula.left],
                        "denominator_stat_definition_id": (
                            inputs[formula.right] if formula.right else None
                        ),
                        "denominator_constant": formula.right_constant,
                        "multiplier": formula.multiplier,
                        "offset": formula.offset,
                        "round_mode": formula.round_mode,
                    }
                )
            elif formula.kind in ("min", "max"):
                assert formula.operands is not None
                self.rows["computed_stat_extremum"].append(
                    key | {"pick": formula.kind, "round_mode": formula.round_mode}
                )
                self.rows["computed_stat_extremum_input"].extend(
                    key
                    | {
                        "position": position,
                        "source_stat_definition_id": None if stat is None else inputs[stat],
                        "constant": constant,
                    }
                    for position, (stat, constant) in enumerate(formula.operands)
                )
            elif formula.kind == "linear":
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
                self.rows["computed_stat_contents"].append(
                    key
                    | {
                        "source_stat_definition_id": (
                            inputs[formula.source] if formula.source else None
                        ),
                        "aggregate": formula.aggregate or "sum",
                        "only_active": bool(formula.only_active),
                        "only_kind": formula.only_kind,
                        "where_stat_definition_id": (
                            inputs[formula.where] if formula.where else None
                        ),
                        "if_none": formula.if_none,
                    }
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
                    "shared_with_participants": info_id in c.participant_information_audiences,
                    "order": info.order,
                    "created_by": user_id,
                }
            )
            step.information += 1
        local_payloads: dict[uuid.UUID, uuid.UUID] = {}
        for source_payload_id, payload in c.payloads.items():
            local_info = local_information.get(payload.information_id)
            if local_info is None:
                continue
            if payload.kind == "picture" and payload.fields["file_type"] == "image/svg+xml":
                try:
                    check_svg(payload.fields["data"])
                except SvgRefused:
                    drop("payload_picture", source_payload_id, "its SVG is not valid here")
                    continue
            new = uuid.uuid4()
            local_payloads[source_payload_id] = new
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
        for source, redirect in c.manuscript_redirects.items():
            if not copies("entity", source):
                continue
            destination, payload, child = (redirect[k] for k in ("destination", "payload", "child"))
            local_destination = self._local(c, "entity", destination) if destination else None
            local_child = self._local(c, "entity", child) if child else None
            local_payload = local_payloads.get(payload)
            if (
                (destination and local_destination is None)
                or (child and local_child is None)
                or (payload and local_payload is None)
            ):
                raise InvalidRepositoryUpdateError(
                    detail="Copy a joined Chapter together with its destination and section."
                )
            self.rows["manuscript_redirect"].append(
                {
                    "tenant_id": tenant_id,
                    "source_id": self._local(c, "entity", source),
                    "destination_id": local_destination,
                    "payload_id": local_payload,
                    "child_id": local_child,
                }
            )
        # The pictures under a Map: a layer goes with its Information (ADR 0361), keeping the
        # fingerprint it was reviewed against, since the bytes are the same.
        for drawn_on, layers in c.map_layers.items():
            if not copies("entity", drawn_on):
                continue
            for position, layer in enumerate(layers):
                local_info = local_information.get(uuid.UUID(layer["information"]))
                if local_info is None:
                    drop("map_layer", drawn_on, "its picture's Information was not copied")
                    continue
                try:
                    calibration = validate_calibration(layer["calibration"])
                    opacity = validate_opacity(layer["opacity"])
                except MapDocumentError:
                    drop("map_layer", drawn_on, "its calibration is not valid here")
                    continue
                self.rows["map_layer"].append(
                    {
                        "tenant_id": tenant_id,
                        "map_entity_id": self.local["entity"][drawn_on],
                        "position": position,
                        "information_id": local_info,
                        "calibration": calibration,
                        "opacity": opacity,
                        "reviewed_sha256": None
                        if layer["reviewed"] is None
                        else bytes.fromhex(layer["reviewed"]),
                    }
                )
        # A connection joins two entries: written once every entry has its place (ADR 0363).
        for e, joined in c.connections.items():
            if not copies("entity", e):
                continue
            end_a = self._local(c, "entity", joined["end_a"])
            end_b = self._local(c, "entity", joined["end_b"])
            if end_a is None or end_b is None or end_a == end_b:
                drop("connection", e, "an end of it was not copied")
                continue
            self.rows["connection"].append(
                {
                    "entity_id": self.local["entity"][e],
                    "tenant_id": tenant_id,
                    "end_a": end_a,
                    "end_b": end_b,
                    "one_way": True if joined["one_way"] else None,
                }
            )
        # A relationship ties two entries: written once every entry has its place (ADR 0399).
        written_relationships: set[uuid.UUID] = set()
        for e, tied in c.relationships.items():
            if not copies("entity", e):
                continue
            end_a = self._local(c, "entity", tied["end_a"])
            end_b = self._local(c, "entity", tied["end_b"])
            if end_a is None or end_b is None or end_a == end_b:
                drop("relationship", e, "an end of it was not copied")
                continue
            self.rows["relationship"].append(
                {
                    "entity_id": self.local["entity"][e],
                    "tenant_id": tenant_id,
                    "end_a": end_a,
                    "end_b": end_b,
                    "one_way": True if tied["one_way"] else None,
                    "starts_at": self._local(c, "entity", tied["starts_at"])
                    if tied["starts_at"]
                    else None,
                    "ends_at": self._local(c, "entity", tied["ends_at"])
                    if tied["ends_at"]
                    else None,
                }
            )
            written_relationships.add(e)
            if (tied["starts_at"] and self.rows["relationship"][-1]["starts_at"] is None) or (
                tied["ends_at"] and self.rows["relationship"][-1]["ends_at"] is None
            ):
                drop("relationship_time", e, "an Event that bounded it was not copied")
        # A step is written only when both relationships were copied; the steps are renumbered
        # from 1, so what was hidden from a copy leaves no gap (ADR 0402).
        for e, chain in c.relationship_through.items():
            if e not in written_relationships:
                continue
            kept = [via for via in chain if via in written_relationships]
            for position, via in enumerate(kept, start=1):
                self.rows["relationship_through"].append(
                    {
                        "relationship_entity_id": self.local["entity"][e],
                        "step": position,
                        "via_entity_id": self.local["entity"][via],
                        "tenant_id": tenant_id,
                    }
                )
            if len(kept) != len(chain):
                drop("relationship_through", e, "a step of it was not copied")
        # A SocialWeb carries its settings, the members and the types that were copied, and leaves a
        # dropped member out with a note (ADR 0406).
        for e, saved in c.social_webs.items():
            if not copies("entity", e):
                continue
            standing = self.local["stat_definition"].get(saved["standing_stat"])
            as_of = self._local(c, "entity", saved["as_of_event"]) if saved["as_of_event"] else None
            self.rows["social_web"].append(
                {
                    "entity_id": self.local["entity"][e],
                    "tenant_id": tenant_id,
                    "layout": saved["layout"],
                    "layout_seed": saved["layout_seed"],
                    "theme_hint": saved["theme_hint"],
                    "view": saved["view"],
                    "standing_stat_id": standing,
                    "as_of_event": as_of,
                }
            )
            lost = False
            for (owner, entry), held_at in c.social_web_entries.items():
                if owner != e:
                    continue
                local_entry = self._local(c, "entity", entry)
                if local_entry is None:
                    lost = True
                    continue
                self.rows["social_web_entry"].append(
                    {
                        "web_entity_id": self.local["entity"][e],
                        "entry_entity_id": local_entry,
                        "tenant_id": tenant_id,
                        "x": held_at["x"],
                        "y": held_at["y"],
                    }
                )
            for owner, type_entry in sorted(c.social_web_types, key=str):
                if owner != e:
                    continue
                local_kind = self._local(c, "entity", type_entry)
                if local_kind is None:
                    lost = True
                    continue
                self.rows["social_web_type"].append(
                    {
                        "web_entity_id": self.local["entity"][e],
                        "type_entity_id": local_kind,
                        "tenant_id": tenant_id,
                    }
                )
            if lost:
                drop("social_web", e, "an entry or type of it was not copied")
        for source_id, settings in c.manuscript_contents.items():
            if copies("entity", source_id):
                self.rows["manuscript_contents"].append(
                    {
                        "entity_id": self.local["entity"][source_id],
                        "tenant_id": tenant_id,
                        "settings": settings,
                    }
                )
        for source_id, settings in c.manuscript_numbering.items():
            if copies("entity", source_id):
                self.rows["manuscript_numbering"].append(
                    {
                        "entity_id": self.local["entity"][source_id],
                        "tenant_id": tenant_id,
                        "settings": settings,
                    }
                )
        for covered in c.carrier_coverage.values():
            if not copies("entity", covered["carrier"]):
                continue
            target_entry = self._local(c, "entity", covered["entry"]) if covered["entry"] else None
            target_payload = local_payloads.get(covered["payload"])
            anchor = local_payloads.get(covered["before"])
            if (
                (covered["entry"] and target_entry is None)
                or (covered["payload"] and target_payload is None)
                or (covered["before"] and anchor is None)
            ):
                raise InvalidRepositoryUpdateError(
                    detail="Copy the Carrier together with its covered writing and direct prose."
                )
            self.rows["carrier_coverage"].append(
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "carrier_id": self.local["entity"][covered["carrier"]],
                    "target_entity_id": target_entry,
                    "target_payload_id": target_payload,
                    "before_payload_id": anchor,
                    "position": covered["position"],
                }
            )
        for child, placement in c.manuscript_placements.items():
            parent = placement["parent"]
            if copies("entity", child) or copies("entity", parent):
                local_child, local_parent = (
                    self._local(c, "entity", child),
                    self._local(c, "entity", parent),
                )
                before = placement["before"]
                if (
                    local_child is None
                    or local_parent is None
                    or (before and before not in local_payloads)
                ):
                    raise InvalidRepositoryUpdateError(
                        detail="Copy this complete manuscript subtree together with its parent."
                    )
                self.rows["manuscript_placement"].append(
                    {
                        "child_entity_id": local_child,
                        "parent_entity_id": local_parent,
                        "tenant_id": tenant_id,
                        "before_payload_id": local_payloads.get(before),
                        "position": placement["position"],
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
        from lorenzo_api.clock_conversion import RelationDefinition, canonical

        for (first, second), relation_value in c.clock_relationships.items():
            if copies("entity", first) or copies("entity", second):
                local_first, local_second = (
                    self._local(c, "entity", first),
                    self._local(c, "entity", second),
                )
                if local_first is None or local_second is None:
                    drop(
                        "clock_relationship",
                        first if copies("entity", first) else second,
                        "its other clock was not copied",
                    )
                else:
                    first_id, second_id, relation_definition = canonical(
                        local_first,
                        local_second,
                        RelationDefinition.model_validate(relation_value["data"]),
                    )
                    self.rows["clock_relationship"].append(
                        {
                            "tenant_id": tenant_id,
                            "clock_entity_id": first_id,
                            "reference_clock_entity_id": second_id,
                            "data": relation_definition.model_dump(),
                            "is_shared": relation_value["is_shared"],
                        }
                    )
        for field_name, table, source_column in [
            ("clock_readings", "event_clock_reading", "event_entity_id"),
            ("calendar_reckonings", "calendar_reckoning", "calendar_entity_id"),
        ]:
            for (source, clock), value in getattr(c, field_name).items():
                if copies("entity", source):
                    local_clock = self._local(c, "entity", clock)
                    if local_clock is None:
                        drop(table, source, "its clock was not copied")
                    else:
                        self.rows[table].append(
                            {
                                "tenant_id": tenant_id,
                                source_column: self.local["entity"][source],
                                "clock_entity_id": local_clock,
                                **value,
                            }
                        )
        assert_acyclic(c.location_parts)
        for child, part in c.location_parts.items():
            if copies("entity", child):
                local_parent = self._local(c, "entity", part["parent"])
                if local_parent is None:
                    drop("location_part", child, "its parent Location was not copied")
                else:
                    self.rows["location_part"].append(
                        {
                            "tenant_id": tenant_id,
                            "child_entity_id": self.local["entity"][child],
                            "parent_entity_id": local_parent,
                            "level_ordinal": None
                            if part["ordinal"] is None
                            else Decimal(part["ordinal"]),
                        }
                    )
        for (drawn_on, entry), record in c.map_placements.items():
            if not copies("entity", drawn_on):
                continue
            local_entry = self._local(c, "entity", entry)
            if local_entry is None:
                drop("map_placement", drawn_on, "its entry was not copied")
                continue
            try:
                checked = validate_placement(
                    record["geometry"],
                    record["role"],
                    record["style"],
                    record["z"],
                    c.maps[drawn_on]["system"],
                )
            except MapDocumentError:
                drop("map_placement", drawn_on, "its geometry is not valid here")
                continue
            self.rows["map_placement"].append(
                {
                    "tenant_id": tenant_id,
                    "map_entity_id": self.local["entity"][drawn_on],
                    "entry_entity_id": local_entry,
                    "geometry": checked.geometry,
                    "role": checked.role,
                    "style": checked.style,
                    "z": checked.z,
                    "bytes": checked.bytes,
                    "minx": checked.bbox[0],
                    "miny": checked.bbox[1],
                    "maxx": checked.bbox[2],
                    "maxy": checked.bbox[3],
                }
            )
        for entry, at in c.entity_locations.items():
            if copies("entity", entry):
                local_at = self._local(c, "entity", at)
                if entry in c.containment:
                    drop("entity_location", entry, "it is in a container, which places it")
                elif local_at is None:
                    drop("entity_location", entry, "its Location was not copied")
                else:
                    self.rows["entity_location"].append(
                        {
                            "tenant_id": tenant_id,
                            "entity_id": self.local["entity"][entry],
                            "location_entity_id": local_at,
                        }
                    )
        for entry, framed_axes in c.frames.items():
            if copies("entity", entry):
                for frame_axis in framed_axes:
                    if frame_axis not in AXES:
                        drop("frame", entry, f"this version does not know the axis {frame_axis}")
                    else:
                        self.rows["frame"].append(
                            {
                                "tenant_id": tenant_id,
                                "entity_id": self.local["entity"][entry],
                                "axis": frame_axis,
                            }
                        )
        for entry, memberships in c.entity_frames.items():
            if copies("entity", entry):
                for member_axis, target_frame in memberships.items():
                    local_frame = self._local(c, "entity", target_frame)
                    if member_axis not in AXES:
                        drop(
                            "entity_frame",
                            entry,
                            f"this version does not know the axis {member_axis}",
                        )
                    elif member_axis not in c.frames.get(target_frame, []):
                        drop(
                            "entity_frame",
                            entry,
                            "its frame is not a frame on that axis",
                        )
                    elif local_frame is None:
                        drop("entity_frame", entry, "its frame was not copied")
                    else:
                        self.rows["entity_frame"].append(
                            {
                                "tenant_id": tenant_id,
                                "entity_id": self.local["entity"][entry],
                                "axis": member_axis,
                                "frame_entity_id": local_frame,
                            }
                        )
        for field_name, table, target_column in [
            ("scene_facts", "scene_fact", "fact_entity_id"),
            ("scene_events", "scene_event", "event_entity_id"),
            ("scene_beings", "scene_being", "being_entity_id"),
        ]:
            for (source, target), shared in getattr(c, field_name).items():
                if copies("entity", source):
                    local_target = self._local(c, "entity", target)
                    if local_target is None:
                        drop(table, source, "its target was not copied")
                    else:
                        self.rows[table].append(
                            {
                                "tenant_id": tenant_id,
                                "scene_entity_id": self.local["entity"][source],
                                target_column: local_target,
                                "is_shared": shared,
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
        self.participations.update(
            (row["event_entity_id"], row["being_entity_id"])
            for row in self.rows["event_participant"]
        )
        for being, source, target, shared in c.lived_before:
            if not copies("entity", source):
                continue
            b, a, z = (self._local(c, "entity", i) for i in (being, source, target))
            if (
                b is None
                or a is None
                or z is None
                or (a, b) not in self.participations
                or (z, b) not in self.participations
            ):
                drop("lived_before", source, "its being or participations were not copied")
                continue
            self.rows["lived_before"].append(
                {
                    "tenant_id": tenant_id,
                    "being_entity_id": b,
                    "from_event_id": a,
                    "to_event_id": z,
                    "is_shared": shared,
                }
            )
        shared_relationships = set(c.shared_event_relationships)
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
                            "is_shared": (source, target, kind) in shared_relationships,
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

        self._plan_grant_rules(step)
        self._plan_grant_records(step)
        if only is None:
            self._plan_templates(step)
            self._plan_attachments(step)

        if record_copy:
            self.rows["repository_copy"].append(
                {
                    "tenant_id": tenant_id,
                    "repository_tenant_id": repository_id,
                    "repository_name": step.name,
                    "copied_by": user_id,
                    "synced_release_id": step.release_id,
                    "carries": carries_of(c, repository_id, for_itself=step.head),
                }
            )

    @staticmethod
    def _scale(definition: dict[str, Any]) -> dict[str, Any]:
        return {
            "unit": definition["unit"],
            "min_value": definition["min_value"],
            "max_value": definition["max_value"],
        }

    def _differs(self, local_id: uuid.UUID, definition: dict[str, Any]) -> bool:
        scale = self._scale(definition)
        return self.scales.get(local_id, scale) != scale

    def _blocked(self, local_id: uuid.UUID, definition: dict[str, Any]) -> bool:
        """Whether a merge into the library's stat is refused: its unit or bounds differ and the
        copy is strict about them (ADR 0453)."""
        return self.strict_units and self._differs(local_id, definition)

    def _note_scale(
        self,
        step: Step,
        source_id: uuid.UUID,
        name: str,
        local_id: uuid.UUID,
        definition: dict[str, Any],
    ) -> None:
        """Reports a merge that keeps the library's unit or bounds where the repository's differ."""
        if self._differs(local_id, definition):
            self.warnings.append(
                ScaleWarning(
                    step.repository_id,
                    source_id,
                    local_id,
                    name,
                    dict(self.scales[local_id]),
                    self._scale(definition),
                )
            )

    def _system_of(self, c: Content, group: dict[str, Any]) -> uuid.UUID | None:
        """The library's game system a repository's stat group belongs to, found by slug: none for a
        neutral group, and for a system an update does not bring."""
        group_system = group.get("system")
        system = c.systems.get(group_system) if group_system is not None else None
        return self.system_ids.get(system["slug"]) if system is not None else None

    def _plan_templates(self, step: Step) -> None:
        """Plans a repository's templates (ADR 0453), after its groups, stats and entries, whose
        ids they are re-pointed to. A template is left out, and reported, when the library has one
        of its name, or when its ancestor entry, a stat group or a stat it shows was not copied:
        a template that shows less than it says would be a wrong one."""
        c = step.content
        assert c is not None
        for template_id in sorted(c.templates, key=lambda t: c.templates[t]["name"]):
            template = c.templates[template_id]
            name = template["name"]

            def drop(reason: str, template_id: uuid.UUID = template_id) -> None:
                step.dropped.append(Dropped("template", template_id, reason))

            if name in self.template_names:
                drop(f"the library already has a template called {name!r}")
                continue
            ancestor = None
            if template["ancestor"] is not None:
                ancestor = self._local(c, "entity", template["ancestor"])
                if ancestor is None:
                    drop("its ancestor entry wasn't copied")
                    continue
            slots: list[
                tuple[dict[str, Any], uuid.UUID | None, list[uuid.UUID], list[uuid.UUID]]
            ] = []
            missing = ""
            for slot in template["slots"]:
                group = None
                if slot["group"] is not None:
                    group = self._local(c, "stat_group", slot["group"])
                    if group is None:
                        missing = "a stat group it shows wasn't copied"
                        break
                listed = [self._local(c, "stat_definition", s) for s, _ in slot["stats"]]
                if any(s is None for s in listed):
                    missing = "a stat it lists wasn't copied"
                    break
                left_out = [self._local(c, "stat_definition", s) for s in slot["exclude"]]
                slots.append(
                    (
                        slot,
                        group,
                        [s for s in listed if s is not None],
                        [s for s in left_out if s is not None],
                    )
                )
            if missing:
                drop(missing)
                continue
            self.template_names.add(name)
            system = c.systems.get(template["system"])
            new = uuid.uuid4()
            self.rows["template"].append(
                {
                    "id": new,
                    "tenant_id": self.tenant_id,
                    "name": name,
                    "system_id": self.system_ids.get(system["slug"]) if system else None,
                    "required_kind": template["kind"],
                    "required_ancestor_entry_id": ancestor,
                }
            )
            for position, (slot, group, listed_ids, left_out_ids) in enumerate(slots):
                slot_id = uuid.uuid4()
                self.rows["template_slot"].append(
                    {
                        "id": slot_id,
                        "tenant_id": self.tenant_id,
                        "template_id": new,
                        "position": position,
                        "kind": slot["kind"],
                        "label": slot["label"],
                        "stat_group_id": group,
                        "information_type": slot["information_type"],
                        "held_order": slot["held_order"],
                    }
                )
                # Two stats merged into one in the library are listed once.
                taken: set[uuid.UUID] = set()
                for stat, (_, label) in zip(listed_ids, slot["stats"], strict=True):
                    if stat in taken:
                        continue
                    taken.add(stat)
                    self.rows["template_slot_stat"].append(
                        {
                            "slot_id": slot_id,
                            "position": len(taken) - 1,
                            "tenant_id": self.tenant_id,
                            "stat_definition_id": stat,
                            "label": label,
                        }
                    )
                for stat in dict.fromkeys(left_out_ids):
                    self.rows["template_slot_exclusion"].append(
                        {
                            "slot_id": slot_id,
                            "stat_definition_id": stat,
                            "tenant_id": self.tenant_id,
                        }
                    )
            step.templates += 1

    def _plan_grant_rules(self, step: Step) -> None:
        """Plans a repository's grant rules and the prerequisites of its features (ADR 0455), after
        its entries and stats, whose ids they are re-pointed to. A rule is left out, and reported,
        when its source or its category was not copied, when a stat it reads was not, or when none
        of its options was (a rule that grants less than it says is a wrong one, but one whose
        every option is gone grants nothing: an option that was not copied is left out of a rule
        with others). A prerequisite on a stat that was not copied is left out with the feature's
        others."""
        c = step.content
        assert c is not None
        # Only the entries this plan makes get rules and prerequisites: an entry the library
        # already had (a merge) keeps its own, and an update that adds an entry brings its rules.
        created = {row["id"] for row in self.rows["entity"]}
        for rule_id in sorted(
            c.grant_rules,
            key=lambda r: (str(c.grant_rules[r]["entry"]), c.grant_rules[r]["position"], str(r)),
        ):
            rule = c.grant_rules[rule_id]

            def drop(reason: str, rule_id: uuid.UUID = rule_id) -> None:
                step.dropped.append(Dropped("grant_rule", rule_id, reason))

            entry = self._local(c, "entity", rule["entry"])
            if entry is None or entry not in created or not c.own("entity", rule["entry"]):
                continue
            category = None
            if rule["category"] is not None:
                category = self._local(c, "entity", rule["category"])
                if category is None:
                    drop("its category entry wasn't copied")
                    continue
            count_stat = None
            if rule["count_stat"] is not None:
                count_stat = self._local(c, "stat_definition", rule["count_stat"])
                if count_stat is None:
                    drop("the stat it counts with wasn't copied")
                    continue
            options = [self._local(c, "entity", o) for o in rule["options"]]
            kept_options = list(dict.fromkeys(o for o in options if o is not None))
            if rule["category"] is None and not kept_options:
                drop("none of its options was copied")
                continue
            conditions: list[dict[str, Any]] = []
            missing = False
            for position, condition in enumerate(rule["conditions"]):
                stat = self._local(c, "stat_definition", condition["stat"])
                right = (
                    None
                    if condition["right_stat"] is None
                    else self._local(c, "stat_definition", condition["right_stat"])
                )
                if stat is None or (condition["right_stat"] is not None and right is None):
                    missing = True
                    break
                conditions.append(
                    {
                        "position": position,
                        "subject": condition["subject"],
                        "stat_definition_id": stat,
                        "comparator": condition["comparator"],
                        "right_constant": condition["constant"],
                        "right_stat_definition_id": right,
                    }
                )
            if missing:
                drop("a stat one of its conditions reads wasn't copied")
                continue
            new = uuid.uuid4()
            self.rule_ids[rule_id] = new
            self.rows["grant_rule"].append(
                {
                    "id": new,
                    "tenant_id": self.tenant_id,
                    "entry_id": entry,
                    "label": rule["label"],
                    "position": rule["position"],
                    "mode": rule["mode"],
                    "min_count": rule["min"],
                    "max_count": rule["max"],
                    "count_stat_definition_id": count_stat,
                    "option_category_entry_id": category,
                    "lasts": rule["lasts"],
                    "changeable": rule["changeable"],
                }
            )
            for condition in conditions:
                self.rows["grant_rule_condition"].append(
                    {"id": uuid.uuid4(), "tenant_id": self.tenant_id, "rule_id": new, **condition}
                )
            for position, option in enumerate(kept_options):
                self.rows["grant_rule_option"].append(
                    {
                        "rule_id": new,
                        "option_entry_id": option,
                        "tenant_id": self.tenant_id,
                        "position": position,
                    }
                )
        for feature_id in sorted(c.prerequisites, key=str):
            feature = self._local(c, "entity", feature_id)
            if feature is None or feature not in created or not c.own("entity", feature_id):
                continue
            position = 0
            for prerequisite in c.prerequisites[feature_id]:
                stat = self._local(c, "stat_definition", prerequisite["stat"])
                right = (
                    None
                    if prerequisite["right_stat"] is None
                    else self._local(c, "stat_definition", prerequisite["right_stat"])
                )
                if stat is None or (prerequisite["right_stat"] is not None and right is None):
                    step.dropped.append(
                        Dropped(
                            "feature_prerequisite",
                            feature_id,
                            "a stat it reads wasn't copied",
                        )
                    )
                    continue
                self.rows["feature_prerequisite"].append(
                    {
                        "id": uuid.uuid4(),
                        "tenant_id": self.tenant_id,
                        "feature_id": feature,
                        "position": position,
                        "stat_definition_id": stat,
                        "comparator": prerequisite["comparator"],
                        "right_constant": prerequisite["constant"],
                        "right_stat_definition_id": right,
                    }
                )
                position += 1

    def _plan_grant_records(self, step: Step) -> None:
        """Plans how the holders of a repository came to have their features (ADR 0456): a record
        for each instance this plan makes, with its rule (as the library's own copy of it) and its
        source. A record whose rule or source was not copied is left out, and the instance stays as
        if it had been awarded. Copied once and never changed by an update, as an instance is."""
        c = step.content
        assert c is not None
        created = {row["id"] for row in self.rows["entity"]}
        for record_id in sorted(c.grant_records, key=str):
            record = c.grant_records[record_id]
            holder = self._local(c, "entity", record["holder"])
            instance = self._local(c, "entity", record["instance"])
            feature = self._local(c, "entity", record["feature"])
            if (
                holder is None
                or instance is None
                or feature is None
                or instance not in created
                or not c.own("entity", record["instance"])
            ):
                continue
            rule = None
            if record["rule"] is not None:
                rule = self.rule_ids.get(record["rule"])
                if rule is None:
                    continue
            source = None
            if record["source"] is not None:
                source = self._local(c, "entity", record["source"])
                if source is None:
                    continue
            self.rows["grant_record"].append(
                {
                    "id": uuid.uuid4(),
                    "tenant_id": self.tenant_id,
                    "holder_id": holder,
                    "rule_id": rule,
                    "source_ref_id": source,
                    "feature_id": feature,
                    "feature_instance_id": instance,
                    "state": "active",
                    "created_by": self.user_id,
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
    strict_units: bool = False,
) -> Plan:
    """Everything a copy would do, without writing. Raises nothing about
    collisions or grants: the plan carries them, for `copy-plan` to show
    and `apply_plan` to refuse."""
    steps = await manifest(session, tenant_id=tenant_id, repository_id=repository_id)
    # A retired repository blocks every new copy, a dependency the library has not copied yet
    # included. Only a step the library can read gets here with its words: for any other the
    # manifest has answered `404`, or the plan says it is missing (ADR 0384).
    top = steps[-1]
    # A protected repository is a step of a copy and never its head, for a library: only a
    # repository of its own, which its Owner invited, is built on it (ADR 0434).
    if top.protected and not await _is_repository(session, tenant_id):
        raise _protected_alone()
    if top.deprecated and top.readable:
        raise copy_refusal(top.name, top.deprecated_message)
    if not top.already_copied:
        for step in steps[:-1]:
            if step.deprecated and step.readable and not step.already_copied:
                raise copy_refusal(step.name, step.deprecated_message)
    steps[-1].head = True
    plan = Plan(tenant_id=tenant_id, steps=steps)
    if steps[-1].already_copied or plan.missing:
        return plan
    links = await load_links(session, tenant_id)
    planner = _Planner(
        tenant_id,
        user_id,
        links,
        {(r.kind, r.source_id): r for r in resolutions},
        strict_units=strict_units,
    )
    await planner.load_local_names(session)
    for step in plan.to_copy:
        # Every step but the head is read through the head, as the manifest read it (ADR 0434).
        via = None if step is steps[-1] else steps[-1].repository_id
        async with reading_repository(session, step.repository_id, via=via) as allowed:
            assert allowed  # manifest already checked grant and publication
            upstream = await load_upstream(session, step.repository_id)
            step.content = upstream.content
            step.release_id = upstream.release.id if upstream.release else None
        planner.plan_step(step)
    plan.collisions = planner.collisions
    plan.warnings = planner.warnings
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

    for tenant_id in sorted(
        {r["tenant_id"] for r in rows.get("event_relationship", []) + rows.get("lived_before", [])}
    ):
        await lock_event_order(session, tenant_id)
    from lorenzo_api.models import Clock
    from lorenzo_api.routers.clocks import lock_clock_entries, mutation_lock

    clock_dependencies: dict[uuid.UUID, set[uuid.UUID]] = {}
    for table in ("event_clock_reading", "calendar_reckoning", "clock_relationship"):
        for record in rows.get(table, []):
            clock_dependencies.setdefault(record["tenant_id"], set()).add(record["clock_entity_id"])
            if table == "clock_relationship":
                clock_dependencies[record["tenant_id"]].add(record["reference_clock_entity_id"])
    clock_tenants = set(clock_dependencies) | {
        record["tenant_id"] for record in rows.get("clock", [])
    }
    for tenant in sorted(clock_tenants):
        await mutation_lock(session, tenant)
        identities = clock_dependencies.get(tenant, set())
        await lock_clock_entries(session, tenant, list(identities))
        available = set(
            await session.scalars(
                select(Clock.entity_id).where(
                    Clock.tenant_id == tenant,
                    Clock.entity_id.in_(identities),
                    Clock.ticking.is_(True),
                )
            )
        )
        available |= {
            record["entity_id"]
            for record in rows.get("clock", [])
            if record["tenant_id"] == tenant and record.get("ticking", True)
        }
        if identities - available:
            raise InvalidRepositoryUpdateError(
                detail="Copy ticking clock dependencies before their records"
            )
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
    for target, source in await session.execute(
        select(
            ComputedStatExtremumInput.stat_definition_id,
            ComputedStatExtremumInput.source_stat_definition_id,
        ).where(
            ComputedStatExtremumInput.tenant_id == tenant_id,
            ComputedStatExtremumInput.source_stat_definition_id.is_not(None),
        )
    ):
        edges[target].add(source)
    for target, source in await session.execute(
        select(
            ComputedStatProductFactor.stat_definition_id,
            ComputedStatProductFactor.source_stat_definition_id,
        ).where(ComputedStatProductFactor.tenant_id == tenant_id)
    ):
        edges[target].add(source)
    for target, source in await session.execute(
        select(
            ComputedStatSelect.stat_definition_id, ComputedStatSelect.source_stat_definition_id
        ).where(ComputedStatSelect.tenant_id == tenant_id)
    ):
        edges[target].add(source)
    for target, source in await session.execute(
        select(
            ComputedStatSelect.stat_definition_id, ComputedStatSelect.otherwise_stat_definition_id
        ).where(
            ComputedStatSelect.tenant_id == tenant_id,
            ComputedStatSelect.otherwise_stat_definition_id.is_not(None),
        )
    ):
        edges[target].add(source)
    for target, source in await session.execute(
        select(
            ComputedStatSelectStep.stat_definition_id,
            ComputedStatSelectStep.result_stat_definition_id,
        ).where(
            ComputedStatSelectStep.tenant_id == tenant_id,
            ComputedStatSelectStep.result_stat_definition_id.is_not(None),
        )
    ):
        edges[target].add(source)
    for target, numerator, denominator in await session.execute(
        select(
            ComputedStatRatio.stat_definition_id,
            ComputedStatRatio.numerator_stat_definition_id,
            ComputedStatRatio.denominator_stat_definition_id,
        ).where(ComputedStatRatio.tenant_id == tenant_id)
    ):
        edges[target].add(numerator)
        if denominator is not None:
            edges[target].add(denominator)
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
    await refresh_hidden(session, plan.tenant_id)
    for step in plan.to_copy:
        reported_dropped = sum(
            d.kind
            not in ("event_relationship", "event_participant", "event_learning", "lived_before")
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
        from lorenzo_api.routers.clocks import mutation_lock

        await mutation_lock(session, t)
        # Serialize with materialization and date edits before inspecting local references.
        await session.execute(
            select(Entity.id)
            .where(Entity.tenant_id == t, Entity.id.in_(entities))
            .order_by(Entity.id)
            .with_for_update()
        )
        if await session.scalar(
            select(Edition.entity_id)
            .where(
                Edition.tenant_id == t,
                Edition.book_entity_id.in_(entities),
                Edition.entity_id.not_in(entities),
            )
            .limit(1)
        ) or await session.scalar(
            select(ManuscriptPlacement.child_entity_id)
            .where(
                ManuscriptPlacement.tenant_id == t,
                ManuscriptPlacement.parent_entity_id.in_(entities),
                ManuscriptPlacement.child_entity_id.not_in(entities),
            )
            .limit(1)
        ):
            raise EntityKindInUseError(detail="Local manuscript structure still uses this copy.")
        if await session.scalar(
            select(SceneTelling.entity_id)
            .where(
                SceneTelling.tenant_id == t,
                SceneTelling.entity_id.not_in(entities),
                or_(
                    SceneTelling.scene_entity_id.in_(entities),
                    SceneTelling.viewpoint_entity_id.in_(entities),
                ),
            )
            .limit(1)
        ):
            raise EntityKindInUseError(
                detail="Local tellings still reference this repository copy."
            )
        if await session.scalar(
            select(CarrierCoverage.id)
            .where(
                CarrierCoverage.tenant_id == t,
                CarrierCoverage.carrier_id.not_in(entities),
                or_(
                    CarrierCoverage.target_entity_id.in_(entities),
                    CarrierCoverage.target_payload_id.in_(
                        select(Payload.id)
                        .join(Information, Information.id == Payload.information_id)
                        .where(Information.entity_id.in_(entities))
                    ),
                ),
            )
            .limit(1)
        ):
            raise EntityKindInUseError(
                detail="Local Carrier coverage still references this repository copy."
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
        from lorenzo_api.models import EventPresentation

        local_presentation = await session.scalar(
            select(
                exists().where(
                    EventPresentation.tenant_id == t,
                    EventPresentation.event_entity_id.in_(entities),
                )
            )
        )
        local_story = await session.scalar(
            select(
                exists().where(
                    SceneAppearance.tenant_id == t,
                    SceneAppearance.scene_entity_id.in_(entities),
                    SceneAppearance.entity_id.not_in(entities),
                )
            )
        )
        local_story_period = await session.scalar(
            select(
                exists().where(
                    StorySession.tenant_id == t,
                    StorySession.start_period_id.in_(entities),
                )
            )
        )
        local_scene_period = await session.scalar(
            select(
                exists().where(
                    Scene.tenant_id == t,
                    Scene.entity_id.not_in(entities),
                    Scene.period_entity_id.in_(entities),
                )
            )
        )
        if (
            local_period
            or local_date
            or local_rule
            or local_story
            or local_presentation
            or local_story_period
            or local_scene_period
        ):
            raise EntityKindInUseError(
                detail="Local dated material still references this copy. Resolve it before purging."
            )
        clock_bindings: list[tuple[type[EventClockReading] | type[CalendarReckoning], Any]] = [
            (EventClockReading, EventClockReading.event_entity_id),
            (CalendarReckoning, CalendarReckoning.calendar_entity_id),
        ]
        for clock_model, source in clock_bindings:
            if await session.scalar(
                select(source)
                .where(
                    clock_model.tenant_id == t,
                    source.not_in(entities),
                    clock_model.clock_entity_id.in_(entities),
                )
                .limit(1)
            ):
                raise InvalidRepositoryUpdateError(
                    detail="Resolve local references before purging this copy"
                )
        if await session.scalar(
            select(ClockRelationship.clock_entity_id)
            .where(
                ClockRelationship.tenant_id == t,
                or_(
                    ClockRelationship.clock_entity_id.in_(entities)
                    & ClockRelationship.reference_clock_entity_id.not_in(entities),
                    ClockRelationship.reference_clock_entity_id.in_(entities)
                    & ClockRelationship.clock_entity_id.not_in(entities),
                ),
            )
            .limit(1)
        ):
            raise InvalidRepositoryUpdateError(
                detail="Resolve local references before purging this copy"
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
                ComputedStatProductFactor.entity_id == ComputedStat.entity_id,
                ComputedStatProductFactor.stat_definition_id == ComputedStat.stat_definition_id,
                ComputedStatProductFactor.source_stat_definition_id.in_(all_definitions),
            ),
            exists().where(
                ComputedStatSelect.entity_id == ComputedStat.entity_id,
                ComputedStatSelect.stat_definition_id == ComputedStat.stat_definition_id,
                or_(
                    ComputedStatSelect.source_stat_definition_id.in_(all_definitions),
                    ComputedStatSelect.otherwise_stat_definition_id.in_(all_definitions),
                ),
            ),
            exists().where(
                ComputedStatSelectStep.entity_id == ComputedStat.entity_id,
                ComputedStatSelectStep.stat_definition_id == ComputedStat.stat_definition_id,
                ComputedStatSelectStep.result_stat_definition_id.in_(all_definitions),
            ),
            exists().where(
                ComputedStatRatio.entity_id == ComputedStat.entity_id,
                ComputedStatRatio.stat_definition_id == ComputedStat.stat_definition_id,
                or_(
                    ComputedStatRatio.numerator_stat_definition_id.in_(all_definitions),
                    ComputedStatRatio.denominator_stat_definition_id.in_(all_definitions),
                ),
            ),
            exists().where(
                ComputedStatExtremumInput.entity_id == ComputedStat.entity_id,
                ComputedStatExtremumInput.stat_definition_id == ComputedStat.stat_definition_id,
                ComputedStatExtremumInput.source_stat_definition_id.in_(all_definitions),
            ),
            exists().where(
                ComputedStatContents.entity_id == ComputedStat.entity_id,
                ComputedStatContents.stat_definition_id == ComputedStat.stat_definition_id,
                or_(
                    ComputedStatContents.source_stat_definition_id.in_(all_definitions),
                    ComputedStatContents.where_stat_definition_id.in_(all_definitions),
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
        from lorenzo_api.story_context import SCENE_REFERENCES

        for binding in SCENE_REFERENCES.values():
            source = getattr(binding.model, binding.source)
            target = getattr(binding.model, binding.target)
            also[binding.model.__tablename__] = await _count(
                session,
                binding.model,
                binding.model.tenant_id == t,
                or_(
                    source.in_(entities) & target.not_in(entities),
                    target.in_(entities) & source.not_in(entities),
                ),
            )
        for clock_model, source in clock_bindings:
            also[clock_model.__tablename__] = await _count(
                session,
                clock_model,
                clock_model.tenant_id == t,
                or_(
                    source.in_(entities) & clock_model.clock_entity_id.not_in(entities),
                    clock_model.clock_entity_id.in_(entities) & source.not_in(entities),
                ),
            )
        also["clock_relationship"] = await _count(
            session,
            ClockRelationship,
            ClockRelationship.tenant_id == t,
            or_(
                ClockRelationship.clock_entity_id.in_(entities)
                & ClockRelationship.reference_clock_entity_id.not_in(entities),
                ClockRelationship.reference_clock_entity_id.in_(entities)
                & ClockRelationship.clock_entity_id.not_in(entities),
            ),
        )
        also["map_placement"] = await _count(
            session,
            MapPlacement,
            MapPlacement.tenant_id == t,
            or_(
                MapPlacement.map_entity_id.in_(entities)
                & MapPlacement.entry_entity_id.not_in(entities),
                MapPlacement.entry_entity_id.in_(entities)
                & MapPlacement.map_entity_id.not_in(entities),
            ),
        )
        also["entity_frame"] = await _count(
            session,
            EntityFrame,
            EntityFrame.tenant_id == t,
            or_(
                EntityFrame.entity_id.in_(entities) & EntityFrame.frame_entity_id.not_in(entities),
                EntityFrame.frame_entity_id.in_(entities) & EntityFrame.entity_id.not_in(entities),
            ),
        )
        also["entity_location"] = await _count(
            session,
            EntityLocation,
            EntityLocation.tenant_id == t,
            or_(
                EntityLocation.entity_id.in_(entities)
                & EntityLocation.location_entity_id.not_in(entities),
                EntityLocation.location_entity_id.in_(entities)
                & EntityLocation.entity_id.not_in(entities),
            ),
        )
        also["location_part"] = await _count(
            session,
            LocationPart,
            LocationPart.tenant_id == t,
            or_(
                LocationPart.child_entity_id.in_(entities)
                & LocationPart.parent_entity_id.not_in(entities),
                LocationPart.parent_entity_id.in_(entities)
                & LocationPart.child_entity_id.not_in(entities),
            ),
        )
        also["lived_before"] = await _count(
            session,
            LivedBefore,
            LivedBefore.tenant_id == t,
            or_(
                LivedBefore.being_entity_id.in_(entities),
                LivedBefore.from_event_id.in_(entities),
                LivedBefore.to_event_id.in_(entities),
            ),
        )
        # A chain that joins a copied relationship to one that was not copied here (ADR 0402).
        also["relationship_through"] = await _count(
            session,
            RelationshipThrough,
            RelationshipThrough.tenant_id == t,
            or_(
                RelationshipThrough.relationship_entity_id.in_(entities)
                & RelationshipThrough.via_entity_id.not_in(entities),
                RelationshipThrough.via_entity_id.in_(entities)
                & RelationshipThrough.relationship_entity_id.not_in(entities),
            ),
        )
        # A web that holds an entry copied here, or a copied web that holds one that was not (ADR
        # 0406).
        also["social_web_entry"] = await _count(
            session,
            SocialWebEntry,
            SocialWebEntry.tenant_id == t,
            or_(
                SocialWebEntry.web_entity_id.in_(entities)
                & SocialWebEntry.entry_entity_id.not_in(entities),
                SocialWebEntry.entry_entity_id.in_(entities)
                & SocialWebEntry.web_entity_id.not_in(entities),
            ),
        )
        also["social_web_type"] = await _count(
            session,
            SocialWebType,
            SocialWebType.tenant_id == t,
            or_(
                SocialWebType.web_entity_id.in_(entities)
                & SocialWebType.type_entity_id.not_in(entities),
                SocialWebType.type_entity_id.in_(entities)
                & SocialWebType.web_entity_id.not_in(entities),
            ),
        )
        also["manuscript_placement"] = await _count(
            session,
            ManuscriptPlacement,
            ManuscriptPlacement.tenant_id == t,
            ManuscriptPlacement.child_entity_id.in_(entities),
        )
        also["carrier_coverage"] = await _count(
            session,
            CarrierCoverage,
            CarrierCoverage.tenant_id == t,
            CarrierCoverage.carrier_id.in_(entities),
        )
        # A template that shows a purged group or stat, or is for a purged entry, goes with them:
        # its slots would point at nothing (ADR 0453).
        shows_purged = Template.id.in_(
            select(TemplateSlot.template_id).where(
                TemplateSlot.tenant_id == t,
                or_(
                    TemplateSlot.stat_group_id.in_(groups),
                    TemplateSlot.id.in_(
                        select(TemplateSlotStat.slot_id).where(
                            TemplateSlotStat.tenant_id == t,
                            TemplateSlotStat.stat_definition_id.in_(all_definitions),
                        )
                    ),
                    TemplateSlot.id.in_(
                        select(TemplateSlotExclusion.slot_id).where(
                            TemplateSlotExclusion.tenant_id == t,
                            TemplateSlotExclusion.stat_definition_id.in_(all_definitions),
                        )
                    ),
                ),
            )
        ) | Template.required_ancestor_entry_id.in_(entities)
        also["template"] = await _count(session, Template, Template.tenant_id == t, shows_purged)
        # A grant rule that reads a purged stat, or is on or for a purged entry, goes with them, and
        # so does a prerequisite on a purged stat or feature (ADR 0455); a stat key cascades not.
        reads_purged_stat = GrantRule.id.in_(
            select(GrantRule.id).where(
                GrantRule.tenant_id == t,
                or_(
                    GrantRule.count_stat_definition_id.in_(all_definitions),
                    GrantRule.id.in_(
                        select(GrantRuleCondition.rule_id).where(
                            GrantRuleCondition.tenant_id == t,
                            or_(
                                GrantRuleCondition.stat_definition_id.in_(all_definitions),
                                GrantRuleCondition.right_stat_definition_id.in_(all_definitions),
                            ),
                        )
                    ),
                ),
            )
        )
        rules_purged = (
            reads_purged_stat
            | GrantRule.entry_id.in_(entities)
            | GrantRule.option_category_entry_id.in_(entities)
        )
        also["grant_rule"] = await _count(
            session, GrantRule, GrantRule.tenant_id == t, rules_purged
        )
        prerequisites_purged = (
            FeaturePrerequisite.stat_definition_id.in_(all_definitions)
            | FeaturePrerequisite.right_stat_definition_id.in_(all_definitions)
            | FeaturePrerequisite.feature_id.in_(entities)
        )
        also["feature_prerequisite"] = await _count(
            session, FeaturePrerequisite, FeaturePrerequisite.tenant_id == t, prerequisites_purged
        )
        # The counts above are hand-written; the registry says which tables they are for.
        assert set(also) == PURGE_COUNTED, set(also) ^ PURGE_COUNTED
        previous.also_removed = {kind: n for kind, n in also.items() if n}
        # Formula inputs don't cascade (ADR 0104), so the tenant's own
        # formulas reading a purged definition go first; everything else
        # cascades from the rows themselves.
        await session.execute(delete(ComputedStat).where(own_formulas, uses_definition))
        await session.execute(delete(Template).where(Template.tenant_id == t, shows_purged))
        await session.execute(delete(GrantRule).where(GrantRule.tenant_id == t, rules_purged))
        await session.execute(
            delete(FeaturePrerequisite).where(
                FeaturePrerequisite.tenant_id == t, prerequisites_purged
            )
        )
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
            delete(LivedBefore).where(
                LivedBefore.tenant_id == t,
                or_(
                    LivedBefore.being_entity_id.in_(entities),
                    LivedBefore.from_event_id.in_(entities),
                    LivedBefore.to_event_id.in_(entities),
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
        for clock_model, source in clock_bindings:
            await session.execute(
                delete(clock_model).where(
                    clock_model.tenant_id == t,
                    or_(source.in_(entities), clock_model.clock_entity_id.in_(entities)),
                )
            )
        await session.execute(
            delete(ClockRelationship).where(
                ClockRelationship.tenant_id == t,
                or_(
                    ClockRelationship.clock_entity_id.in_(entities),
                    ClockRelationship.reference_clock_entity_id.in_(entities),
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
        from lorenzo_api.story_context import SCENE_REFERENCES, SESSION_REFERENCES

        for binding in [*SCENE_REFERENCES.values(), *SESSION_REFERENCES.values()]:
            await session.execute(
                delete(binding.model).where(
                    binding.model.tenant_id == t,
                    or_(
                        getattr(binding.model, binding.source).in_(entities),
                        getattr(binding.model, binding.target).in_(entities),
                    ),
                )
            )
        # Composition parents deliberately refuse individual deletion. A reviewed
        # purge removes the copied relationships before their parent entities.
        await session.execute(
            delete(ManuscriptPlacement).where(
                ManuscriptPlacement.tenant_id == t,
                ManuscriptPlacement.child_entity_id.in_(entities),
            )
        )
        await session.execute(
            delete(SceneTelling).where(
                SceneTelling.tenant_id == t, SceneTelling.entity_id.in_(entities)
            )
        )
        await session.execute(
            delete(Edition).where(Edition.tenant_id == t, Edition.entity_id.in_(entities))
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
    await refresh_hidden(session, t)
    reported_removed = sum(
        count
        for kind, count in previous.also_removed.items()
        if kind not in ("event_relationship", "event_participant", "event_learning", "lived_before")
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
