"""An in-process token-bucket rate limiter - ADR 0092's *backstop* for the
two public invite-link routes, not the control.

Each Cloud Run instance keeps its own buckets, so this only limits every
instance separately. The real control is an edge rate-limit rule
(docs/operations/invite-link-rate-limiting.md); this exists so a
misconfigured or missing edge rule does not leave the endpoints entirely
open, and so a single client hammering one instance is slowed regardless.

Pure Python, no I/O, no awaits inside `check` - a single asyncio event loop
never interleaves two callers inside it, so it needs no lock.
"""

import math
import time
from dataclasses import dataclass

import structlog
from fastapi import Request

from lorenzo_api.config import get_settings
from lorenzo_api.exceptions import TooManyRequestsError

# Past this many tracked clients, drop the ones whose bucket has refilled
# completely - they are indistinguishable from a client never seen.
_PRUNE_ABOVE = 10_000


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketLimiter:
    def __init__(self, per_minute: int) -> None:
        self.capacity = float(per_minute)
        self._refill_per_second = per_minute / 60
        self._buckets: dict[str, _Bucket] = {}

    def check(self, key: str, *, now: float | None = None) -> float | None:
        """Spends one token for `key`. Returns None if allowed, otherwise
        the seconds to wait until a token is available again.
        """
        now = time.monotonic() if now is None else now
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = self._buckets[key] = _Bucket(self.capacity, now)
        else:
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self._refill_per_second)
            bucket.updated_at = now

        if bucket.tokens >= 1:
            bucket.tokens -= 1
            if len(self._buckets) > _PRUNE_ABOVE:
                self._prune(now)
            return None
        return (1 - bucket.tokens) / self._refill_per_second

    def _prune(self, now: float) -> None:
        full = [
            key
            for key, bucket in self._buckets.items()
            if bucket.tokens + (now - bucket.updated_at) * self._refill_per_second >= self.capacity
        ]
        for key in full:
            del self._buckets[key]


_limiter: TokenBucketLimiter | None = None


def get_invite_rate_limiter() -> TokenBucketLimiter:
    global _limiter
    if _limiter is None:
        _limiter = TokenBucketLimiter(get_settings().invite_rate_limit_per_minute)
    return _limiter


def reset_invite_rate_limiter() -> None:
    """For tests: forget every bucket and re-read the settings."""
    global _limiter
    _limiter = None


def client_key(request: Request, *, trusted_proxy_hops: int) -> str:
    """Who this request is *from*, for keying the limiter.

    With `trusted_proxy_hops = 0` that is the direct peer. Behind a trusted
    reverse proxy it is the `X-Forwarded-For` entry that many hops from the
    right: the rightmost entry is the address the nearest proxy actually
    saw, and everything to its left is whatever the client chose to send -
    trusting the leftmost entry would let a caller dodge the limiter by
    spoofing the header.
    """
    if trusted_proxy_hops > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [part.strip() for part in forwarded.split(",") if part.strip()]
            if len(parts) >= trusted_proxy_hops:
                return parts[-trusted_proxy_hops]
    return request.client.host if request.client else "unknown"


def request_source(request: Request) -> str:
    """The client address as the limiter sees it - also what a rejected
    invite attempt is logged against (never the token itself).
    """
    return client_key(
        request, trusted_proxy_hops=get_settings().invite_rate_limit_trusted_proxy_hops
    )


async def enforce_invite_rate_limit(request: Request) -> None:
    """FastAPI dependency for the two public invite-link routes. Raises 429
    with `Retry-After` when the caller's bucket is empty; a no-op if the
    limit is configured to 0.
    """
    settings = get_settings()
    if settings.invite_rate_limit_per_minute <= 0:
        return
    key = request_source(request)
    retry_after = get_invite_rate_limiter().check(key)
    if retry_after is not None:
        structlog.get_logger().warning("invite_rate_limited", source=key)
        raise TooManyRequestsError(
            detail="Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )
