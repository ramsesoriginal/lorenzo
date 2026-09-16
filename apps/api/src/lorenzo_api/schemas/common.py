import uuid

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import Entity


class EntitySummary(BaseModel):
    """A lightweight entity reference - used anywhere an entity is pointed
    at generically (a container, a prototype, an owner) rather than fully
    described. See ADR 0020.

    `quantity` (ADR 0041) is only ever populated for `EntityDetailOut.
    children` entries - "how many of *this* child are in the entity being
    described" is a fact about that specific containment edge, not about
    the entity being referenced in general, so it stays unset (`None`) for
    every other use of this shape (`prototypes`, `instances`, `stat_groups`,
    `parent`).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    quantity: int | None = None

    @classmethod
    def from_entity(cls, entity: Entity, *, quantity: int | None = None) -> EntitySummary:
        return cls(id=entity.id, name=entity.name, quantity=quantity)
