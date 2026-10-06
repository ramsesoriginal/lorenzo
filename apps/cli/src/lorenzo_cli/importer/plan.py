"""Working out what an import would do (RFC 0025 §2, R4, R5, R6, ADR 0144).

The plan is a function of the evaluated files, the mapping, and what the tenant already holds. It
reads from the tenant and writes nothing. `apply` carries out a plan; it never recomputes a slug.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from lorenzo_cli import descriptions
from lorenzo_cli.client.models import (
    EntityDetailOut,
    ResolvedSlugOut,
    StatDefinitionOut,
    TenantOut,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.evalworker import EvalResult
from lorenzo_cli.importer import tenant_view
from lorenzo_cli.importer.draft import Ancestry, ItemDraft, NewCategory, draft_item, part_view
from lorenzo_cli.importer.manifest import Manifest
from lorenzo_cli.importer.mapping import LoadedMapping, Mapping, Part
from lorenzo_cli.importer.packs import (
    NameIndex,
    Placed,
    Target,
    Unresolved,
    build_contents,
    parse_entries,
    render,
    resolve_refs,
)
from lorenzo_cli.importer.parts import Parts
from lorenzo_cli.importer.slugs import LIST_TOKENS, assign_slugs
from lorenzo_cli.importer.transforms import Issue
from lorenzo_cli.seed import SeedSpec

Status = Literal["create", "complete", "retitle", "exists", "held", "skipped", "moved"]
# Written last: an existing item without it is one an earlier run stopped part-way through.
MARKER_STAT = "sourcebook"
SEED_LIST = {token: name for name, token in LIST_TOKENS.items()}


@dataclass
class PlannedItem:
    draft: ItemDraft
    slug: str = ""
    status: Status = "create"
    entity_id: UUID | None = None
    # An existing item whose parents differ from what the map now says.
    reparent: bool = False
    moved_from: str | None = None
    # What an existing item already holds, so `complete` writes only what is missing.
    have_stats: frozenset[str] = frozenset()
    has_description: bool = False
    # The types of information entries it already has (other names, notes...).
    have_information: frozenset[str] = frozenset()
    # Its description, titled with the placeholder the CLI used to give every one: the row, and
    # the name it should be titled with (ADR 0165).
    retitle: tuple[UUID, str] | None = None
    # The system pass (ADR 0182): the neutral item this prototype is for, by slug and id, and
    # whether the prototype is among its parents already.
    neutral_slug: str = ""
    neutral_id: UUID | None = None
    attached: bool = False


@dataclass(frozen=True)
class NewDefinition:
    name: str
    group: str
    value_type: str


@dataclass
class ImportPlan:
    tenant: TenantOut
    loaded: LoadedMapping
    seed_version: str
    items: list[PlannedItem] = field(default_factory=list)
    categories: list[NewCategory] = field(default_factory=list)
    definitions: list[NewDefinition] = field(default_factory=list)
    overrides: list[dict[str, str]] = field(default_factory=list)
    file_errors: list[str] = field(default_factory=list)
    stubbed: list[str] = field(default_factory=list)
    # The tenant can't take this import as it is (not seeded, a stat of the wrong type...).
    problems: list[str] = field(default_factory=list)
    # Which half of the items this plan is for (ADR 0182); None writes both onto one item.
    part: Part | None = None
    # The parents the importer places (the seed's categories and those a row mints): re-parenting
    # replaces these and keeps every other parent.
    managed_ids: frozenset[UUID] = frozenset()

    def count(self, status: Status) -> int:
        return sum(1 for i in self.items if i.status == status)

    @property
    def held(self) -> list[PlannedItem]:
        return [i for i in self.items if i.status in ("held", "moved")]

    @property
    def retitle_count(self) -> int:
        return sum(1 for i in self.items if i.retitle is not None)

    @property
    def reparent_count(self) -> int:
        return sum(1 for i in self.items if i.reparent)

    def unmapped(self) -> dict[tuple[str, str], int]:
        """Attributes no rule mentions, once each per list, with how many items had it."""
        counts: Counter[tuple[str, str]] = Counter()
        for item in self.items:
            if item.status != "skipped":
                counts.update((item.draft.list_name, a) for a in item.draft.unmapped)
        return dict(sorted(counts.items()))

    def pack_unresolved(self) -> list[tuple[PlannedItem, Unresolved]]:
        """Entries of a pack that nothing could be linked to: reported, never guessed at."""
        return [
            (i, u)
            for i in self.items
            if i.status not in ("skipped", "held")
            for u in i.draft.pack_unresolved
        ]

    @property
    def pending(self) -> bool:
        return any(i.status in ("create", "complete", "retitle") for i in self.items)


@dataclass(frozen=True)
class Options:
    accept_moves: bool = False
    reconcile: bool = False
    part: Part | None = None


def build_drafts(result: EvalResult, loaded: LoadedMapping, seed: SeedSpec) -> list[ItemDraft]:
    ancestry = Ancestry(seed)
    parts = Parts(seed)
    drafts: list[ItemDraft] = []
    for variable, token in LIST_TOKENS.items():
        entries = result.lists.get(variable, {})
        origins = result.origins.get(variable, {})
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            drafts.append(
                draft_item(token, key, entry, origins.get(key, ""), loaded.mapping, ancestry, parts)
            )
    return drafts


def _final_slugs(
    client: LorenzoClient, tenant_id: UUID, drafts: list[ItemDraft]
) -> tuple[dict[tuple[str, str], str], dict[str, ResolvedSlugOut]]:
    """Slugs for the drafts, taking a suffix where two collide or the tenant's slug is held by
    something that isn't an item; and what the tenant has under them."""
    taken: set[str] = set()
    while True:
        slugs = assign_slugs([(d.namespace, d.list_name, d.key) for d in drafts], taken)
        found = tenant_view.resolve_slugs(client, tenant_id, list(slugs.values()))
        held_by_others = {
            slug for slug, hit in found.items() if "item" not in {kind.value for kind in hit.kinds}
        }
        # A base slug someone else holds: every member of it takes a suffix.
        newly = {s for s in held_by_others if s not in taken}
        if not newly:
            return slugs, found
        taken |= newly


