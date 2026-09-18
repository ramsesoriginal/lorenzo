from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Self

from fastapi import Request
from pydantic import BaseModel, ConfigDict, model_validator

from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, VItem, VItemInstance
from lorenzo_api.schemas.common import EntitySummary, ProblemOut

__all__ = [
    "DescriptionOut",
    "PictureRefOut",
    "StatValueOut",
    "TagValueOut",
    "ItemCreate",
    "ItemUpdate",
    "ItemOut",
    "ItemInstanceCreate",
    "ItemInstanceUpdate",
    "ItemInstanceOut",
    "OwnedGroupOut",
    "OwnedByResponse",
    "SetOwnerRequest",
    "SetContainerRequest",
    "SetPrototypesRequest",
    "SplitItemInstanceRequest",
    "MergeItemInstanceRequest",
    "ProblemOut",
    "BulkAssignItem",
    "BulkAssignResultItem",
    "BulkMoveItem",
    "BulkMoveContainerRequest",
    "BulkMoveResultItem",
    "PrototypeAncestorOut",
    "BulkReparentPrototypeRequest",
    "BulkReparentResultItem",
    "BulkAddPrototypeRequest",
    "BulkAddPrototypeResultItem",
    "BulkRemovePrototypeRequest",
    "BulkRemovePrototypeResultItem",
]


class DescriptionOut(BaseModel):
    """Wraps one entry of `EntityViewMixin.descriptions` - see ADR 0020: the
    raw `tuple[str, str]` is a fine internal shape but a weak external JSON
    contract (no field names), so it's wrapped into a small named schema.
    """

    model_config = ConfigDict(from_attributes=True)

    content: str
    locale: str


class PictureRefOut(BaseModel):
    """A picture reference - a `url` pointing at the existing payload-content
    endpoint, plus `file_type`. `_picture_refs` below walks
    entity.information -> payloads -> picture directly rather than through
    an `EntityViewMixin` property (there never was one - checked, `pictures`
    would have needed the owning `Payload` row's own id to link through,
    not just its bytes, so it was never a fit here). Inlining raw picture
    bytes into a paginated list response (`GET /items` can return up to
    100 items per page) would make list responses balloon for anything
    with real images, and would be inconsistent with how the Entities
    endpoint represents the exact same underlying data
    (`schemas/payloads.py`'s `PayloadPictureOut`, also a `url`).
    """

    url: str
    file_type: str


def _picture_refs(
    entity: Entity, request: Request, visibility: InformationVisibility
) -> list[PictureRefOut]:
    return [
        PictureRefOut(
            url=str(
                request.url_for(
                    "payload_content", tenant_id=payload.tenant_id, payload_id=payload.id
                )
            ),
            file_type=payload.picture.file_type,
        )
        for info in entity.information
        if info.type == "description" and visibility.can_see(info)
        for payload in info.payloads
        if payload.picture is not None
    ]


class StatValueOut(BaseModel):
    """Wraps one entry of physical_stats/economic_stats/destroyable_stats/
    damaging_stats (each `list[tuple[str, int | None]]`)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    value: int | None


class TagValueOut(BaseModel):
    """Wraps one entry of `EntityViewMixin.tags` (`list[tuple[str, bool | None]]`)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    value: bool | None


def _descriptions_out(pairs: list[tuple[str, str]]) -> list[DescriptionOut]:
    return [DescriptionOut(content=content, locale=locale) for content, locale in pairs]


def _stats_out(pairs: list[tuple[str, int | None]]) -> list[StatValueOut]:
    return [StatValueOut(name=name, value=value) for name, value in pairs]


def _tags_out(pairs: list[tuple[str, bool | None]]) -> list[TagValueOut]:
    return [TagValueOut(name=name, value=value) for name, value in pairs]


