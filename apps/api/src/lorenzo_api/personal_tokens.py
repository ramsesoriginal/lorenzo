"""Personal access tokens and the device-code flow that hands them out (ADR 0268).

A token is `lor_pat_` + 256 random bits; only its SHA-256 is stored, so the lookup is an indexed
equality on the hash and nothing is compared in time. The flow follows RFC 8628: a device asks for
a code, the user approves it signed in, the device polls and receives the secret once. The secret
is never written down before that: the first poll that finds the request approved mints the token
and deletes the request in the same transaction.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import (
    AccessDeniedError,
    AuthorizationPendingError,
    DeviceCodeExpiredError,
    SlowDownError,
)
from lorenzo_api.models import DeviceAuthorization, PersonalAccessToken

TOKEN_PREFIX = "lor_pat_"
# Consonants only (no words, no 0/O/1/I lookalikes): twenty letters, eight of them, ~2.6e10 codes.
USER_CODE_ALPHABET = "BCDFGHJKMNPQRSTVWXYZ"
USER_CODE_LENGTH = 8
DEVICE_CODE_LIFETIME = timedelta(minutes=10)
POLL_INTERVAL_SECONDS = 5
# last_used_at moves at most this often, so a busy token is not one write per request.
LAST_USED_GRANULARITY = timedelta(minutes=5)
MAX_ACTIVE_TOKENS = 50


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_user_code() -> str:
    raw = "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_user_code(code: str) -> str:
    """What a person typed, as stored: upper case, only the alphabet, dashed in the middle."""
    raw = "".join(c for c in code.upper() if c in USER_CODE_ALPHABET)
    return f"{raw[:4]}-{raw[4:]}" if len(raw) == USER_CODE_LENGTH else code.upper()


def is_personal_token(value: str) -> bool:
    return value.startswith(TOKEN_PREFIX)


def now() -> datetime:
    return datetime.now(UTC)


def is_live(token: PersonalAccessToken, at: datetime | None = None) -> bool:
    at = at or now()
    return token.revoked_at is None and (token.expires_at is None or token.expires_at > at)


async def find_live_token(session: AsyncSession, secret: str) -> PersonalAccessToken | None:
    token = (
        await session.execute(
            select(PersonalAccessToken).where(PersonalAccessToken.token_hash == hash_secret(secret))
        )
    ).scalar_one_or_none()
    return token if token is not None and is_live(token) else None


async def touch_last_used(session: AsyncSession, token_id: uuid.UUID) -> None:
    """Moves `last_used_at` forward if it is older than the granularity; one conditional UPDATE."""
    at = now()
    await session.execute(
        update(PersonalAccessToken)
        .where(
            PersonalAccessToken.id == token_id,
            (PersonalAccessToken.last_used_at.is_(None))
            | (PersonalAccessToken.last_used_at < at - LAST_USED_GRANULARITY),
        )
        .values(last_used_at=at)
    )
    await session.commit()


async def start_device_authorization(
    session: AsyncSession, *, client_name: str | None
) -> tuple[str, DeviceAuthorization]:
    """A new pending request. Returns the device code (shown once, only its hash is kept)."""
    device_code = secrets.token_urlsafe(32)
    row = DeviceAuthorization(
        device_code_hash=hash_secret(device_code),
        user_code=new_user_code(),
        client_name=client_name,
        expires_at=now() + DEVICE_CODE_LIFETIME,
    )
    session.add(row)
    await session.commit()
    return device_code, row


async def find_pending_by_user_code(
    session: AsyncSession, user_code: str
) -> DeviceAuthorization | None:
    row = (
        await session.execute(
            select(DeviceAuthorization)
            .where(DeviceAuthorization.user_code == normalize_user_code(user_code))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None or row.status != "pending" or row.expires_at <= now():
        return None
    return row


async def redeem_device_code(
    session: AsyncSession, device_code: str
) -> tuple[PersonalAccessToken, str]:
    """One poll. Raises the RFC 8628 answer for every state but success; on success mints the
    token, deletes the request and returns (token, secret).
    """
    row = (
        await session.execute(
            select(DeviceAuthorization)
            .where(DeviceAuthorization.device_code_hash == hash_secret(device_code))
            .with_for_update()
        )
    ).scalar_one_or_none()
    at = now()
    if row is None:
        raise DeviceCodeExpiredError(detail="This device code is not valid any more.")
    if row.expires_at <= at:
        await session.delete(row)
        await session.commit()
        raise DeviceCodeExpiredError(detail="This device code is not valid any more.")
    too_fast = row.last_polled_at is not None and (
        at - row.last_polled_at < timedelta(seconds=POLL_INTERVAL_SECONDS)
    )
    row.last_polled_at = at
    if too_fast:
        await session.commit()
        raise SlowDownError(
            detail=f"Poll no more often than every {POLL_INTERVAL_SECONDS} seconds.",
            headers={"Retry-After": str(POLL_INTERVAL_SECONDS)},
        )
    if row.status == "pending":
        await session.commit()
        raise AuthorizationPendingError(detail="The request has not been approved yet.")
    if row.status == "denied":
        await session.delete(row)
        await session.commit()
        raise AccessDeniedError(detail="The request was denied.")
    if row.user_id is None or row.token_name is None:  # approved rows always carry both
        raise DeviceCodeExpiredError(detail="This device code is not valid any more.")
    if row.token_expires_at is not None and row.token_expires_at <= at:
        await session.delete(row)
        await session.commit()
        raise DeviceCodeExpiredError(detail="This device code is not valid any more.")

    secret = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token = PersonalAccessToken(
        user_id=row.user_id,
        name=row.token_name,
        token_hash=hash_secret(secret),
        token_hint=secret[-4:],
        expires_at=row.token_expires_at,
    )
    session.add(token)
    await session.delete(row)
    await session.flush()
    await session.refresh(token)
    await session.commit()
    return token, secret
