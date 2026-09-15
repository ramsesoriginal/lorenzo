"""Typed "not found" problems - see ADR 0020 and errors.py.

fastapi-problem's own convention (see its README's "Custom Errors" section)
is to subclass its StatusProblem types with a fixed `title` per distinct
error condition, rather than raising a bare HTTPException(404, detail=...)
at every call site - the class name also drives the response's `type` field
(CamelCase -> kebab-case, "Error" suffix stripped), giving API consumers a
stable, programmatically-distinguishable value beyond the human-readable
`detail` string.
"""

from fastapi_problem.error import (
    ConflictProblem,
    ForbiddenProblem,
    NotFoundProblem,
    StatusProblem,
    UnauthorisedProblem,
    UnprocessableProblem,
)

__all__ = [
    "CampaignNotFoundError",
    "CharacterNotFoundError",
    "EntityNotFoundError",
    "EntityStatManagementForbiddenError",
    "InvalidItemPrototypeError",
    "InvalidStatGroupError",
    "InvalidStatValueTypeError",
    "InvalidTokenError",
    "ItemInstanceManagementForbiddenError",
    "ItemInstanceNotFoundError",
    "ItemNotFoundError",
    "ItemPrototypeInUseError",
    "PayloadContentNotFoundError",
    "PayloadNotFoundError",
    "PlayerNotFoundError",
    "PreconditionFailedError",
    "StatDefinitionNotFoundError",
    "StatGroupNotFoundError",
    "TenantNotFoundError",
]


class InvalidTokenError(UnauthorisedProblem):
    title = "Invalid or missing authentication token"


class TenantNotFoundError(NotFoundProblem):
    title = "Tenant not found"


class EntityNotFoundError(NotFoundProblem):
    title = "Entity not found"


class CampaignNotFoundError(NotFoundProblem):
    title = "Campaign not found"


class ItemNotFoundError(NotFoundProblem):
    title = "Item not found"


class ItemInstanceNotFoundError(NotFoundProblem):
    title = "Item instance not found"


class PayloadNotFoundError(NotFoundProblem):
    title = "Payload not found"


class PayloadContentNotFoundError(NotFoundProblem):
    title = "Payload has no binary content"


class PlayerNotFoundError(NotFoundProblem):
    title = "Player not found"


class CharacterNotFoundError(NotFoundProblem):
    """Also covers "this is a being with no character row" - the same
    non-enumerable collapsing every other not-found condition in this
    codebase already does (ADR 0031/RFC 0004).
    """

    title = "Character not found"


class ItemPrototypeInUseError(ConflictProblem):
    """DELETE /items/{id} guard - see ADR 0032/RFC 0005: deleting a base
    item that some instance still directly prototypes would otherwise
    silently strip that instance's inherited stats via ADR 0018's blanket
    cascade.
    """

    title = "Item is still in use as a prototype"


class InvalidItemPrototypeError(UnprocessableProblem):
    """POST /item-instances - prototype_id doesn't resolve to an entity with
    a matching Item row. See ADR 0032/RFC 0005 and ADR 0019's own
    real-but-unenforced invariant this endpoint now enforces at creation
    time.
    """

    title = "Prototype id is not a base item"


class ItemInstanceManagementForbiddenError(ForbiddenProblem):
    """Self-or-managed authorization failed - see ADR 0032/RFC 0005. The
    caller already passed get_tenant_context (a real, non-enumerable 404
    boundary), so this is deliberately 403, not 404: they can already read
    this instance, they just lack a specific write permission over it.
    """

    title = "Not authorized to manage this item instance"


class StatGroupNotFoundError(NotFoundProblem):
    title = "Stat group not found"


class StatDefinitionNotFoundError(NotFoundProblem):
    title = "Stat definition not found"


class InvalidStatGroupError(UnprocessableProblem):
    """POST /stat-definitions - stat_group_id doesn't resolve to a stat
    group in this tenant. See ADR 0037/RFC 0008; mirrors
    InvalidItemPrototypeError's own "body references something that isn't
    there" shape.
    """

    title = "Stat group id is not valid"


class InvalidStatValueTypeError(UnprocessableProblem):
    """PUT .../entities/{id}/stats/{stat_definition_id} - the request body's
    value isn't shaped like the target stat_definition's declared
    value_type (int/text/float/bool). entity_stat's own CHECK constraint
    (ADR 0014) only enforces "exactly one value_* column is set," not which
    one matches the definition - this is that missing application-level
    check, surfaced as a real 422 instead of an opaque DB error. See ADR
    0037/RFC 0008.
    """

    title = "Stat value does not match its definition's value type"


class EntityStatManagementForbiddenError(ForbiddenProblem):
    """Self-or-managed authorization failed for an entity_stat write - see
    ADR 0037/RFC 0008. Mirrors ItemInstanceManagementForbiddenError's own
    404-vs-403 reasoning: the caller already knows this entity exists (it
    passed get_entity_or_404), they just lack a specific write permission
    over its stats.
    """

    title = "Not authorized to manage this entity's stats"


class PreconditionFailedError(StatusProblem):
    """If-Match didn't match the resource's current ETag - see ADR
    0032/RFC 0005. fastapi_problem has no named 412 convenience base
    (only the 7 status codes its own StatusProblem subclasses cover), so
    this subclasses the generic StatusProblem directly, the same way its
    own named bases are themselves built on it.
    """

    status = 412
    title = "Precondition failed"
