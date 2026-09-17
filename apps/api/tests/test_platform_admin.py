"""Platform operations - a platform-operator role, admin listing, and
account suspension. See ADR 0057.
"""

import uuid

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from conftest import delete_tenant
from httpx import AsyncClient

from lorenzo_api.dependencies import require_platform_operator_role
from lorenzo_api.exceptions import PlatformOperatorRoleRequiredError
from lorenzo_api.models import Tenant, User

# Mirrors dependencies._AUTHGEAR_ROLES_CLAIM (private to that module) - same
# precedent test_milestone_scenario.py already established for granting a
# role via a real token rather than the `client` fixture's fake override.
_ROLES_CLAIM = "https://authgear.com/claims/user/roles"


async def test_require_platform_operator_role_checks_the_claim_directly() -> None:
    """Tested directly against the predicate, not just through HTTP -
    mirrors test_require_tenant_creator_role_checks_the_claim_directly's
    own precedent (test_api_tenants.py).
    """
    user_with_role = User(authgear_subject_id="has-platform-operator-role")
    user_with_role.authgear_roles = frozenset({"platform-operator"})
    await require_platform_operator_role(user_with_role)  # must not raise

    user_without_role = User(authgear_subject_id="no-roles-at-all")
    user_without_role.authgear_roles = frozenset()
    with pytest.raises(PlatformOperatorRoleRequiredError):
        await require_platform_operator_role(user_without_role)

    user_with_other_roles = User(authgear_subject_id="has-unrelated-roles")
    user_with_other_roles.authgear_roles = frozenset({"tenant-creator"})
    with pytest.raises(PlatformOperatorRoleRequiredError):
        await require_platform_operator_role(user_with_other_roles)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/tenants"),
        ("GET", "/admin/users"),
        ("PUT", "/admin/users/00000000-0000-0000-0000-000000000000/suspend"),
        ("DELETE", "/admin/users/00000000-0000-0000-0000-000000000000/suspend"),
        ("POST", "/admin/notifications"),
    ],
)
async def test_admin_routes_403_without_the_platform_operator_role(
    client: AsyncClient, method: str, path: str
) -> None:
    """`client`'s default role set (tenant-creator only) must not be
    enough - every /admin/* route needs platform-operator specifically.
    """
    response = await client.request(method, path, json={})
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"


