from __future__ import annotations

import uuid
from typing import Self

from fastapi import Request
from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import Entity, VItem, VItemInstance
from lorenzo_api.schemas.common import EntitySummary

__all__ = [
    "DescriptionOut",
    "PictureRefOut",
    "StatValueOut",
    "TagValueOut",
    "ItemOut",
    "ItemInstanceOut",
    "OwnedGroupOut",
    "OwnedByResponse",
]


class DescriptionOut(BaseModel):
    """Wraps one entry of `ItemViewMixin.descriptions` - see ADR 0020: the
    raw `tuple[str, str]` is a fine internal shape but a weak external JSON
    contract (no field names), so it's wrapped into a small named schema.
    """

    model_config = ConfigDict(from_attributes=True)

    content: str
    locale: str


class PictureRefOut(BaseModel):
    """A picture reference - a `url` pointing at the existing payload-content
    endpoint, plus `file_type`. Deliberately *not* built from
    `ItemViewMixin.pictures` (which returns bare `(data, file_type)` tuples
    with no payload id to link through) - inlining raw picture bytes into a
    paginated list response (`GET /items` can return up to 100 items per
    page) would make list responses balloon for anything with real images,
    and would be inconsistent with how the Entities endpoint represents the
    exact same underlying data (`schemas/payloads.py`'s `PayloadPictureOut`,
    also a `url`). `_picture_refs` below re-walks the same
    entity.information -> payloads -> picture path `ItemViewMixin.pictures`
    does internally, keeping the `Payload` row (and its id) instead of
    discarding it.
    """

    url: str
    file_type: str


def _picture_refs(entity: Entity, request: Request) -> list[PictureRefOut]:
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
        if info.type == "description"
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
    """Wraps one entry of `ItemViewMixin.tags` (`list[tuple[str, bool | None]]`)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    value: bool | None


def _descriptions_out(pairs: list[tuple[str, str]]) -> list[DescriptionOut]:
    return [DescriptionOut(content=content, locale=locale) for content, locale in pairs]


def _stats_out(pairs: list[tuple[str, int | None]]) -> list[StatValueOut]:
    return [StatValueOut(name=name, value=value) for name, value in pairs]


def _tags_out(pairs: list[tuple[str, bool | None]]) -> list[TagValueOut]:
    return [TagValueOut(name=name, value=value) for name, value in pairs]


class ItemOut(BaseModel):
    """A base item type ("Shovel"), from `VItem` - see ADR 0019/0020.

    Constructing this requires the source `VItem` to already have its
    entity->information->payloads->description/picture and
    entity->stats->stat_definition->stat_group eager-loaded (see
    `routers.items.eager_load_options`, the exact recipe proven in
    `tests/test_v_item.py`) - the seven wrapped properties raise
    MissingGreenlet otherwise, they do not silently lazy-load.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    title: str | None
    weight: int | None
    height: int | None
    price: int | None
    rarity: int | None
    hp: int | None
    armor: int | None
    container_entity_id: uuid.UUID | None
    is_magical: bool | None
    is_cursed: bool | None
    descriptions: list[DescriptionOut]
    pictures: list[PictureRefOut]
    physical_stats: list[StatValueOut]
    economic_stats: list[StatValueOut]
    destroyable_stats: list[StatValueOut]
    damaging_stats: list[StatValueOut]
    tags: list[TagValueOut]

    @classmethod
    def from_v_item(cls, view: VItem, request: Request) -> Self:
        return cls(
            entity_id=view.entity_id,
            title=view.title,
            weight=view.weight,
            height=view.height,
            price=view.price,
            rarity=view.rarity,
            hp=view.hp,
            armor=view.armor,
            container_entity_id=view.container_entity_id,
            is_magical=view.is_magical,
            is_cursed=view.is_cursed,
            descriptions=_descriptions_out(view.descriptions),
            pictures=_picture_refs(view.entity, request),
            physical_stats=_stats_out(view.physical_stats),
            economic_stats=_stats_out(view.economic_stats),
            destroyable_stats=_stats_out(view.destroyable_stats),
            damaging_stats=_stats_out(view.damaging_stats),
            tags=_tags_out(view.tags),
        )


class ItemInstanceOut(BaseModel):
    """A specific, ownable item ("My Shovel"), from `VItemInstance` -
    identical to `ItemOut` plus `owner_entity_id`. See ADR 0019/0020 and
    `ItemOut`'s docstring for the eager-load requirement.
    """

    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    owner_entity_id: uuid.UUID | None
    title: str | None
    weight: int | None
    height: int | None
    price: int | None
    rarity: int | None
    hp: int | None
    armor: int | None
    container_entity_id: uuid.UUID | None
    is_magical: bool | None
    is_cursed: bool | None
    descriptions: list[DescriptionOut]
    pictures: list[PictureRefOut]
    physical_stats: list[StatValueOut]
    economic_stats: list[StatValueOut]
    destroyable_stats: list[StatValueOut]
    damaging_stats: list[StatValueOut]
    tags: list[TagValueOut]

    @classmethod
    def from_v_item_instance(cls, view: VItemInstance, request: Request) -> Self:
        return cls(
            entity_id=view.entity_id,
            owner_entity_id=view.owner_entity_id,
            title=view.title,
            weight=view.weight,
            height=view.height,
            price=view.price,
            rarity=view.rarity,
            hp=view.hp,
            armor=view.armor,
            container_entity_id=view.container_entity_id,
            is_magical=view.is_magical,
            is_cursed=view.is_cursed,
            descriptions=_descriptions_out(view.descriptions),
            pictures=_picture_refs(view.entity, request),
            physical_stats=_stats_out(view.physical_stats),
            economic_stats=_stats_out(view.economic_stats),
            destroyable_stats=_stats_out(view.destroyable_stats),
            damaging_stats=_stats_out(view.damaging_stats),
            tags=_tags_out(view.tags),
        )


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
