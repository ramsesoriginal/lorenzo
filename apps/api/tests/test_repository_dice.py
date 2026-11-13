"""ADR 0462: a dice value travels with a repository - copied into a library as the parts it is, its
change upstream found and applied as one value, a merge of identical pieces taking it into account.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import (
    ComputedStat,
    ComputedStatDiceValue,
    Entity,
    EntityStat,
    EntityStatGroup,
    RepositoryCopyLinkEntity,
    StatDefinition,
    StatGroup,
    StatValueType,
)


async def _repository(author, name: str = "Weapons"):  # type: ignore[no-untyped-def]
    repository = await author.create_tenant(name, kind="repository")
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=repository, name="Combat")
        session.add(group)
        await session.flush()
        damage = StatDefinition(
            tenant_id=repository,
            stat_group_id=group.id,
            name="Damage",
            value_type=StatValueType.DICE,
        )
        max_damage = StatDefinition(
            tenant_id=repository,
            stat_group_id=group.id,
            name="Max damage",
            value_type=StatValueType.INT,
        )
        longsword = Entity(tenant_id=repository, name="Longsword")
        dagger = Entity(tenant_id=repository, name="Dagger")
        session.add_all([damage, max_damage, longsword, dagger])
        await session.flush()
        session.add_all(
            [
                EntityStatGroup(
                    entity_id=longsword.id, stat_group_id=group.id, tenant_id=repository
                ),
                EntityStatGroup(entity_id=dagger.id, stat_group_id=group.id, tenant_id=repository),
                EntityStat(
                    entity_id=longsword.id,
                    stat_definition_id=damage.id,
                    tenant_id=repository,
                    dice_count=2,
                    dice_sides=6,
                ),
                EntityStat(
                    entity_id=dagger.id,
                    stat_definition_id=damage.id,
                    tenant_id=repository,
                    dice_count=4,
                    dice_sides=6,
                    dice_drop_mode="lowest",
                    dice_drop_count=1,
                ),
            ]
        )
        # What the longsword can do at most: a formula that reads its dice (ADR 0463).
        session.add(
            ComputedStat(
                entity_id=longsword.id, stat_definition_id=max_damage.id, tenant_id=repository
            )
        )
        await session.flush()
        session.add(
            ComputedStatDiceValue(
                entity_id=longsword.id,
                stat_definition_id=max_damage.id,
                tenant_id=repository,
                source_stat_definition_id=damage.id,
                read_as="max",
            )
        )
        await session.commit()
        return repository, damage.id, longsword.id, dagger.id, max_damage.id


async def _copy(author, gm, repository: uuid.UUID) -> uuid.UUID:  # type: ignore[no-untyped-def]
    table = await gm.create_tenant("My Table")
    assert (await author.put(f"/tenants/{repository}/subscribers/{table}")).status_code == 201
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
    copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
    assert copied.status_code == 201, copied.text
    return table


async def _values(gm, table: uuid.UUID) -> dict[str, dict]:  # type: ignore[no-untyped-def, type-arg]
    """The table's own entries by name: their `Damage` as the API reads it."""
    async with admin_session_factory() as session:
        entries = dict(
            (
                await session.execute(
                    select(Entity.name, Entity.id).where(Entity.tenant_id == table)
                )
            ).all()
        )
    found = {}
    for name, entity_id in entries.items():
        read = await gm.get(f"/tenants/{table}/entities/{entity_id}")
        assert read.status_code == 200, read.text
        found[name] = {s["name"]: s for s in read.json()["stats"]}
    return found