def _title_out(title: str | None, *, name: str) -> str:
    """`title` (`VItem`/`VItemInstance`'s own description-payload-sourced
    display field, ADR 0019 - `None` whenever there's no "description"
    Information row at all) falls back to the entity's own always-set
    `name` when empty, so a client always has *something* to display -
    see ADR 0067. `or`, not `if title is not None`, so an authored but
    literally empty-string title (`Information.title` is `NOT NULL`, not
    non-empty) falls back too, the same "empty counts as unset" reading
    `bool(...)` already gives everywhere else in this schema module.
    """
    return title or name


def _is_container_out(tags: list[tuple[str, bool | None]], *, has_children: bool) -> bool | None:
    """`is_container` as a first-class field, mirroring whatever `tags`
    already carries for that name - see ADR 0066. Not a new stat_definition
    lookup of its own and not a new `v_item`/`v_item_instance` SQL column
    like `is_magical`/`is_cursed`'s hardcoded whitelist (ADR 0037/0039) -
    purely a convenience read of the same already-resolved `tags` list
    `_tags_out` above wraps unchanged, so a client reading the generic
    `tags` array still sees the identical entry.

    An explicit tag value (`True` or `False`) always wins - authorial
    intent over structural inference. Only when no `is_container` entry is
    present at all (the tenant never defined that stat_definition in the
    `tags` stat group, or never set a value for this entity/instance) does
    `has_children` (ADR 0066 - whether `Containment` currently has any row
    naming this entity as `parent_entity_id`, i.e. something is actually
    contained in it right now) get a say: `True` if so, otherwise still
    `None` - a container that's merely empty right now is indistinguishable
    from "we don't know" under this heuristic, so it stays unset rather
    than being inferred `False`.
    """
    for name, value in tags:
        if name == "is_container":
            return value
    return True if has_children else None


class ItemCreate(BaseModel):
    """POST /items - see ADR 0032/RFC 0005. Creates Entity + Item + one
    EntityPrototype row per id in prototype_ids, one transaction.
    """

    name: str
    prototype_ids: list[uuid.UUID] = []


class ItemUpdate(BaseModel):
    """PATCH /items/{id} - only Entity.name is mutable through this
    endpoint; nothing else on a bare Item row exists to update.
    """

    name: str | None = None


def _prototype_ids_out(entity: Entity) -> list[uuid.UUID]:
    """entity.prototype_links (ADR 0015) - this entity's own direct
    prototypes, as bare ids. Sorted for a deterministic response; the
    underlying edges are an unordered set (entity_prototype carries no
    ordering column of its own).
    """
    return sorted((link.prototype_id for link in entity.prototype_links), key=str)


def _common_item_fields(
    view: VItem | VItemInstance, request: Request, *, visibility: InformationVisibility
) -> dict[str, Any]:
    """Every field ItemOut and ItemInstanceOut share - both views expose the
    identical EntityViewMixin-backed surface (ADR 0019), differing only in
    ItemInstanceOut's own extra owner_entity_id/slug. Extracted so the two
    schemas' constructors can't drift apart the way they used to (every
    field added here historically meant editing both from_v_item and
    from_v_item_instance by hand, in lockstep).
    """
    return dict(
        entity_id=view.entity_id,
        title=_title_out(view.title, name=view.entity.name),
        weight=view.weight,
        height=view.height,
        price=view.price,
        rarity=view.rarity,
        hp=view.hp,
        armor=view.armor,
        container_entity_id=view.container_entity_id,
        quantity=view.quantity,
        prototype_ids=_prototype_ids_out(view.entity),
        is_magical=view.is_magical,
        is_cursed=view.is_cursed,
        is_container=_is_container_out(view.tags, has_children=bool(view.entity.contained_links)),
        descriptions=_descriptions_out(view.descriptions(visibility)),
        pictures=_picture_refs(view.entity, request, visibility),
        physical_stats=_stats_out(view.physical_stats),
        economic_stats=_stats_out(view.economic_stats),
        destroyable_stats=_stats_out(view.destroyable_stats),
        damaging_stats=_stats_out(view.damaging_stats),
        tags=_tags_out(view.tags),
        created_by=view.entity.created_by,
        updated_by=view.entity.updated_by,
        updated_at=view.entity.updated_at,
    )


class ItemOut(BaseModel):
    """A base item type ("Shovel"), from `VItem` - see ADR 0019/0020.
    `title` is always populated - `VItem.title` itself is still nullable
    (no "description" Information row authored at all), but `_title_out`
    (ADR 0067) falls back to the entity's own `name` whenever it's empty,
    so a client always has something to display without checking for
    `None` first.

    Constructing this requires the source `VItem` to already have its
    entity->information->payloads->description/picture,
    entity->information->knowledge_links (ADR 0028 - `descriptions` is
    visibility-gated, not a bare property anymore),
    entity->stats->stat_definition->stat_group, entity->contained_links
    (ADR 0066 - `_is_container_out`'s own structural fallback), and
    entity->prototype_links (ADR 0072 - `prototype_ids`) eager-loaded (see
    `routers.items.eager_load_options`, the exact recipe proven in
    `tests/test_v_item.py`) - the six wrapped properties/methods (plus
    `contained_links`/`prototype_links` themselves) raise MissingGreenlet
    otherwise, they do not silently lazy-load.

    `ItemInstanceOut` below extends this directly - identical fields plus
    `owner_entity_id`/`slug` - rather than repeating the field list a
    second time.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    title: str
    weight: int | None
    height: int | None
    price: int | None
    rarity: int | None
    hp: int | None
    armor: int | None
    container_entity_id: uuid.UUID | None
    quantity: int | None
    prototype_ids: list[uuid.UUID]
    is_magical: bool | None
    is_cursed: bool | None
    is_container: bool | None
    descriptions: list[DescriptionOut]
    pictures: list[PictureRefOut]
    physical_stats: list[StatValueOut]
    economic_stats: list[StatValueOut]
    destroyable_stats: list[StatValueOut]
    damaging_stats: list[StatValueOut]
    tags: list[TagValueOut]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    updated_at: datetime

    @classmethod
    def from_v_item(
        cls, view: VItem, request: Request, *, visibility: InformationVisibility
    ) -> Self:
        return cls(**_common_item_fields(view, request, visibility=visibility))


class ItemInstanceCreate(BaseModel):
    """POST /item-instances ("instantiate") - see ADR 0032/RFC 0005.
    prototype_id must resolve to an entity with a matching Item row.
    One transaction creates Entity (name defaults to the prototype's own
    name if omitted) + ItemInstance + EntityPrototype, plus an Ownership
    row if owner_character_id is given and/or a Containment row if
    container_entity_id is given. slug (ADR 0043) is optional, unique per
    tenant when set, and resolvable later via GET .../by-slug/{slug}.
    """

    name: str | None = None
    prototype_id: uuid.UUID
    owner_character_id: uuid.UUID | None = None
    container_entity_id: uuid.UUID | None = None
    slug: str | None = None


class ItemInstanceUpdate(BaseModel):
    """PATCH /item-instances/{id} - owner/container are handled by the
    dedicated sub-resource actions below, not folded into this general
    PATCH body, so a client can't accidentally no-op an owner change by
    omitting the field from a partial update.
    """

    name: str | None = None


class SetOwnerRequest(BaseModel):
    """PUT /item-instances/{id}/owner body."""

    owner_character_id: uuid.UUID


class SetContainerRequest(BaseModel):
    """PUT /item-instances/{id}/container body."""

    container_entity_id: uuid.UUID


class SetPrototypesRequest(BaseModel):
    """PUT /items/{id}/prototypes body - see ADR 0072. Full replacement,
    same shape as ItemCreate.prototype_ids - the given list becomes the
    item's complete new set of direct prototypes.
    """

    prototype_ids: list[uuid.UUID] = []


class SplitItemInstanceRequest(BaseModel):
    """POST /item-instances/{id}/split body - see ADR 0041/0044. `quantity`
    is how many units to split *off* into a new sibling instance; the
    source must currently hold strictly more than this (splitting off "all
    of it" is a container/owner reassignment of the whole stack, not a
    split). `owner_character_id` (ADR 0044) is optional - when given, the
    new split-off instance is created with that owner instead of copying
    the source's current owner (the behavior when omitted, unchanged from
    ADR 0041).
    """

    quantity: int
    owner_character_id: uuid.UUID | None = None


class MergeItemInstanceRequest(BaseModel):
    """POST /item-instances/{id}/merge body - see ADR 0044. into_entity_id
    is the surviving stack; the path's own entity_id is fully consumed
    into it and then deleted.
    """

    into_entity_id: uuid.UUID


class BulkAssignItem(BaseModel):
    """POST /item-instances/bulk-assign - one input entry. See ADR 0044:
    quantity given delegates to split-with-owner (creating a new instance);
    omitted delegates to the plain owner-PUT path (reassigning entity_id
    itself). if_match is optional, exactly like every other write in this
    router - honored per item, a stale claim becomes that item's own
    "error" entry rather than failing the whole batch.
    """

    entity_id: uuid.UUID
    owner_character_id: uuid.UUID
    quantity: int | None = None
    if_match: str | None = None


class ItemInstanceOut(ItemOut):
    """A specific, ownable item ("My Shovel"), from `VItemInstance` -
    identical to `ItemOut` plus `owner_entity_id`/`slug`. See ADR 0019/0020
    and `ItemOut`'s docstring for the eager-load requirement.
    """

    owner_entity_id: uuid.UUID | None
    slug: str | None

    @classmethod
    def from_v_item_instance(
        cls, view: VItemInstance, request: Request, *, visibility: InformationVisibility
    ) -> Self:
        return cls(
            **_common_item_fields(view, request, visibility=visibility),
            owner_entity_id=view.owner_entity_id,
            slug=view.slug,
        )


class BulkAssignResultItem(BaseModel):
    """POST /item-instances/bulk-assign - one output entry, always present
    for every input entry regardless of outcome (ADR 0044: never
    all-or-nothing). Exactly one of item_instance/problem is set, matching
    status.
    """

    entity_id: uuid.UUID
    status: Literal["ok", "error"]
    item_instance: ItemInstanceOut | None = None
    problem: ProblemOut | None = None


class BulkMoveItem(BaseModel):
    """POST /item-instances/bulk-move - one entry of the `items` mode. See
    ADR 0065. `if_match` is optional, exactly like `BulkAssignItem`'s
    identical field - honored per item, a stale claim becomes that item's
    own "error" entry rather than failing the whole batch.
    """

    entity_id: uuid.UUID
    if_match: str | None = None


class BulkMoveContainerRequest(BaseModel):
    """POST /item-instances/bulk-move body - see ADR 0065. Exactly one of
    `from_container_entity_id` ("move everything directly inside this
    container") or `items` ("move exactly this list") must be given -
    a request-shape invariant, not a domain rule with a row to `CHECK`,
    so it's validated here rather than via a typed `Problem`.
    """

    to_container_entity_id: uuid.UUID
    from_container_entity_id: uuid.UUID | None = None
    items: list[BulkMoveItem] | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> Self:
        if (self.from_container_entity_id is None) == (self.items is None):
            raise ValueError("Exactly one of from_container_entity_id/items must be given")
        return self


class BulkMoveResultItem(BaseModel):
    """POST /item-instances/bulk-move - one output entry, always present
    for every resolved item regardless of outcome (ADR 0065: never
    all-or-nothing). Exactly one of item_instance/problem is set, matching
    status - the identical shape `BulkAssignResultItem` already
    established.
    """

    entity_id: uuid.UUID
    status: Literal["ok", "error"]
    item_instance: ItemInstanceOut | None = None
    problem: ProblemOut | None = None


class PrototypeAncestorOut(BaseModel):
    """GET /items/{id}/prototypes/ancestry - one entry. See ADR 0073.
    `prototype_ids` is this ancestor's own *direct* prototypes (always a
    subset of the full returned ancestor set) - a flat list of nodes with
    their own edges, not a pre-built tree, since multiple inheritance means
    the real shape can be a DAG rather than a clean chain; the client
    renders whatever structure actually exists from these edges rather than
    this endpoint forcing a linear breadcrumb that would lie about
    branching cases.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    name: str
    prototype_ids: list[uuid.UUID]


