import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.etag import etag_for
from lorenzo_api.models import (
    CampaignGm,
    Character,
    CharacterPlayer,
    Entity,
    EntityStat,
    Item,
    ItemInstance,
    Membership,
    Ownership,
    Player,
    StatDefinition,
    StatGroup,
    StatValueType,
    User,
)


async def _make_own_character(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, campaign_id: uuid.UUID
) -> Character:
    """Mirrors test_api_item_instances.py's identical helper - what the
    self-or-managed tests below need to make `client`'s fixed test_user_id
    actually control a character. Kept as a local copy rather than promoted
    to conftest.py: still exactly two call sites (this file and
    test_api_item_instances.py), the same threshold that hasn't yet
    triggered promotion for other twice-duplicated helpers in this codebase.
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


async def _make_stat(
    tenant_id: uuid.UUID, *, name: str = "weight", value_type: StatValueType = StatValueType.INT
) -> uuid.UUID:
    async with admin_session_factory() as session:
        stat_group = StatGroup(tenant_id=tenant_id, name=f"group-{name}")
        session.add(stat_group)
        await session.flush()
        stat_definition = StatDefinition(
            tenant_id=tenant_id, stat_group_id=stat_group.id, name=name, value_type=value_type
        )
        session.add(stat_definition)
        await session.commit()
        return stat_definition.id


async def _make_bare_entity(tenant_id: uuid.UUID, name: str = "Sword") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


async def test_set_entity_stat_creates_a_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    stat_definition_id = await _make_stat(tenant_id)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}",
        json={"value": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(entity_id)
    assert body["stats"] == [{"name": "weight", "value": 5}]

    async with admin_session_factory() as session:
        stat = await session.get_one(EntityStat, (entity_id, stat_definition_id))
        assert stat.value_int == 5

    await delete_tenant(tenant_id)


async def test_set_entity_stat_overwrites_an_existing_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    stat_definition_id = await _make_stat(tenant_id)
    first = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}",
        json={"value": 5},
    )
    assert first.status_code == 200

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}",
        json={"value": 9},
    )

    assert response.status_code == 200
    assert response.json()["stats"] == [{"name": "weight", "value": 9}]

    await delete_tenant(tenant_id)


async def test_set_entity_stat_on_own_character_directly(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A player setting their own character's stat directly - RFC 0008's
    own "a player should be able to set their own character's... stats
    without GM involvement," the case entity_access.can_self_manage_entity
    covers via the character being one of reachable_entity_ids' own roots,
    not something reached *through* a root.
    """
    tenant_id = await make_tenant(test_user_id)
    hp_id = await _make_stat(tenant_id, name="hp")
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        character = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        # Demote test_user_id from tenant OWNER - proves this is genuinely
        # self-service, not riding along on tenant-admin standing.
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        await session.commit()
        character_entity_id = character.entity_id

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{character_entity_id}/stats/{hp_id}",
        json={"value": 12},
    )

    assert response.status_code == 200
    assert response.json()["stats"] == [{"name": "hp", "value": 12}]

    await delete_tenant(tenant_id)


async def test_set_entity_stat_catalog_item_allowed_for_tenant_owner(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A bare, unowned catalog item ("Sword") has no Ownership row and is
    reachable from no character - the ownerless fallback
    (can_manage_any_campaign_in_tenant) is what makes it settable at all,
    satisfied here by test_user_id's tenant OWNER standing even though zero
    campaigns exist yet (campaign_access.is_tenant_admin, unconditional).
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Sword")
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        entity_id = entity.id
    weight_id = await _make_stat(tenant_id)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}", json={"value": 5}
    )

    assert response.status_code == 200
    await delete_tenant(tenant_id)


async def test_set_entity_stat_forbidden_for_unrelated_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    weight_id = await _make_stat(tenant_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        # Demote to a bare participant with no GM/admin standing anywhere.
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}", json={"value": 5}
    )

    assert response.status_code == 403
    await delete_tenant(tenant_id)


