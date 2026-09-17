"""GitHub milestone #1's own scenario (docs/architecture/overview.md's
Roadmap; ADR 0038's own Context), played out as one continuous story
entirely through the real HTTP API - every actor authenticated with their
own real, verified JWT (`raw_client`, ADR 0023), not the `client` fixture's
fake `get_current_user` override every other test in this suite uses. Every
piece this exercises already has its own narrower, more targeted test
elsewhere (ADR 0032-0038); this is the one place they all run together, in
the order the milestone actually describes them, proving the whole thing
holds end to end - JWT verification, campaign authorization, RLS, prototype
resolution, containment, ownership, information resolution, and the
underlying SQL projections - rather than only piecewise.

Actor structure exactly as the milestone specifies: Oscar (tenant OWNER of
"The Shattered Realms"), Zorro (GM of "The Ashen Crown" via a CampaignGm
grant, deliberately with no tenant-wide Membership of his own - RFC 0009's
own "a campaign's GM shouldn't need tenant-wide access" case), Xavier (a
Player controlling Alice) and Yvonne (a Player controlling Bob). Oscar never
authors or is granted any Information here - the whole scenario proves his
administrative OWNER role never implies seeing Alice's, Bob's, or the GM's
own secrets (RFC 0009's "administrative access != automatic character/GM
knowledge" principle), exactly by never needing to lean on it for anything
narrative.
"""

from __future__ import annotations

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from httpx import AsyncClient

from lorenzo_api.models import Entity, Tenant, User

# Mirrors dependencies._AUTHGEAR_ROLES_CLAIM (private to that module, and
# this is the only other place that needs the literal claim key) - grants
# Oscar/Uninvited the tenant-creator role (ADR 0033/RFC 0012) via a real
# token, rather than the `client` fixture's fake override every other
# tenant-creation test uses.
_ROLES_CLAIM = "https://authgear.com/claims/user/roles"


async def _provision(raw_client: AsyncClient, headers: dict[str, str]) -> uuid.UUID:
    """GET /me auto-provisions (ADR 0023) and reports the real app_user id
    behind a subject - needed before that subject can be the target of a
    campaign GM grant or a player invite, both of which reference a user_id.
    """
    response = await raw_client.get("/me", headers=headers)
    assert response.status_code == 200
    return uuid.UUID(response.json()["id"])