class BulkReparentPrototypeRequest(BaseModel):
    """POST /items/bulk-reparent-prototype body - see ADR 0073. For every
    affected item currently having from_prototype_id as a direct prototype,
    replaces that edge with to_prototype_id. item_ids omitted means "every
    item with from_prototype_id as a direct prototype"; given explicitly, an
    item that doesn't currently have from_prototype_id is a tolerated no-op,
    not an error.
    """

    from_prototype_id: uuid.UUID
    to_prototype_id: uuid.UUID
    item_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def _from_and_to_differ(self) -> Self:
        if self.from_prototype_id == self.to_prototype_id:
            raise ValueError("from_prototype_id and to_prototype_id must differ")
        return self


class BulkReparentResultItem(BaseModel):
    """POST /items/bulk-reparent-prototype - one output entry, always
    present for every resolved item regardless of outcome (ADR 0073: never
    all-or-nothing). Exactly one of item/problem is set, matching status -
    the same shape BulkMoveResultItem/BulkAssignResultItem already
    established, just wrapping ItemOut instead of ItemInstanceOut.
    """

    entity_id: uuid.UUID
    status: Literal["ok", "error"]
    item: ItemOut | None = None
    problem: ProblemOut | None = None


class BulkAddPrototypeRequest(BaseModel):
    """POST /items/bulk-add-prototype body - see ADR 0073. Adds
    prototype_id to every listed item's direct prototype set; an item that
    already has it is a tolerated no-op.
    """

    prototype_id: uuid.UUID
    item_ids: list[uuid.UUID]


