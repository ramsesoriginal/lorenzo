import uuid
from decimal import Decimal

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    CharacterPlayer,
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    EntityStatGroup,
    GroupMember,
    Information,
    Knowledge,
    Membership,
    MembershipRole,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    Player,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
    TenantAdminCampaignOptOut,
    User,
)


async def test_list_entities_returns_paginated_summaries_ordered_by_name(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        session.add_all(
            [
                Entity(tenant_id=tenant.id, name="Charlie"),
                Entity(tenant_id=tenant.id, name="Alpha"),
                Entity(tenant_id=tenant.id, name="Bravo"),
            ]
        )
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/entities", params={"page": 1, "size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["size"] == 2
    assert body["pages"] == 2
    assert [item["name"] for item in body["items"]] == ["Alpha", "Bravo"]

    response = await client.get(f"/tenants/{tenant_id}/entities", params={"page": 2, "size": 2})
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Charlie"]

    await delete_tenant(tenant_id)


async def test_list_entities_only_returns_the_requesting_tenants_entities(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all(
            [
                Membership(tenant_id=tenant_a.id, user_id=test_user_id, role=MembershipRole.OWNER),
                Membership(tenant_id=tenant_b.id, user_id=test_user_id, role=MembershipRole.OWNER),
            ]
        )
        session.add(Entity(tenant_id=tenant_a.id, name="Tenant A Entity"))
        session.add(Entity(tenant_id=tenant_b.id, name="Tenant B Entity"))
        await session.commit()
        tenant_a_id, tenant_b_id = tenant_a.id, tenant_b.id

    response = await client.get(f"/tenants/{tenant_a_id}/entities")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Tenant A Entity"]

    response = await client.get(f"/tenants/{tenant_b_id}/entities")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Tenant B Entity"]

    await delete_tenant(tenant_a_id)
    await delete_tenant(tenant_b_id)


async def test_list_entities_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get("/tenants/00000000-0000-0000-0000-000000000000/entities")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


async def test_get_entity_returns_full_detail_with_every_relationship_resolved(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """One entity wired up with all four StatDefinition.value_types, all
    four Payload kinds (with one Information row bundling two heterogeneous
    kinds - a real fixture fact, confirmed in test_v_item.py, not assumed),
    a prototype/instance pair, and a parent/child pair.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        main = Entity(tenant_id=tenant_id, name="Main Entity")
        proto = Entity(tenant_id=tenant_id, name="Proto Entity")
        instance = Entity(tenant_id=tenant_id, name="Instance Entity")
        parent = Entity(tenant_id=tenant_id, name="Parent Entity")
        child = Entity(tenant_id=tenant_id, name="Child Entity")
        session.add_all([main, proto, instance, parent, child])
        await session.flush()

        session.add_all(
            [
                EntityPrototype(entity_id=main.id, prototype_id=proto.id, tenant_id=tenant_id),
                EntityPrototype(entity_id=instance.id, prototype_id=main.id, tenant_id=tenant_id),
                Containment(
                    child_entity_id=main.id, parent_entity_id=parent.id, tenant_id=tenant_id
                ),
                Containment(
                    child_entity_id=child.id, parent_entity_id=main.id, tenant_id=tenant_id
                ),
            ]
        )

        stat_group = StatGroup(tenant_id=tenant_id, name="physical")
        session.add(stat_group)
        await session.flush()
        session.add(
            EntityStatGroup(entity_id=main.id, stat_group_id=stat_group.id, tenant_id=tenant_id)
        )

        weight_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="weight",
            value_type=StatValueType.INT,
        )
        label_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="label",
            value_type=StatValueType.TEXT,
        )
        sharpness_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="sharpness",
            value_type=StatValueType.FLOAT,
        )
        magical_def = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=stat_group.id,
            name="is_magical",
            value_type=StatValueType.BOOL,
        )
        session.add_all([weight_def, label_def, sharpness_def, magical_def])
        await session.flush()

        session.add_all(
            [
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=weight_def.id,
                    tenant_id=tenant_id,
                    value_int=3,
                ),
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=label_def.id,
                    tenant_id=tenant_id,
                    value_text="sharp",
                ),
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=sharpness_def.id,
                    tenant_id=tenant_id,
                    value_float=9.5,
                ),
                EntityStat(
                    entity_id=main.id,
                    stat_definition_id=magical_def.id,
                    tenant_id=tenant_id,
                    value_bool=True,
                ),
            ]
        )

        # Information #1: description + picture as sibling payloads under
        # the *same* information_id - the mixed-kinds-per-row fixture fact.
        # is_public=True on both info rows below - this test is about the
        # full detail shape resolving correctly, not about visibility
        # narrowing (see test_information_visibility.py and the dedicated
        # visibility tests further down this file for that).
        info1 = Information(
            tenant_id=tenant_id,
            entity_id=main.id,
            title="A fine sword",
            type="description",
            is_public=True,
        )
        session.add(info1)
        await session.flush()
        description_payload = Payload(tenant_id=tenant_id, information_id=info1.id)
        picture_payload = Payload(tenant_id=tenant_id, information_id=info1.id)
        session.add_all([description_payload, picture_payload])
        await session.flush()
        session.add(
            PayloadDescription(
                payload_id=description_payload.id,
                tenant_id=tenant_id,
                locale="en-US",
                content="A gleaming blade.",
            )
        )
        session.add(
            PayloadPicture(
                payload_id=picture_payload.id,
                tenant_id=tenant_id,
                data=b"\x89PNG\r\n\x1a\n",
                file_type="image/png",
            )
        )

        # Information #2: number + document, rounding out all four payload
        # kinds across the entity's information as a whole.
        info2 = Information(
            tenant_id=tenant_id,
            entity_id=main.id,
            title="Appraisal",
            type="gm-note",
            is_public=True,
        )
        session.add(info2)
        await session.flush()
        number_payload = Payload(tenant_id=tenant_id, information_id=info2.id)
        document_payload = Payload(tenant_id=tenant_id, information_id=info2.id)
        session.add_all([number_payload, document_payload])
        await session.flush()
        session.add(
            PayloadNumber(payload_id=number_payload.id, tenant_id=tenant_id, value=Decimal("42.5"))
        )
        session.add(
            PayloadDocument(
                payload_id=document_payload.id,
                tenant_id=tenant_id,
                data=b"%PDF-1.4",
                filename="appraisal.pdf",
                file_type="application/pdf",
            )
        )

        await session.commit()
        main_id, picture_payload_id, document_payload_id = (
            main.id,
            picture_payload.id,
            document_payload.id,
        )

    response = await client.get(f"/tenants/{tenant_id}/entities/{main_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["id"] == str(main_id)
    assert body["name"] == "Main Entity"
    assert body["created_at"]
    assert body["updated_at"]

    stats = {s["name"]: s["value"] for s in body["stats"]}
    assert stats == {"weight": 3, "label": "sharp", "sharpness": 9.5, "is_magical": True}

    assert [g["name"] for g in body["stat_groups"]] == ["physical"]

    information_by_type = {info["type"]: info for info in body["information"]}
    assert set(information_by_type) == {"description", "gm-note"}

    description_info = information_by_type["description"]
    assert description_info["title"] == "A fine sword"
    payloads_by_kind = {p["kind"]: p for p in description_info["payloads"]}
    assert set(payloads_by_kind) == {"description", "picture"}
    assert payloads_by_kind["description"]["content"] == "A gleaming blade."
    assert payloads_by_kind["description"]["locale"] == "en-US"
    assert payloads_by_kind["picture"]["file_type"] == "image/png"
    assert payloads_by_kind["picture"]["url"].endswith(
        f"/tenants/{tenant_id}/payloads/{picture_payload_id}/content"
    )

    gm_note_info = information_by_type["gm-note"]
    payloads_by_kind = {p["kind"]: p for p in gm_note_info["payloads"]}
    assert set(payloads_by_kind) == {"number", "document"}
    assert payloads_by_kind["number"]["value"] == "42.5"
    assert payloads_by_kind["document"]["filename"] == "appraisal.pdf"
    assert payloads_by_kind["document"]["url"].endswith(
        f"/tenants/{tenant_id}/payloads/{document_payload_id}/content"
    )

    assert [e["name"] for e in body["prototypes"]] == ["Proto Entity"]
    assert [e["name"] for e in body["instances"]] == ["Instance Entity"]
    assert body["parent"] is not None
    assert body["parent"]["name"] == "Parent Entity"
    assert [e["name"] for e in body["children"]] == ["Child Entity"]

    # The picture/document URLs must actually resolve, through the
    # already-existing payload_content route - confirms url_for's route
    # name matches, not just that a plausible-looking string was built.
    content_response = await client.get(payloads_by_kind["document"]["url"])
    assert content_response.status_code == 200
    assert content_response.content == b"%PDF-1.4"

    await delete_tenant(tenant_id)


async def test_get_entity_404_for_unknown_entity_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(
        f"/tenants/{tenant_id}/entities/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_get_entity_404_for_entity_belonging_to_a_different_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Membership on *both* tenants, deliberately - the 404 here must be
    about the entity belonging to a different tenant, not merely about
    missing membership in tenant_b (a different, already-covered case).
    """
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        session.add_all(
            [
                Membership(tenant_id=tenant_a.id, user_id=test_user_id, role=MembershipRole.OWNER),
                Membership(tenant_id=tenant_b.id, user_id=test_user_id, role=MembershipRole.OWNER),
            ]
        )
        entity = Entity(tenant_id=tenant_a.id, name="Tenant A's Entity")
        session.add(entity)
        await session.commit()
        tenant_a_id, tenant_b_id, entity_id = tenant_a.id, tenant_b.id, entity.id

    # Entity exists, but under tenant_a - requesting it via tenant_b's path
    # must 404, not leak it across tenants.
    response = await client.get(f"/tenants/{tenant_b_id}/entities/{entity_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_a_id)
    await delete_tenant(tenant_b_id)


async def test_get_entity_404_for_unknown_tenant_id(client: AsyncClient) -> None:
    response = await client.get(
        "/tenants/00000000-0000-0000-0000-000000000000/entities/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


async def test_get_entity_hides_gm_only_information_from_a_plain_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The core regression test (ADR 0028's addendum): information with no
    is_public and no Knowledge row is GM-only by default (RFC 0001) - a
    plain member must not see it.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        entity = Entity(tenant_id=tenant_id, name="Entity")
        session.add(entity)
        await session.flush()
        session.add(
            Information(tenant_id=tenant_id, entity_id=entity.id, title="Secret", type="gm-note")
        )
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert response.status_code == 200
    assert response.json()["information"] == []

    await delete_tenant(tenant_id)


async def test_get_entity_shows_public_information_to_any_tenant_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        entity = Entity(tenant_id=tenant_id, name="Entity")
        session.add(entity)
        await session.flush()
        session.add(
            Information(
                tenant_id=tenant_id,
                entity_id=entity.id,
                title="Town square",
                type="description",
                is_public=True,
            )
        )
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert response.status_code == 200
    assert [info["title"] for info in response.json()["information"]] == ["Town square"]

    await delete_tenant(tenant_id)


async def test_get_entity_shows_information_known_via_direct_character_knowledge(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Full Campaign/Player/Being/CharacterPlayer/Knowledge chain, not a
    shortcut - proves the real roster-reuse traversal, not just that a
    Knowledge row with a matching id exists somewhere.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        character = Entity(tenant_id=tenant_id, name="Character")
        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add_all([character, subject])
        await session.flush()
        session.add(Being(entity_id=character.id, tenant_id=tenant_id))
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=character.id, player_id=player.id, tenant_id=tenant_id
            )
        )
        info = Information(
            tenant_id=tenant_id, entity_id=subject.id, title="A secret", type="gm-note"
        )
        session.add(info)
        await session.flush()
        session.add(
            Knowledge(tenant_id=tenant_id, knower_entity_id=character.id, information_id=info.id)
        )
        await session.commit()
        subject_id = subject.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{subject_id}")
    assert response.status_code == 200
    assert [info["title"] for info in response.json()["information"]] == ["A secret"]

    await delete_tenant(tenant_id)


async def test_get_entity_shows_information_known_via_group_membership(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        character = Entity(tenant_id=tenant_id, name="Character")
        group = Entity(tenant_id=tenant_id, name="Group")
        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add_all([character, group, subject])
        await session.flush()
        session.add(Being(entity_id=character.id, tenant_id=tenant_id))
        await session.flush()
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=character.id, player_id=player.id, tenant_id=tenant_id
                ),
                GroupMember(
                    group_entity_id=group.id, character_entity_id=character.id, tenant_id=tenant_id
                ),
            ]
        )
        info = Information(
            tenant_id=tenant_id, entity_id=subject.id, title="Guild secret", type="gm-note"
        )
        session.add(info)
        await session.flush()
        # Knowledge on the GROUP, not the character directly - proves the
        # one-level group-derived path specifically.
        session.add(
            Knowledge(tenant_id=tenant_id, knower_entity_id=group.id, information_id=info.id)
        )
        await session.commit()
        subject_id = subject.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{subject_id}")
    assert response.status_code == 200
    assert [info["title"] for info in response.json()["information"]] == ["Guild secret"]

    await delete_tenant(tenant_id)


async def test_get_entity_shows_information_known_via_direct_player_knowledge(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """No Being/CharacterPlayer at all - the OOC-hint case, knower_player_id
    only.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add(subject)
        await session.flush()
        info = Information(
            tenant_id=tenant_id, entity_id=subject.id, title="OOC hint", type="gm-note"
        )
        session.add(info)
        await session.flush()
        session.add(
            Knowledge(tenant_id=tenant_id, knower_player_id=player.id, information_id=info.id)
        )
        await session.commit()
        subject_id = subject.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{subject_id}")
    assert response.status_code == 200
    assert [info["title"] for info in response.json()["information"]] == ["OOC hint"]

    await delete_tenant(tenant_id)


async def test_get_entity_hides_information_known_only_to_a_different_users_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Guards against an implementation that checks "does any Knowledge
    exist" instead of "does this caller's own resolved id set match" -
    test_user_id has their own unrelated player/character with no matching
    Knowledge; a separate user's character is the actual knower.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()

        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        my_player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        other_player = Player(user_id=other_user.id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add_all([my_player, other_player])
        await session.flush()

        my_character = Entity(tenant_id=tenant_id, name="My Character")
        other_character = Entity(tenant_id=tenant_id, name="Other Character")
        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add_all([my_character, other_character, subject])
        await session.flush()
        session.add_all(
            [
                Being(entity_id=my_character.id, tenant_id=tenant_id),
                Being(entity_id=other_character.id, tenant_id=tenant_id),
            ]
        )
        await session.flush()
        session.add_all(
            [
                CharacterPlayer(
                    character_entity_id=my_character.id,
                    player_id=my_player.id,
                    tenant_id=tenant_id,
                ),
                CharacterPlayer(
                    character_entity_id=other_character.id,
                    player_id=other_player.id,
                    tenant_id=tenant_id,
                ),
            ]
        )
        info = Information(
            tenant_id=tenant_id, entity_id=subject.id, title="Not yours", type="gm-note"
        )
        session.add(info)
        await session.flush()
        session.add(
            Knowledge(
                tenant_id=tenant_id, knower_entity_id=other_character.id, information_id=info.id
            )
        )
        await session.commit()
        subject_id, other_user_id = subject.id, other_user.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{subject_id}")
    assert response.status_code == 200
    assert response.json()["information"] == []

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_user_id))
        await session.commit()


async def test_get_entity_orga_sees_everything_regardless_of_knowledge(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))
        entity = Entity(tenant_id=tenant_id, name="Entity")
        session.add(entity)
        await session.flush()
        session.add(
            Information(tenant_id=tenant_id, entity_id=entity.id, title="Secret", type="gm-note")
        )
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert response.status_code == 200
    assert [info["title"] for info in response.json()["information"]] == ["Secret"]

    await delete_tenant(tenant_id)


async def test_get_entity_orga_bypass_suppressed_by_opt_out(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0028's addendum: an ORGA's blanket bypass is suppressed on this
    route by any active TenantAdminCampaignOptOut anywhere in the tenant - the
    fail-closed choice, since this route has no campaign context to check
    the opt-out's own per-campaign scope against.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))
        campaign = await make_campaign(
            session, tenant_id=tenant_id, name="Campaign", game_system="D&D 5e"
        )
        await session.flush()
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign.id
            )
        )
        entity = Entity(tenant_id=tenant_id, name="Entity")
        session.add(entity)
        await session.flush()
        session.add(
            Information(tenant_id=tenant_id, entity_id=entity.id, title="Secret", type="gm-note")
        )
        await session.commit()
        entity_id = entity.id

    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert response.status_code == 200
    assert response.json()["information"] == []

    await delete_tenant(tenant_id)


async def test_get_entity_information_visibility_is_tenant_scoped(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A matching Knowledge chain in a second tenant must not leak
    visibility into the first tenant's otherwise-identical, non-public,
    no-Knowledge information.
    """
    async with admin_session_factory() as session:
        tenant_a = Tenant()
        tenant_b = Tenant()
        session.add_all([tenant_a, tenant_b])
        await session.flush()
        tenant_a_id, tenant_b_id = tenant_a.id, tenant_b.id
        session.add_all(
            [
                Membership(tenant_id=tenant_a_id, user_id=test_user_id, role=MembershipRole.OWNER),
                Membership(tenant_id=tenant_b_id, user_id=test_user_id, role=MembershipRole.OWNER),
            ]
        )

        entity_a = Entity(tenant_id=tenant_a_id, name="Entity A")
        session.add(entity_a)
        await session.flush()
        session.add(
            Information(
                tenant_id=tenant_a_id, entity_id=entity_a.id, title="Secret A", type="gm-note"
            )
        )

        # Tenant B: a full player/character/Knowledge chain that would
        # grant visibility - but only within tenant B.
        campaign_b = await make_campaign(
            session, tenant_id=tenant_b_id, name="Campaign B", game_system="D&D 5e"
        )
        await session.flush()
        player_b = Player(user_id=test_user_id, campaign_id=campaign_b.id, tenant_id=tenant_b_id)
        session.add(player_b)
        await session.flush()
        character_b = Entity(tenant_id=tenant_b_id, name="Character B")
        session.add(character_b)
        await session.flush()
        session.add(Being(entity_id=character_b.id, tenant_id=tenant_b_id))
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=character_b.id, player_id=player_b.id, tenant_id=tenant_b_id
            )
        )
        entity_b = Entity(tenant_id=tenant_b_id, name="Entity B")
        session.add(entity_b)
        await session.flush()
        info_b = Information(
            tenant_id=tenant_b_id, entity_id=entity_b.id, title="Secret B", type="gm-note"
        )
        session.add(info_b)
        await session.flush()
        session.add(
            Knowledge(
                tenant_id=tenant_b_id, knower_entity_id=character_b.id, information_id=info_b.id
            )
        )
        await session.commit()
        entity_a_id = entity_a.id

    response = await client.get(f"/tenants/{tenant_a_id}/entities/{entity_a_id}")
    assert response.status_code == 200
    assert response.json()["information"] == []

    await delete_tenant(tenant_a_id)
    await delete_tenant(tenant_b_id)
