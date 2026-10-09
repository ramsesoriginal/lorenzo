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
    "AccountSuspendedError",
    "CampaignAdminOptOutRequiresAdminError",
    "CampaignManagementForbiddenError",
    "CampaignNotEmptyError",
    "CampaignNotFoundError",
    "InvalidInviteExpiryError",
    "InviteNotFoundError",
    "CharacterManagementForbiddenError",
    "CharacterNotFoundError",
    "EntityNotFoundError",
    "EntityPrototypeCycleError",
    "EntitySlugConflictError",
    "EntitySlugManagementForbiddenError",
    "EntitySlugNotFoundError",
    "EntityStatManagementForbiddenError",
    "InvalidCharacterError",
    "InvalidGroupMemberError",
    "InvalidItemPrototypeError",
    "InvalidMergeError",
    "InvalidPrototypeError",
    "InformationAlreadyExistsError",
    "InformationManagementForbiddenError",
    "InformationNotFoundError",
    "InvalidSplitQuantityError",
    "InvalidSubscriberError",
    "InvalidStatGroupError",
    "InvalidProfilePictureError",
    "InvalidStatValueTypeError",
    "InvalidTokenError",
    "InvalidUserError",
    "InventoryItemParentsError",
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
    "NotificationNotFoundError",
    "PayloadContentNotFoundError",
    "PayloadNotFoundError",
    "PlatformOperatorRoleRequiredError",
    "PlayerAlreadyExistsError",
    "PlayerNotFoundError",
    "NotARepositoryError",
    "PreconditionFailedError",
    "RepositoryHasNoCampaignsError",
    "RepositoryManagementForbiddenError",
    "RepositoryNotFoundError",
    "RepositoryStillGrantedError",
    "ProfilePictureNotFoundError",
    "SlugConflictError",
    "SubscriptionNotFoundError",
    "StackNeedsContainerError",
    "ItemNotYoursToGiveError",
    "BindingNotLiftableError",
    "CapacityExceededError",
    "ItemBoundError",
    "OverrideForbiddenError",
    "SelfServiceDisabledError",
    "NotAPackError",
    "PackListError",
    "InvalidPackOwnerError",
    "StatDefinitionNotFoundError",
    "StatGroupNotFoundError",
    "TenantCreationForbiddenError",
    "TenantDeletionForbiddenError",
    "TooManyRequestsError",
    "TenantNotFoundError",
    "UserNotFoundError",
    "InvalidRepositoryCopyChoiceError",
    "RepositoryAlreadyCopiedError",
    "RepositoryCopyFormulaCycleError",
    "RepositoryCopyNeedsChoicesError",
    "RepositoryCopyNeedsGrantsError",
    "InvalidRepositoryUpdateError",
    "RepositoryNotCopiedError",
    "RepositoryUpdateNeedsChoicesError",
    "ReleaseLabelTakenError",
    "ReleaseHasBreakingChangesError",
    "EntityKindInUseError",
    "InvalidKindRequestError",
    "InventoryItemKindError",
    "RepositoryHasUnprovenKindsError",
    "ReleaseNotFoundError",
    "UpdateNeedsConfirmationError",
]


class InvalidTokenError(UnauthorisedProblem):
    title = "Invalid or missing authentication token"


class TenantNotFoundError(NotFoundProblem):
    title = "Tenant not found"


class EntityNotFoundError(NotFoundProblem):
    title = "Entity not found"


class EntitySlugNotFoundError(NotFoundProblem):
    """GET .../entities/by-slug/{slug} - see ADR 0107. Non-enumerable, like
    ItemInstanceSlugNotFoundError: a slug in another tenant 404s the same.
    """

    title = "Entity not found"


class ClientIdUnavailableError(ConflictProblem):
    """A create that carried its own `id` (ADR 0222) named an id that cannot be used: it belongs
    to a row the caller cannot see, or to a row of another kind or another entry. The same
    answer for each, so it does not say which, and never names another tenant.
    """

    title = "Id not available"


