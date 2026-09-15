import uuid
from functools import lru_cache
from typing import Annotated, Any

import jwt
import structlog
from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi_pagination import Params
from jwt import PyJWKClient
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.campaign_access import can_access_campaign
from lorenzo_api.config import get_settings
from lorenzo_api.db import get_db_session
from lorenzo_api.exceptions import (
    CampaignNotFoundError,
    EntityNotFoundError,
    InvalidTokenError,
    TenantCreationForbiddenError,
    TenantNotFoundError,
)
from lorenzo_api.models import Campaign, Entity, Membership, Tenant, User

__all__ = [
    "CurrentUser",
    "ParamsDep",
    "SessionDep",
    "get_campaign_context",
    "get_current_user",
    "get_entity_or_404",
    "get_jwks_client",
    "get_tenant_context",
    "get_tenant_or_404",
    "require_tenant_creator_role",
    "set_tenant_rls_context",
    "verify_token",
]

# Authgear's own claim name for a user's assigned roles - see ADR
# 0033/RFC 0012. Flagged there for empirical verification against a real
# Authgear Cloud project (not fully certain from Authgear's docs alone,
# which don't list `roles` among the JWT access token's documented default
# claims - plausibly because it only appears once a user actually has a
# role assigned); this codebase has no live Authgear project to verify
# against yet, so this is implemented per Authgear's roles/groups guide and
# left for that empirical confirmation before relying on it in production.
_AUTHGEAR_ROLES_CLAIM = "https://authgear.com/claims/user/roles"

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
ParamsDep = Annotated[Params, Depends()]

logger = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer()
BearerCredentialsDep = Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)]


@lru_cache
def get_jwks_client() -> PyJWKClient:
    """A singleton, mirroring get_settings()'s own @lru_cache - PyJWKClient
    caches the whole JWKS response internally (5 minutes by default);
    building a fresh one per request would throw that away and pay a
    blocking fetch on every single request. Its own dependency specifically
    so tests can override it to point at a fake JWKS server - see ADR 0023.
    """
    return PyJWKClient(get_settings().authgear_jwks_url)


JwksClientDep = Annotated[PyJWKClient, Depends(get_jwks_client)]


async def verify_token(
    credentials: BearerCredentialsDep, jwks_client: JwksClientDep
) -> dict[str, Any]:
    """Verifies an Authgear-issued access token against its JWKS - see ADR
    0023. Both PyJWKClient's key lookup and jwt.decode are synchronous
    (stdlib urllib, no async support) - run off the event loop via
    run_in_threadpool, or an occasional blocking JWKS fetch would freeze it
    for every concurrent request.
    """
    settings = get_settings()
    token = credentials.credentials
    try:
        signing_key = await run_in_threadpool(jwks_client.get_signing_key_from_jwt, token)
        claims: dict[str, Any] = await run_in_threadpool(
            jwt.decode,
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.authgear_audience,
            issuer=settings.authgear_issuer,
        )
    except jwt.PyJWTError as exc:
        logger.info("token_verification_failed", error=str(exc))
        raise InvalidTokenError(detail="Invalid or expired authentication token") from exc
    return claims


TokenClaimsDep = Annotated[dict[str, Any], Depends(verify_token)]


async def get_current_user(claims: TokenClaimsDep, session: SessionDep) -> User:
    """Maps the verified `sub` claim to an app_user row, auto-provisioning
    one on a subject's first-ever request. Atomic upsert, not
    check-then-insert - two concurrent first-requests from a brand-new
    subject would otherwise race each other on the UNIQUE constraint. See
    ADR 0023 for why this dependency commits the upsert itself.

    Also sets app.user_id on this session - membership's RLS policy uses
    it to let a caller see their own Membership rows across every tenant
    (GET /me is deliberately not tenant-scoped, so there's no single
    app.tenant_id to set for that query - see ADR 0023). Set *after* the
    commit above, not before: set_config(..., is_local=true) only lasts
    for the current transaction, and the commit ends the one the upsert
    itself ran in.

    Also attaches user.authgear_roles (ADR 0033/RFC 0012) - a plain,
    non-persisted attribute (see models.User's own docstring on it), read
    by require_tenant_creator_role below. Defaults to an empty frozenset if
    the claim is absent entirely - no role granted, no access, the
    closed-by-default behavior this whole mechanism exists for.
    """
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError(detail="Token has no subject claim")

    stmt = (
        pg_insert(User)
        .values(authgear_subject_id=subject)
        .on_conflict_do_update(
            index_elements=[User.authgear_subject_id],
            set_={"authgear_subject_id": subject},
        )
        .returning(User)
    )
    user = (await session.scalars(stmt)).one()
    await session.commit()
    await session.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user.id)})
    roles = claims.get(_AUTHGEAR_ROLES_CLAIM)
    user.authgear_roles = frozenset(roles) if isinstance(roles, list) else frozenset()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_tenant_creator_role(user: CurrentUser) -> None:
    """Gates POST /tenants (ADR 0033/RFC 0012) - a platform-level check,
    independent of any tenant, since none exists yet for a tenant-scoped
    dependency like get_tenant_context to check against. Reads the role
    claim get_current_user already attached to `user` rather than
    re-verifying the token itself - see that function's own docstring for
    why (the `client` test fixture's get_current_user override has no real
    token to re-verify).

    403, not 404: there's no existence to hide here - POST /tenants is the
    one endpoint with nothing tenant-scoped to leak - the caller just lacks
    a specific, nameable platform privilege, same reasoning RFC 0005
    already established for "can read, can't write."
    """
    if get_settings().tenant_creator_role_key not in user.authgear_roles:
        raise TenantCreationForbiddenError(detail="Missing the platform's tenant-creator role")