class BulkAddPrototypeResultItem(BaseModel):
    """POST /items/bulk-add-prototype - one output entry per item. See
    BulkReparentResultItem's own docstring for the shared shape/reasoning.
    """

    entity_id: uuid.UUID
    status: Literal["ok", "error"]
    item: ItemOut | None = None
    problem: ProblemOut | None = None


class BulkRemovePrototypeRequest(BaseModel):
    """POST /items/bulk-remove-prototype body - see ADR 0073. Removes
    prototype_id from every listed item's direct prototype set; an item
    that doesn't have it is a tolerated no-op.
    """

    prototype_id: uuid.UUID
    item_ids: list[uuid.UUID]


class BulkRemovePrototypeResultItem(BaseModel):
    """POST /items/bulk-remove-prototype - one output entry per item. See
    BulkReparentResultItem's own docstring for the shared shape/reasoning.
    """

    entity_id: uuid.UUID
    status: Literal["ok", "error"]
    item: ItemOut | None = None
    problem: ProblemOut | None = None


class OwnedGroupOut(BaseModel):
    """One container-group within the owned-by response - ADR 0020's "by
    owner, grouped" shape. `container` is the lightweight `EntitySummary`
    (not an `ItemOut`) since `containment.parent_entity_id` isn't
    restricted to item-tagged entities - the container itself might not be
    an item/item_instance at all (e.g. a room, a character).
    """

    container: EntitySummary | None
    item_instances: list[ItemInstanceOut]


class OwnedByResponse(BaseModel):
    """GET .../item-instances/owned-by/{owner_entity_id} - deliberately not
    paginated (ADR 0020 / task brief): bounded by one owner's inventory.
    """

    groups: list[OwnedGroupOut]