class EntitySlugConflictError(ConflictProblem):
    """PUT .../entities/{id}/slug - another entity in this tenant already
    has the slug (UNIQUE(tenant_id, slug), ADR 0107). Pre-checked, rather
    than surfacing the constraint violation as a 500.
    """

    title = "Slug already in use"


class StackNeedsContainerError(ConflictProblem):
    """Setting a stack of more than one down - DELETE .../container on it, or
    deleting a container in no container that holds it - without `split`: a
    stack's count lives on its containment row (ADR 0041), so deleting the row
    would drop it. `split=true` sets it down as single items (ADR 0132); moving
    it into its owner keeps it a stack (ADR 0115).
    """

    title = "A stack needs a container"


class EntitySlugManagementForbiddenError(ForbiddenProblem):
    """Self-or-managed authorization failed for setting or clearing an
    entity's slug - see ADR 0107, which reuses ADR 0038's tier. 403, not
    404: the caller can already read the entity.
    """

    title = "Not authorized to manage this entity's slug"


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
    user has that exact value. See ADR 0055.
    """

    title = "User not found"


class NotificationNotFoundError(NotFoundProblem):
    """POST /me/notifications/{id}/read - no such notification, or one that
    exists but isn't the caller's own - collapsed indistinguishably, same
    non-enumerable shape every other not-found condition in this codebase
    already uses. See ADR 0058.
    """

    title = "Notification not found"


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
    `Settings.profile_picture_max_bytes`. See ADR 0056.
    """

    title = "Invalid profile picture"


class InvalidItemPrototypeError(UnprocessableProblem):
    """POST /item-instances - prototype_id doesn't resolve to an entity with
    a matching Item row. See ADR 0032/RFC 0005 and ADR 0019's own
    real-but-unenforced invariant this endpoint now enforces at creation
    time.
    """

    title = "Prototype id is not a base item"


class InvalidPrototypeError(UnprocessableProblem):
    """PUT /items/{id}/prototypes - a given prototype_ids entry doesn't
    resolve to an existing entity in this tenant. See ADR 0072. Deliberately
    not InvalidItemPrototypeError - that one requires resolving to a base
    Item specifically (ItemInstanceCreate's own invariant); a catalog item's
    own prototypes are a generic entity_prototype edge (ADR 0015), with no
    such restriction, matching POST /items's own existing (unvalidated)
    prototype_ids handling.
    """

    title = "Prototype id does not reference an existing entity in this tenant"


class EntityPrototypeCycleError(UnprocessableProblem):
    """PUT /items/{id}/prototypes - the given prototype set would create an
    inheritance cycle, direct (entity_id naming itself) or transitive
    (entity_prototype's own BEFORE INSERT trigger, ADR 0015). See ADR 0072.
    """

    title = "Prototype set would create an inheritance cycle"


class InventoryItemParentsError(ConflictProblem):
    """PUT /entities/{id}/parents - the entry is an inventory item (item_instance), whose one
    parent changes through PATCH /item-instances/{id} (ADR 0192). See ADR 0216.
    """

    title = "An inventory item's parent is changed through its own route"


class InvalidSplitQuantityError(UnprocessableProblem):
    """POST /item-instances/{id}/split - see ADR 0041. Either the source has
    no Containment row at all (nothing to split from), or the requested
    quantity isn't strictly less than the source's current stack size -
    splitting off "all of it" is a container/owner reassignment of the
    whole stack, not a split.
    """

    title = "Invalid split quantity"


