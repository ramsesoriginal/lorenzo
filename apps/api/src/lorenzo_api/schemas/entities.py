import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import Request
from pydantic import BaseModel, Field, model_validator

from lorenzo_api.information_visibility import InformationReader
from lorenzo_api.models import Entity, Information, VEffectiveStat
from lorenzo_api.schemas.common import EntitySummary, Slug
from lorenzo_api.schemas.payloads import PayloadOut, payload_to_schema
from lorenzo_api.stat_evaluation import evaluate


class FactUpdate(BaseModel):
    """The name of a canonical fact; information and audiences have their own writes."""

    name: str = Field(min_length=1)


class EntryKnowerOut(BaseModel):
    """An explicit outer recipient, without inventing a grant date."""

    kind: Literal["entity", "player"]
    knower_entity_id: uuid.UUID | None = None
    player_id: uuid.UUID | None = None
    name: str | None


class EntitySlugUpdate(BaseModel):
    """PUT /tenants/{tenant_id}/entities/{entity_id}/slug - see ADR 0107."""

    slug: Slug


class EntitySlugOut(BaseModel):
    entity_id: uuid.UUID
    slug: str


EntityKind = Literal[
    "item",
    "item_instance",
    "being",
    "character",
    "fact",
    "calendar",
    "clock",
    "location",
    "map",
    "connection",
    "calendar_period",
    "event",
    "observance",
    "book",
    "edition",
    "chapter",
    "scene_telling",
    "scene",
    "scene_appearance",
    "session",
]


class ResolvedSlugOut(BaseModel):
    """One entry of GET .../entities/resolve - see ADR 0107. `kinds` says
    what the entity is, so a client can honour a LorenzoScript view hint
    (`being/ashfang`) and choose where the link leads.
    """

    slug: str
    entity_id: uuid.UUID
    name: str
    kinds: list[EntityKind]


class EntityCreate(BaseModel):
    """POST /tenants/{tenant_id}/entities - see ADR 0217. The entry, its link name, its kinds
    and its parents, in one transaction. `kinds` is `item` and/or `being`; empty makes a bare
    entry, which is what a group is. `in_public_catalog` is only for an `item`.
    """

    id: uuid.UUID | None = None
    name: str
    slug: Slug | None = None
    kinds: list[Literal["item", "being", "fact", "event"]] = []
    parents: list[uuid.UUID] = []
    in_public_catalog: bool | None = None
    visibility: Literal["restricted", "participants", "library"] | None = None

    @model_validator(mode="after")
    def _catalog_needs_item(self) -> EntityCreate:
        if self.in_public_catalog is not None and "item" not in self.kinds:
            raise ValueError("in_public_catalog is only for an entry of the kind item")
        if self.visibility is not None:
            if set(self.kinds) not in ({"event"}, {"fact"}):
                raise ValueError("Creation visibility is for Events and Facts")
            if self.visibility == "participants" and self.kinds != ["event"]:
                raise ValueError("Facts have no participants")
        return self


class EntityKindPut(BaseModel):
    """PUT /tenants/{tenant_id}/entities/{entity_id}/kinds/{kind} - the kind's own columns. Only
    `item` has one, `in_public_catalog`, and `map` its `system` (ADR 0336, required for a Map); the
    body may be left out for the others."""

    in_public_catalog: bool | None = None
    system: dict[str, Any] | None = None


class EntityParentsRequest(BaseModel):
    """PUT /tenants/{tenant_id}/entities/{entity_id}/parents - see ADR 0216. The complete new set
    of the entry's direct parents; empty clears it. Same shape as SetPrototypesRequest, which
    names the same thing as the item route does."""

    parent_ids: list[uuid.UUID] = []


class InformationOrderRequest(BaseModel):
    """PUT /tenants/{tenant_id}/entities/{entity_id}/information/order - see ADR 0237. Every
    piece of information the caller can see on the entry, each once, in the order it should
    have. Information the caller cannot see keeps its own position."""

    information_ids: list[uuid.UUID]