async def test_milestone_scenario_end_to_end(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    oscar_headers = {
        "Authorization": "Bearer "
        + fake_jwks_server.issue_token(
            f"authgear|oscar-{uuid.uuid4()}", **{_ROLES_CLAIM: ["tenant_creator"]}
        )
    }
    zorro_headers = {
        "Authorization": f"Bearer {fake_jwks_server.issue_token(f'authgear|zorro-{uuid.uuid4()}')}"
    }
    xavier_headers = {
        "Authorization": f"Bearer {fake_jwks_server.issue_token(f'authgear|xavier-{uuid.uuid4()}')}"
    }
    yvonne_headers = {
        "Authorization": f"Bearer {fake_jwks_server.issue_token(f'authgear|yvonne-{uuid.uuid4()}')}"
    }

    oscar_id = await _provision(raw_client, oscar_headers)
    zorro_id = await _provision(raw_client, zorro_headers)
    xavier_id = await _provision(raw_client, xavier_headers)
    yvonne_id = await _provision(raw_client, yvonne_headers)

    # --- "Tenant creates Campaign A." -------------------------------------
    tenant_response = await raw_client.post(
        "/tenants", json={"name": "The Shattered Realms"}, headers=oscar_headers
    )
    assert tenant_response.status_code == 201
    tenant_id = tenant_response.json()["id"]

    campaign_response = await raw_client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "The Ashen Crown",
            "game_system": "D&D 5e",
            "slug": "the-ashen-crown",
            "description": "A campaign of ash and embers.",
        },
        headers=oscar_headers,
    )
    assert campaign_response.status_code == 201
    campaign_id = campaign_response.json()["id"]

    # Zorro GMs the campaign, but holds no tenant-wide Membership of his own
    # (RFC 0009) - granted by Oscar, the tenant OWNER.
    gm_grant_response = await raw_client.put(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{zorro_id}", headers=oscar_headers
    )
    assert gm_grant_response.status_code == 200

    # Zorro (now able to manage his own campaign's roster) invites Xavier
    # and Yvonne as players.
    xavier_player_response = await raw_client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players",
        json={"user_id": str(xavier_id)},
        headers=zorro_headers,
    )
    assert xavier_player_response.status_code == 201
    xavier_player_id = xavier_player_response.json()["id"]

    yvonne_player_response = await raw_client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players",
        json={"user_id": str(yvonne_id)},
        headers=zorro_headers,
    )
    assert yvonne_player_response.status_code == 201
    yvonne_player_id = yvonne_player_response.json()["id"]

    # Xavier and Yvonne each roll their own character, self-service (ADR
    # 0036): touching only their own Player row needs no GM/admin standing.
    alice_response = await raw_client.post(
        f"/tenants/{tenant_id}/characters",
        json={
            "name": "Alice",
            "owner_player_id": xavier_player_id,
            "player_ids": [xavier_player_id],
        },
        headers=xavier_headers,
    )
    assert alice_response.status_code == 201
    alice_id = alice_response.json()["entity_id"]

    bob_response = await raw_client.post(
        f"/tenants/{tenant_id}/characters",
        json={"name": "Bob", "owner_player_id": yvonne_player_id, "player_ids": [yvonne_player_id]},
        headers=yvonne_headers,
    )
    assert bob_response.status_code == 201

    # --- "A generic Sword entity exists. A Flaming Sword prototypes
    # Sword." - authoring the shared catalog is a tenant-admin concern
    # (ADR 0032), so Oscar (OWNER) builds it. -------------------------------
    sword_response = await raw_client.post(
        f"/tenants/{tenant_id}/items", json={"name": "Sword"}, headers=oscar_headers
    )
    assert sword_response.status_code == 201
    sword_id = sword_response.json()["entity_id"]

    flaming_sword_response = await raw_client.post(
        f"/tenants/{tenant_id}/items",
        json={"name": "Flaming Sword", "prototype_ids": [sword_id]},
        headers=oscar_headers,
    )
    assert flaming_sword_response.status_code == 201
    flaming_sword_id = flaming_sword_response.json()["entity_id"]

    # A "weight" stat set only on the generic Sword, two prototype hops away
    # from the concrete instance created below - proving effective stat
    # resolution walks the whole chain (ADR 0037), not just one hop.
    stat_group_response = await raw_client.post(
        f"/tenants/{tenant_id}/stat-groups", json={"name": "physical"}, headers=oscar_headers
    )
    assert stat_group_response.status_code == 201
    physical_group_id = stat_group_response.json()["id"]

    stat_definition_response = await raw_client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": "weight", "stat_group_id": physical_group_id, "value_type": "int"},
        headers=oscar_headers,
    )
    assert stat_definition_response.status_code == 201
    weight_definition_id = stat_definition_response.json()["id"]

    set_weight_response = await raw_client.put(
        f"/tenants/{tenant_id}/entities/{sword_id}/stats/{weight_definition_id}",
        json={"value": 5},
        headers=oscar_headers,
    )
    assert set_weight_response.status_code == 200

    # Alice's own backpack and a chest - bare world furniture, not items in
    # their own right, so built directly (mirroring
    # test_api_item_instances.py's identical test_set_container_moves_item
    # precedent) rather than through a POST /entities endpoint this API
    # deliberately doesn't have.
    async with admin_session_factory() as session:
        backpack = Entity(tenant_id=uuid.UUID(tenant_id), name="Alice's Backpack")
        chest = Entity(tenant_id=uuid.UUID(tenant_id), name="A Sturdy Chest")
        session.add_all([backpack, chest])
        await session.commit()
        backpack_id, chest_id = str(backpack.id), str(chest.id)

    # --- "One concrete sword instance exists. Alice owns it. It is inside
    # Alice's backpack." - Zorro, GM of Alice's own campaign, instantiates
    # it for her (ADR 0032's "assigning to someone else's character" tier).
    ashfang_response = await raw_client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={
            "name": "Ashfang",
            "prototype_id": flaming_sword_id,
            "owner_character_id": alice_id,
            "container_entity_id": backpack_id,
        },
        headers=zorro_headers,
    )
    assert ashfang_response.status_code == 201
    ashfang_body = ashfang_response.json()
    ashfang_id = ashfang_body["entity_id"]
    assert ashfang_body["owner_entity_id"] == alice_id
    assert ashfang_body["container_entity_id"] == backpack_id
    # Inherited through Sword -> Flaming Sword -> Ashfang, two hops away
    # from where it was actually set (ADR 0037).
    assert ashfang_body["weight"] == 5

    # --- "Public information: 'An ornate sword.' Alice knows: 'The sword is
    # magical.' The GM knows: 'The sword is cursed.'" - Zorro, still managing
    # his own campaign's item, authors all three (ADR 0038's self-or-managed
    # tier, deliberately not narrowed per-visibility-tier). ------------------
    public_info_response = await raw_client.post(
        f"/tenants/{tenant_id}/entities/{ashfang_id}/information",
        json={
            "title": "Ashfang",
            "type": "description",
            "is_public": True,
            "content": "An ornate sword with a blackened steel blade.",
        },
        headers=zorro_headers,
    )
    assert public_info_response.status_code == 201

    magic_info_response = await raw_client.post(
        f"/tenants/{tenant_id}/entities/{ashfang_id}/information",
        json={
            "title": "Ashfang's true nature",
            "type": "magic-secret",
            "is_public": False,
            "content": "The sword is magical.",
        },
        headers=zorro_headers,
    )
    assert magic_info_response.status_code == 201
    magic_info_id = magic_info_response.json()["id"]

    # Only Alice's own knowledge needs a real Knowledge row - the GM's own
    # secret below needs none at all, already GM-default (ADR 0028).
    grant_response = await raw_client.put(
        f"/tenants/{tenant_id}/information/{magic_info_id}/knowers/{alice_id}",
        headers=zorro_headers,
    )
    assert grant_response.status_code == 200

    gm_info_response = await raw_client.post(
        f"/tenants/{tenant_id}/entities/{ashfang_id}/information",
        json={
            "title": "Ashfang's curse",
            "type": "gm-note",
            "is_public": False,
            "content": "The sword is cursed.",
        },
        headers=zorro_headers,
    )
    assert gm_info_response.status_code == 201

    # --- The three-observer proof - GET /entities/{id}, not
    # GET /item-instances/{id}: Information's own UniqueConstraint(entity_id,
    # type) forces the public description, Alice's secret, and the GM's
    # secret into three distinct rows, and only the entities endpoint's
    # unfiltered-by-type `information` list surfaces all three at once (ADR
    # 0038's own documented reason for using this endpoint over the
    # single-canonical-description item-instance view). -------------------

    def _types_and_contents(entity_body: dict[str, object]) -> dict[str, str]:
        information = entity_body["information"]
        assert isinstance(information, list)
        return {info["type"]: info["payloads"][0]["content"] for info in information}

    # "GET item as Alice: sees magical, does not see cursed" - Xavier
    # controls Alice directly.
    alice_view_response = await raw_client.get(
        f"/tenants/{tenant_id}/entities/{ashfang_id}", headers=xavier_headers
    )
    assert alice_view_response.status_code == 200
    alice_view = _types_and_contents(alice_view_response.json())
    assert alice_view == {
        "description": "An ornate sword with a blackened steel blade.",
        "magic-secret": "The sword is magical.",
    }

    # "GET item as Bob: sees neither" - Yvonne controls Bob, who has no
    # Knowledge grant at all.
    bob_view_response = await raw_client.get(
        f"/tenants/{tenant_id}/entities/{ashfang_id}", headers=yvonne_headers
    )
    assert bob_view_response.status_code == 200
    bob_view = _types_and_contents(bob_view_response.json())
    assert bob_view == {"description": "An ornate sword with a blackened steel blade."}

    # "GET item as GM: sees everything" - Zorro's gm_reachable_entity_ids
    # (RFC 0009/ADR 0035) covers Ashfang through Alice's own roster spot in
    # his campaign, entirely independently of any Knowledge row.
    gm_view_response = await raw_client.get(
        f"/tenants/{tenant_id}/entities/{ashfang_id}", headers=zorro_headers
    )
    assert gm_view_response.status_code == 200
    gm_view = _types_and_contents(gm_view_response.json())
    assert gm_view == {
        "description": "An ornate sword with a blackened steel blade.",
        "magic-secret": "The sword is magical.",
        "gm-note": "The sword is cursed.",
    }

    # --- "Alice moves the sword into a chest. Effective stats still inherit
    # correctly." - Xavier, self-service (Ashfang is still reachable from
    # his own character Alice, regardless of which container it's in). -----
    move_response = await raw_client.put(
        f"/tenants/{tenant_id}/item-instances/{ashfang_id}/container",
        json={"container_entity_id": chest_id},
        headers=xavier_headers,
    )
    assert move_response.status_code == 200
    moved_body = move_response.json()
    assert moved_body["container_entity_id"] == chest_id
    assert moved_body["owner_entity_id"] == alice_id
    assert moved_body["weight"] == 5

    # Visibility is unaffected by the move - same three-observer shape as
    # before, re-checked to guard against container state ever leaking into
    # information_visibility's own resolution.
    bob_view_after_move = _types_and_contents(
        (
            await raw_client.get(
                f"/tenants/{tenant_id}/entities/{ashfang_id}", headers=yvonne_headers
            )
        ).json()
    )
    assert bob_view_after_move == {"description": "An ornate sword with a blackened steel blade."}
    gm_view_after_move = _types_and_contents(
        (
            await raw_client.get(
                f"/tenants/{tenant_id}/entities/{ashfang_id}", headers=zorro_headers
            )
        ).json()
    )
    assert set(gm_view_after_move) == {"description", "magic-secret", "gm-note"}

    # --- "No other tenant can see any row involved." - a second tenant,
    # administered by a totally unrelated user, must 404 reaching for
    # Ashfang through its own path - RLS plus the explicit tenant_id filter
    # every query in this codebase already carries (ADR 0002/0021), not just
    # an authorization-layer coincidence. -----------------------------------
    uninvited_headers = {
        "Authorization": "Bearer "
        + fake_jwks_server.issue_token(
            f"authgear|uninvited-{uuid.uuid4()}", **{_ROLES_CLAIM: ["tenant_creator"]}
        )
    }
    uninvited_id = await _provision(raw_client, uninvited_headers)
    other_tenant_response = await raw_client.post(
        "/tenants", json={"name": "An Unrelated World"}, headers=uninvited_headers
    )
    assert other_tenant_response.status_code == 201
    other_tenant_id = other_tenant_response.json()["id"]

    cross_tenant_response = await raw_client.get(
        f"/tenants/{other_tenant_id}/entities/{ashfang_id}", headers=uninvited_headers
    )
    assert cross_tenant_response.status_code == 404

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, uuid.UUID(tenant_id)))
        await session.delete(await session.get_one(Tenant, uuid.UUID(other_tenant_id)))
        await session.commit()
        for user_id in (oscar_id, zorro_id, xavier_id, yvonne_id, uninvited_id):
            await session.delete(await session.get_one(User, user_id))
        await session.commit()
