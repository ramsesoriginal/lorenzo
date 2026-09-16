import uuid

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import Entity


class EntitySummary(BaseModel):
    """A lightweight entity reference - used anywhere an entity is pointed
    at generically (a container, a prototype, an owner) rather than fully
    described. See ADR 0020.

    `quantity` (ADR 0041) is only ever populated where this reference
    describes one side of an actual `Containment` edge - `EntityDetailOut.
    children` entries ("how many of *this* child are in the entity being
    described") and `EntityDetailOut.parent` ("how many of the described
    entity sit in that parent" - the same number as `EntityDetailOut.
    quantity` itself, attached to the parent reference too). It stays
    unset (`None`) for every use of this shape that isn't a containment
    edge at all (`prototypes`, `instances`, `stat_groups`) - "how many"
    has no meaning for those relationships, so leaving it `None` there
    represents "not applicable," not "exactly one."
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    quantity: int | None = None

    @classmethod
    def from_entity(cls, entity: Entity, *, quantity: int | None = None) -> EntitySummary:
        return cls(id=entity.id, name=entity.name, quantity=quantity)