class EntityListOut(EntitySummary):
    """One row of GET .../entities - an EntitySummary and what the entry is (ADR 0215):
    `kinds`, in the order of `EntityKind`, empty for a bare entry (a group, or a category node).
    `parent_ids` (ADR 0229) are the entry's direct parents, in their order (ADR 0266), so a client
    can draw the whole tree from the list without reading every entry.
    """

    kinds: list[EntityKind]
    parent_ids: list[uuid.UUID]


class BacklinkOut(BaseModel):
    """One entry of GET .../entities/{id}/backlinks - see ADR 0110: a piece
    of information, visible to the caller, whose description links to the
    entity or shows its picture. `entity_id`, `name` and `kinds` are the
    entity that information is about, so a client can link to it.
    """

    entity_id: uuid.UUID
    name: str
    kinds: list[EntityKind]
    information_id: uuid.UUID
    title: str
    type: str


class InformationCreate(BaseModel):
    """POST /tenants/{tenant_id}/entities/{entity_id}/information - see ADR
    0038/RFC 0011. One call creates the Information row plus exactly one
    PayloadDescription - mirroring RFC 0005's "one transaction, one
    coherent unit" precedent (instantiate creating Entity+ItemInstance+
    EntityPrototype together), not two separate calls that could leave an
    Information row with no Payload yet.

    Deliberately description-only - payload_number/picture/document
    creation is still out of scope (RFC 0015 sub-slice 4's binary upload
    question). `type` is Information's own free-text narrative category
    (RFC 0001: "a rumor, an official record, a GM note, ..."), not the
    payload's kind. Only singleton types (information_type.is_singleton:
    `description`, `main_picture`) are one per entity; every other type can
    repeat (ADR 0101). `order` is the row's position among the entity's
    information; omitted, the server appends it after the last one.
    """

    id: uuid.UUID | None = None
    title: str
    type: str
    is_public: bool = False
    content: str
    locale: str = "en-US"
    order: int | None = None


class InformationUpdate(BaseModel):
    """PATCH /tenants/{tenant_id}/information/{information_id} - see ADR
    0101. Merge-patch semantics (`exclude_unset`), like every other PATCH
    in this API: an omitted field is left alone. Payload text is edited on
    the payload itself (PATCH .../payloads/{id}), not here.
    """

    title: str | None = None
    type: str | None = None
    is_public: bool | None = None
    order: int | None = None


class EntityStatValueOut(BaseModel):
    """A resolved stat value, keyed by its definition's name - see ADR 0020.
    Always the *effective* value (ADR 0039), prototype-inherited or
    computed (ADR 0104) - built by _stats_out below from
    stat_evaluation.evaluate, which picks the value_* column matching
    StatDefinition.value_type for a stored winner and evaluates a formula
    for a computed one.
    """

    name: str
    value: int | str | float | bool
    # ADR 0111: the entity holds the winning value itself, stored or
    # computed; false when it's inherited.
    own: bool
    # ADR 0276: where the winning row is held, when it is not this entity: the
    # prototype the value (or its formula) comes from. Null when `own`.
    from_entity: EntitySummary | None = None
    # ADR 0276: a formula produced the value, held by this entity or inherited.
    computed: bool = False


class InformationOut(BaseModel):
    """A titled, categorized piece of information about an entity, with its
    payloads already resolved to their concrete kind - see ADR 0020. A
    single Information row's payloads can be of heterogeneous kinds, so
    each is resolved independently via payload_to_schema rather than
    assuming one kind per row. Needs `author` loaded (ADR 0277).
    """

    id: uuid.UUID
    title: str
    type: str
    is_public: bool
    order: int
    # ETag/If-Match source for PATCH/DELETE .../information/{id} (ADR
    # 0042/0101). Each payload carries its own, separately.
    updated_at: datetime
    payloads: list[PayloadOut]
    # ADR 0277: who wrote it, shown wherever the row is. Null for a row written
    # before attribution existed or by an account since deleted; the name is
    # the author's display name, else their nickname, else null.
    created_by: uuid.UUID | None = None
    created_by_name: str | None = None

    @classmethod
    def from_information(cls, information: Information, request: Request) -> InformationOut:
        author = information.author
        return cls(
            id=information.id,
            title=information.title,
            type=information.type,
            is_public=information.is_public,
            order=information.order,
            updated_at=information.updated_at,
            payloads=[payload_to_schema(payload, request) for payload in information.payloads],
            created_by=information.created_by,
            created_by_name=(author.display_name or author.nickname) if author else None,
        )


