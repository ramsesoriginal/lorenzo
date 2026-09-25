import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from lorenzo_api.models import Entity

# ADR 0107: what LorenzoScript's `[text](slug)` can name (RFC 0027 §3),
# checked on every write. Matched exactly, case included.
Slug = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=100)]


class ProblemOut(BaseModel):
    """A plain-dict-shaped mirror of `fastapi_problem.error.Problem.
    marshal()` - see ADR 0044. Used inside a bulk operation's per-item
    result (`BulkAssignResultItem`, `BulkMembershipResultItem`, ADR 0062)
    to embed what a real single-item error response body would have
    looked like without actually raising/catching it as this request's own
    top-level response. Lives here, not in `schemas/items.py` (its
    original, ADR 0044 home), since it has nothing item-specific about it
    and now has a second, unrelated consumer.
    """

    type: str
    title: str
    status: int
    detail: str | None = None


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