def build_plan(
    client: LorenzoClient,
    tenant: TenantOut,
    loaded: LoadedMapping,
    result: EvalResult,
    seed: SeedSpec,
    manifest: Manifest,
    options: Options | None = None,
) -> ImportPlan:
    options = options or Options()
    plan = ImportPlan(tenant=tenant, loaded=loaded, seed_version=seed.version, part=options.part)
    plan.overrides = [
        {"list": o.list, "key": o.key, "replaced_file": o.replaced_file, "by_file": o.by_file}
        for o in result.overrides
    ]
    plan.file_errors = [f"{f.name}: {f.error}" for f in result.files if f.status != "ok"]
    plan.stubbed = [s.name for s in result.stubs]

    drafts = build_drafts(result, loaded, seed)
    planned = [PlannedItem(d) for d in drafts]
    index, plain_items = _resolve_packs(planned, loaded.mapping)
    planned += plain_items
    live = [p for p in planned if p.draft.skip_reason is None]
    for item in planned:
        if item.draft.skip_reason is not None:
            item.status = "skipped"

    # The neutral slugs come first, over the whole run in every pass, so that the system pass
    # finds the items the neutral pass made (ADR 0182).
    slugs, found = _final_slugs(client, tenant.id, [p.draft for p in live])
    for item in live:
        item.slug = item.neutral_slug = slugs[(item.draft.list_name, item.draft.key)]
    _render_packs(live, index, slugs)

    parts = Parts(seed)
    if options.part == "neutral":
        for item in live:
            item.draft = part_view(item.draft, "neutral", parts)
    elif options.part == "system":
        live, found = _system_items(client, tenant.id, live, parts)

    categories: dict[str, NewCategory] = {}
    for item in live:
        for category in item.draft.categories:
            categories.setdefault(category.slug, category)
    plan.categories = list(categories.values())

    needed_parents = sorted({p for i in live for p in i.draft.parents} - categories.keys())
    parent_ids = {
        slug: hit.entity_id
        for slug, hit in tenant_view.resolve_slugs(client, tenant.id, needed_parents).items()
    }
    managed = tenant_view.resolve_slugs(
        client, tenant.id, sorted({n.slug for n in seed.nodes} | loaded.mapping.minted_slugs())
    )
    plan.managed_ids = frozenset(
        {hit.entity_id for hit in managed.values()} | set(parent_ids.values())
    )
    tenant_defs = tenant_view.stat_definitions(client, tenant.id)
    _check_seeded(plan, live, needed_parents, parent_ids, tenant_defs, seed)
    for item in live:
        _decide(client, tenant.id, item, found, parent_ids, plan.managed_ids, manifest, options)
    plan.items = planned
    return plan


