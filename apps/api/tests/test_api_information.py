import uuid

from _admin_db import admin_session_factory
from conftest import (
    delete_tenant,
    make_campaign,
    make_character,
    make_opted_out_admin,
    make_tenant,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    CampaignGm,
    Character,
    CharacterPlayer,
    Entity,
    Information,
    Item,
    Knowledge,
    Membership,
    Ownership,
    Payload,
    PayloadDescription,
    Player,
    User,
)


async def _make_own_character(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, campaign_id: uuid.UUID
) -> Character:
    """A Player+Character+CharacterPlayer roster link for user_id
    specifically - mirrors test_api_item_instances.py's identical helper.
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


async def _make_item(tenant_id: uuid.UUID, name: str = "Sword") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def test_create_information_self_service_public_description(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        entity_id = character.entity_id
        await session.commit()

    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={
            "title": "An ornate sword",
            "type": "description",
            "is_public": True,
            "content": "An ornate sword with a blackened steel blade.",
            "locale": "en-US",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "An ornate sword"
    assert body["type"] == "description"
    assert body["payloads"] == [
        {
            "kind": "description",
            "content": "An ornate sword with a blackened steel blade.",
            "locale": "en-US",
        }
    ]
    assert response.headers["location"].endswith(f"/tenants/{tenant_id}/information/{body['id']}")

    await delete_tenant(tenant_id)


async def test_create_information_404_for_unknown_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/entities/00000000-0000-0000-0000-000000000000/information",
        json={"title": "x", "type": "description", "content": "x"},
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_create_information_403_for_unrelated_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        bob = await make_character(session, tenant_id=tenant_id, name="Bob")
        entity_id = bob.entity_id
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "x", "type": "description", "content": "x"},
    )

    assert response.status_code == 403
    await delete_tenant(tenant_id)


async def test_create_information_409_for_duplicate_type(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)

    first = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "First", "type": "description", "content": "x"},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "Second", "type": "description", "content": "y"},
    )
    assert second.status_code == 409

    await delete_tenant(tenant_id)


async def test_get_information_visible_to_participant_when_public(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    create_response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "x", "type": "description", "is_public": True, "content": "Public fact."},
    )
    information_id = create_response.json()["id"]

    response = await client.get(f"/tenants/{tenant_id}/information/{information_id}")

    assert response.status_code == 200
    assert response.json()["payloads"][0]["content"] == "Public fact."
    await delete_tenant(tenant_id)


async def test_get_information_404_when_gm_only_and_caller_has_no_standing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A GM-only secret (is_public=False, no knowers) is invisible to a
    plain, unrelated participant - the same 404-not-403 non-enumerable
    collapse routers/payloads.py already established.
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    create_response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "x", "type": "gm-note", "is_public": False, "content": "Secret."},
    )
    information_id = create_response.json()["id"]

    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/information/{information_id}")

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def _make_ashfang_with_three_secrets(
    tenant_id: uuid.UUID, *, owner_character_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """The milestone's own information shape, built directly via the admin
    session (mirroring test_get_item_instance_gm_with_no_tenant_membership_
    sees_gm_only_secret's identical precedent in test_api_item_instances.py
    - fixture setup bypasses the API, only the GET under test goes through
    it): three Information rows forced into three distinct `type` values by
    Information's own UniqueConstraint(entity_id, type) - a public
    description, a character-specific secret (with a Knowledge grant for
    owner_character_id), and a GM-only secret (is_public=False, zero
    Knowledge rows at all, per ADR 0028). Returns (ashfang_entity_id,
    magic_secret_information_id).
    """
    async with admin_session_factory() as session:
        ashfang = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(ashfang)
        await session.flush()
        session.add(
            Ownership(
                owned_entity_id=ashfang.id,
                owner_character_id=owner_character_id,
                tenant_id=tenant_id,
            )
        )

        public_info = Information(
            tenant_id=tenant_id,
            entity_id=ashfang.id,
            title="Ashfang",
            type="description",
            is_public=True,
        )
        session.add(public_info)
        await session.flush()
        public_payload = Payload(tenant_id=tenant_id, information_id=public_info.id)
        session.add(public_payload)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=public_payload.id,
                tenant_id=tenant_id,
                locale="en-US",
                content="An ornate sword with a blackened steel blade.",
            )
        )

        magic_info = Information(
            tenant_id=tenant_id,
            entity_id=ashfang.id,
            title="Ashfang's true nature",
            type="magic-secret",
            is_public=False,
        )
        session.add(magic_info)
        await session.flush()
        magic_payload = Payload(tenant_id=tenant_id, information_id=magic_info.id)
        session.add(magic_payload)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=magic_payload.id,
                tenant_id=tenant_id,
                locale="en-US",
                content="The sword is magical.",
            )
        )
        session.add(
            Knowledge(
                tenant_id=tenant_id,
                knower_entity_id=owner_character_id,
                information_id=magic_info.id,
            )
        )

        cursed_info = Information(
            tenant_id=tenant_id,
            entity_id=ashfang.id,
            title="Ashfang's curse",
            type="gm-note",
            is_public=False,
        )
        session.add(cursed_info)
        await session.flush()
        cursed_payload = Payload(tenant_id=tenant_id, information_id=cursed_info.id)
        session.add(cursed_payload)
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=cursed_payload.id,
                tenant_id=tenant_id,
                locale="en-US",
                content="The sword is cursed.",
            )
        )

        await session.commit()
        return ashfang.id, magic_info.id


def _visible_description_contents(body: dict) -> set[str]:
    return {
        payload["content"]
        for info in body["information"]
        for payload in info["payloads"]
        if payload["kind"] == "description"
    }


async def test_milestone_scenario_alice_sees_public_and_her_own_secret(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The GitHub milestone #1 scenario's own "GET item as Alice" step,
    checked via GET /entities/{id} (which lists every visible Information
    row regardless of `type`) - not GET /item-instances/{id}, whose own
    `descriptions` field stays scoped to the single canonical
    type="description" row and is unaffected by this ADR (see ADR 0038).
    test_user_id plays Alice directly (self-owning her own character),
    matching test_api_item_instances.py's own established convention for
    these observer-specific visibility tests.
    """
    tenant_id = await make_tenant(test_user_id)
    await make_opted_out_admin(tenant_id, test_user_id)  # no information bypass (ADR 0091)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        alice = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        alice_id = alice.entity_id
        await session.commit()

    ashfang_id, _ = await _make_ashfang_with_three_secrets(tenant_id, owner_character_id=alice_id)

    response = await client.get(f"/tenants/{tenant_id}/entities/{ashfang_id}")

    assert response.status_code == 200
    assert _visible_description_contents(response.json()) == {
        "An ornate sword with a blackened steel blade.",
        "The sword is magical.",
    }
    await delete_tenant(tenant_id)