def stat_display_key(stat: VEffectiveStat) -> tuple[int, str, int, str]:
    """Where a stat comes in an entity's list (ADR 0278): its group's
    position and name, then its own position and name. Needs the stat's
    definition and its group loaded."""
    definition = stat.stat_definition
    return (
        definition.stat_group.position,
        definition.stat_group.name,
        definition.position,
        definition.name,
    )


def _stats_out(entity: Entity, visibility: InformationReader) -> list[EntityStatValueOut]:
    """Every effective stat with a value, computed ones evaluated (ADR
    0104). A computed stat whose inputs don't resolve is left out, like an
    unset stat. Needs each stat's `source_entity` loaded: the view names the
    holder of every winner (ADR 0276), so `own` is "the holder is this entity"
    and an inherited value says which prototype it comes from. A contents
    formula needs stat_contents.attach_contents first (ADR 0127)."""
    values = evaluate(entity.effective_stats, entity_id=entity.id, contents=entity.stat_contents)
    return [
        EntityStatValueOut(
            name=stat.stat_definition.name,
            value=values[stat.stat_definition_id],
            own=stat.source_entity_id == entity.id,
            from_entity=(
                None
                if stat.source_entity_id == entity.id
                or not visibility.can_see_entry(stat.source_entity_id)
                else EntitySummary.from_entity(stat.source_entity)
            ),
            computed=stat.computed_entity_id is not None,
        )
        for stat in sorted(entity.effective_stats, key=stat_display_key)
        if stat.stat_definition_id in values
    ]


class KnowerOut(BaseModel):
    """One knower of an Information row - see ADR 0109. `kind` says which
    id is set: `entity` (a character or group, knower_entity_id) or
    `player` (player_id). `name` is the entity's name, or the player's
    user display name falling back to their nickname; either can be null.
    A later per-knower `confidence` (RFC 0029) would be one more field
    here.
    """

    kind: Literal["entity", "player"]
    knower_entity_id: uuid.UUID | None = None
    player_id: uuid.UUID | None = None
    name: str | None
    granted_at: datetime


def _kinds_out(entity: Entity) -> list[EntityKind]:
    """Needs entity.item, item_instance and being loaded, and being.character."""
    kinds: list[EntityKind] = []
    if entity.__dict__.get("clock") is not None:
        kinds.append("clock")
    if entity.__dict__.get("book") is not None:
        kinds.append("book")
    if entity.__dict__.get("edition") is not None:
        kinds.append("edition")
    if entity.__dict__.get("scene_telling") is not None:
        kinds.append("scene_telling")
    if entity.__dict__.get("chapter") is not None:
        kinds.append("chapter")
    if entity.__dict__.get("scene") is not None:
        kinds.append("scene")
    if entity.__dict__.get("scene_appearance") is not None:
        kinds.append("scene_appearance")
    if entity.__dict__.get("story_session") is not None:
        kinds.append("session")
    if entity.calendar_observance is not None:
        kinds.append("observance")
    if entity.calendar_period is not None:
        kinds.append("calendar_period")
    if entity.story_event is not None:
        kinds.append("event")
    if entity.calendar is not None:
        kinds.append("calendar")
    if entity.fact is not None:
        kinds.append("fact")
    if entity.item is not None:
        kinds.append("item")
    if entity.item_instance is not None:
        kinds.append("item_instance")
    if entity.being is not None:
        kinds.append("being")
        if entity.being.character is not None:
            kinds.append("character")
    if entity.__dict__.get("location") is not None:
        kinds.append("location")
    if entity.__dict__.get("map") is not None:
        kinds.append("map")
    if entity.__dict__.get("connection") is not None:
        kinds.append("connection")
    return kinds


