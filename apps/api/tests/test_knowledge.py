import pytest
from _admin_db import admin_session_factory
from conftest import make_player
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from lorenzo_api.db import engine
from lorenzo_api.models import (
    Being,
    Campaign,
    Entity,
    GroupMember,
    Information,
    Knowledge,
    Tenant,
    User,
)


async def test_group_member_basic_membership() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        group = Entity(tenant_id=tenant_id, name="The Thieves' Guild")
        char_a = Entity(tenant_id=tenant_id, name="Char A")
        char_b = Entity(tenant_id=tenant_id, name="Char B")
        session.add_all([group, char_a, char_b])
        await session.flush()
        session.add_all(
            [
                Being(entity_id=char_a.id, tenant_id=tenant_id),
                Being(entity_id=char_b.id, tenant_id=tenant_id),
            ]
        )
        await session.flush()
        group_id, char_a_id, char_b_id = group.id, char_a.id, char_b.id
        session.add_all(
            [
                GroupMember(
                    group_entity_id=group_id, character_entity_id=char_a_id, tenant_id=tenant_id
                ),
                GroupMember(
                    group_entity_id=group_id, character_entity_id=char_b_id, tenant_id=tenant_id
                ),
            ]
        )
        await session.commit()

        members = (
            (
                await session.execute(
                    select(GroupMember.character_entity_id).where(
                        GroupMember.group_entity_id == group_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert set(members) == {char_a_id, char_b_id}

        await session.delete(tenant)
        await session.commit()


async def test_group_member_self_loop_rejected() -> None:
    """RFC 0001: an entity isn't limited to one concrete table - nothing
    stops something used as a group from also having a Being row. The
    CHECK still must reject it listing itself as its own member.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        dual = Entity(tenant_id=tenant_id, name="Both a group and a being")
        session.add(dual)
        await session.flush()
        dual_id = dual.id
        session.add(Being(entity_id=dual_id, tenant_id=tenant_id))
        await session.commit()

        session.add(
            GroupMember(group_entity_id=dual_id, character_entity_id=dual_id, tenant_id=tenant_id)
        )
        with pytest.raises(IntegrityError, match="group_member_no_self_loop"):
            await session.commit()
        await session.rollback()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_group_member_cascades_on_group_or_character_deletion() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        group_1 = Entity(tenant_id=tenant_id, name="Group 1")
        char_1 = Entity(tenant_id=tenant_id, name="Char 1")
        group_2 = Entity(tenant_id=tenant_id, name="Group 2")
        char_2 = Entity(tenant_id=tenant_id, name="Char 2")
        session.add_all([group_1, char_1, group_2, char_2])
        await session.flush()
        group_1_id, char_1_id = group_1.id, char_1.id
        group_2_id, char_2_id = group_2.id, char_2.id
        session.add_all(
            [
                Being(entity_id=char_1_id, tenant_id=tenant_id),
                Being(entity_id=char_2_id, tenant_id=tenant_id),
            ]
        )
        await session.flush()
        session.add_all(
            [
                GroupMember(
                    group_entity_id=group_1_id, character_entity_id=char_1_id, tenant_id=tenant_id
                ),
                GroupMember(
                    group_entity_id=group_2_id, character_entity_id=char_2_id, tenant_id=tenant_id
                ),
            ]
        )
        await session.commit()

        # Deleting the group removes the membership row, not the character.
        await session.delete(await session.get_one(Entity, group_1_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(GroupMember, (group_1_id, char_1_id)) is None
        assert await session.get(Entity, char_1_id) is not None

        # Deleting the character removes the membership row, not the group.
        await session.delete(await session.get_one(Entity, char_2_id))
        await session.commit()

    async with admin_session_factory() as session:
        assert await session.get(GroupMember, (group_2_id, char_2_id)) is None
        assert await session.get(Entity, group_2_id) is not None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_knowledge_requires_exactly_one_knower_rejects_neither_set() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        entity = Entity(tenant_id=tenant_id, name="Entity")
        session.add(entity)
        await session.flush()
        info = Information(tenant_id=tenant_id, entity_id=entity.id, title="Secret", type="rumor")
        session.add(info)
        await session.commit()
        info_id = info.id

        session.add(Knowledge(tenant_id=tenant_id, information_id=info_id))
        with pytest.raises(IntegrityError, match="knowledge_exactly_one_knower"):
            await session.commit()
        await session.rollback()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_knowledge_requires_exactly_one_knower_rejects_both_set() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)

        entity = Entity(tenant_id=tenant_id, name="Entity")
        session.add(entity)
        await session.flush()
        info = Information(tenant_id=tenant_id, entity_id=entity.id, title="Secret", type="rumor")
        session.add(info)
        await session.commit()
        info_id, entity_id = info.id, entity.id
        player_id, user_id = player.id, player.user_id

        session.add(
            Knowledge(
                tenant_id=tenant_id,
                knower_entity_id=entity_id,
                knower_player_id=player_id,
                information_id=info_id,
            )
        )
        with pytest.raises(IntegrityError, match="knowledge_exactly_one_knower"):
            await session.commit()
        await session.rollback()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_knowledge_character_knower_end_to_end() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        character = Entity(tenant_id=tenant_id, name="Character")
        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add_all([character, subject])
        await session.flush()
        character_id = character.id
        session.add(Being(entity_id=character_id, tenant_id=tenant_id))
        info = Information(tenant_id=tenant_id, entity_id=subject.id, title="Secret", type="rumor")
        session.add(info)
        await session.flush()
        info_id = info.id
        session.add(
            Knowledge(tenant_id=tenant_id, knower_entity_id=character_id, information_id=info_id)
        )
        await session.commit()

        row = (
            await session.execute(select(Knowledge).where(Knowledge.information_id == info_id))
        ).scalar_one()
        assert row.knower_entity_id == character_id
        assert row.knower_player_id is None

        await session.delete(tenant)
        await session.commit()


async def test_knowledge_group_knower_end_to_end() -> None:
    """The same knower_entity_id column covers the group case too - a bare
    entity with GroupMember rows, disambiguated only by having no Being
    row of its own (RFC 0001).
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        group = Entity(tenant_id=tenant_id, name="Group")
        member = Entity(tenant_id=tenant_id, name="Member")
        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add_all([group, member, subject])
        await session.flush()
        group_id, member_id = group.id, member.id
        session.add(Being(entity_id=member_id, tenant_id=tenant_id))
        await session.flush()
        session.add(
            GroupMember(
                group_entity_id=group_id, character_entity_id=member_id, tenant_id=tenant_id
            )
        )
        info = Information(tenant_id=tenant_id, entity_id=subject.id, title="Secret", type="rumor")
        session.add(info)
        await session.flush()
        info_id = info.id
        session.add(
            Knowledge(tenant_id=tenant_id, knower_entity_id=group_id, information_id=info_id)
        )
        await session.commit()

        row = (
            await session.execute(select(Knowledge).where(Knowledge.information_id == info_id))
        ).scalar_one()
        assert row.knower_entity_id == group_id
        # The group itself has no Being row - that's what makes it a group
        # rather than a character, per RFC 0001.
        assert await session.get(Being, group_id) is None

        await session.delete(tenant)
        await session.commit()


async def test_knowledge_player_knower_end_to_end() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)

        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add(subject)
        await session.flush()
        info = Information(tenant_id=tenant_id, entity_id=subject.id, title="Secret", type="rumor")
        session.add(info)
        await session.flush()
        player_id, info_id, user_id = player.id, info.id, player.user_id
        session.add(
            Knowledge(tenant_id=tenant_id, knower_player_id=player_id, information_id=info_id)
        )
        await session.commit()

        row = (
            await session.execute(select(Knowledge).where(Knowledge.information_id == info_id))
        ).scalar_one()
        assert row.knower_player_id == player_id
        assert row.knower_entity_id is None

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_knowledge_duplicate_entity_knower_information_pair_rejected() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        character = Entity(tenant_id=tenant_id, name="Character")
        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add_all([character, subject])
        await session.flush()
        character_id = character.id
        session.add(Being(entity_id=character_id, tenant_id=tenant_id))
        info = Information(tenant_id=tenant_id, entity_id=subject.id, title="Secret", type="rumor")
        session.add(info)
        await session.flush()
        info_id = info.id
        session.add(
            Knowledge(tenant_id=tenant_id, knower_entity_id=character_id, information_id=info_id)
        )
        await session.commit()

        session.add(
            Knowledge(tenant_id=tenant_id, knower_entity_id=character_id, information_id=info_id)
        )
        with pytest.raises(IntegrityError, match="knowledge_unique_entity_knower_information"):
            await session.commit()
        await session.rollback()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_knowledge_duplicate_player_knower_information_pair_rejected() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)

        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add(subject)
        await session.flush()
        info = Information(tenant_id=tenant_id, entity_id=subject.id, title="Secret", type="rumor")
        session.add(info)
        await session.flush()
        player_id, info_id, user_id = player.id, info.id, player.user_id
        session.add(
            Knowledge(tenant_id=tenant_id, knower_player_id=player_id, information_id=info_id)
        )
        await session.commit()

        session.add(
            Knowledge(tenant_id=tenant_id, knower_player_id=player_id, information_id=info_id)
        )
        with pytest.raises(IntegrityError, match="knowledge_unique_player_knower_information"):
            await session.commit()
        await session.rollback()

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_knowledge_allows_same_information_for_different_knowers() -> None:
    """The two UniqueConstraints only block an *identical* knower pointing
    at the same information row twice - several different knowers sharing
    one information row (the "visible to a subset" case) must still work.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = Campaign(tenant_id=tenant_id, name="Campaign", game_system="D&D 5e")
        session.add(campaign)
        await session.flush()
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)

        character_a = Entity(tenant_id=tenant_id, name="Character A")
        character_b = Entity(tenant_id=tenant_id, name="Character B")
        subject = Entity(tenant_id=tenant_id, name="Subject")
        session.add_all([character_a, character_b, subject])
        await session.flush()
        char_a_id, char_b_id = character_a.id, character_b.id
        session.add_all(
            [
                Being(entity_id=char_a_id, tenant_id=tenant_id),
                Being(entity_id=char_b_id, tenant_id=tenant_id),
            ]
        )
        info = Information(tenant_id=tenant_id, entity_id=subject.id, title="Secret", type="rumor")
        session.add(info)
        await session.flush()
        info_id, player_id, user_id = info.id, player.id, player.user_id

        session.add_all(
            [
                Knowledge(tenant_id=tenant_id, knower_entity_id=char_a_id, information_id=info_id),
                Knowledge(tenant_id=tenant_id, knower_entity_id=char_b_id, information_id=info_id),
                Knowledge(tenant_id=tenant_id, knower_player_id=player_id, information_id=info_id),
            ]
        )
        await session.commit()

        rows = (
            (await session.execute(select(Knowledge.id).where(Knowledge.information_id == info_id)))
            .scalars()
            .all()
        )
        assert len(rows) == 3

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_information_is_public_defaults_false() -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

        entity = Entity(tenant_id=tenant_id, name="Entity")
        session.add(entity)
        await session.flush()
        info = Information(tenant_id=tenant_id, entity_id=entity.id, title="Secret", type="rumor")
        session.add(info)
        await session.commit()
        info_id = info.id

        fetched = await session.get(Information, info_id)
        assert fetched is not None
        assert fetched.is_public is False

        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_group_member_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    async with admin_session_factory() as session:
        tenant_a = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        group_a = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'group-a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        char_a = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'char-a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        group_b = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'group-b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        char_b = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'char-b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()

        await session.execute(
            text("INSERT INTO being (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": char_a, "t": tenant_a},
        )
        await session.execute(
            text("INSERT INTO being (entity_id, tenant_id) VALUES (:e, :t)"),
            {"e": char_b, "t": tenant_b},
        )
        await session.execute(
            text(
                "INSERT INTO group_member (group_entity_id, character_entity_id, tenant_id) "
                "VALUES (:g, :c, :t)"
            ),
            {"g": group_a, "c": char_a, "t": tenant_a},
        )
        await session.execute(
            text(
                "INSERT INTO group_member (group_entity_id, character_entity_id, tenant_id) "
                "VALUES (:g, :c, :t)"
            ),
            {"g": group_b, "c": char_b, "t": tenant_b},
        )
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            members = (
                (await conn.execute(text("SELECT character_entity_id FROM group_member")))
                .scalars()
                .all()
            )
            assert list(members) == [char_a]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            members = (
                (await conn.execute(text("SELECT character_entity_id FROM group_member")))
                .scalars()
                .all()
            )
            assert list(members) == [char_b]

        async with engine.begin() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT character_entity_id FROM group_member"))
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM group_member WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM being WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.commit()


async def test_knowledge_rls_isolates_tenants_for_a_non_superuser_role() -> None:
    async with admin_session_factory() as session:
        tenant_a = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()
        tenant_b = (
            await session.execute(text("INSERT INTO tenant DEFAULT VALUES RETURNING id"))
        ).scalar_one()

        entity_a = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'a') RETURNING id"),
                {"t": tenant_a},
            )
        ).scalar_one()
        entity_b = (
            await session.execute(
                text("INSERT INTO entity (tenant_id, name) VALUES (:t, 'b') RETURNING id"),
                {"t": tenant_b},
            )
        ).scalar_one()
        info_a = (
            await session.execute(
                text(
                    "INSERT INTO information (tenant_id, entity_id, title, type) "
                    "VALUES (:t, :e, 'Secret', 'rumor') RETURNING id"
                ),
                {"t": tenant_a, "e": entity_a},
            )
        ).scalar_one()
        info_b = (
            await session.execute(
                text(
                    "INSERT INTO information (tenant_id, entity_id, title, type) "
                    "VALUES (:t, :e, 'Secret', 'rumor') RETURNING id"
                ),
                {"t": tenant_b, "e": entity_b},
            )
        ).scalar_one()
        knowledge_a = (
            await session.execute(
                text(
                    "INSERT INTO knowledge (tenant_id, knower_entity_id, information_id) "
                    "VALUES (:t, :e, :i) RETURNING id"
                ),
                {"t": tenant_a, "e": entity_a, "i": info_a},
            )
        ).scalar_one()
        knowledge_b = (
            await session.execute(
                text(
                    "INSERT INTO knowledge (tenant_id, knower_entity_id, information_id) "
                    "VALUES (:t, :e, :i) RETURNING id"
                ),
                {"t": tenant_b, "e": entity_b, "i": info_b},
            )
        ).scalar_one()
        await session.commit()

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_a)}
            )
            rows = (await conn.execute(text("SELECT id FROM knowledge"))).scalars().all()
            assert list(rows) == [knowledge_a]

        async with engine.begin() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_b)}
            )
            rows = (await conn.execute(text("SELECT id FROM knowledge"))).scalars().all()
            assert list(rows) == [knowledge_b]

        async with engine.begin() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT id FROM knowledge"))
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM knowledge WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM information WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM entity WHERE tenant_id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.execute(
                text("DELETE FROM tenant WHERE id IN (:a, :b)"),
                {"a": tenant_a, "b": tenant_b},
            )
            await session.commit()
