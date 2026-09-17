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
    "CharacterManagementForbiddenError",
    "CharacterNotFoundError",
    "EntityNotFoundError",
    "EntityStatManagementForbiddenError",
    "InvalidItemPrototypeError",
    "InvalidMergeError",
    "InformationAlreadyExistsError",
    "InformationManagementForbiddenError",
    "InformationNotFoundError",
    "InvalidSplitQuantityError",
    "InvalidStatGroupError",
    "InvalidProfilePictureError",
    "InvalidStatValueTypeError",
    "InvalidTokenError",
    "InvalidUserError",
    "ItemInstanceManagementForbiddenError",
    "ItemInstanceNotFoundError",
    "ItemInstanceSlugConflictError",
    "ItemInstanceSlugNotFoundError",
    "ItemNotFoundError",
    "ItemPrototypeInUseError",
    "LastOwnerError",
    "MembershipAlreadyExistsError",
    "MembershipManagementForbiddenError",
    "MembershipNotFoundError",
    "NicknameConflictError",
    "PayloadContentNotFoundError",
    "PayloadNotFoundError",
    "PlayerAlreadyExistsError",
    "PlayerNotFoundError",
    "PreconditionFailedError",
    "ProfilePictureNotFoundError",
    "SlugConflictError",
    "StatDefinitionNotFoundError",
    "StatGroupNotFoundError",
    "TenantCreationForbiddenError",
    "TenantNotFoundError",
    "UserNotFoundError",
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


class UserNotFoundError(NotFoundProblem):
    """GET /users/by-email/{email}, GET /users/by-nickname/{nickname} - no
    user has that exact value. See ADR 0051.
    """

    title = "User not found"


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


class InvalidProfilePictureError(UnprocessableProblem):
    """PUT .../picture - the uploaded content-type isn't in the allow-list
    (image/png, image/jpeg, image/webp, image/gif), or the body exceeds
    `Settings.profile_picture_max_bytes`. See ADR 0052.
    """

    title = "Invalid profile picture"


class InvalidItemPrototypeError(UnprocessableProblem):
    """POST /item-instances - prototype_id doesn't resolve to an entity with
    a matching Item row. See ADR 0032/RFC 0005 and ADR 0019's own
    real-but-unenforced invariant this endpoint now enforces at creation
    time.
    """

    title = "Prototype id is not a base item"


class InvalidSplitQuantityError(UnprocessableProblem):
    """POST /item-instances/{id}/split - see ADR 0041. Either the source has
    no Containment row at all (nothing to split from), or the requested
    quantity isn't strictly less than the source's current stack size -
    splitting off "all of it" is a container/owner reassignment of the
    whole stack, not a split.
    """

    title = "Invalid split quantity"


class ItemInstanceSlugConflictError(ConflictProblem):
    """POST /item-instances - the given slug is already used by another item
    instance in this tenant (the partial unique index on
    (tenant_id, slug), ADR 0043). Pre-checked explicitly, matching
    MembershipAlreadyExistsError/PlayerAlreadyExistsError/SlugConflictError's
    own established precedent, rather than letting the constraint violation
    surface as a bare 500.
    """

    title = "Item instance slug already in use"


class ItemInstanceSlugNotFoundError(NotFoundProblem):
    """GET .../item-instances/by-slug/{slug} - see ADR 0043. Non-enumerable,
    same as ItemInstanceNotFoundError: "no such slug in this tenant" and
    "the slug exists in a different tenant" both 404 identically.
    """

    title = "Item instance not found"


class InvalidMergeError(UnprocessableProblem):
    """POST /item-instances/{id}/merge - see ADR 0044. Covers every guard
    that route enforces with one type (merging into itself, either side
    missing a Containment row, the two sides having different containers,
    the two sides having different current owners) - which guard failed is
    a detail-string distinction, matching InvalidSplitQuantityError's own
    precedent of one type per route rather than one per specific reason.
    """

    title = "Invalid merge"


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


class ProfilePictureNotFoundError(NotFoundProblem):
    """GET .../picture - no uploaded picture and, for a user, no email to
    fall back to a Gravatar with either. See ADR 0052.
    """

    title = "Profile picture not found"


class TenantCreationForbiddenError(ForbiddenProblem):
    """POST /tenants - the caller lacks the platform-level tenant-creator
    Authgear role (ADR 0033/RFC 0012). 403, not 404: there's no
    tenant-scoped existence to hide behind - POST /tenants is the one
    endpoint with nothing tenant-scoped to leak - the caller just lacks a
    specific, nameable platform privilege, the same 403-not-404 reasoning
    RFC 0005 already established for "can read, can't write."
    """

    title = "Missing the tenant-creator role"


class SlugConflictError(ConflictProblem):
    """An explicitly-given slug (POST /tenants or PATCH /tenants/{id}) is
    already taken by another tenant. No auto-suffix here, unlike an
    omitted slug on create - silently rewriting something the caller
    explicitly asked for would be the wrong failure mode for an explicit
    choice. See ADR 0033/RFC 0012.
    """

    title = "Slug already in use"


