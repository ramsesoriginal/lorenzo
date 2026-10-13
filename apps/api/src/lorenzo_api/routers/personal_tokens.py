"""Personal access tokens and the device-code flow (ADR 0268).

The two unauthenticated routes (`POST /device-codes` and `.../token`) sit behind the in-process
rate-limit backstop. Everything under `/me` needs an interactive Authgear session: a personal
access token manages nothing about tokens.
"""

import uuid
from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from lorenzo_api.app_links import device_url
from lorenzo_api.config import get_settings
from lorenzo_api.dependencies import InteractiveUser, SessionDep
from lorenzo_api.exceptions import (
    DeviceCodeNotFoundError,
    InvalidTokenExpiryError,
    PersonalTokenNotFoundError,
    TooManyTokensError,
)
from lorenzo_api.models import PersonalAccessToken
from lorenzo_api.personal_tokens import (
    DEVICE_CODE_LIFETIME,
    MAX_ACTIVE_TOKENS,
    POLL_INTERVAL_SECONDS,
    find_pending_by_user_code,
    is_live,
    now,
    redeem_device_code,
    start_device_authorization,
)
from lorenzo_api.rate_limit import enforce_device_lookup_rate_limit, enforce_device_rate_limit
from lorenzo_api.schemas.personal_tokens import (
    DeviceApproval,
    DeviceCodeCreate,
    DeviceCodeOut,
    DeviceCodePreviewOut,
    DeviceTokenRequest,
    PersonalTokenIssuedOut,
    PersonalTokenOut,
)

router = APIRouter(tags=["personal-access-tokens"])
log = structlog.get_logger()


@router.post(
    "/device-codes",
    status_code=201,
    dependencies=[Depends(enforce_device_rate_limit)],
)
async def create_device_code(body: DeviceCodeCreate, session: SessionDep) -> DeviceCodeOut:
    """Unauthenticated. A device asks for a code to be approved by its user (ADR 0268)."""
    device_code, row = await start_device_authorization(session, client_name=body.client_name)
    page = device_url(get_settings()).rstrip("/")
    return DeviceCodeOut(
        device_code=device_code,
        user_code=row.user_code,
        verification_uri=page,
        verification_uri_complete=f"{page}?code={row.user_code}",
        interval=POLL_INTERVAL_SECONDS,
        expires_in=int(DEVICE_CODE_LIFETIME.total_seconds()),
    )


@router.post("/device-codes/token", dependencies=[Depends(enforce_device_rate_limit)])
async def poll_device_code(body: DeviceTokenRequest, session: SessionDep) -> PersonalTokenIssuedOut:
    """Unauthenticated. The device polls; the answers are the RFC 8628 ones, as problems whose
    `type` is `authorization-pending`, `slow-down`, `device-code-expired` or `access-denied`.
    On success the token's secret is in the answer, and nowhere else, once.
    """
    token, secret = await redeem_device_code(session, body.device_code)
    log.info("personal_token_created", token_id=str(token.id), user_id=str(token.user_id))
    return PersonalTokenIssuedOut(
        access_token=secret, id=token.id, name=token.name, expires_at=token.expires_at
    )


@router.get("/me/device-codes/{user_code}")
async def preview_device_code(
    user_code: str, user: InteractiveUser, session: SessionDep
) -> DeviceCodePreviewOut:
    enforce_device_lookup_rate_limit(f"user:{user.id}")
    row = await find_pending_by_user_code(session, user_code)
    if row is None:
        raise DeviceCodeNotFoundError(detail="No pending request has this code.")
    return DeviceCodePreviewOut(
        user_code=row.user_code, client_name=row.client_name, expires_at=row.expires_at
    )


@router.post("/me/device-codes/{user_code}/approve", status_code=204)
async def approve_device_code(
    user_code: str, body: DeviceApproval, user: InteractiveUser, session: SessionDep
) -> Response:
    """Approves the pending request as the caller, with the token's name and optional expiry."""
    enforce_device_lookup_rate_limit(f"user:{user.id}")
    at = now()
    if body.expires_at is not None and body.expires_at <= at + timedelta(minutes=1):
        raise InvalidTokenExpiryError(detail="The token's expiry must be in the future.")
    row = await find_pending_by_user_code(session, user_code)
    if row is None:
        raise DeviceCodeNotFoundError(detail="No pending request has this code.")
    live = (
        await session.scalars(
            select(PersonalAccessToken).where(
                PersonalAccessToken.user_id == user.id, PersonalAccessToken.revoked_at.is_(None)
            )
        )
    ).all()
    if sum(1 for t in live if is_live(t, at)) >= MAX_ACTIVE_TOKENS:
        raise TooManyTokensError(detail=f"At most {MAX_ACTIVE_TOKENS} active tokens; revoke some.")
    row.status = "approved"
    row.user_id = user.id
    row.token_name = body.name.strip() or (row.client_name or "Device")
    row.token_expires_at = body.expires_at
    await session.commit()
    return Response(status_code=204)


@router.post("/me/device-codes/{user_code}/deny", status_code=204)
async def deny_device_code(user_code: str, user: InteractiveUser, session: SessionDep) -> Response:
    enforce_device_lookup_rate_limit(f"user:{user.id}")
    row = await find_pending_by_user_code(session, user_code)
    if row is None:
        raise DeviceCodeNotFoundError(detail="No pending request has this code.")
    row.status = "denied"
    row.user_id = user.id
    await session.commit()
    return Response(status_code=204)


def _out(token: PersonalAccessToken) -> PersonalTokenOut:
    return PersonalTokenOut(
        id=token.id,
        name=token.name,
        hint=token.token_hint,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        expires_at=token.expires_at,
        is_expired=not is_live(token),
    )


@router.get("/me/tokens")
async def list_my_tokens(user: InteractiveUser, session: SessionDep) -> list[PersonalTokenOut]:
    """The caller's tokens that have not been revoked (an expired one is listed, marked)."""
    rows = await session.scalars(
        select(PersonalAccessToken)
        .where(PersonalAccessToken.user_id == user.id, PersonalAccessToken.revoked_at.is_(None))
        .order_by(PersonalAccessToken.created_at.desc())
    )
    return [_out(t) for t in rows]


@router.delete("/me/tokens/{token_id}", status_code=204)
async def revoke_my_token(
    token_id: uuid.UUID, user: InteractiveUser, session: SessionDep
) -> Response:
    token = (
        await session.execute(
            select(PersonalAccessToken).where(
                PersonalAccessToken.id == token_id, PersonalAccessToken.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if token is None:
        raise PersonalTokenNotFoundError(detail="No such token.")
    if token.revoked_at is None:
        token.revoked_at = func.now()
        await session.commit()
        log.info("personal_token_revoked", token_id=str(token.id), user_id=str(user.id))
    return Response(status_code=204)
