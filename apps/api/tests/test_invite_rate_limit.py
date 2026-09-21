"""The in-process rate-limit backstop on the public invite-link routes - ADR
0092. It is a backstop, not the control (each instance keeps its own
buckets); the edge rule is the real one. These pin down the bucket
arithmetic, how a client is identified behind a proxy (the spoofing case
especially), and the real HTTP behaviour.
"""

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from starlette.requests import Request

from lorenzo_api.rate_limit import TokenBucketLimiter, client_key, reset_invite_rate_limiter


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> Iterator[None]:
    """Reset before *and after*: several tests here swap in a tiny limit,
    and that limiter must not outlive them for whichever test runs next.
    """
    reset_invite_rate_limiter()
    yield
    reset_invite_rate_limiter()


# --- the bucket ---------------------------------------------------------------


def test_a_bucket_allows_its_capacity_then_says_how_long_to_wait() -> None:
    limiter = TokenBucketLimiter(per_minute=3)

    assert [limiter.check("a", now=0.0) for _ in range(3)] == [None, None, None]
    retry_after = limiter.check("a", now=0.0)

    assert retry_after is not None
    assert retry_after == pytest.approx(20.0)  # 3/minute = one token per 20s


def test_a_bucket_refills_over_time_but_never_past_capacity() -> None:
    limiter = TokenBucketLimiter(per_minute=3)
    for _ in range(3):
        assert limiter.check("a", now=0.0) is None
    assert limiter.check("a", now=0.0) is not None

    assert limiter.check("a", now=20.0) is None  # one token back after 20s
    assert limiter.check("a", now=20.0) is not None

    # A long idle stretch refills to capacity, not beyond it.
    assert [limiter.check("a", now=10_000.0) for _ in range(3)] == [None, None, None]
    assert limiter.check("a", now=10_000.0) is not None


def test_each_client_has_its_own_bucket() -> None:
    limiter = TokenBucketLimiter(per_minute=1)

    assert limiter.check("a", now=0.0) is None
    assert limiter.check("a", now=0.0) is not None
    assert limiter.check("b", now=0.0) is None  # someone else's hammering doesn't touch b


def test_idle_buckets_are_pruned_once_there_are_very_many() -> None:
    limiter = TokenBucketLimiter(per_minute=60)
    for i in range(10_100):
        limiter.check(f"client-{i}", now=0.0)

    # Every one of those has long since refilled; the next call prunes them.
    limiter.check("fresh", now=1_000.0)

    assert len(limiter._buckets) < 10_100  # noqa: SLF001


# --- who is the client --------------------------------------------------------


def _request(*, forwarded: str | None, peer: str = "10.0.0.9") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request(
        {"type": "http", "headers": headers, "client": (peer, 1234), "method": "GET", "path": "/"}
    )


def test_without_a_trusted_proxy_the_direct_peer_is_the_client() -> None:
    assert client_key(_request(forwarded="1.1.1.1"), trusted_proxy_hops=0) == "10.0.0.9"


def test_behind_one_trusted_proxy_the_rightmost_entry_is_the_client() -> None:
    request = _request(forwarded="203.0.113.7")

    assert client_key(request, trusted_proxy_hops=1) == "203.0.113.7"


def test_a_spoofed_leftmost_entry_is_ignored() -> None:
    """Entries to the left of the proxy's own are whatever the client chose
    to send. Trusting the leftmost would let anyone dodge the limiter by
    rotating a fake header value; the rightmost is what the proxy saw.
    """
    request = _request(forwarded="6.6.6.6, 203.0.113.7")

    assert client_key(request, trusted_proxy_hops=1) == "203.0.113.7"


def test_two_trusted_hops_read_the_second_from_the_right() -> None:
    request = _request(forwarded="6.6.6.6, 203.0.113.7, 198.51.100.2")

    assert client_key(request, trusted_proxy_hops=2) == "203.0.113.7"


def test_a_header_shorter_than_the_trusted_hops_falls_back_to_the_peer() -> None:
    assert client_key(_request(forwarded="203.0.113.7"), trusted_proxy_hops=3) == "10.0.0.9"
    assert client_key(_request(forwarded=None), trusted_proxy_hops=1) == "10.0.0.9"


# --- over HTTP ----------------------------------------------------------------


def _settings(monkeypatch: pytest.MonkeyPatch, *, per_minute: int, hops: int = 0) -> None:
    monkeypatch.setattr(
        "lorenzo_api.rate_limit.get_settings",
        lambda: SimpleNamespace(
            invite_rate_limit_per_minute=per_minute, invite_rate_limit_trusted_proxy_hops=hops
        ),
    )
    reset_invite_rate_limiter()


async def test_the_public_routes_return_429_with_retry_after(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings(monkeypatch, per_minute=3)

    statuses = [(await client.get("/invites/nope")).status_code for _ in range(3)]
    limited = await client.get("/invites/nope")
    limited_redeem = await client.post("/invites/nope/redeem")

    assert statuses == [404, 404, 404]
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    assert limited.json()["type"] == "too-many-requests"
    assert limited_redeem.status_code == 429  # one bucket per client, across both routes


async def test_a_different_client_behind_the_proxy_gets_its_own_bucket(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings(monkeypatch, per_minute=1, hops=1)

    first = await client.get("/invites/nope", headers={"x-forwarded-for": "203.0.113.7"})
    second = await client.get("/invites/nope", headers={"x-forwarded-for": "203.0.113.7"})
    other = await client.get("/invites/nope", headers={"x-forwarded-for": "198.51.100.9"})
    # Same real client, new spoofed leftmost entry: still the same bucket.
    spoofed = await client.get("/invites/nope", headers={"x-forwarded-for": "6.6.6.6, 203.0.113.7"})

    assert (first.status_code, second.status_code) == (404, 429)
    assert other.status_code == 404
    assert spoofed.status_code == 429


async def test_a_limit_of_zero_disables_the_backstop(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings(monkeypatch, per_minute=0)

    statuses = {(await client.get("/invites/nope")).status_code for _ in range(10)}

    assert statuses == {404}
