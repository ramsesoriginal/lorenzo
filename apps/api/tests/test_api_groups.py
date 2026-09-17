import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Character,
    CharacterPlayer,
    Entity,
    GroupMember,
    Membership,
    Player,
    Tenant,
    User,
)


async def test_list_groups_returns_distinct_group_entities(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0045: a group is any entity with at least one GroupMember row
    naming it - DISTINCT so a group with two members appears once, not
    once per member.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        goblins = Entity(tenant_id=tenant_id, name="Goblins")
        thieves_guild = Entity(tenant_id=tenant_id, name="Thieves' Guild")
        not_a_group = Entity(tenant_id=tenant_id, name="Just an Entity")
        session.add_all([goblins, thieves_guild, not_a_group])
        await session.flush()
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        session.add_all(
            [
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=alice.entity_id,
                    tenant_id=tenant_id,
                ),
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=bob.entity_id,
                    tenant_id=tenant_id,
                ),
                GroupMember(
                    group_entity_id=thieves_guild.id,
                    character_entity_id=alice.entity_id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        goblins_id, thieves_guild_id, not_a_group_id = goblins.id, thieves_guild.id, not_a_group.id

    response = await client.get(f"/tenants/{tenant_id}/groups")

    assert response.status_code == 200
    group_ids = {item["id"] for item in response.json()["items"]}
    assert group_ids == {str(goblins_id), str(thieves_guild_id)}
    assert str(not_a_group_id) not in group_ids

    await delete_tenant(tenant_id)


async def test_list_group_members_returns_characters(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        goblins = Entity(tenant_id=tenant_id, name="Goblins")
        session.add(goblins)
        await session.flush()
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        session.add_all(
            [
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=alice.entity_id,
                    tenant_id=tenant_id,
                ),
                GroupMember(
                    group_entity_id=goblins.id,
                    character_entity_id=bob.entity_id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        await session.commit()
        goblins_id = goblins.id
        alice_id, bob_id = alice.entity_id, bob.entity_id

    response = await client.get(f"/tenants/{tenant_id}/groups/{goblins_id}/members")

    assert response.status_code == 200
    member_ids = {item["id"] for item in response.json()}
    assert member_ids == {str(alice_id), str(bob_id)}

    await delete_tenant(tenant_id)


async def test_list_group_members_empty_list_for_a_real_entity_with_no_members(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0045: unlike ADR 0040's item-instance precedent, "exists but has
    no members" stays a distinguishable 200/[] here, not collapsed into a
    404 - a group's bare existence isn't a secret.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Just an Entity")
        session.add(entity)
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/groups/{entity_id}/members")

    assert response.status_code == 200
    assert response.json() == []

    await delete_tenant(tenant_id)


async def test_list_group_members_404_for_unknown_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/groups/00000000-0000-0000-0000-000000000000/members"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_list_groups_404_for_non_participant(client: AsyncClient) -> None:
    """No test_user_id fixture use at all - an authenticated caller with
    zero standing in this tenant (no Membership/Player/CampaignGm row)
    can't browse its groups, mirroring routers/item_instances.py's
    identical _require_participant precedent.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/groups")

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def _make_own_character(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, campaign_id: uuid.UUID
) -> Character:
    """A Player+Character+CharacterPlayer roster link for user_id
    specifically - mirrors test_api_item_instances.py's identical helper,
    duplicated here rather than shared since these are private, per-file
    test fixtures.
    """
    player = Player(user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id)
    session.add(player)
    await session.flush()
    character = await make_character(session, tenant_id=tenant_id, owner_player_id=player.id)
    session.add(
        CharacterPlayer(
            character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
        )
    )
    await session.flush()
    return character


async def _make_cross_campaign_fixture(
    tenant_id: uuid.UUID, *, test_user_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """test_user_id's own character (Alice, Campaign A) plus a character
    rostered only in a separate Campaign B test_user_id has no standing
    over (Bob) - mirrors test_api_item_instances.py's own
    _make_cross_owner_fixture shape. Alice's Player row also keeps
    test_user_id a tenant participant (require_tenant_participant) even
    after _downgrade_from_tenant_owner below removes its Membership row,
    without granting any standing over Bob specifically. Returns
    (alice_character_entity_id, bob_character_entity_id, bob_user_id) -
    the last for callers to clean up after delete_tenant (a Tenant delete
    doesn't cascade to User, ADR 0022).
    """
    async with admin_session_factory() as session:
        campaign_a = await make_campaign(session, tenant_id=tenant_id, name="Campaign A")
        campaign_b = await make_campaign(session, tenant_id=tenant_id, name="Campaign B")
        await session.flush()
        alice = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_a.id
        )

        bob_user = User(authgear_subject_id=f"bob-{uuid.uuid4()}")
        session.add(bob_user)
        await session.flush()
        bob_player = Player(user_id=bob_user.id, campaign_id=campaign_b.id, tenant_id=tenant_id)
        session.add(bob_player)
        await session.flush()
        bob = await make_character(
            session, tenant_id=tenant_id, name="Bob", owner_player_id=bob_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=bob.entity_id, player_id=bob_player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        return alice.entity_id, bob.entity_id, bob_user.id


async def _downgrade_from_tenant_owner(tenant_id: uuid.UUID, *, test_user_id: uuid.UUID) -> None:
    """can_manage_any_campaign_in_tenant's own tenant-OWNER/ORGA bypass
    would otherwise give test_user_id a free pass over any character in
    the tenant, defeating the point of _make_cross_campaign_fixture above -
    mirrors test_api_item_instances.py's identical downgrade precedent.
    """
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        await session.commit()


async def test_create_group_with_initial_members(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        await session.commit()
        alice_id = alice.entity_id

    response = await client.post(
        f"/tenants/{tenant_id}/groups",
        json={"name": "The Party", "member_character_ids": [str(alice_id)]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "The Party"
    assert "Location" in response.headers
    assert response.headers["Location"].endswith(f"/tenants/{tenant_id}/groups/{body['id']}")

    members_response = await client.get(f"/tenants/{tenant_id}/groups/{body['id']}/members")
    assert {m["id"] for m in members_response.json()} == {str(alice_id)}

    await delete_tenant(tenant_id)


async def test_create_group_422_for_unknown_character_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/groups",
        json={
            "name": "The Party",
            "member_character_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_create_group_403_for_uncontrolled_initial_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    _, bob_id, bob_user_id = await _make_cross_campaign_fixture(
        tenant_id, test_user_id=test_user_id
    )
    await _downgrade_from_tenant_owner(tenant_id, test_user_id=test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/groups",
        json={"name": "The Party", "member_character_ids": [str(bob_id)]},
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_get_group_404_for_unknown_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(f"/tenants/{tenant_id}/groups/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_update_group_renames_and_honors_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    create_response = await client.post(f"/tenants/{tenant_id}/groups", json={"name": "Goblins"})
    group_id = create_response.json()["id"]
    etag = create_response.headers["ETag"]

    stale = await client.patch(
        f"/tenants/{tenant_id}/groups/{group_id}",
        json={"name": "Renamed Twice"},
        headers={"If-Match": 'W/"stale"'},
    )
    assert stale.status_code == 412

    response = await client.patch(
        f"/tenants/{tenant_id}/groups/{group_id}",
        json={"name": "Goblin Warband"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Goblin Warband"

    await delete_tenant(tenant_id)


async def test_delete_group_removes_membership_but_keeps_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """See ADR 0064: DELETE ungroups everyone but deliberately doesn't
    delete the underlying Entity - it might have other roles.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        await session.commit()
        alice_id = alice.entity_id

    create_response = await client.post(
        f"/tenants/{tenant_id}/groups",
        json={"name": "Goblins", "member_character_ids": [str(alice_id)]},
    )
    group_id = create_response.json()["id"]

    delete_response = await client.delete(f"/tenants/{tenant_id}/groups/{group_id}")
    assert delete_response.status_code == 204

    # Idempotent - deleting an already-empty group is a no-op, not a 404.
    second_delete = await client.delete(f"/tenants/{tenant_id}/groups/{group_id}")
    assert second_delete.status_code == 204

    members_response = await client.get(f"/tenants/{tenant_id}/groups/{group_id}/members")
    assert members_response.json() == []

    # The entity itself survives - GET /groups/{id} is really just
    # GET-the-entity, unaware group membership has been fully emptied.
    get_response = await client.get(f"/tenants/{tenant_id}/groups/{group_id}")
    assert get_response.status_code == 200

    await delete_tenant(tenant_id)


async def test_add_and_remove_group_member_are_idempotent(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        await session.commit()
        alice_id = alice.entity_id
    group_id = (await client.post(f"/tenants/{tenant_id}/groups", json={"name": "Goblins"})).json()[
        "id"
    ]

    first_add = await client.put(f"/tenants/{tenant_id}/groups/{group_id}/members/{alice_id}")
    assert first_add.status_code == 200
    assert {m["id"] for m in first_add.json()} == {str(alice_id)}

    second_add = await client.put(f"/tenants/{tenant_id}/groups/{group_id}/members/{alice_id}")
    assert second_add.status_code == 200
    assert {m["id"] for m in second_add.json()} == {str(alice_id)}

    first_remove = await client.delete(f"/tenants/{tenant_id}/groups/{group_id}/members/{alice_id}")
    assert first_remove.status_code == 200
    assert first_remove.json() == []

    second_remove = await client.delete(
        f"/tenants/{tenant_id}/groups/{group_id}/members/{alice_id}"
    )
    assert second_remove.status_code == 200
    assert second_remove.json() == []

    await delete_tenant(tenant_id)


async def test_add_group_member_422_for_self_loop(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """See ADR 0064: an entity can't be a member of its own group - checked
    even though this is only reachable if the group entity also happens to
    have a Character row (RFC 0001 allows an entity more than one role).
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        session.add(
            GroupMember(
                group_entity_id=alice.entity_id,
                character_entity_id=bob.entity_id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        alice_id = alice.entity_id

    response = await client.put(f"/tenants/{tenant_id}/groups/{alice_id}/members/{alice_id}")

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_add_group_member_403_for_uncontrolled_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    _, bob_id, bob_user_id = await _make_cross_campaign_fixture(
        tenant_id, test_user_id=test_user_id
    )
    group_id = (await client.post(f"/tenants/{tenant_id}/groups", json={"name": "Goblins"})).json()[
        "id"
    ]
    await _downgrade_from_tenant_owner(tenant_id, test_user_id=test_user_id)

    response = await client.put(f"/tenants/{tenant_id}/groups/{group_id}/members/{bob_id}")

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_bulk_add_group_members_reports_mixed_outcomes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0064: never all-or-nothing - an uncontrolled character and a
    nonexistent one don't stop a legitimate member from being added.
    """
    tenant_id = await make_tenant(test_user_id)
    alice_id, bob_id, bob_user_id = await _make_cross_campaign_fixture(
        tenant_id, test_user_id=test_user_id
    )
    group_id = (await client.post(f"/tenants/{tenant_id}/groups", json={"name": "Goblins"})).json()[
        "id"
    ]
    await _downgrade_from_tenant_owner(tenant_id, test_user_id=test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/groups/{group_id}/members/bulk",
        json=[str(alice_id), str(bob_id), "00000000-0000-0000-0000-000000000000"],
    )

    assert response.status_code == 200
    results = {r["character_entity_id"]: r for r in response.json()}
    assert results[str(alice_id)]["status"] == "ok"
    assert results[str(bob_id)]["status"] == "error"
    assert results[str(bob_id)]["problem"]["status"] == 403
    assert results["00000000-0000-0000-0000-000000000000"]["status"] == "error"
    assert results["00000000-0000-0000-0000-000000000000"]["problem"]["status"] == 422

    members_response = await client.get(f"/tenants/{tenant_id}/groups/{group_id}/members")
    assert {m["id"] for m in members_response.json()} == {str(alice_id)}

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user_id))
        await session.commit()


async def test_duplicate_group_copies_roster(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        await session.commit()
        alice_id = alice.entity_id
    source_id = (
        await client.post(
            f"/tenants/{tenant_id}/groups",
            json={"name": "Goblins", "member_character_ids": [str(alice_id)]},
        )
    ).json()["id"]

    response = await client.post(
        f"/tenants/{tenant_id}/groups/{source_id}/duplicate", json={"name": "Goblins (Copy)"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Goblins (Copy)"
    assert body["id"] != source_id

    duplicate_members = await client.get(f"/tenants/{tenant_id}/groups/{body['id']}/members")
    assert {m["id"] for m in duplicate_members.json()} == {str(alice_id)}

    # The source is untouched.
    source_members = await client.get(f"/tenants/{tenant_id}/groups/{source_id}/members")
    assert {m["id"] for m in source_members.json()} == {str(alice_id)}

    await delete_tenant(tenant_id)