def _system_items(
    client: LorenzoClient, tenant_id: UUID, live: list[PlannedItem], parts: Parts
) -> tuple[list[PlannedItem], dict[str, ResolvedSlugOut]]:
    """The system pass (ADR 0182): each item's prototype, in the system's namespace, for the item
    the neutral pass made. An item with nothing of the system's has no prototype; an item that
    isn't in this tenant is held, with the way to put it there."""
    prototypes: list[PlannedItem] = []
    for item in live:
        item.draft = part_view(item.draft, "system", parts)
        if item.draft.skip_reason is not None:
            item.status = "skipped"
        else:
            prototypes.append(item)
    slugs, found = _final_slugs(client, tenant_id, [i.draft for i in prototypes])
    neutral = tenant_view.resolve_slugs(client, tenant_id, [i.neutral_slug for i in prototypes])
    for item in prototypes:
        item.slug = slugs[(item.draft.list_name, item.draft.key)]
        hit = neutral.get(item.neutral_slug)
        if hit is None or "item" not in {kind.value for kind in hit.kinds}:
            item.draft.issues.append(
                Issue(
                    "neutral-item",
                    "",
                    item.neutral_slug,
                    f"its neutral item {item.neutral_slug} isn't in this tenant",
                    "run `lorenzo apply --part neutral` in the equipment repository, and take "
                    "it here with `lorenzo repo copy` or `lorenzo repo updates`",
                )
            )
        else:
            item.neutral_id = hit.entity_id
    return prototypes, found


def _check_seeded(
    plan: ImportPlan,
    live: list[PlannedItem],
    needed_parents: list[str],
    present_parents: dict[str, UUID],
    tenant_defs: dict[str, StatDefinitionOut],
    seed: SeedSpec,
) -> None:
    """The import needs the seed's categories and stats to be there. Say so once, plainly."""
    missing_parents = [p for p in needed_parents if p not in present_parents]
    seed_types = {d.name: (d.value_type, d.group) for d in seed.definitions}
    wanted: dict[str, tuple[str, str | None]] = {}
    for item in live:
        for stat in item.draft.stats:
            value_type = (
                seed_types[stat][0] if stat in seed_types else item.draft.stat_types.get(stat)
            )
            group = item.draft.stat_groups.get(stat) or (
                seed_types[stat][1] if stat in seed_types else None
            )
            if value_type is not None:
                wanted[stat] = (value_type, group)
    missing_stats: list[str] = []
    new_defs: dict[str, NewDefinition] = {}
    for stat, (value_type, group) in sorted(wanted.items()):
        existing = tenant_defs.get(stat)
        if existing is not None:
            if existing.value_type.value != value_type:
                plan.problems.append(
                    f"The stat {stat!r} is a {existing.value_type.value} stat in this tenant, "
                    f"and this import writes a {value_type}."
                )
            continue
        if stat in seed_types:
            missing_stats.append(stat)
        elif group is None:
            plan.problems.append(
                f"A rule writes the stat {stat!r}, which this tenant doesn't have. Give the rule "
                "a `group` to create it in, or create the stat first."
            )
        else:
            new_defs[stat] = NewDefinition(stat, group, value_type)
    plan.definitions = list(new_defs.values())
    if missing_parents or missing_stats:
        shown = ", ".join([*missing_parents[:6], *missing_stats[:6]])
        plan.problems.append(
            f"This tenant hasn't been seeded: it lacks {shown}"
            f"{' and more' if len(missing_parents) + len(missing_stats) > 12 else ''}. "
            "Run `lorenzo seed` on it first."
        )