async def test_milestone_scenario_bob_sees_only_public(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """test_user_id plays Bob: a player in the same campaign, no relation
    to Ashfang or its owner at all.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        alice = await make_character(session, tenant_id=tenant_id, name="Alice")
        alice_id = alice.entity_id
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    ashfang_id, _ = await _make_ashfang_with_three_secrets(tenant_id, owner_character_id=alice_id)

    response = await client.get(f"/tenants/{tenant_id}/entities/{ashfang_id}")

    assert response.status_code == 200
    assert _visible_description_contents(response.json()) == {
        "An ornate sword with a blackened steel blade."
    }
    await delete_tenant(tenant_id)


async def test_milestone_scenario_gm_sees_everything(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """test_user_id plays Zorro: GM of the campaign, zero tenant-wide
    Membership, no character of his own - sees the GM-only secret purely
    through ADR 0035's CampaignGm-reachability, with no explicit Knowledge
    grant at all (ADR 0028's "GM-only is just the default").
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        campaign = await make_campaign(session, tenant_id=tenant_id, name="The Ashen Crown")
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id))

        alice_user = User(authgear_subject_id=f"alice-{uuid.uuid4()}")
        session.add(alice_user)
        await session.flush()
        alice_player = Player(user_id=alice_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(alice_player)
        await session.flush()
        alice = await make_character(
            session, tenant_id=tenant_id, name="Alice", owner_player_id=alice_player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=alice.entity_id,
                player_id=alice_player.id,
                tenant_id=tenant_id,
            )
        )
        await session.commit()
        alice_id, alice_user_id = alice.entity_id, alice_user.id

    ashfang_id, _ = await _make_ashfang_with_three_secrets(tenant_id, owner_character_id=alice_id)

    response = await client.get(f"/tenants/{tenant_id}/entities/{ashfang_id}")

    assert response.status_code == 200
    assert _visible_description_contents(response.json()) == {
        "An ornate sword with a blackened steel blade.",
        "The sword is magical.",
        "The sword is cursed.",
    }

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, alice_user_id))
        await session.commit()