class ItemInstanceSlugConflictError(ConflictProblem):
    """POST /item-instances - the given slug is already used by another
    entity in this tenant (entity_slug's UNIQUE(tenant_id, slug), ADR 0107;
    item instances only, before that, ADR 0043). Pre-checked explicitly, matching
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


class ItemNotYoursToGiveError(ForbiddenProblem):
    """The caller holds this item but doesn't control its owner (ADR 0124):
    they may move it, but only its owner or a GM may give it away or
    destroy it. Its own type, so a client can say so in its own words."""

    title = "Not yours to give away"


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


class InvalidComputedStatError(UnprocessableProblem):
    """PUT/preview .../computed-stats/{id} - the formula doesn't fit its
    stats: an input that isn't a stat definition in this tenant, a stat
    reading itself, operand or target types the kind doesn't support, an
    int target without rounding, or text/enum results that are missing or
    not allowed (ADR 0104).
    """

    title = "Invalid formula"


class ComputedStatCycleError(UnprocessableProblem):
    """PUT/preview .../computed-stats/{id} - the formula would close a
    cycle in the tenant's formula dependencies (ADR 0104: checked at the
    stat-definition level, across every entity). `detail` names the path.
    """

    title = "Formula would depend on itself"


class ComputedStatConflictError(ConflictProblem):
    """An entity can hold a formula or a direct value for a stat, not both
    (ADR 0104) - setting either while the other exists. Clear the other
    one first.
    """

    title = "This stat already has a value of the other kind on this entity"


class ComputedStatNotFoundError(NotFoundProblem):
    """DELETE .../entities/{id}/computed-stats/{stat_definition_id} - the
    entity holds no formula of its own for that stat (ADR 0104).
    """

    title = "Formula not found"


class InvalidStatValueError(UnprocessableProblem):
    """PUT .../entities/{id}/stats/{stat_definition_id} on an `enum` stat
    with a string that isn't one of its allowed values (ADR 0103).
    """

    title = "Value is not allowed for this stat"


class InvalidStatEnumValuesError(UnprocessableProblem):
    """POST /stat-definitions or .../enum-values - enum_values given for a
    non-enum stat, missing or empty for an enum one, or containing
    duplicates; or an enum value added to a non-enum definition (ADR 0103).
    """

    title = "Invalid enum values for this stat definition"


class StatEnumValueAlreadyExistsError(ConflictProblem):
    """POST .../stat-definitions/{id}/enum-values - the value is already
    allowed (UNIQUE(stat_definition_id, value), ADR 0103).
    """

    title = "This value is already allowed for this stat"


class StatEnumValueInUseError(ConflictProblem):
    """DELETE .../enum-values/{id} while an entity directly holds that
    value - removing it would leave stored values outside the allowed set
    (ADR 0103).
    """

    title = "This value is still in use"


class StatDefinitionInUseError(ConflictProblem):
    """DELETE /stat-definitions/{id} while a value, a formula or a formula
    that reads it uses it - deleting it would take those with it (ADR 0167).
    """

    title = "This stat definition is still in use"


class StatGroupInUseError(ConflictProblem):
    """DELETE /stat-groups/{id} while it holds a stat definition or an
    entity has acquired it - deleting it would take those with it (ADR 0167).
    """

    title = "This stat group is still in use"


class StatEnumValueNotFoundError(NotFoundProblem):
    """DELETE .../stat-definitions/{id}/enum-values/{id} - no such value on
    that definition in this tenant (ADR 0103).
    """

    title = "Enum value not found"


class InvalidStatValueTypeError(UnprocessableProblem):
    """PUT .../entities/{id}/stats/{stat_definition_id} - the request body's
    value isn't shaped like the target stat_definition's declared
    value_type (int/text/float/bool/enum), or a tag route (ADR 0103) names
    a stat that isn't bool. entity_stat's own CHECK constraint
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
    fall back to a Gravatar with either. See ADR 0056.
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


class TenantDeletionForbiddenError(ForbiddenProblem):
    """DELETE /tenants/{id} - the caller is a member of the tenant but not
    one of its OWNERs (ADR 0184). Narrower than update_tenant's ORGA gate,
    like membership management (ADR 0036): deleting the world is not
    day-to-day administration. A caller without the platform tenant-creator
    role gets TenantCreationForbiddenError instead, before the tenant is
    looked at, and a non-member gets the same 404 as for any tenant.
    """

    title = "Only an owner can delete a tenant"


