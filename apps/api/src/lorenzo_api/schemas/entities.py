import uuid
from datetime import datetime

from fastapi import Request
from pydantic import BaseModel

from lorenzo_api.models import Entity, EntityStat, Information, StatValueType
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.payloads import PayloadOut, payload_to_schema


class StatValueOut(BaseModel):
    """A resolved stat value, keyed by its definition's name - see ADR 0020.

    Reshaping, not a plain-column mapping, so built via a classmethod
    rather than from_attributes: which value_* column actually holds the
    value is chosen by reading StatDefinition.value_type first, not by
    probing all four columns for non-null (the DB's own CHECK constraint
    on entity_stat already guarantees exactly one is ever set).
    """

    name: str
    value: int | str | float | bool

    @classmethod
    def from_entity_stat(cls, stat: EntityStat) -> StatValueOut:
        definition = stat.stat_definition
        value: int | str | float | bool | None
        if definition.value_type is StatValueType.INT:
            value = stat.value_int
        elif definition.value_type is StatValueType.TEXT:
            value = stat.value_text
        elif definition.value_type is StatValueType.FLOAT:
            value = stat.value_float
        elif definition.value_type is StatValueType.BOOL:
            value = stat.value_bool
        else:
            raise ValueError(f"Unhandled StatValueType: {definition.value_type!r}")
        if value is None:
            raise ValueError(
                f"EntityStat({stat.entity_id}, {stat.stat_definition_id}) is declared "
                f"{definition.value_type.value} but its value column is null"
            )
        return cls(name=definition.name, value=value)


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
    payloads: list[PayloadOut]

    @classmethod
    def from_information(cls, information: Information, request: Request) -> InformationOut:
        return cls(
            id=information.id,
            title=information.title,
            type=information.type,
            payloads=[payload_to_schema(payload, request) for payload in information.payloads],
        )


class EntityDetailOut(BaseModel):
    """The full shape of a single entity - every relationship resolved and
    inlined. See ADR 0020. Deliberately not reused for the list endpoint,
    which returns EntitySummary instead to avoid an N+1-heavy response
    when listing many entities.
    """

    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime
    stats: list[StatValueOut]
    stat_groups: list[EntitySummary]
    information: list[InformationOut]
    prototypes: list[EntitySummary]
    instances: list[EntitySummary]
    parent: EntitySummary | None
    children: list[EntitySummary]

    @classmethod
    def from_entity(
        cls, entity: Entity, request: Request, *, visible_information_ids: set[uuid.UUID]
    ) -> EntityDetailOut:
        return cls(
            id=entity.id,
            name=entity.name,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            stats=[StatValueOut.from_entity_stat(stat) for stat in entity.stats],
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
                if info.id in visible_information_ids
            ],
            prototypes=[EntitySummary.from_entity(e) for e in entity.prototypes],
            instances=[EntitySummary.from_entity(e) for e in entity.instances],
            parent=EntitySummary.from_entity(entity.parent) if entity.parent is not None else None,
            children=[EntitySummary.from_entity(e) for e in entity.children],
        )
