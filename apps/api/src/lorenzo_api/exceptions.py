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
    "CampaignAdminOptOutRequiresAdminError",
    "CampaignManagementForbiddenError",
    "CampaignNotEmptyError",
    "CampaignNotFoundError",
    "CharacterNotFoundError",
    "EntityNotFoundError",
    "InvalidItemPrototypeError",
    "InvalidTokenError",
    "ItemInstanceManagementForbiddenError",
    "ItemInstanceNotFoundError",
    "ItemNotFoundError",
    "ItemPrototypeInUseError",
    "PayloadContentNotFoundError",
    "PayloadNotFoundError",
    "PlayerNotFoundError",
    "PreconditionFailedError",
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


class CampaignNotEmptyError(ConflictProblem):
    """DELETE /campaigns/{id} guard - see ADR 0034/RFC 0006: deleting a
    campaign that still has a Player or CampaignGm row needs an explicit
    ?force=true, or the existing ON DELETE CASCADE chain would silently
    take the whole roster down with it.
    """

    title = "Campaign still has players or GMs"


class CampaignManagementForbiddenError(ForbiddenProblem):
    """can_manage_campaign (ADR 0032) failed - see ADR 0034/RFC 0006. The
    caller already passed get_campaign_context (a real, non-enumerable 404
    boundary via can_access_campaign), so this is deliberately 403, not
    404: they can already read the campaign, they just lack a specific
    management permission over it.
    """

    title = "Not authorized to manage this campaign"


class CampaignAdminOptOutRequiresAdminError(UnprocessableProblem):
    """PUT .../admin-opt-out - see ADR 0034/RFC 0006: opting out of a
    tenant-admin bypass the caller doesn't currently hold (no tenant-wide
    OWNER/ORGA Membership) is meaningless, not merely redundant - 422, not
    a silent no-op.
    """

    title = "Opting out requires holding tenant-wide OWNER or ORGA"


class PreconditionFailedError(StatusProblem):
    """If-Match didn't match the resource's current ETag - see ADR
    0032/RFC 0005. fastapi_problem has no named 412 convenience base
    (only the 7 status codes its own StatusProblem subclasses cover), so
    this subclasses the generic StatusProblem directly, the same way its
    own named bases are themselves built on it.
    """

    status = 412
    title = "Precondition failed"