def _decide(
    client: LorenzoClient,
    tenant_id: UUID,
    item: PlannedItem,
    found: dict[str, ResolvedSlugOut],
    parent_ids: dict[str, UUID],
    managed_ids: frozenset[UUID],
    manifest: Manifest,
    options: Options,
) -> None:
    draft = item.draft
    if draft.issues:
        item.status = "held"
        return
    system = options.part == "system"
    # The system pass keeps its slugs apart from the neutral pass's, which may share a tenant.
    token = f"system:{draft.list_name}" if system else draft.list_name
    hit = found.get(item.slug)
    if hit is None:
        previous = manifest.slug_for(token, draft.key)
        if previous and previous != item.slug and not options.accept_moves:
            still_there = tenant_view.resolve_slugs(client, tenant_id, [previous])
            if previous in still_there:
                item.status, item.moved_from = "moved", previous
                return
        item.status = "create"
        return
    item.entity_id = hit.entity_id
    detail = tenant_view.entity_detail(client, tenant_id, hit.entity_id)
    item.have_stats = frozenset(s.name for s in detail.stats if s.own)
    item.has_description = any(i.type == "description" for i in detail.information)
    item.have_information = frozenset(i.type for i in detail.information)
    wanted = {parent_ids[p] for p in draft.parents if p in parent_ids}
    # Only the parents the importer places count: an attached prototype, or a parent an author
    # added, is neither wrong nor to be removed (ADR 0182).
    placed = {p.id for p in detail.prototypes if p.id in managed_ids}
    if placed != wanted and len(wanted) == len(draft.parents):
        item.reparent = True
    if system:
        # The attachment is the system pass's last step, so it is what says a prototype is done.
        assert item.neutral_id is not None
        neutral = tenant_view.entity_detail(client, tenant_id, item.neutral_id)
        item.attached = entity_is_parent(neutral, item.entity_id)
        incomplete = not item.attached
    else:
        incomplete = (MARKER_STAT in draft.stats and MARKER_STAT not in item.have_stats) or (
            bool(draft.pack_lines) and not item.has_description
        )
    stale = descriptions.placeholder_description(detail)
    if stale is not None:
        item.retitle = (stale.id, detail.name)
    item.status = "complete" if incomplete else ("retitle" if stale is not None else "exists")


def entity_is_parent(detail: EntityDetailOut, parent_id: UUID) -> bool:
    return any(p.id == parent_id for p in detail.prototypes)


def _resolve_packs(
    planned: list[PlannedItem], mapping: Mapping
) -> tuple[NameIndex, list[PlannedItem]]:
    """First step of a pack's contents: decide what each entry refers to. An entry the sheet has no
    item for becomes a simple plain item of its own, one per name however many packs mention it;
    these are added to the run so they get slugs like everything else."""
    index = NameIndex()
    live = [p for p in planned if p.draft.skip_reason is None]
    for item in live:
        draft = item.draft
        if draft.list_name != "packs":
            index.add(
                draft.list_name,
                draft.key,
                Target("", draft.name or draft.key, draft.bundle),
                draft.names,
            )
    plain: dict[str, PlannedItem] = {}
    for item in live:
        draft = item.draft
        if draft.list_name != "packs" or draft.pack_items is None:
            continue
        draft.pack_resolution = resolve_refs(parse_entries(draft.pack_items), index, mapping)
        for placed in draft.pack_resolution.placed:
            if placed.ref.kind == "item" and placed.ref.key not in plain:
                plain[placed.ref.key] = PlannedItem(_plain_draft(placed, draft))
    return index, list(plain.values())


def _plain_draft(placed: Placed, pack: ItemDraft) -> ItemDraft:
    """A simple plain item for a pack entry: its name, gear, the pack's citation, its weight."""
    draft = ItemDraft("gear", placed.ref.key, pack.file, pack.namespace)
    draft.name = placed.entry.name
    draft.names = [placed.entry.name]
    draft.parents = ["gear"]
    draft.made_for = pack.key
    if "sourcebook" in pack.stats:
        draft.stats["sourcebook"] = pack.stats["sourcebook"]
    if placed.entry.weight is not None:
        draft.stats["own_weight"] = placed.entry.weight
    return draft


def _render_packs(
    live: list[PlannedItem], index: NameIndex, slugs: dict[tuple[str, str], str]
) -> None:
    """Second step: with every slug known, write each pack's lines."""
    index.set_slugs(slugs)
    plain_slugs = {key: slug for (list_name, key), slug in slugs.items() if list_name == "gear"}
    for item in live:
        draft = item.draft
        if draft.pack_resolution is None:
            continue
        contents = build_contents(draft.pack_resolution, index, plain_slugs)
        draft.pack_lines = contents.lines
        draft.pack_unresolved = contents.unresolved
        draft.notes.extend(contents.notes)
        if contents.lines:
            draft.description = render(contents.lines)
            draft.description_part = "neutral"  # a pack's contents are its equipment's