async def set_tenant_rls_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """set_config(..., is_local=true) only lasts for the current
    transaction (see get_current_user's identical note on app.user_id) -
    get_tenant_context/get_tenant_or_404 set this once at dependency
    resolution, before a route handler's own body runs, which is enough
    for every read-only route (never commits, so the setting survives for
    the whole request). A write route that commits mid-request (ADR
    0032/RFC 0005 onward) ends that same transaction, silently losing
    app.tenant_id for anything it queries afterward (e.g. re-reading its
    own row through a security_invoker view to build the response) - such
    a route must call this again itself, right after its own commit,
    before its own post-commit read.
    """
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )


async def get_tenant_context(
    tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> uuid.UUID:
    """Validates tenant_id is real *and* the caller actually has a
    Membership in it, then sets app.tenant_id on this same request-scoped
    session, which RLS policies now actually filter on, since the app
    connects as a restricted, non-superuser role (ADR 0002/0021) - see
    ADR 0020/0022/0023. Every route must still filter its own queries by
    tenant_id explicitly regardless; RLS is defense in depth for a missed
    filter, not a replacement for filtering deliberately (ADR 0002).

    "Tenant doesn't exist" and "tenant exists but you're not a member"
    raise the exact same TenantNotFoundError - same class, same body - so
    a non-member can't distinguish the two (ADR 0023).
    """
    if await session.get(Tenant, tenant_id) is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    if await session.get(Membership, (tenant_id, user.id)) is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    await set_tenant_rls_context(session, tenant_id)
    return tenant_id


async def get_tenant_or_404(
    tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> uuid.UUID:
    """Existence-only - no Membership check, unlike get_tenant_context. See
    ADR 0030/RFC 0003: which RLS partition a query runs against is a
    scoping decision, not an authorization one - get_campaign_context (or a
    route's own explicit predicate, e.g. is_tenant_participant) layers
    authorization on top of this rather than folding it in here, the same
    division get_tenant_context/can_access_campaign already keep separate.

    `user: CurrentUser` is unused below - it exists purely to force
    dependency ordering, a real bug found and fixed while building ADR
    0038: get_current_user performs its own internal commit (the
    auto-provisioning upsert, ADR 0023), which ends whatever transaction
    was active - including one this function's own set_tenant_rls_context
    call below just started. Without an explicit dependency on `user`
    here, FastAPI has no reason to resolve get_current_user before this
    function's body runs, and when it resolves it *after* instead (which
    it did, deterministically, for every router using this as a bare
    router-level dependency with no `user` parameter of its own -
    routers/item_instances.py, characters.py, entity_stats.py, campaigns.py
    via get_campaign_context, entities.py, information.py), the
    just-set app.tenant_id is silently lost before any query in this
    request ever uses it. Confirmed via a real end-to-end test using a
    genuine verified token (`raw_client`), not the test suite's normal
    `client` fixture, whose fake get_current_user override never commits
    and so could never have surfaced this. get_tenant_context above has
    never had this problem, purely incidentally - it already took `user`
    for its own membership check.
    """
    if await session.get(Tenant, tenant_id) is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    await set_tenant_rls_context(session, tenant_id)
    return tenant_id


TenantOrNotFound = Annotated[uuid.UUID, Depends(get_tenant_or_404)]


async def get_campaign_context(
    tenant_id: TenantOrNotFound, campaign_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> uuid.UUID:
    """Tenant must exist (get_tenant_or_404 - depended on directly, not just
    called, so FastAPI's per-request dependency caching means a router that
    also depends on get_tenant_or_404 itself doesn't pay for a second
    query), campaign must exist and belong to that tenant, and
    can_access_campaign(...) must be true - all three failures raise the
    *same* CampaignNotFoundError, extending get_tenant_context's existing
    "can't distinguish doesn't-exist from not-a-member" rule (ADR 0023)
    from two cases to three. Returns just campaign_id, mirroring
    get_tenant_context's own return shape - routes needing the full
    Campaign row re-query with their own eager-load chain, the same
    division of labor entities.py's get_entity already uses relative to
    get_entity_or_404. See ADR 0030/RFC 0003.
    """
    not_found = CampaignNotFoundError(
        detail=f"No campaign with id {campaign_id} in tenant {tenant_id}"
    )
    stmt = select(Campaign.id).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
    if (await session.execute(stmt)).first() is None:
        raise not_found
    if not await can_access_campaign(
        session, user_id=user.id, campaign_id=campaign_id, tenant_id=tenant_id
    ):
        raise not_found
    return campaign_id


async def get_entity_or_404(
    session: AsyncSession, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> Entity:
    # WHERE tenant_id = ... in the query itself, not a Python-level check
    # after a plain session.get() - ADR 0020's own explicit rule, matching
    # every route's own eager-loaded lookup.
    stmt = select(Entity).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    entity = (await session.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    return entity
