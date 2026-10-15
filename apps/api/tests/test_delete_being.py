"""ADR 0302: permanent being deletion, permissions and inventory settlement."""

import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_campaign, make_character, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import (
    Being,
    CampaignGm,
    Character,
    CharacterPlayer,
    Containment,
    Entity,
    EntitySlug,
    EntityStat,
    Information,
    ItemInstance,
    Membership,
    Ownership,
    Payload,
    Player,
    StatDefinition,
    StatGroup,
    User,
)


async def _instance(session, tenant_id, name, *, owner=None, container=None, quantity=1):
    entity = Entity(tenant_id=tenant_id, name=name)
    session.add(entity)
    await session.flush()
    session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
    if owner is not None:
        session.add(
            Ownership(tenant_id=tenant_id, owned_entity_id=entity.id, owner_character_id=owner)
        )
    if container is not None:
        session.add(
            Containment(
                tenant_id=tenant_id,
                child_entity_id=entity.id,
                parent_entity_id=container,
                quantity=quantity,
            )
        )
    await session.flush()
    return entity.id


async def test_inventory_matrix_and_entity_cleanup(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        victim = (await make_character(session, tenant_id=tenant, name="Departing")).entity_id
        other = (await make_character(session, tenant_id=tenant, name="Staying")).entity_id
        bag = await _instance(session, tenant, "Bag", owner=victim, container=victim)
        doomed = await _instance(session, tenant, "Owned in bag", owner=victim, container=bag)
        borrowed = await _instance(session, tenant, "Borrowed", owner=other, container=bag)
        carried_only = await _instance(session, tenant, "Ownerless", container=victim)
        away = await _instance(session, tenant, "Lent", owner=victim, container=other)
        stored = await _instance(session, tenant, "Stored", owner=victim)
        untouched = await _instance(
            session, tenant, "Other inventory", owner=other, container=other
        )
        session.add(EntitySlug(tenant_id=tenant, entity_id=victim, slug="departing"))
        group = StatGroup(tenant_id=tenant, name="Traits")
        session.add(group)
        await session.flush()
        definition = StatDefinition(
            tenant_id=tenant, stat_group_id=group.id, name="strength", value_type="int"
        )
        session.add(definition)
        await session.flush()
        session.add(
            EntityStat(
                tenant_id=tenant, entity_id=victim, stat_definition_id=definition.id, value_int=12
            )
        )
        await session.commit()
    note = await client.post(
        f"/tenants/{tenant}/entities/{victim}/information",
        json={
            "title": "A secret",
            "type": "note",
            "is_public": False,
            "content": "Private text",
        },
    )
    assert note.status_code == 201, note.text
    note_id = uuid.UUID(note.json()["id"])
    payload_ids = [uuid.UUID(p["id"]) for p in note.json()["payloads"]]

    response = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert response.status_code == 204, response.text
    async with admin_session_factory() as session:
        for entity_id in (victim, bag, doomed):
            assert await session.get(Entity, entity_id) is None
        assert await session.get(Being, victim) is None
        assert await session.get(Character, victim) is None
        assert await session.get(EntitySlug, victim) is None
        assert (
            await session.scalar(select(EntityStat).where(EntityStat.entity_id == victim)) is None
        )
        assert await session.get(Information, note_id) is None
        for payload_id in payload_ids:
            assert await session.get(Payload, payload_id) is None
        for entity_id in (borrowed, carried_only, away, stored):
            assert await session.get(ItemInstance, entity_id) is not None
            assert await session.get(Containment, entity_id) is None
        assert (await session.get_one(Ownership, borrowed)).owner_character_id == other
        for entity_id in (away, stored):
            assert await session.get(Ownership, entity_id) is None
        assert (await session.get_one(Containment, untouched)).parent_entity_id == other
        assert (await session.get_one(Ownership, untouched)).owner_character_id == other
    await delete_tenant(tenant)


async def test_surviving_containers_keep_contents_and_stacks_keep_quantity(
    client: AsyncClient,
    test_user_id: uuid.UUID,
):
    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        victim = (await make_being(session, tenant_id=tenant)).entity_id
        other = (await make_being(session, tenant_id=tenant)).entity_id
        bag = await _instance(session, tenant, "Deleted bag", owner=victim, container=victim)
        await _instance(session, tenant, "Borrowed arrows", owner=other, container=bag, quantity=3)
        kept_bag = await _instance(session, tenant, "Borrowed bag", owner=other, container=victim)
        kept_child = await _instance(session, tenant, "Rope", owner=other, container=kept_bag)
        await _instance(session, tenant, "Lent arrows", owner=victim, container=other, quantity=2)
        await session.commit()
    response = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert response.status_code == 204, response.text
    async with admin_session_factory() as session:
        arrows = list(
            await session.scalars(
                select(Entity).where(
                    Entity.tenant_id == tenant, Entity.name.in_(["Borrowed arrows", "Lent arrows"])
                )
            )
        )
        assert len(arrows) == 5
        for arrow in arrows:
            assert await session.get(Containment, arrow.id) is None
            owner = await session.get(Ownership, arrow.id)
            if arrow.name == "Borrowed arrows":
                assert owner is not None and owner.owner_character_id == other
            else:
                assert owner is None
        assert await session.get(Containment, kept_bag) is None
        assert (await session.get_one(Containment, kept_child)).parent_entity_id == kept_bag
    await delete_tenant(tenant)


async def test_contained_being_is_a_boundary(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        victim = (await make_being(session, tenant_id=tenant)).entity_id
        passenger = (await make_being(session, tenant_id=tenant)).entity_id
        session.add(
            Containment(tenant_id=tenant, child_entity_id=passenger, parent_entity_id=victim)
        )
        item = await _instance(
            session, tenant, "Held by passenger", owner=victim, container=passenger
        )
        await session.commit()
    response = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert response.status_code == 204, response.text
    async with admin_session_factory() as session:
        assert await session.get(Being, passenger) is not None
        assert await session.get(ItemInstance, item) is not None
        assert await session.get(Ownership, item) is None
        assert await session.get(Containment, item) is None
    await delete_tenant(tenant)


@pytest.mark.parametrize("bare", [False, True])
async def test_stale_etag_is_atomic(client: AsyncClient, test_user_id: uuid.UUID, bare: bool):
    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        factory = make_being if bare else make_character
        victim = (await factory(session, tenant_id=tenant)).entity_id
        item = await _instance(session, tenant, "Keep", owner=victim, container=victim)
        await session.commit()
    response = await client.delete(
        f"/tenants/{tenant}/beings/{victim}", headers={"If-Match": 'W/"stale"'}
    )
    assert response.status_code == 412, response.text
    async with admin_session_factory() as session:
        assert await session.get(Being, victim) is not None
        assert await session.get(ItemInstance, item) is not None
        assert (await session.get_one(Ownership, item)).owner_character_id == victim
    await delete_tenant(tenant)


async def test_player_can_delete_own_but_not_another_being(
    client: AsyncClient,
    test_user_id: uuid.UUID,
):
    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant)
        seat = Player(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id)
        session.add(seat)
        await session.flush()
        own = (await make_character(session, tenant_id=tenant, owner_player_id=seat.id)).entity_id
        session.add(CharacterPlayer(tenant_id=tenant, character_entity_id=own, player_id=seat.id))
        another = (await make_character(session, tenant_id=tenant)).entity_id
        await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
        await session.commit()
    refused = await client.delete(f"/tenants/{tenant}/beings/{another}")
    assert refused.status_code == 403, refused.text
    accepted = await client.delete(f"/tenants/{tenant}/beings/{own}")
    assert accepted.status_code == 204, accepted.text
    await delete_tenant(tenant)


async def test_gm_needs_every_campaign(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        victim = (await make_character(session, tenant_id=tenant)).entity_id
        other = User(authgear_subject_id=f"other-{uuid.uuid4()}")
        session.add(other)
        await session.flush()
        campaigns = [await make_campaign(session, tenant_id=tenant) for _ in range(2)]
        for campaign in campaigns:
            seat = Player(tenant_id=tenant, campaign_id=campaign.id, user_id=other.id)
            session.add(seat)
            await session.flush()
            session.add(
                CharacterPlayer(tenant_id=tenant, character_entity_id=victim, player_id=seat.id)
            )
        session.add(CampaignGm(tenant_id=tenant, campaign_id=campaigns[0].id, user_id=test_user_id))
        await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
        await session.commit()
        second = campaigns[1].id
    refused = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert refused.status_code == 403, refused.text
    async with admin_session_factory() as session:
        assert await session.get(Entity, victim) is not None
        session.add(CampaignGm(tenant_id=tenant, campaign_id=second, user_id=test_user_id))
        await session.commit()
    accepted = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert accepted.status_code == 204, accepted.text
    await delete_tenant(tenant)


async def test_cross_tenant_and_non_being_are_not_found(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    foreign = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        victim = (await make_being(session, tenant_id=foreign)).entity_id
        ordinary = Entity(tenant_id=tenant, name="Not a being")
        session.add(ordinary)
        await session.commit()
        ordinary_id = ordinary.id
    for entity_id in (victim, ordinary_id, uuid.uuid4()):
        response = await client.delete(f"/tenants/{tenant}/beings/{entity_id}")
        assert response.status_code == 404, response.text
    async with admin_session_factory() as session:
        assert await session.get(Being, victim) is not None
    await delete_tenant(tenant)
    await delete_tenant(foreign)


@pytest.mark.parametrize("kind", ["inventory", "catalog", "campaign"])
async def test_other_kind_guards_refuse_before_changing_inventory(
    client: AsyncClient,
    test_user_id: uuid.UUID,
    kind: str,
):
    from lorenzo_api.models import EntityPrototype, Item

    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        if kind == "campaign":
            campaign = await make_campaign(session, tenant_id=tenant)
            victim = campaign.entity_id
            session.add(Being(tenant_id=tenant, entity_id=victim))
        else:
            victim = (await make_being(session, tenant_id=tenant)).entity_id
            if kind == "inventory":
                session.add(ItemInstance(tenant_id=tenant, entity_id=victim))
            else:
                session.add(Item(tenant_id=tenant, entity_id=victim))
                instance = await _instance(session, tenant, "Uses this prototype")
                session.add(
                    EntityPrototype(
                        tenant_id=tenant, entity_id=instance, prototype_id=victim, position=0
                    )
                )
        item = await _instance(
            session, tenant, "Keep carried inventory", owner=victim, container=victim
        )
        await session.commit()
    response = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert response.status_code == 409, response.text
    async with admin_session_factory() as session:
        assert await session.get(Being, victim) is not None
        assert await session.get(ItemInstance, item) is not None
        assert (await session.get_one(Ownership, item)).owner_character_id == victim
        assert (await session.get_one(Containment, item)).parent_entity_id == victim
    await delete_tenant(tenant)


async def test_private_npc_management_follows_authorship(
    client: AsyncClient,
    test_user_id: uuid.UUID,
):
    from lorenzo_api.models import Tenant

    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        victim = (await make_being(session, tenant_id=tenant)).entity_id
        campaign = await make_campaign(session, tenant_id=tenant)
        session.add(CampaignGm(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id))
        (await session.get_one(Tenant, tenant)).npcs_shared_with_gms = False
        await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
        await session.commit()
    refused = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert refused.status_code == 403, refused.text
    async with admin_session_factory() as session:
        (await session.get_one(Entity, victim)).created_by = test_user_id
        await session.commit()
    accepted = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert accepted.status_code == 204, accepted.text
    await delete_tenant(tenant)


async def test_nonparticipant_cannot_delete(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        victim = (await make_being(session, tenant_id=tenant)).entity_id
        await session.delete(await session.get_one(Membership, (tenant, test_user_id)))
        await session.commit()
    response = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert response.status_code == 404, response.text
    async with admin_session_factory() as session:
        assert await session.get(Being, victim) is not None
    await delete_tenant(tenant)


@pytest.mark.parametrize("inherited", [False, True])
async def test_repository_author_keeps_existing_entry_deletion_guard(
    client: AsyncClient,
    test_user_id: uuid.UUID,
    inherited: bool,
):
    from lorenzo_api.models import EntityPrototype, MembershipRole, Tenant, TenantKind

    async with admin_session_factory() as session:
        repository = Tenant(kind=TenantKind.REPOSITORY)
        session.add(repository)
        await session.flush()
        tenant = repository.id
        session.add(Membership(tenant_id=tenant, user_id=test_user_id, role=MembershipRole.AUTHOR))
        victim = (await make_being(session, tenant_id=tenant)).entity_id
        if inherited:
            child = (await make_being(session, tenant_id=tenant)).entity_id
            session.add(
                EntityPrototype(tenant_id=tenant, entity_id=child, prototype_id=victim, position=0)
            )
        await session.commit()
    response = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert response.status_code == (403 if inherited else 204), response.text
    async with admin_session_factory() as session:
        assert (await session.get(Entity, victim) is not None) == inherited
    await delete_tenant(tenant)


async def test_audit_and_inventory_feed_survive_the_deleted_character(
    client: AsyncClient,
    test_user_id: uuid.UUID,
):
    from lorenzo_api.models import AuditLog, EntityChange

    tenant = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        recipient = User(authgear_subject_id=f"deletion-feed-{uuid.uuid4()}")
        session.add(recipient)
        await session.flush()
        campaign = await make_campaign(session, tenant_id=tenant)
        seat = Player(tenant_id=tenant, campaign_id=campaign.id, user_id=recipient.id)
        session.add(seat)
        await session.flush()
        victim = (
            await make_character(session, tenant_id=tenant, owner_player_id=seat.id)
        ).entity_id
        session.add(
            CharacterPlayer(tenant_id=tenant, character_entity_id=victim, player_id=seat.id)
        )
        removed = await _instance(session, tenant, "Deleted sword", owner=victim, container=victim)
        kept = await _instance(session, tenant, "Stored shield", owner=victim)
        recipient_id = recipient.id
        await session.commit()
    response = await client.delete(f"/tenants/{tenant}/beings/{victim}")
    assert response.status_code == 204, response.text
    async with admin_session_factory() as session:
        events = list(
            await session.scalars(
                select(EntityChange).where(
                    EntityChange.tenant_id == tenant, EntityChange.user_id == recipient_id
                )
            )
        )
        assert {(event.entity_id, event.kind) for event in events} == {
            (removed, "deleted"),
            (kept, "given_away"),
        }
        assert all(
            event.character_entity_id == victim and not event.actor_visible for event in events
        )
        actions = set(
            await session.scalars(select(AuditLog.action).where(AuditLog.tenant_id == tenant))
        )
        assert {"being.deleted", "item_instance.deleted"} <= actions
    await delete_tenant(tenant)
