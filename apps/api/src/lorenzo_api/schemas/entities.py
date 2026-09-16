import uuid
from datetime import datetime

from fastapi import Request
from pydantic import BaseModel

from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, Information, StatValueType, VEffectiveStat
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.payloads import PayloadOut, payload_to_schema


class InformationCreate(BaseModel):
    """POST /tenants/{tenant_id}/entities/{entity_id}/information - see ADR
    0038/RFC 0011. One call creates the Information row plus exactly one
    PayloadDescription - mirroring RFC 0005's "one transaction, one
    coherent unit" precedent (instantiate creating Entity+ItemInstance+
    EntityPrototype together), not two separate calls that could leave an
    Information row with no Payload yet.

    Deliberately description-only for this slice - payload_number/picture/
    document creation is explicitly out of scope (RFC 0011's own flagged
    "binary payload upload mechanics... not resolved here"; a JSON body
    has nowhere to put raw bytes without base64 or multipart, neither
    decided). `type` is Information's own free-text narrative category
    (RFC 0001: "a rumor, an official record, a GM note, ..."), not the
    payload's kind - callers authoring more than one piece of information
    about the same entity must give each a distinct `type`, since
    Information carries UniqueConstraint(entity_id, type).
    """

    title: str
    type: str
    is_public: bool = False
    content: str
    locale: str = "en-US"


class EntityStatValueOut(BaseModel):
    """A resolved stat value, keyed by its definition's name - see ADR 0020.

    Reshaping, not a plain-column mapping, so built via a classmethod
    rather than from_attributes: which value_* column actually holds the
    value is chosen by reading StatDefinition.value_type first, not by
    probing all four columns for non-null (the DB's own CHECK constraint
    on entity_stat, and v_effective_stat's identical shape, already
    guarantees exactly one is ever set).
    """

    name: str
    value: int | str | float | bool

    @classmethod
    def from_effective_stat(cls, stat: VEffectiveStat) -> EntityStatValueOut:
        """Takes a v_effective_stat row (ADR 0039), not an EntityStat - this
        always reflects prototype-inherited values, not just an entity's own
        direct ones.
        """
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
                f"VEffectiveStat({stat.entity_id}, {stat.stat_definition_id}) is declared "
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
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            stats=[EntityStatValueOut.from_effective_stat(stat) for stat in entity.effective_stats],
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
