"""ADR 0117: every foreign key between two tenant tables is composite with
tenant_id, so no row can point into another tenant - whatever the code
writing it does. Uses the privileged connection throughout: a foreign-key
check doesn't care about RLS, and neither does this test.
"""

import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import make_campaign, make_character, make_player
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    Information,
    StatDefinition,
    StatGroup,
    StatValueType,
    Tenant,
    User,
)


async def _two_tenants() -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_session_factory() as session:
        a, b = Tenant(), Tenant()
        session.add_all([a, b])
        await session.commit()
        return a.id, b.id


async def _delete(*tenant_ids: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        for tenant_id in tenant_ids:
            await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def test_prototype_edge_into_another_tenant_is_refused() -> None:
    tenant_a, tenant_b = await _two_tenants()
    try:
        async with admin_session_factory() as session:
            mine = Entity(tenant_id=tenant_a, name="Mine")
            theirs = Entity(tenant_id=tenant_b, name="Theirs")
            session.add_all([mine, theirs])
            await session.flush()
            session.add(
                EntityPrototype(entity_id=mine.id, prototype_id=theirs.id, tenant_id=tenant_a)
            )
            with pytest.raises(IntegrityError, match="entity_prototype_prototype_id_fkey"):
                await session.commit()
    finally:
        await _delete(tenant_a, tenant_b)


async def test_row_claiming_the_wrong_tenant_is_refused() -> None:
    """Both ends in tenant B, the row itself labelled tenant A: refused too,
    so a row can't be smuggled into another tenant's graph by its own
    tenant_id either."""
    tenant_a, tenant_b = await _two_tenants()
    try:
        async with admin_session_factory() as session:
            box = Entity(tenant_id=tenant_b, name="Box")
            coin = Entity(tenant_id=tenant_b, name="Coin")
            session.add_all([box, coin])
            await session.flush()
            session.add(
                Containment(child_entity_id=coin.id, parent_entity_id=box.id, tenant_id=tenant_a)
            )
            with pytest.raises(IntegrityError, match="containment_child_entity_id_fkey"):
                await session.commit()
    finally:
        await _delete(tenant_a, tenant_b)


async def test_stat_value_for_another_tenants_definition_is_refused() -> None:
    tenant_a, tenant_b = await _two_tenants()
    try:
        async with admin_session_factory() as session:
            group = StatGroup(tenant_id=tenant_b, name="Theirs")
            session.add(group)
            await session.flush()
            definition = StatDefinition(
                tenant_id=tenant_b,
                stat_group_id=group.id,
                name="Strength",
                value_type=StatValueType.INT,
            )
            mine = Entity(tenant_id=tenant_a, name="Mine")
            session.add_all([definition, mine])
            await session.flush()
            session.add(
                EntityStat(
                    entity_id=mine.id,
                    stat_definition_id=definition.id,
                    tenant_id=tenant_a,
                    value_int=18,
                )
            )
            with pytest.raises(IntegrityError, match="entity_stat_stat_definition_id_fkey"):
                await session.commit()
    finally:
        await _delete(tenant_a, tenant_b)


async def test_information_about_another_tenants_entity_is_refused() -> None:
    tenant_a, tenant_b = await _two_tenants()
    try:
        async with admin_session_factory() as session:
            theirs = Entity(tenant_id=tenant_b, name="Theirs")
            session.add(theirs)
            await session.flush()
            session.add(
                Information(
                    tenant_id=tenant_a, entity_id=theirs.id, title="Secret", type="description"
                )
            )
            with pytest.raises(IntegrityError, match="information_entity_id_fkey"):
                await session.commit()
    finally:
        await _delete(tenant_a, tenant_b)


async def test_deleting_a_player_clears_only_owner_player_id() -> None:
    """The one nulling key is `ON DELETE SET NULL (owner_player_id)`: a
    plain SET NULL on a composite key would try to null tenant_id as well,
    and fail on its NOT NULL."""
    tenant_id, other = await _two_tenants()
    try:
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant_id)
            player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
            character = await make_character(
                session, tenant_id=tenant_id, owner_player_id=player.id
            )
            user_id, character_id = player.user_id, character.entity_id
            await session.commit()

            await session.execute(text("DELETE FROM player WHERE id = :p"), {"p": player.id})
            await session.commit()

            row = (
                await session.execute(
                    text('SELECT owner_player_id, tenant_id FROM "character" WHERE entity_id = :c'),
                    {"c": character_id},
                )
            ).one()
            assert row.owner_player_id is None
            assert row.tenant_id == tenant_id

            await session.delete(await session.get_one(User, user_id))
            await session.commit()
    finally:
        await _delete(tenant_id, other)


async def test_every_key_between_tenant_tables_includes_tenant_id() -> None:
    """The tripwire: a new table referencing tenant data with a plain
    single-column key fails here, not in production."""
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT c.conrelid::regclass::text AS tbl, c.conname
                    FROM pg_constraint c
                    JOIN pg_attribute src
                      ON src.attrelid = c.conrelid AND src.attname = 'tenant_id'
                    JOIN pg_attribute tgt
                      ON tgt.attrelid = c.confrelid AND tgt.attname = 'tenant_id'
                    WHERE c.contype = 'f'
                      AND c.confrelid <> 'tenant'::regclass
                      AND NOT (src.attnum = ANY (c.conkey))
                    ORDER BY 1, 2
                    """
                )
            )
        ).all()
    assert rows == []
