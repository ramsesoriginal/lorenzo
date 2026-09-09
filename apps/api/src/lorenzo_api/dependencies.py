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
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.config import get_settings
from lorenzo_api.db import get_db_session
from lorenzo_api.exceptions import EntityNotFoundError, InvalidTokenError, TenantNotFoundError
from lorenzo_api.models import Entity, Membership, Tenant, User

__all__ = [
    "CurrentUser",
    "ParamsDep",
    "SessionDep",
    "TenantId",
    "get_current_user",
    "get_entity_or_404",
    "get_jwks_client",
    "get_tenant_context",
    "verify_token",
]

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
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


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
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )
    return tenant_id


TenantId = Annotated[uuid.UUID, Depends(get_tenant_context)]


async def get_entity_or_404(
    session: AsyncSession, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> Entity:
    entity = await session.get(Entity, entity_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    return entity