async def test_admin_list_tenants_is_platform_wide(
    client_with_platform_operator_role: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Unlike GET /tenants (ADR 0030), this must include a tenant the
    caller has no relationship to at all.
    """
    async with admin_session_factory() as session:
        tenant = Tenant(name="Not My Tenant")
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client_with_platform_operator_role.get("/admin/tenants")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(tenant_id) in ids

    await delete_tenant(tenant_id)


async def test_admin_list_users_browse_and_search(
    client_with_platform_operator_role: AsyncClient,
) -> None:
    unique = uuid.uuid4()
    async with admin_session_factory() as session:
        target = User(
            authgear_subject_id=f"authgear|admin-search-{unique}",
            nickname=f"FindMe-{unique}",
            email=f"findme-{unique}@example.com",
        )
        session.add(target)
        await session.commit()
        target_id = target.id

    # Not asserting the target shows up in the unfiltered, default-paginated
    # list - the shared test-session DB accumulates enough app_user rows
    # across the whole suite that a newly-created (and therefore
    # newest-by-created_at) row isn't guaranteed to land on page one. The
    # `q`-filtered search below is the real point of this test.
    unfiltered_response = await client_with_platform_operator_role.get("/admin/users")
    assert unfiltered_response.status_code == 200

    search_response = await client_with_platform_operator_role.get(
        "/admin/users", params={"q": f"FindMe-{unique}"}
    )
    assert search_response.status_code == 200
    search_ids = {item["id"] for item in search_response.json()["items"]}
    assert search_ids == {str(target_id)}
    assert search_response.json()["items"][0]["email"] == f"findme-{unique}@example.com"

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, target_id))
        await session.commit()


async def test_admin_suspend_and_unsuspend_round_trip(
    client_with_platform_operator_role: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        target = User(authgear_subject_id=f"authgear|to-suspend-{uuid.uuid4()}")
        session.add(target)
        await session.commit()
        target_id = target.id

    suspend_response = await client_with_platform_operator_role.put(
        f"/admin/users/{target_id}/suspend", json={"reason": "spam"}
    )
    assert suspend_response.status_code == 200
    body = suspend_response.json()
    assert body["suspended_at"] is not None
    assert body["suspension_reason"] == "spam"

    async with admin_session_factory() as session:
        row = await session.get_one(User, target_id)
        assert row.suspended_at is not None
        assert row.suspended_by == test_user_id
        assert row.suspension_reason == "spam"

    unsuspend_response = await client_with_platform_operator_role.delete(
        f"/admin/users/{target_id}/suspend"
    )
    assert unsuspend_response.status_code == 200
    assert unsuspend_response.json()["suspended_at"] is None

    async with admin_session_factory() as session:
        row = await session.get_one(User, target_id)
        assert row.suspended_at is None
        assert row.suspended_by is None
        assert row.suspension_reason is None
        await session.delete(row)
        await session.commit()


async def test_admin_unsuspend_is_a_noop_when_not_suspended(
    client_with_platform_operator_role: AsyncClient,
) -> None:
    async with admin_session_factory() as session:
        target = User(authgear_subject_id=f"authgear|never-suspended-{uuid.uuid4()}")
        session.add(target)
        await session.commit()
        target_id = target.id

    response = await client_with_platform_operator_role.delete(f"/admin/users/{target_id}/suspend")
    assert response.status_code == 200
    assert response.json()["suspended_at"] is None

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, target_id))
        await session.commit()


async def test_admin_suspend_404_for_unknown_user(
    client_with_platform_operator_role: AsyncClient,
) -> None:
    response = await client_with_platform_operator_role.put(
        f"/admin/users/{uuid.uuid4()}/suspend", json={}
    )
    assert response.status_code == 404


async def test_suspended_account_is_rejected_on_its_very_next_request(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The actual proof of ADR 0057's central claim: suspension is
    enforced in dependencies.get_current_user itself, not scattered per
    router - a real, logged-in user's *next* request to any route (not
    just future logins) is rejected the moment they're suspended.

    Both the operator and the target use real tokens through `raw_client`
    only - deliberately not `client_with_platform_operator_role`, whose
    `app.dependency_overrides[get_current_user]` is process-global for the
    whole test and would silently short-circuit `raw_client`'s own
    requests too, defeating the point of testing the real enforcement path
    (confirmed the hard way: the target's "rejected" request came back 200,
    because the override was still installed and answered for it instead
    of the real, suspended-checking dependency).
    """
    operator_token = fake_jwks_server.issue_token(
        f"authgear|suspend-operator-{uuid.uuid4()}", **{_ROLES_CLAIM: ["platform-operator"]}
    )
    operator_headers = {"Authorization": f"Bearer {operator_token}"}

    target_token = fake_jwks_server.issue_token(f"authgear|to-be-suspended-{uuid.uuid4()}")
    target_headers = {"Authorization": f"Bearer {target_token}"}

    me_response = await raw_client.get("/me", headers=target_headers)
    assert me_response.status_code == 200
    target_id = uuid.UUID(me_response.json()["id"])

    suspend_response = await raw_client.put(
        f"/admin/users/{target_id}/suspend",
        json={"reason": "under review"},
        headers=operator_headers,
    )
    assert suspend_response.status_code == 200

    rejected_response = await raw_client.get("/me", headers=target_headers)
    assert rejected_response.status_code == 403
    assert rejected_response.headers["content-type"] == "application/problem+json"
    assert "under review" in rejected_response.json()["detail"]

    async with admin_session_factory() as session:
        operator_id = uuid.UUID(
            (await raw_client.get("/me", headers=operator_headers)).json()["id"]
        )
        await session.delete(await session.get_one(User, target_id))
        await session.delete(await session.get_one(User, operator_id))
        await session.commit()