class PlatformOperatorRoleRequiredError(ForbiddenProblem):
    """/admin/* - the caller lacks the platform-level platform-operator
    Authgear role. See ADR 0057 - exact mirror of
    TenantCreationForbiddenError's own reasoning: a platform-wide
    capability, not tenant-scoped, so 403 not 404.
    """

    title = "Missing the platform-operator role"


class AccountSuspendedError(ForbiddenProblem):
    """Raised by dependencies.get_current_user, before anything else runs,
    for any request from a suspended account - see ADR 0057. 403, not 401:
    the token itself is genuinely valid, the account it names is simply
    blocked from acting.
    """

    title = "This account has been suspended"


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
    See ADR 0054. Nicknames are globally unique, not tenant-scoped - the
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
    """POST /tenants/{id}/memberships, POST .../players, and
    PUT .../campaigns/{id}/gms/{user_id} - user_id doesn't resolve to an
    existing app_user row. Real, not hypothetical: RFC 0007's "invite by
    user_id, not email" design ("Invitation, honestly") means an
    owner/manager can only reference someone who has already signed in at
    least once - by-email/by-nickname lookup (ADR 0055) helps find that
    user_id, but doesn't remove the underlying constraint. Mirrors
    InvalidItemPrototypeError/InvalidStatGroupError's own "body references
    something that isn't there" shape.
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
    """POST /tenants/{id}/entities/{id}/information, or PATCH
    .../information/{id} changing `type` - this entity already has an
    Information row of a *singleton* type (information_type.is_singleton,
    ADR 0101 - other types repeat freely). Pre-checked explicitly
    rather than relying on the constraint violation to surface, matching
    MembershipAlreadyExistsError/PlayerAlreadyExistsError's own established
    precedent (ADR 0036) for a real, easily-reachable duplicate-write case.
    See ADR 0038/RFC 0011.
    """

    title = "This entity already has information of this type"


class InformationOrderConflictError(ConflictProblem):
    """POST .../entities/{id}/information or PATCH .../information/{id}
    with an explicit `order` another row of the same entity already holds
    (ADR 0101: unique per entity, pre-checked under the entity's row lock).
    """

    title = "Another piece of information already has this position"


class PayloadKindNotEditableError(ConflictProblem):
    """PATCH .../payloads/{id} on a payload that isn't a description (ADR
    0101) - number/picture/document authoring is still RFC 0015 sub-slice
    4's open question.
    """

    title = "Only description payloads can be edited"


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


class InvalidCharacterError(UnprocessableProblem):
    """POST /groups, PUT .../groups/{id}/members/{character_entity_id},
    POST .../groups/{id}/members/bulk - the given id doesn't resolve to a
    real Character in this tenant. Mirrors InvalidUserError/
    InvalidItemPrototypeError's own "body references something that isn't
    there" shape - without this, GroupMember.character_entity_id's own FK
    to character.entity_id would otherwise surface as a bare 500. See ADR
    0064.
    """

    title = "Character id does not reference an existing character"


class InvalidGroupMemberError(UnprocessableProblem):
    """PUT .../groups/{group_entity_id}/members/{character_entity_id} and
    its bulk/create-time equivalents - character_entity_id equals
    group_entity_id. Pre-checked rather than left to surface as a raw
    group_member_no_self_loop CHECK violation - a real, reachable case
    since nothing stops an entity from independently acquiring both a
    group role and a Character row (RFC 0001). See ADR 0064.
    """

    title = "An entity cannot be a member of its own group"


class InviteNotFoundError(NotFoundProblem):
    """GET /invites/{token} and POST /invites/{token}/redeem - see ADR 0092.
    One class, one fixed `detail`, for *every* reason a link can fail: an
    unknown, expired, revoked or exhausted token must be indistinguishable
    to whoever is holding it, or the difference tells an attacker a token
    was once real. Never carries the token.
    """

    title = "Invite link not valid"


class InvalidInviteExpiryError(UnprocessableProblem):
    """POST .../invites - `expires_at` must be in the future and no more
    than 30 days out (ADR 0092: a link always ends, and not too far off).
    """

    title = "Invalid invite expiry"


class TooManyRequestsError(StatusProblem):
    """The in-process rate-limit backstop on the public invite-link routes
    (ADR 0092). Carries `Retry-After`. fastapi_problem has no named 429
    base, so this subclasses StatusProblem directly, the way
    PreconditionFailedError does for 412.
    """

    status = 429
    title = "Too many requests"


class RepositoryHasNoCampaignsError(ConflictProblem):
    """POST .../campaigns on a repository tenant - ADR 0118. A repository
    is a reusable setting nobody plays in; a trigger on `campaign` refuses
    the row too, this just answers first and plainly."""

    title = "A repository holds no campaigns"


class NotARepositoryError(ConflictProblem):
    """A repository-only action (publishing, granting access) on a play
    tenant - ADR 0118."""

    title = "This tenant isn't a repository"


class RepositoryManagementForbiddenError(ForbiddenProblem):
    """Publishing a repository or granting access to it takes the
    repository tenant's OWNER role; removing a grant from the subscribing
    side takes that tenant's OWNER role - ADR 0118."""

    title = "Only a tenant's owners can do this"


