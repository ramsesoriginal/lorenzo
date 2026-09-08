import uuid

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import Entity


class EntitySummary(BaseModel):
    """A lightweight entity reference - used anywhere an entity is pointed
    at generically (a container, a prototype, an owner) rather than fully
    described. See ADR 0020.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str

    @classmethod
    def from_entity(cls, entity: Entity) -> "EntitySummary":
        return cls(id=entity.id, name=entity.name)