class EntityDetailOut(BaseModel):
    """The full shape of a single entity - every relationship resolved and
    inlined. See ADR 0020. Deliberately not reused for the list endpoint,
    which returns EntitySummary instead to avoid an N+1-heavy response
    when listing many entities.
    """

    id: uuid.UUID
    name: str
    # ADR 0107: how LorenzoScript text links to this entity, if it can.
    slug: str | None
    created_at: datetime
    updated_at: datetime
    stats: list[EntityStatValueOut]
    stat_groups: list[EntitySummary]
    information: list[InformationOut]
    # What the entry is (ADR 0217): the marker rows it has, in the order of EntityKind.
    kinds: list[EntityKind]
    prototypes: list[EntitySummary]
    instances: list[EntitySummary]
    parent: EntitySummary | None
    quantity: int | None
    children: list[EntitySummary]

    @classmethod
    def from_entity(
        cls, entity: Entity, request: Request, *, visibility: InformationReader
    ) -> EntityDetailOut:
        return cls(
            id=entity.id,
            name=entity.name,
            slug=entity.slug.slug if entity.slug is not None else None,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            kinds=_kinds_out(entity),
            stats=_stats_out(entity, visibility),
            # entity.stat_groups is list[StatGroup], not list[Entity] - built
            # directly rather than through EntitySummary.from_entity (which
            # is typed for Entity specifically), reusing EntitySummary only
            # for its identical {id, name} shape.
            stat_groups=[
                EntitySummary(id=group.id, name=group.name) for group in entity.stat_groups
            ],
            # Filtered by the caller's resolved information_visibility
            # (ADR 0028's addendum) - required, no default, so a caller
            # that forgets to pass it fails loudly rather than silently
            # defaulting toward showing everything.
            information=[
                InformationOut.from_information(info, request)
                for info in entity.information
                if visibility.can_see(info)
            ],
            # quantity stays unset (None) for prototypes/instances/
            # stat_groups below - those aren't containment edges at all, so
            # "how many" doesn't apply; defaulting it to 1 there would
            # assert a fact about a relationship that has no such concept,
            # not correctly describe one that happens to be singular.
            prototypes=[
                EntitySummary.from_entity(e)
                for e in entity.prototypes
                if visibility.can_see_entry(e.id)
            ],
            instances=[
                EntitySummary.from_entity(e)
                for e in entity.instances
                if visibility.can_see_entry(e.id)
            ],
            # ADR 0041: entity.containment (the scalar Containment row for
            # this entity's own edge), not entity.parent - only the former
            # carries quantity alongside the parent entity. parent/quantity
            # are always both None or both set together (no containment
            # row at all vs. exactly one). parent.quantity mirrors the
            # top-level quantity field below - both describe the identical
            # edge ("how many of this entity sit in that parent"), just
            # attached to the parent reference too, for the same reason
            # each children[] entry already carries its own quantity rather
            # than leaving it to the reader to cross-reference by id.
            parent=(
                EntitySummary.from_entity(
                    entity.containment.parent, quantity=entity.containment.quantity
                )
                if entity.containment is not None
                and visibility.can_see_entry(entity.containment.parent_entity_id)
                else None
            ),
            quantity=entity.containment.quantity
            if entity.containment is not None
            and visibility.can_see_entry(entity.containment.parent_entity_id)
            else None,
            # entity.contained_links (the Containment association-object
            # list), not entity.children (the bare Entity list) - only the
            # former carries each child's own quantity within this entity.
            children=[
                EntitySummary.from_entity(link.child, quantity=link.quantity)
                for link in entity.contained_links
                if visibility.can_see_entry(link.child_entity_id)
            ],
        )


class PreviousOwnStat(BaseModel):
    """What an entry's own direct value for a stat was before a write (ADR 0225, RFC 0039 W1).
    `had_own_value` false means the entry had none and inherited, so `value` is null and
    undoing the write is clearing the value; true means `value` is what to put back."""

    had_own_value: bool
    value: int | str | float | bool | None = None


class EntityStatWriteOut(EntityDetailOut):
    """The entry as the routes that write one of its stats return it, plus `previous`: what the
    write replaced. Everything an `EntityDetailOut` has, so a caller of these routes before
    `previous` existed is unaffected (ADR 0225)."""

    previous: PreviousOwnStat