async def test_set_entity_stat_allowed_via_campaign_gm_for_owned_by_other_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weight_id = await _make_stat(tenant_id)
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
        entity = Entity(tenant_id=tenant_id, name="Ashfang")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(
            Ownership(
                owned_entity_id=entity.id, owner_character_id=bob.entity_id, tenant_id=tenant_id
            )
        )
        # Demote test_user_id from tenant OWNER to a bare participant.
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        entity_id = entity.id

    forbidden_response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}", json={"value": 5}
    )
    assert forbidden_response.status_code == 403

    async with admin_session_factory() as session:
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id))
        await session.commit()

    allowed_response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}", json={"value": 5}
    )
    assert allowed_response.status_code == 200

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_owner.id))
        await session.commit()


async def test_set_entity_stat_404_for_unknown_entity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weight_id = await _make_stat(tenant_id)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/00000000-0000-0000-0000-000000000000/stats/{weight_id}",
        json={"value": 5},
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    await delete_tenant(tenant_id)


async def test_set_entity_stat_404_for_unknown_stat_definition(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/00000000-0000-0000-0000-000000000000",
        json={"value": 5},
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_set_entity_stat_422_for_wrong_value_type(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    weight_id = await _make_stat(tenant_id, name="weight", value_type=StatValueType.INT)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}",
        json={"value": "heavy"},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_set_entity_stat_422_for_bool_sent_as_int(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """bool is an int subclass in Python - confirms the endpoint checks
    isinstance(value, bool) before isinstance(value, int), not after.
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    is_magical_id = await _make_stat(tenant_id, name="is_magical", value_type=StatValueType.BOOL)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{is_magical_id}",
        json={"value": 1},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_set_entity_stat_accepts_text_and_float_and_bool(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    text_id = await _make_stat(tenant_id, name="material", value_type=StatValueType.TEXT)
    float_id = await _make_stat(tenant_id, name="ratio", value_type=StatValueType.FLOAT)
    bool_id = await _make_stat(tenant_id, name="is_magical", value_type=StatValueType.BOOL)

    text_response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{text_id}",
        json={"value": "mithril"},
    )
    float_response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{float_id}",
        json={"value": 1.5},
    )
    bool_response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{bool_id}",
        json={"value": True},
    )

    assert text_response.status_code == 200
    assert float_response.status_code == 200
    assert bool_response.status_code == 200
    stats = {s["name"]: s["value"] for s in bool_response.json()["stats"]}
    assert stats == {"material": "mithril", "ratio": 1.5, "is_magical": True}

    await delete_tenant(tenant_id)


async def test_set_entity_stat_precondition_failed_with_stale_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    weight_id = await _make_stat(tenant_id)
    first = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}", json={"value": 5}
    )
    assert first.status_code == 200

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}",
        json={"value": 9},
        headers={"If-Match": 'W/"stale"'},
    )

    assert response.status_code == 412
    await delete_tenant(tenant_id)


async def test_set_entity_stat_succeeds_with_correct_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    weight_id = await _make_stat(tenant_id)
    first = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}", json={"value": 5}
    )
    assert first.status_code == 200
    async with admin_session_factory() as session:
        stat = await session.get_one(EntityStat, (entity_id, weight_id))
        current_etag = etag_for(stat.updated_at)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}",
        json={"value": 9},
        headers={"If-Match": current_etag},
    )

    assert response.status_code == 200
    await delete_tenant(tenant_id)


async def test_set_entity_stat_first_write_ignores_if_match(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """No prior version exists yet on a first-ever set - an If-Match header
    (however implausible) has nothing to have gone stale relative to.
    """
    tenant_id = await make_tenant(test_user_id)
    entity_id = await _make_bare_entity(tenant_id)
    weight_id = await _make_stat(tenant_id)

    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{weight_id}",
        json={"value": 5},
        headers={"If-Match": 'W/"anything"'},
    )

    assert response.status_code == 200
    await delete_tenant(tenant_id)


async def test_effective_stats_resolve_through_prototype_chain_and_survive_container_move(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The exact GitHub milestone #1 scenario, end to end through the real
    API (not a direct ORM/view proof like test_v_item.py's own resolution
    tests): "Sword" -> "Flaming Sword" -> "Ashfang" resolves as one
    coherent effective stat set, a direct override on Ashfang wins outright,
    and moving Ashfang between containers (via ADR 0032's existing PUT
    .../container) leaves its resolved stats untouched - proven as a
    genuinely self-service move, not one riding on tenant-admin standing.
    """
    tenant_id = await make_tenant(test_user_id)
    chest_a = str(await _make_bare_entity(tenant_id, "Chest A"))
    chest_b = str(await _make_bare_entity(tenant_id, "Chest B"))
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        alice = await _make_own_character(
            session, tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
        )
        await session.commit()
        alice_entity_id = str(alice.entity_id)

    # Catalog: Sword, then Flaming Sword prototyping it - test_user_id is
    # still tenant OWNER at this point, the ordinary "someone authors the
    # catalog" setup phase.
    sword_response = await client.post(f"/tenants/{tenant_id}/items", json={"name": "Sword"})
    assert sword_response.status_code == 201
    sword_id = sword_response.json()["entity_id"]

    flaming_sword_response = await client.post(
        f"/tenants/{tenant_id}/items",
        json={"name": "Flaming Sword", "prototype_ids": [sword_id]},
    )
    assert flaming_sword_response.status_code == 201
    flaming_sword_id = flaming_sword_response.json()["entity_id"]

    stat_group_response = await client.post(
        f"/tenants/{tenant_id}/stat-groups", json={"name": "physical"}
    )
    assert stat_group_response.status_code == 201
    stat_group_id = stat_group_response.json()["id"]
    stat_definition_response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": "weight", "stat_group_id": stat_group_id, "value_type": "int"},
    )
    assert stat_definition_response.status_code == 201
    weight_id = stat_definition_response.json()["id"]

    # Sword alone sets weight - Flaming Sword inherits it through one hop.
    set_sword_weight = await client.put(
        f"/tenants/{tenant_id}/entities/{sword_id}/stats/{weight_id}", json={"value": 5}
    )
    assert set_sword_weight.status_code == 200

    flaming_sword_get = await client.get(f"/tenants/{tenant_id}/items/{flaming_sword_id}")
    assert flaming_sword_get.status_code == 200
    assert flaming_sword_get.json()["weight"] == 5

    # Ashfang: an instance of Flaming Sword, owned by Alice, starting in
    # Chest A - inherits weight through two hops (Ashfang -> Flaming Sword
    # -> Sword).
    ashfang_response = await client.post(
        f"/tenants/{tenant_id}/item-instances",
        json={
            "name": "Ashfang",
            "prototype_id": flaming_sword_id,
            "owner_character_id": alice_entity_id,
            "container_entity_id": chest_a,
        },
    )
    assert ashfang_response.status_code == 201
    ashfang_id = ashfang_response.json()["entity_id"]
    assert ashfang_response.json()["weight"] == 5

    ashfang_get = await client.get(f"/tenants/{tenant_id}/item-instances/{ashfang_id}")
    assert ashfang_get.status_code == 200
    assert ashfang_get.json()["weight"] == 5
    assert ashfang_get.json()["container_entity_id"] == chest_a

    # A direct override on Ashfang itself wins outright over anything
    # inherited (zero hops beats two).
    override_response = await client.put(
        f"/tenants/{tenant_id}/entities/{ashfang_id}/stats/{weight_id}", json={"value": 99}
    )
    assert override_response.status_code == 200
    assert override_response.json()["stats"] == [{"name": "weight", "value": 99}]

    overridden_get = await client.get(f"/tenants/{tenant_id}/item-instances/{ashfang_id}")
    assert overridden_get.status_code == 200
    assert overridden_get.json()["weight"] == 99

    # Demote test_user_id off tenant-admin standing entirely - what follows
    # must work purely because Alice is their own character.
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        await session.delete(membership)
        await session.commit()

    move_response = await client.put(
        f"/tenants/{tenant_id}/item-instances/{ashfang_id}/container",
        json={"container_entity_id": chest_b},
    )
    assert move_response.status_code == 200
    assert move_response.json()["container_entity_id"] == chest_b
    # Moving Ashfang did not touch its resolved stats at all.
    assert move_response.json()["weight"] == 99

    final_get = await client.get(f"/tenants/{tenant_id}/item-instances/{ashfang_id}")
    assert final_get.status_code == 200
    assert final_get.json()["weight"] == 99
    assert final_get.json()["container_entity_id"] == chest_b

    await delete_tenant(tenant_id)