class LastOwnerError(ConflictProblem):
    """DELETE /me, PATCH/DELETE /tenants/{id}/memberships/{user_id} - see
    ADR 0036/RFC 0007. Every tenant needs at least one OWNER able to
    administer it; this is the one guard shared by all three routes that
    could otherwise leave a tenant with none - removing yourself, having
    someone else remove you, or having someone else demote you away from
    OWNER, when you're the sole one.
    """

    title = "Cannot remove the tenant's only OWNER"


class MembershipManagementForbiddenError(ForbiddenProblem):
    """POST/PATCH/DELETE /tenants/{id}/memberships[/{user_id}] - see ADR
    0036/RFC 0007. Deliberately narrower than CampaignManagementForbiddenError:
    membership management is OWNER-only, not ORGA - granting/revoking
    tenant-wide administrative access is more sensitive than day-to-day
    tenant administration. The caller already passed get_tenant_context (a
    real Membership row, so a real non-enumerable 404 boundary already
    cleared), so this is deliberately 403, not 404.
    """

    title = "Not authorized to manage memberships in this tenant"


class MembershipNotFoundError(NotFoundProblem):
    """PATCH/DELETE /tenants/{id}/memberships/{user_id} - the target user_id
    has no Membership row in this tenant. See ADR 0036/RFC 0007.
    """

    title = "Membership not found"


class MembershipAlreadyExistsError(ConflictProblem):
    """POST /tenants/{id}/memberships - user_id already has a Membership row
    in this tenant. Not named anywhere in RFC 0007's own text (which
    doesn't address a duplicate invite), but a real, easily-reachable case:
    without this, a second POST for the same user_id would otherwise hit
    the table's own composite-PK violation as a bare, unhandled 500. Points
    the caller at PATCH instead, which is the route that actually exists to
    change an existing member's role.
    """

    title = "This user already has a membership in this tenant"


class NicknameConflictError(ConflictProblem):
    """PATCH /me - the requested nickname is already taken by another user.
    See ADR 0050. Nicknames are globally unique, not tenant-scoped - the
    same "explicit choice, no silent auto-suffix" reasoning SlugConflictError
    already gives for an explicitly-requested tenant slug.
    """

    title = "Nickname already in use"


class PlayerAlreadyExistsError(ConflictProblem):
    """POST /tenants/{id}/campaigns/{id}/players - user_id already has a
    Player row in this campaign (player's own UniqueConstraint(campaign_id,
    user_id), ADR 0024). Same reasoning as MembershipAlreadyExistsError
    above - not named in RFC 0007's own text, added so a second join
    attempt gets a clean 409 instead of an unhandled 500.
    """

    title = "This user already has a player in this campaign"


class InvalidUserError(UnprocessableProblem):
    """POST /tenants/{id}/memberships and POST .../players - user_id doesn't
    resolve to an existing app_user row. Real, not hypothetical: RFC 0007's
    "invite by user_id, not email" design ("Invitation, honestly") means an
    owner/manager can only reference someone who has already signed in at
    least once - this API has no email to look anyone up by (ADR 0009).
    Mirrors InvalidItemPrototypeError/InvalidStatGroupError's own "body
    references something that isn't there" shape.
    """

    title = "User id does not reference an existing user"


class CharacterManagementForbiddenError(ForbiddenProblem):
    """Self-or-managed authorization failed for a character write - see ADR
    0036/RFC 0007. Covers all three "managed" tiers (roster-link,
    any-one-current-campaign, every-campaign) with one error class, same as
    ItemInstanceManagementForbiddenError covers every item-instance write
    tier - which tier failed is a `detail`-string distinction, not a
    separate type. 403, not 404: the caller already passed
    get_tenant_or_404 (plus, for the two pre-existing read routes,
    get_tenant_context) - they already know this character exists, they
    just lack the specific write permission over it.
    """

    title = "Not authorized to manage this character"


class InformationAlreadyExistsError(ConflictProblem):
    """POST /tenants/{id}/entities/{id}/information - this entity already
    has an Information row of the given `type` (Information's own
    UniqueConstraint(entity_id, type), ADR 0017). Pre-checked explicitly
    rather than relying on the constraint violation to surface, matching
    MembershipAlreadyExistsError/PlayerAlreadyExistsError's own established
    precedent (ADR 0036) for a real, easily-reachable duplicate-write case.
    See ADR 0038/RFC 0011.
    """

    title = "This entity already has information of this type"


class InformationNotFoundError(NotFoundProblem):
    """GET/PUT/DELETE .../information[/{id}[/knowers/{id}]] - see ADR
    0038/RFC 0011. Also covers "exists, but the caller's
    information_visibility can't see it" - the same non-enumerable
    collapsing routers/payloads.py's GET .../content already does for the
    identical shape (an Information row is only as visible as its own
    is_public/knowledge state, not a separate authorization concern).
    """

    title = "Information not found"


class InformationManagementForbiddenError(ForbiddenProblem):
    """Self-or-managed authorization failed for authoring Information/
    Payload on an entity, or for granting/revoking a Knowledge row - see
    ADR 0038/RFC 0011. Mirrors EntityStatManagementForbiddenError's own
    404-vs-403 reasoning: the caller already knows the target entity/
    information exists, they just lack a specific write permission over
    it.
    """

    title = "Not authorized to manage this entity's information"