class RepositoryNotFoundError(NotFoundProblem):
    """A repository this tenant holds no grant for, or one that isn't
    published - ADR 0118. Both answer the same, so a draft's existence
    doesn't leak."""

    title = "Repository not found"


class SubscriptionNotFoundError(NotFoundProblem):
    """Removing a grant that doesn't exist - ADR 0118."""

    title = "No such grant"


class InvalidSubscriberError(UnprocessableProblem):
    """Granting a repository to itself - ADR 0118."""

    title = "A repository can't be granted to itself"


class RepositoryStillGrantedError(ConflictProblem):
    """DELETE /tenants/{id} on a repository that other tenants still hold a
    grant on (ADR 0184): deleting it would cut them off from its updates
    without anyone having chosen that. Revoke the grants (or delete the
    tenants that hold them) first.
    """

    title = "Other tenants still hold this repository"


class RepositoryAlreadyCopiedError(ConflictProblem):
    """A second copy of a repository - ADR 0119. Later changes come in as
    updates (ADR 0121), not as another copy."""

    title = "This repository has already been copied"


class RepositoryCopyNeedsChoicesError(ConflictProblem):
    """A copy would collide with names or slugs already in use - ADR 0119.
    Carries `collisions`, each with the choices it allows; send one
    `resolution` per collision."""

    title = "Some names are already in use here"


class RepositoryCopyNeedsGrantsError(ConflictProblem):
    """A copy needs a repository this tenant holds no grant for, or one
    that isn't published - ADR 0120. Carries `missing`."""

    title = "This copy needs access to more repositories"


class InvalidRepositoryCopyChoiceError(UnprocessableProblem):
    """A collision choice that can't work: a rename onto a name that's
    taken, a merge across value types, a malformed slug - ADR 0119."""

    title = "That choice can't be applied"


class RepositoryCopyFormulaCycleError(ConflictProblem):
    """A copy whose merged stats would make formulas depend on each other
    in a loop - ADR 0119. Nothing is copied."""

    title = "The copy would make formulas loop"


class RepositoryNotCopiedError(ConflictProblem):
    """Checking or applying updates for a repository this tenant hasn't
    copied - ADR 0121. Copy it first."""

    title = "This repository hasn't been copied here"


class RepositoryUpdateNeedsChoicesError(ConflictProblem):
    """Applying an update where this tenant changed a field too, without
    saying whether to keep its own value or take the repository's - ADR
    0121. Carries `conflicts`: name each in `keep_local` or
    `take_upstream`."""

    title = "Some changes conflict with your own edits"


class ReleaseLabelTakenError(ConflictProblem):
    """Publishing, or relabelling, a release with a label the repository has used
    already, whatever its case - ADR 0207."""

    title = "That release label is taken"


class ReleaseHasBreakingChangesError(ConflictProblem):
    """Publishing a release that holds changes the update engine cannot carry to a library that
    already copied the repository, without `acknowledge_breaking` - ADR 0208, RFC 0037 §3.
    Carries `breaking_rows`: each row, with the reason it breaks, in words."""

    title = "This release would break things"


