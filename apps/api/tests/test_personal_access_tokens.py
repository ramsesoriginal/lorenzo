"""Personal access tokens and the device-code flow (ADR 0268): the whole flow over real token
verification, expiry, revocation, hash-only storage, the rate-limit backstop, a token managing
nothing about tokens, and that a token is its user and nobody else.
"""

import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from conftest import make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text, update

from lorenzo_api import personal_tokens
from lorenzo_api.models import DeviceAuthorization, PersonalAccessToken, User
from lorenzo_api.rate_limit import reset_device_rate_limiters

ROLES = "https://authgear.com/claims/user/roles"


@pytest.fixture(autouse=True)
def _fresh_limiters() -> Iterator[None]:
    reset_device_rate_limiters()
    yield
    reset_device_rate_limiters()


@pytest.fixture
def no_poll_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(personal_tokens, "POLL_INTERVAL_SECONDS", 0)


class Account:
    def __init__(self, client: AsyncClient, jwks: FakeJwksServer, roles: list[str]) -> None:
        self.client = client
        self.jwks = jwks
        self.subject = f"authgear|pat-{uuid.uuid4()}"
        self.roles = roles
        self.user_id: uuid.UUID | None = None

    @property
    def session_headers(self) -> dict[str, str]:
        token = self.jwks.issue_token(self.subject, **{ROLES: self.roles})
        return {"Authorization": f"Bearer {token}"}

    async def sign_in(self) -> None:
        response = await self.client.get("/me", headers=self.session_headers)
        assert response.status_code == 200
        self.user_id = uuid.UUID(response.json()["id"])

    async def connect(
        self, name: str = "Laptop", expires_at: datetime | None = None, client_name: str = "CLI"
    ) -> tuple[str, dict[str, object]]:
        """The whole happy path; returns (secret, issued body)."""
        started = await self.client.post("/device-codes", json={"client_name": client_name})
        assert started.status_code == 201
        flow = started.json()
        body: dict[str, object] = {"name": name}
        if expires_at is not None:
            body["expires_at"] = expires_at.isoformat()
        approved = await self.client.post(
            f"/me/device-codes/{flow['user_code']}/approve",
            json=body,
            headers=self.session_headers,
        )
        assert approved.status_code == 204, approved.text
        issued = await self.client.post(
            "/device-codes/token", json={"device_code": flow["device_code"]}
        )
        assert issued.status_code == 200, issued.text
        return issued.json()["access_token"], issued.json()


@pytest.fixture
async def account(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, no_poll_wait: None
) -> AsyncGenerator[Account]:
    acct = Account(raw_client, fake_jwks_server, ["tenant_creator", "platform-operator"])
    await acct.sign_in()
    yield acct
    async with admin_session_factory() as session:
        if (user := await session.get(User, acct.user_id)) is not None:
            await session.delete(user)
            await session.commit()


def bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