async def test_add_and_remove_information_knower(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    await make_opted_out_admin(tenant_id, test_user_id)  # no information bypass (ADR 0091)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        character_id = character.entity_id
        await session.commit()

    create_response = await client.post(
        f"/tenants/{tenant_id}/entities/{character_id}/information",
        json={"title": "x", "type": "secret", "is_public": False, "content": "A secret."},
    )
    information_id = create_response.json()["id"]

    grant_response = await client.put(
        f"/tenants/{tenant_id}/information/{information_id}/knowers/{character_id}"
    )
    assert grant_response.status_code == 200

    get_response = await client.get(f"/tenants/{tenant_id}/information/{information_id}")
    assert get_response.status_code == 200

    remove_response = await client.delete(
        f"/tenants/{tenant_id}/information/{information_id}/knowers/{character_id}"
    )
    assert remove_response.status_code == 200

    get_after_remove = await client.get(f"/tenants/{tenant_id}/information/{information_id}")
    assert get_after_remove.status_code == 404

    await delete_tenant(tenant_id)


async def test_add_information_knower_404_for_unknown_knower_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    create_response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "x", "type": "description", "content": "x"},
    )
    information_id = create_response.json()["id"]

    response = await client.put(
        f"/tenants/{tenant_id}/information/{information_id}"
        f"/knowers/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_add_information_knower_403_for_unrelated_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_item(tenant_id)
    create_response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "x", "type": "description", "content": "x"},
    )
    information_id = create_response.json()["id"]

    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        other = await make_character(session, tenant_id=tenant_id, name="Other")
        other_id = other.entity_id
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.put(
        f"/tenants/{tenant_id}/information/{information_id}/knowers/{other_id}"
    )

    assert response.status_code == 403
    await delete_tenant(tenant_id)


async def test_get_information_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/information/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_get_information_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get(
        "/tenants/00000000-0000-0000-0000-000000000000/information/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


async def test_create_information_allowed_for_gm_of_owners_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The "managed" tier: not self-service (test_user_id controls no
    characters here), but the entity's current owner (Bob) is rostered in
    a campaign test_user_id GMs - mirrors test_api_item_instances.py's
    identical test for RFC 0005's own analogous case.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        bob_owner = User(authgear_subject_id=f"bob-owner-{uuid.uuid4()}")
        session.add(bob_owner)
        await session.flush()
        bob_player = Player(user_id=bob_owner.id, campaign_id=campaign.id, tenant_id=tenant_id)
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
        entity = Entity(tenant_id=tenant_id, name="Bob's Item")
        session.add(entity)
        await session.flush()
        session.add(
            Ownership(
                owned_entity_id=entity.id, owner_character_id=bob.entity_id, tenant_id=tenant_id
            )
        )
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id))
        await session.commit()
        entity_id, bob_owner_id = entity.id, bob_owner.id

    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={"title": "x", "type": "description", "is_public": True, "content": "x"},
    )

    assert response.status_code == 201
    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_owner_id))
        await session.commit()