async def test_a_copy_brings_a_dice_stat_and_its_values_as_parts(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository, damage, _, _, _ = await _repository(author)
    table = await _copy(author, gm, repository)
    try:
        values = await _values(gm, table)
        assert values["Longsword"]["Damage"]["value"] == "2d6"
        assert values["Dagger"]["Damage"]["value"] == "4d6dl1"
        assert values["Dagger"]["Damage"]["dice"] == {
            "count": 4,
            "sides": 6,
            "drop": {"mode": "lowest", "count": 1},
        }
        async with admin_session_factory() as session:
            definition = await session.scalar(
                select(StatDefinition).where(
                    StatDefinition.tenant_id == table, StatDefinition.name == "Damage"
                )
            )
            assert definition is not None and definition.value_type is StatValueType.DICE
            rows = (
                await session.scalars(select(EntityStat).where(EntityStat.tenant_id == table))
            ).all()
            assert sorted((r.dice_count, r.dice_sides, r.value_int) for r in rows) == [
                (2, 6, None),
                (4, 6, None),
            ]
    finally:
        await cleanup([repository, table], [author, gm])


async def test_a_change_upstream_is_one_clean_change_of_the_value_and_is_applied_as_parts(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository, damage, longsword, dagger, _ = await _repository(author)
    table = await _copy(author, gm, repository)
    url = f"/tenants/{table}/repositories/{repository}"
    try:
        assert (await gm.get(f"{url}/updates")).json()["changed"] == []
        async with admin_session_factory() as session:
            row = await session.get_one(EntityStat, (longsword, damage))
            row.dice_count, row.dice_sides = 1, 12
            row = await session.get_one(EntityStat, (dagger, damage))
            row.dice_drop_mode, row.dice_drop_count = "highest", 2
            await session.commit()

        updates = (await gm.get(f"{url}/updates")).json()
        fields = {row["name"]: {f["field"]: f for f in row["fields"]} for row in updates["changed"]}
        stat = fields["Longsword"][f"stats:{damage}"]
        assert (stat["state"], stat["label"]) == ("clean", "Damage")
        assert (stat["base"], stat["upstream"]) == ("2d6", "d12")
        assert fields["Dagger"][f"stats:{damage}"]["upstream"] == "4d6dh2"

        actions = [
            {"kind": "entity", "source_id": str(longsword), "action": "apply"},
            {"kind": "entity", "source_id": str(dagger), "action": "apply"},
        ]
        applied = await gm.post(f"{url}/updates", json={"actions": actions})
        assert applied.status_code == 200, applied.text
        assert applied.json()["applied"] == 2

        values = await _values(gm, table)
        assert values["Longsword"]["Damage"]["value"] == "d12"
        assert values["Longsword"]["Damage"]["dice"] == {"count": 1, "sides": 12, "drop": None}
        assert values["Dagger"]["Damage"]["dice"]["drop"] == {"mode": "highest", "count": 2}
        # Applied, it is up to date: no change is offered again.
        assert (await gm.get(f"{url}/updates")).json()["changed"] == []
        async with admin_session_factory() as session:
            rows = (
                await session.scalars(
                    select(RepositoryCopyLinkEntity).where(
                        RepositoryCopyLinkEntity.tenant_id == table
                    )
                )
            ).all()
            assert len(rows) == 2
    finally:
        await cleanup([repository, table], [author, gm])


async def test_a_dice_value_formula_is_copied_reading_the_copied_dice_and_updated_as_one_change(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository, damage, longsword, _, max_damage = await _repository(author)
    table = await _copy(author, gm, repository)
    url = f"/tenants/{table}/repositories/{repository}"
    try:
        values = await _values(gm, table)
        assert values["Longsword"]["Max damage"]["value"] == 12
        assert values["Longsword"]["Max damage"]["computed"] is True
        async with admin_session_factory() as session:
            local = await session.scalar(
                select(StatDefinition.id).where(
                    StatDefinition.tenant_id == table, StatDefinition.name == "Damage"
                )
            )
            reading = (
                await session.scalars(
                    select(ComputedStatDiceValue).where(ComputedStatDiceValue.tenant_id == table)
                )
            ).one()
            assert (reading.source_stat_definition_id, reading.read_as) == (local, "max")
        assert (await gm.get(f"{url}/updates")).json()["changed"] == []

        async with admin_session_factory() as session:
            row = await session.get_one(ComputedStatDiceValue, (longsword, max_damage))
            row.read_as, row.round_mode = "average", "ceil"
            await session.commit()
        updates = (await gm.get(f"{url}/updates")).json()
        (changed,) = [row for row in updates["changed"] if row["name"] == "Longsword"]
        (formula,) = [f for f in changed["fields"] if f["field"].startswith("formulas:")]
        assert formula["state"] == "clean"
        assert (formula["base"]["as"], formula["upstream"]["as"]) == ("max", "average")
        assert formula["upstream"]["round_mode"] == "ceil"

        actions = [{"kind": "entity", "source_id": str(longsword), "action": "apply"}]
        applied = await gm.post(f"{url}/updates", json={"actions": actions})
        assert applied.status_code == 200, applied.text
        assert applied.json()["not_applied"] == []
        values = await _values(gm, table)
        assert values["Longsword"]["Max damage"]["value"] == 7
        assert (await gm.get(f"{url}/updates")).json()["changed"] == []
    finally:
        await cleanup([repository, table], [author, gm])