async def test_the_whole_device_flow(account: Account) -> None:
    client = account.client
    started = await client.post("/device-codes", json={"client_name": "lorenzo CLI on laptop"})
    assert started.status_code == 201
    flow = started.json()
    assert len(flow["user_code"]) == 9 and flow["user_code"][4] == "-"
    assert not set(flow["user_code"].replace("-", "")) & set("AEIOU01")
    assert flow["verification_uri"].endswith("/device")
    assert (
        flow["verification_uri_complete"] == f"{flow['verification_uri']}?code={flow['user_code']}"
    )
    assert flow["interval"] > 0 and flow["expires_in"] == 600
    poll = {"device_code": flow["device_code"]}

    pending = await client.post("/device-codes/token", json=poll)
    assert pending.status_code == 400
    assert pending.json()["type"].endswith("authorization-pending")

    preview = await client.get(
        f"/me/device-codes/{flow['user_code'].lower()}", headers=account.session_headers
    )
    assert preview.status_code == 200
    assert preview.json()["client_name"] == "lorenzo CLI on laptop"

    approve = await client.post(
        f"/me/device-codes/{flow['user_code']}/approve",
        json={"name": "Laptop"},
        headers=account.session_headers,
    )
    assert approve.status_code == 204

    issued = await client.post("/device-codes/token", json=poll)
    assert issued.status_code == 200
    body = issued.json()
    assert body["access_token"].startswith("lor_pat_")
    assert body["token_type"] == "Bearer"
    assert body["name"] == "Laptop" and body["expires_at"] is None

    # The secret is shown once: the request is gone.
    again = await client.post("/device-codes/token", json=poll)
    assert again.status_code == 400 and again.json()["type"].endswith("device-code-expired")

    me = await client.get("/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == str(account.user_id)


async def test_polling_too_fast_is_told_to_slow_down(
    account: Account, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(personal_tokens, "POLL_INTERVAL_SECONDS", 60)
    flow = (await account.client.post("/device-codes", json={})).json()
    poll = {"device_code": flow["device_code"]}
    first = await account.client.post("/device-codes/token", json=poll)
    assert first.json()["type"].endswith("authorization-pending")
    second = await account.client.post("/device-codes/token", json=poll)
    assert second.status_code == 400
    assert second.json()["type"].endswith("slow-down")
    assert second.headers["retry-after"] == "60"


async def test_a_denied_request_is_access_denied_and_gives_no_token(account: Account) -> None:
    flow = (await account.client.post("/device-codes", json={})).json()
    deny = await account.client.post(
        f"/me/device-codes/{flow['user_code']}/deny", headers=account.session_headers
    )
    assert deny.status_code == 204
    polled = await account.client.post(
        "/device-codes/token", json={"device_code": flow["device_code"]}
    )
    assert polled.status_code == 400 and polled.json()["type"].endswith("access-denied")
    listed = await account.client.get("/me/tokens", headers=account.session_headers)
    assert listed.json() == []


async def test_an_expired_or_unknown_code_is_expired_and_cannot_be_approved(
    account: Account,
) -> None:
    client = account.client
    flow = (await client.post("/device-codes", json={})).json()
    async with admin_session_factory() as session:
        await session.execute(
            update(DeviceAuthorization)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            .where(DeviceAuthorization.user_code == flow["user_code"])
        )
        await session.commit()
    approve = await client.post(
        f"/me/device-codes/{flow['user_code']}/approve",
        json={"name": "x"},
        headers=account.session_headers,
    )
    assert approve.status_code == 404
    polled = await client.post("/device-codes/token", json={"device_code": flow["device_code"]})
    assert polled.json()["type"].endswith("device-code-expired")
    unknown = await client.post("/device-codes/token", json={"device_code": "nope"})
    assert unknown.json()["type"].endswith("device-code-expired")
    missing = await client.get("/me/device-codes/BCDF-GHJK", headers=account.session_headers)
    assert missing.status_code == 404


async def test_only_the_hash_of_a_secret_is_stored(account: Account) -> None:
    secret, issued = await account.connect()
    async with admin_session_factory() as session:
        row = await session.get_one(PersonalAccessToken, uuid.UUID(issued["id"]))  # type: ignore[arg-type]
        assert row.token_hash == personal_tokens.hash_secret(secret)
        assert secret not in (row.token_hash, row.token_hint, row.name)
        assert row.token_hint == secret[-4:]
        dump = await session.execute(
            text("SELECT count(*) FROM personal_access_token WHERE token_hash = :s"), {"s": secret}
        )
        assert dump.scalar_one() == 0
        left = await session.scalars(
            select(DeviceAuthorization).where(DeviceAuthorization.user_id == account.user_id)
        )
        assert left.all() == []  # the request went with the minting


async def test_a_token_can_be_given_an_expiry_and_stops_working(account: Account) -> None:
    secret, issued = await account.connect(expires_at=datetime.now(UTC) + timedelta(days=30))
    assert issued["expires_at"] is not None
    assert (await account.client.get("/me", headers=bearer(secret))).status_code == 200
    async with admin_session_factory() as session:
        await session.execute(
            update(PersonalAccessToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    expired = await account.client.get("/me", headers=bearer(secret))
    assert expired.status_code == 401
    listed = (await account.client.get("/me/tokens", headers=account.session_headers)).json()
    assert [t["is_expired"] for t in listed] == [True]


async def test_an_expiry_in_the_past_is_refused(account: Account) -> None:
    flow = (await account.client.post("/device-codes", json={})).json()
    response = await account.client.post(
        f"/me/device-codes/{flow['user_code']}/approve",
        json={"name": "x", "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
        headers=account.session_headers,
    )
    assert response.status_code == 422


async def test_revoking_a_token_ends_it_at_once(account: Account) -> None:
    secret, issued = await account.connect(name="Old laptop")
    listed = await account.client.get("/me/tokens", headers=account.session_headers)
    assert [t["name"] for t in listed.json()] == ["Old laptop"]
    assert set(listed.json()[0]) >= {
        "id",
        "name",
        "hint",
        "created_at",
        "last_used_at",
        "expires_at",
    }
    assert "access_token" not in listed.json()[0]

    revoked = await account.client.delete(
        f"/me/tokens/{issued['id']}", headers=account.session_headers
    )
    assert revoked.status_code == 204
    assert (await account.client.get("/me", headers=bearer(secret))).status_code == 401
    assert (await account.client.get("/me/tokens", headers=account.session_headers)).json() == []
    # Revoking again is fine; an unknown id is not.
    again = await account.client.delete(
        f"/me/tokens/{issued['id']}", headers=account.session_headers
    )
    assert again.status_code == 204
    unknown = await account.client.delete(
        f"/me/tokens/{uuid.uuid4()}", headers=account.session_headers
    )
    assert unknown.status_code == 404


async def test_a_wrong_token_is_the_usual_401(account: Account) -> None:
    response = await account.client.get("/me", headers=bearer("lor_pat_" + "x" * 43))
    assert response.status_code == 401


async def test_last_used_moves_at_most_once_per_few_minutes(account: Account) -> None:
    secret, issued = await account.connect()
    token_id = uuid.UUID(issued["id"])  # type: ignore[arg-type]

    async def last_used() -> datetime | None:
        async with admin_session_factory() as session:
            return (await session.get_one(PersonalAccessToken, token_id)).last_used_at

    assert await last_used() is None
    await account.client.get("/me", headers=bearer(secret))
    first = await last_used()
    assert first is not None
    await account.client.get("/me", headers=bearer(secret))
    assert await last_used() == first  # inside the window: not written again
    async with admin_session_factory() as session:
        await session.execute(
            update(PersonalAccessToken).values(last_used_at=first - timedelta(minutes=10))
        )
        await session.commit()
    await account.client.get("/me", headers=bearer(secret))
    later = await last_used()
    assert later is not None and later > first - timedelta(minutes=1)


async def test_a_token_manages_nothing_about_tokens(account: Account) -> None:
    secret, issued = await account.connect()
    client = account.client
    flow = (await client.post("/device-codes", json={})).json()
    code = flow["user_code"]
    for method, url, kwargs in (
        ("GET", f"/me/device-codes/{code}", {}),
        ("POST", f"/me/device-codes/{code}/approve", {"json": {"name": "sneaky"}}),
        ("POST", f"/me/device-codes/{code}/deny", {}),
        ("GET", "/me/tokens", {}),
        ("DELETE", f"/me/tokens/{issued['id']}", {}),
        ("DELETE", "/me", {}),
    ):
        response = await client.request(method, url, headers=bearer(secret), **kwargs)  # type: ignore[arg-type]
        assert response.status_code == 403, (method, url)
        assert response.json()["type"].endswith("personal-token-forbidden")
    # The request it tried to approve is untouched, and the token still works.
    assert (
        await client.get(f"/me/device-codes/{code}", headers=account.session_headers)
    ).status_code == 200
    assert (await client.get("/me", headers=bearer(secret))).status_code == 200


async def test_a_token_carries_tenant_creator_but_never_platform_operator(account: Account) -> None:
    secret, _ = await account.connect()
    me = await account.client.get("/me", headers=bearer(secret))
    assert me.json()["capabilities"]["create_tenant"] is True
    admin = await account.client.get("/admin/users", headers=bearer(secret))
    assert admin.status_code == 403


async def test_a_token_is_its_user_and_nobody_else(
    account: Account, raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    other = Account(raw_client, fake_jwks_server, [])
    await other.sign_in()
    assert account.user_id is not None and other.user_id is not None
    mine = await make_tenant(account.user_id)
    theirs = await make_tenant(other.user_id)
    try:
        secret, _ = await account.connect(name="Mine")
        assert (await raw_client.get(f"/tenants/{mine}", headers=bearer(secret))).status_code == 200
        assert (
            await raw_client.get(f"/tenants/{theirs}", headers=bearer(secret))
        ).status_code == 404
        # Nobody sees anyone's token list but their own.
        assert (await raw_client.get("/me/tokens", headers=other.session_headers)).json() == []
        other_secret, _ = await other.connect(name="Theirs")
        names = [
            t["name"]
            for t in (await raw_client.get("/me/tokens", headers=account.session_headers)).json()
        ]
        assert names == ["Mine"]
        # And cannot revoke each other's.
        mine_id = (await raw_client.get("/me/tokens", headers=account.session_headers)).json()[0][
            "id"
        ]
        stolen = await raw_client.delete(f"/me/tokens/{mine_id}", headers=other.session_headers)
        assert stolen.status_code == 404
        assert (await raw_client.get("/me", headers=bearer(other_secret))).json()["id"] == str(
            other.user_id
        )
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM tenant WHERE id = ANY(:ids)"), {"ids": [mine, theirs]}
            )
            await session.delete(await session.get_one(User, other.user_id))
            await session.commit()


async def test_a_suspended_account_cannot_use_its_token(account: Account) -> None:
    secret, _ = await account.connect()
    async with admin_session_factory() as session:
        await session.execute(
            update(User).where(User.id == account.user_id).values(suspended_at=datetime.now(UTC))
        )
        await session.commit()
    assert (await account.client.get("/me", headers=bearer(secret))).status_code == 403


async def test_the_unauthenticated_routes_are_rate_limited(
    raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVICE_RATE_LIMIT_PER_MINUTE", "3")
    from lorenzo_api.config import get_settings

    get_settings.cache_clear()
    reset_device_rate_limiters()
    try:
        codes = [(await raw_client.post("/device-codes", json={})).status_code for _ in range(3)]
        assert codes == [201, 201, 201]
        limited = await raw_client.post("/device-codes", json={})
        assert limited.status_code == 429 and "retry-after" in limited.headers
        polled = await raw_client.post("/device-codes/token", json={"device_code": "x"})
        assert polled.status_code == 429
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        reset_device_rate_limiters()


async def test_looking_codes_up_is_limited_per_signed_in_user(
    account: Account, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVICE_LOOKUP_RATE_LIMIT_PER_MINUTE", "2")
    from lorenzo_api.config import get_settings

    get_settings.cache_clear()
    reset_device_rate_limiters()
    try:
        statuses = [
            (
                await account.client.get(
                    "/me/device-codes/BCDF-GHJK", headers=account.session_headers
                )
            ).status_code
            for _ in range(3)
        ]
        assert statuses == [404, 404, 429]
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        reset_device_rate_limiters()