class UpdateNeedsConfirmationError(ConflictProblem):
    """Applying an update to a row a release since the library last updated called breaking,
    without `confirm` - ADR 0208. Carries `unconfirmed`: each such row and why."""

    title = "Some changes are marked breaking"


class ReleaseNotFoundError(NotFoundProblem):
    """Editing a release the repository has not made - ADR 0207."""

    title = "Release not found"


class InvalidRepositoryUpdateError(UnprocessableProblem):
    """An update action for a row that has nothing of that kind to do -
    ADR 0121."""

    title = "That update can't be applied"


class CapacityExceededError(ConflictProblem):
    """A move would make a container's or a being's load grow past its
    `carry_capacity` or `containment_capacity`, or put something larger than
    its `max_item_size` into it - ADR 0128. Carries `container`, `stat`,
    `limit`, and `load`; `detail` says the same in words."""

    title = "Too much to fit"


class OverrideForbiddenError(ForbiddenProblem):
    """`override: true` or `lift_binding: true` from someone who isn't the
    item's GM - ADR 0128, 0129: moving past capacity or binding, and lifting
    a binding, are a GM's call alone."""

    title = "Only a GM can do that"


class SelfServiceDisabledError(ForbiddenProblem):
    """A player making an item instance for their own character while every
    seat of theirs that plays it has self-service switched off, by the
    campaign or by their own override - RFC 0034, ADR 0186."""

    title = "Self-service is switched off"


class NotAPackError(UnprocessableProblem):
    """POST /item-instances/from-pack - `pack_id` isn't an item of the
    tenant, or its public description holds no contents list - ADR 0149."""

    title = "Not a pack"


class PackListError(UnprocessableProblem):
    """POST /item-instances/from-pack - a pack's contents list can't be
    handed out as it is: a line without a link, a slug that isn't an item of
    the tenant, a quantity or a count over its limit - ADR 0149. Carries
    `lines`, one entry for each thing wrong; nothing was created."""

    title = "The pack's list can't be handed out"


class InvalidPackOwnerError(UnprocessableProblem):
    """POST /item-instances/from-pack - `owner_entity_id` is neither a being
    nor a group (an entity named by `group_member` rows) - ADR 0149."""

    title = "A pack goes to a being or a group"


class ItemBoundError(ConflictProblem):
    """A write would change a bound item's owner, or take a bound thing out
    of what binds it - ADR 0129. Carries `item`, `binding`, and `owner`;
    `detail` says the same in words."""

    title = "Bound to its owner"


class BindingNotLiftableError(UnprocessableProblem):
    """`lift_binding: true` where `binding` can't be set to `none`: the
    tenant's `binding` has no such value, or the item holds its own formula
    for it - ADR 0129."""

    title = "That binding can't be lifted"


class EntityKindInUseError(ConflictProblem):
    """DELETE /entities/{id}/kinds/{kind} and DELETE /entities/{id} - the entry is a character,
    which hangs off its being (its key would cascade away: demote it first), or belongs to a
    campaign. See ADR 0217."""

    title = "Another part of the entry depends on this"


class InventoryItemKindError(ConflictProblem):
    """PUT /entities/{id}/kinds/item and DELETE /entities/{id} - the entry is an inventory item
    (item_instance), which is made from a catalog item, deleted with its own route and never
    takes the kind `item`. See ADR 0217."""

    title = "An inventory item is changed through its own routes"


class RepositoryHasUnprovenKindsError(ConflictProblem):
    """PUT .../published - an entry has a combination of kinds no round-trip matrix covers
    (ADR 0217, RFC 0041 section 2). Carries `entries`: each entry, with its kinds."""

    title = "Some entries have a combination of kinds that cannot be published yet"


class InvalidKindRequestError(UnprocessableProblem):
    """PUT /entities/{id}/kinds/{kind} - a column the kind does not have (ADR 0217)."""

    title = "That column does not belong to this kind"
