import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient

from lorenzo_api.dependencies import require_tenant_creator_role
from lorenzo_api.etag import etag_for
from lorenzo_api.exceptions import TenantCreationForbiddenError
from lorenzo_api.models import CampaignGm, Membership, MembershipRole, Player, Tenant, User


async def test_list_tenants_includes_every_relationship_kind_with_correct_role(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0030/RFC 0003: GET /tenants answers "every tenant I belong to in
    *any* capacity" - a Membership row (role reported directly), a Player
    row, or a CampaignGm row (both report "participant", since neither is a
    tenant-wide role).
    """
    async with admin_session_factory() as session:
        owner_tenant = Tenant(name="Owner Tenant")
        participant_tenant = Tenant(name="Participant Tenant")
        gm_tenant = Tenant(name="GM Tenant")
        session.add_all([owner_tenant, participant_tenant, gm_tenant])
        await session.flush()
        session.add(
            Membership(tenant_id=owner_tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        campaign = await make_campaign(session, tenant_id=participant_tenant.id)
        session.add(
            Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=participant_tenant.id)
        )

        gm_campaign = await make_campaign(session, tenant_id=gm_tenant.id, name="GM Campaign")
        session.add(
            CampaignGm(tenant_id=gm_tenant.id, user_id=test_user_id, campaign_id=gm_campaign.id)
        )
        await session.commit()
        owner_id, participant_id, gm_id = owner_tenant.id, participant_tenant.id, gm_tenant.id

    response = await client.get("/tenants")
    assert response.status_code == 200
    role_by_id = {item["id"]: item["role"] for item in response.json()["items"]}
    assert role_by_id[str(owner_id)] == "owner"
    assert role_by_id[str(participant_id)] == "participant"
    assert role_by_id[str(gm_id)] == "participant"

    await delete_tenant(owner_id)
    await delete_tenant(participant_id)
    await delete_tenant(gm_id)


async def test_list_tenants_excludes_tenants_with_no_relationship(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        unrelated = Tenant()
        session.add(unrelated)
        await session.commit()
        unrelated_id = unrelated.id

    response = await client.get("/tenants")
    assert response.status_code == 200
    assert str(unrelated_id) not in {item["id"] for item in response.json()["items"]}

    await delete_tenant(unrelated_id)


async def test_get_tenant_returns_detail_for_a_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant(name="Detail Tenant", description="A world.")
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.ORGA))
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(tenant_id)
    assert body["name"] == "Detail Tenant"
    assert body["description"] == "A world."
    assert "slug" in body

    await delete_tenant(tenant_id)


async def test_get_tenant_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        other_user = User(authgear_subject_id=f"authgear|not-a-member-{uuid.uuid4()}")
        session.add_all([tenant, other_user])
        await session.commit()
        tenant_id, other_user_id = tenant.id, other_user.id

    response = await client.get(f"/tenants/{tenant_id}")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, other_user_id))
        await session.commit()


async def test_get_tenant_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get("/tenants/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_list_tenant_roster_includes_membership_player_and_gm_kinds(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0031/RFC 0004: broadened from a pure membership list to the
    tenant's full roster - one row per relationship, not per user.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        campaign = await make_campaign(session, tenant_id=tenant_id)
        player_user = User(authgear_subject_id=f"authgear|roster-player-{uuid.uuid4()}")
        session.add(player_user)
        await session.flush()
        session.add(Player(user_id=player_user.id, campaign_id=campaign.id, tenant_id=tenant_id))

        gm_user = User(authgear_subject_id=f"authgear|roster-gm-{uuid.uuid4()}")
        session.add(gm_user)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user.id, campaign_id=campaign.id))
        await session.commit()
        player_user_id, gm_user_id = player_user.id, gm_user.id

    response = await client.get(f"/tenants/{tenant_id}/memberships")
    assert response.status_code == 200
    entries_by_user = {item["user_id"]: item for item in response.json()["items"]}

    owner_entry = entries_by_user[str(test_user_id)]
    assert owner_entry["kind"] == "membership"
    assert owner_entry["role"] == "owner"

    player_entry = entries_by_user[str(player_user_id)]
    assert player_entry["kind"] == "player"
    assert player_entry["campaign_id"] == str(campaign.id)
    assert player_entry["characters"] == []

    gm_entry = entries_by_user[str(gm_user_id)]
    assert gm_entry["kind"] == "gm"
    assert gm_entry["campaign_id"] == str(campaign.id)

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, player_user_id))
        await session.delete(await session.get_one(User, gm_user_id))
        await session.commit()


async def test_list_tenant_roster_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/memberships")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_require_tenant_creator_role_checks_the_claim_directly() -> None:
    """ADR 0033/RFC 0012 - tested directly against the predicate, not just
    through HTTP, mirroring test_campaign_gm_and_access.py's own precedent
    for testing an authorization predicate in isolation.
    """
    user_with_role = User(authgear_subject_id="has-tenant-creator-role")
    user_with_role.authgear_roles = frozenset({"tenant-creator"})
    await require_tenant_creator_role(user_with_role)  # must not raise

    user_without_role = User(authgear_subject_id="no-roles-at-all")
    user_without_role.authgear_roles = frozenset()
    with pytest.raises(TenantCreationForbiddenError):
        await require_tenant_creator_role(user_without_role)

    user_with_other_roles = User(authgear_subject_id="has-unrelated-roles")
    user_with_other_roles.authgear_roles = frozenset({"some-other-role"})
    with pytest.raises(TenantCreationForbiddenError):
        await require_tenant_creator_role(user_with_other_roles)


async def test_create_tenant_creates_owner_membership_and_sets_attribution(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0033/RFC 0012: one transaction creates the Tenant row and a
    Membership(role=OWNER) for the caller - checked directly against the DB,
    not just the response body.
    """
    response = await client.post("/tenants", json={"name": "The Shattered Realms"})

    assert response.status_code == 201
    body = response.json()
    tenant_id = uuid.UUID(body["id"])
    assert body["name"] == "The Shattered Realms"
    assert body["slug"] == "the-shattered-realms"
    assert body["description"] == ""
    assert body["created_by"] == str(test_user_id)
    assert body["updated_by"] == str(test_user_id)
    assert response.headers["location"].endswith(f"/tenants/{tenant_id}")

    async with admin_session_factory() as session:
        membership = await session.get(Membership, (tenant_id, test_user_id))
        assert membership is not None
        assert membership.role == MembershipRole.OWNER

    await delete_tenant(tenant_id)


async def test_create_tenant_403_without_tenant_creator_role(
    client_without_tenant_creator_role: AsyncClient,
) -> None:
    response = await client_without_tenant_creator_role.post(
        "/tenants", json={"name": "Forbidden World"}
    )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"


async def test_create_tenant_slug_auto_suffixed_on_collision(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """my-world, my-world-2, my-world-3, ... - creating a tenant never
    fails just because someone already picked a similar name.
    """
    first = await client.post("/tenants", json={"name": "Same Name"})
    second = await client.post("/tenants", json={"name": "Same Name"})
    third = await client.post("/tenants", json={"name": "Same Name"})

    assert first.status_code == second.status_code == third.status_code == 201
    assert first.json()["slug"] == "same-name"
    assert second.json()["slug"] == "same-name-2"
    assert third.json()["slug"] == "same-name-3"

    await delete_tenant(uuid.UUID(first.json()["id"]))
    await delete_tenant(uuid.UUID(second.json()["id"]))
    await delete_tenant(uuid.UUID(third.json()["id"]))


async def test_create_tenant_explicit_slug_used_as_is(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    response = await client.post("/tenants", json={"name": "Whatever", "slug": "custom-slug"})

    assert response.status_code == 201
    assert response.json()["slug"] == "custom-slug"

    await delete_tenant(uuid.UUID(response.json()["id"]))


async def test_create_tenant_explicit_slug_conflict_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """An explicit slug never gets auto-suffixed on collision, unlike an
    omitted one - silently rewriting an explicit choice would be the wrong
    failure mode.
    """
    first = await client.post("/tenants", json={"name": "A", "slug": "shattered-realms"})
    assert first.status_code == 201

    second = await client.post("/tenants", json={"name": "B", "slug": "shattered-realms"})
    assert second.status_code == 409
    assert second.headers["content-type"] == "application/problem+json"

    await delete_tenant(uuid.UUID(first.json()["id"]))


async def test_create_tenant_description_defaults_to_empty_string(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    response = await client.post("/tenants", json={"name": "X", "description": "A world of ash."})

    assert response.status_code == 201
    assert response.json()["description"] == "A world of ash."

    await delete_tenant(uuid.UUID(response.json()["id"]))


async def test_create_tenant_rejects_malformed_explicit_slug(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    response = await client.post("/tenants", json={"name": "X", "slug": "Not A Slug!"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_update_tenant_renames_and_stamps_updated_by(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(f"/tenants/{tenant_id}", json={"name": "New Name"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["updated_by"] == str(test_user_id)

    await delete_tenant(tenant_id)


async def test_update_tenant_does_not_regenerate_slug(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """RFC 0012: slug/name are independent once a tenant exists - renaming
    never regenerates the slug, a link nobody asked to break shouldn't
    break as a side effect of an unrelated rename.
    """
    tenant_id = await make_tenant(test_user_id)
    original_slug = (await client.get(f"/tenants/{tenant_id}")).json()["slug"]

    response = await client.patch(f"/tenants/{tenant_id}", json={"name": "Renamed Only"})

    assert response.status_code == 200
    assert response.json()["slug"] == original_slug

    await delete_tenant(tenant_id)


async def test_update_tenant_slug_conflict_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Changing slug via PATCH goes through the same explicit-collision-
    check path POST uses - no auto-suffix.
    """
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    taken_slug = (await client.get(f"/tenants/{tenant_a}")).json()["slug"]

    response = await client.patch(f"/tenants/{tenant_b}", json={"slug": taken_slug})

    assert response.status_code == 409
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_update_tenant_description(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}", json={"description": "A newly-described world."}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "A newly-described world."
    assert body["updated_by"] == str(test_user_id)

    await delete_tenant(tenant_id)


async def test_update_tenant_slug_change_succeeds_when_available(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(f"/tenants/{tenant_id}", json={"slug": "brand-new-slug"})

    assert response.status_code == 200
    assert response.json()["slug"] == "brand-new-slug"

    await delete_tenant(tenant_id)


async def test_update_tenant_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}",
        json={"name": "New Name"},
        headers={"If-Match": 'W/"stale"'},
    )

    assert response.status_code == 412
    await delete_tenant(tenant_id)


async def test_update_tenant_succeeds_with_correct_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        tenant = await session.get_one(Tenant, tenant_id)
        current_etag = etag_for(tenant.updated_at)

    response = await client.patch(
        f"/tenants/{tenant_id}",
        json={"name": "New Name"},
        headers={"If-Match": current_etag},
    )

    assert response.status_code == 200
    await delete_tenant(tenant_id)


async def test_update_tenant_with_no_fields_leaves_updated_by_untouched(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A no-op PATCH (empty body) must not stamp a new editor - ADR 0029's
    own rule that updated_by tracks a real write, not merely a request.
    """
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(f"/tenants/{tenant_id}", json={})

    assert response.status_code == 200
    assert response.json()["updated_by"] is None

    await delete_tenant(tenant_id)
