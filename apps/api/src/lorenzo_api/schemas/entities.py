import uuid
from datetime import datetime
from typing import Literal

from fastapi import Request
from pydantic import BaseModel

from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, Information
from lorenzo_api.schemas.common import EntitySummary, Slug
from lorenzo_api.schemas.payloads import PayloadOut, payload_to_schema
from lorenzo_api.stat_evaluation import evaluate


class EntitySlugUpdate(BaseModel):
    """PUT /tenants/{tenant_id}/entities/{entity_id}/slug - see ADR 0107."""

    slug: Slug


class EntitySlugOut(BaseModel):
    entity_id: uuid.UUID
    slug: str


EntityKind = Literal["item", "item_instance", "being", "character"]


class ResolvedSlugOut(BaseModel):
    """One entry of GET .../entities/resolve - see ADR 0107. `kinds` says
    what the entity is, so a client can honour a LorenzoScript view hint
    (`being/ashfang`) and choose where the link leads.
    """

    slug: str
    entity_id: uuid.UUID
    name: str
    kinds: list[EntityKind]


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


class InformationOut(BaseModel):
    """A titled, categorized piece of information about an entity, with its
    payloads already resolved to their concrete kind - see ADR 0020. A
    single Information row's payloads can be of heterogeneous kinds, so
    each is resolved independently via payload_to_schema rather than
    assuming one kind per row.
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

    @classmethod
    def from_information(cls, information: Information, request: Request) -> InformationOut:
        return cls(
            id=information.id,
            title=information.title,
            type=information.type,
            is_public=information.is_public,
            order=information.order,
            updated_at=information.updated_at,
            payloads=[payload_to_schema(payload, request) for payload in information.payloads],
        )


def _stats_out(entity: Entity) -> list[EntityStatValueOut]:
    """Every effective stat with a value, computed ones evaluated (ADR
    0104). A computed stat whose inputs don't resolve is left out, like an
    unset stat. Needs entity.stats (the entity's own rows) loaded too: an
    own row always wins at hop 0, and an entity never holds both a value
    and a formula for one stat (ADR 0104), so `own` is either of those."""
    values = evaluate(entity.effective_stats)
    stored = {stat.stat_definition_id for stat in entity.stats}
    return [
        EntityStatValueOut(
            name=stat.stat_definition.name,
            value=values[stat.stat_definition_id],
            own=stat.stat_definition_id in stored or stat.computed_entity_id == entity.id,
        )
        for stat in entity.effective_stats
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
    prototypes: list[EntitySummary]
    instances: list[EntitySummary]
    parent: EntitySummary | None
    quantity: int | None
    children: list[EntitySummary]

    @classmethod
    def from_entity(
        cls, entity: Entity, request: Request, *, visibility: InformationVisibility
    ) -> EntityDetailOut:
        return cls(
            id=entity.id,
            name=entity.name,
            slug=entity.slug.slug if entity.slug is not None else None,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            stats=_stats_out(entity),
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
            prototypes=[EntitySummary.from_entity(e) for e in entity.prototypes],
            instances=[EntitySummary.from_entity(e) for e in entity.instances],
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
                else None
            ),
            quantity=entity.containment.quantity if entity.containment is not None else None,
            # entity.contained_links (the Containment association-object
            # list), not entity.children (the bare Entity list) - only the
            # former carries each child's own quantity within this entity.
            children=[
                EntitySummary.from_entity(link.child, quantity=link.quantity)
                for link in entity.contained_links
            ],
        )
