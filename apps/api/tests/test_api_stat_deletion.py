"""ADR 0167: deleting a stat definition or a stat group that nothing uses, and refusing the
rest, through the real HTTP API."""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup, make_actor
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import delete, select

from lorenzo_api.models import (
    AuditLog,
    Entity,
    EntityStat,
    EntityStatGroup,
    StatDefinitionEnumValue,
)


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str = "physical") -> str:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _definition(
    client: AsyncClient,
    tenant_id: uuid.UUID,
    group_id: str,
    name: str,
    value_type: str = "int",
    **extra: object,
) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": name, "stat_group_id": group_id, "value_type": value_type, **extra},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _entity(tenant_id: uuid.UUID, name: str = "Door") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


async def _activity(tenant_id: uuid.UUID, action: str) -> list[AuditLog]:
    async with admin_session_factory() as session:
        rows = await session.scalars(
            select(AuditLog).where(AuditLog.tenant_id == tenant_id, AuditLog.action == action)
        )
        return list(rows)


# --- stat definitions ----------------------------------------------------------------------


async def test_an_unused_definition_is_deleted_logged_and_takes_its_enum_values(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    mood = await _definition(
        client, tenant_id, group, "mood", "enum", enum_values=["calm", "angry"]
    )
    url = f"/tenants/{tenant_id}/stat-definitions/{mood}"

    deleted = await client.delete(url)

    assert deleted.status_code == 204, deleted.text
    assert deleted.content == b""
    assert (await client.get(url)).status_code == 404
    listed = await client.get(f"/tenants/{tenant_id}/stat-definitions")
    assert [d["name"] for d in listed.json()["items"]] == []
    async with admin_session_factory() as session:
        left = await session.scalars(
            select(StatDefinitionEnumValue).where(
                StatDefinitionEnumValue.stat_definition_id == uuid.UUID(mood)
            )
        )
        assert list(left) == []
    [entry] = await _activity(tenant_id, "stat_definition.deleted")
    assert entry.target_id == uuid.UUID(mood)
    assert entry.detail == f"stat_group={group}, value_type=enum"
    await delete_tenant(tenant_id)


async def test_a_definition_that_does_not_exist_is_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.delete(f"/tenants/{tenant_id}/stat-definitions/{uuid.uuid4()}")

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_a_definition_in_another_tenant_is_404_and_untouched(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    mine, theirs = await make_tenant(test_user_id), await make_tenant(test_user_id)
    group = await _group(client, theirs)
    weight = await _definition(client, theirs, group, "weight")

    response = await client.delete(f"/tenants/{mine}/stat-definitions/{weight}")

    assert response.status_code == 404
    assert (await client.get(f"/tenants/{theirs}/stat-definitions/{weight}")).status_code == 200
    await delete_tenant(mine)
    await delete_tenant(theirs)


async def test_a_definition_an_entity_holds_a_value_for_is_refused_until_the_value_is_gone(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    weight = await _definition(client, tenant_id, group, "weight")
    door = await _entity(tenant_id)
    set_value = await client.put(
        f"/tenants/{tenant_id}/entities/{door}/stats/{weight}", json={"value": 5}
    )
    assert set_value.status_code == 200, set_value.text
    url = f"/tenants/{tenant_id}/stat-definitions/{weight}"

    refused = await client.delete(url)

    assert refused.status_code == 409
    assert refused.json()["type"].endswith("stat-definition-in-use")
    assert "1 value(s) held" in refused.json()["detail"]
    assert (await client.get(url)).status_code == 200
    assert await _activity(tenant_id, "stat_definition.deleted") == []
    async with admin_session_factory() as session:
        await session.execute(delete(EntityStat).where(EntityStat.entity_id == door))
        await session.commit()
    assert (await client.delete(url)).status_code == 204
    await delete_tenant(tenant_id)


async def test_a_definition_with_a_formula_for_it_or_one_that_reads_it_is_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    strength = await _definition(client, tenant_id, group, "strength")
    modifier = await _definition(client, tenant_id, group, "modifier")
    hero = await _entity(tenant_id, "Hero")
    formula = await client.put(
        f"/tenants/{tenant_id}/entities/{hero}/computed-stats/{modifier}",
        json={
            "kind": "linear",
            "source_stat_definition_id": strength,
            "multiplier": 0.5,
            "round_mode": "floor",
        },
    )
    assert formula.status_code == 200, formula.text
    base = f"/tenants/{tenant_id}/stat-definitions"

    for_it = await client.delete(f"{base}/{modifier}")
    reading_it = await client.delete(f"{base}/{strength}")

    assert for_it.status_code == reading_it.status_code == 409
    assert "1 formula(s) for it" in for_it.json()["detail"]
    assert "1 formula(s) reading it" in reading_it.json()["detail"]
    removed = await client.delete(f"/tenants/{tenant_id}/entities/{hero}/computed-stats/{modifier}")
    assert removed.status_code == 204, removed.text
    assert (await client.delete(f"{base}/{modifier}")).status_code == 204
    assert (await client.delete(f"{base}/{strength}")).status_code == 204
    await delete_tenant(tenant_id)


async def test_a_definition_read_by_a_comparison_sum_or_contents_formula_is_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    left = await _definition(client, tenant_id, group, "left")
    right = await _definition(client, tenant_id, group, "right")
    heavy = await _definition(client, tenant_id, group, "heavy", "bool")
    term = await _definition(client, tenant_id, group, "term")
    total = await _definition(client, tenant_id, group, "total")
    inside = await _definition(client, tenant_id, group, "inside")
    carried = await _definition(client, tenant_id, group, "carried")
    hero = await _entity(tenant_id, "Hero")
    formulas = f"/tenants/{tenant_id}/entities/{hero}/computed-stats"
    bodies = {
        heavy: {
            "kind": "comparison",
            "left_stat_definition_id": left,
            "comparator": "gt",
            "right_stat_definition_id": right,
        },
        total: {"kind": "sum", "terms": [{"stat_definition_id": term}]},
        carried: {"kind": "contents", "source_stat_definition_id": inside},
    }
    for target, body in bodies.items():
        made = await client.put(f"{formulas}/{target}", json=body)
        assert made.status_code == 200, made.text
    base = f"/tenants/{tenant_id}/stat-definitions"

    for read in (left, right, term, inside):
        refused = await client.delete(f"{base}/{read}")
        assert refused.status_code == 409, refused.text
        assert "1 formula(s) reading it" in refused.json()["detail"]
    for target in bodies:
        assert (await client.delete(f"{formulas}/{target}")).status_code == 204
    for read in (left, right, term, inside):
        assert (await client.delete(f"{base}/{read}")).status_code == 204
    await delete_tenant(tenant_id)


# --- stat groups -----------------------------------------------------------------------------


async def test_an_empty_group_is_deleted_and_logged(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    url = f"/tenants/{tenant_id}/stat-groups/{group}"

    deleted = await client.delete(url)

    assert deleted.status_code == 204, deleted.text
    assert (await client.get(url)).status_code == 404
    [entry] = await _activity(tenant_id, "stat_group.deleted")
    assert entry.target_id == uuid.UUID(group)
    assert entry.detail == "priority=0"
    assert (await client.delete(url)).status_code == 404
    await delete_tenant(tenant_id)


async def test_a_group_that_holds_a_definition_is_refused_and_so_are_its_values(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    weight = await _definition(client, tenant_id, group, "weight")
    door = await _entity(tenant_id)
    await client.put(f"/tenants/{tenant_id}/entities/{door}/stats/{weight}", json={"value": 5})
    url = f"/tenants/{tenant_id}/stat-groups/{group}"

    refused = await client.delete(url)

    assert refused.status_code == 409
    assert refused.json()["type"].endswith("stat-group-in-use")
    assert "1 stat definition(s) in it" in refused.json()["detail"]
    # Nothing was cascaded: the definition and its value are still there.
    assert (await client.get(f"/tenants/{tenant_id}/stat-definitions/{weight}")).status_code == 200
    stats = (await client.get(f"/tenants/{tenant_id}/entities/{door}")).json()["stats"]
    assert [s["value"] for s in stats if s["name"] == "weight"] == [5]
    await delete_tenant(tenant_id)


async def test_a_group_an_entity_has_acquired_is_refused_until_it_lets_go(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    door = await _entity(tenant_id)
    async with admin_session_factory() as session:
        session.add(
            EntityStatGroup(entity_id=door, stat_group_id=uuid.UUID(group), tenant_id=tenant_id)
        )
        await session.commit()
    url = f"/tenants/{tenant_id}/stat-groups/{group}"

    refused = await client.delete(url)

    assert refused.status_code == 409
    assert "1 entity(ies) that acquired it" in refused.json()["detail"]
    async with admin_session_factory() as session:
        await session.execute(delete(EntityStatGroup).where(EntityStatGroup.entity_id == door))
        await session.commit()
    assert (await client.delete(url)).status_code == 204
    await delete_tenant(tenant_id)


# --- repositories ------------------------------------------------------------------------------


async def test_a_definition_deleted_upstream_or_locally_shows_up_in_repository_updates(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Nothing about copies had to change: a row vanishing is something they already report."""
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await author.create_tenant("Armoury", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        group = (
            await author.post(f"/tenants/{repository}/stat-groups", json={"name": "Abilities"})
        ).json()["id"]
        made = {}
        for name in ("Wisdom", "Charisma"):
            response = await author.post(
                f"/tenants/{repository}/stat-definitions",
                json={"name": name, "stat_group_id": group, "value_type": "int"},
            )
            assert response.status_code == 201, response.text
            made[name] = response.json()["id"]
        assert (await author.put(f"/tenants/{repository}/subscribers/{table}")).status_code == 201
        assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
        assert copied.status_code == 201, copied.text
        url = f"/tenants/{table}/repositories/{repository}/updates"
        assert (await gm.get(url)).json()["removed"] == []

        # Upstream deletes Wisdom; the table deletes its own copy of Charisma.
        gone = await author.delete(f"/tenants/{repository}/stat-definitions/{made['Wisdom']}")
        assert gone.status_code == 204, gone.text
        mine = {
            d["name"]: d["id"]
            for d in (await gm.get(f"/tenants/{table}/stat-definitions")).json()["items"]
        }
        local = await gm.delete(f"/tenants/{table}/stat-definitions/{mine['Charisma']}")
        assert local.status_code == 204, local.text

        updates = (await gm.get(url)).json()
        assert [(r["kind"], r["name"]) for r in updates["removed"]] == [
            ("stat_definition", "Wisdom")
        ]
        assert [(r["kind"], r["name"]) for r in updates["deleted_locally"]] == [
            ("stat_definition", "Charisma")
        ]
        assert updates["changed"] == [] and updates["added"] == []
    finally:
        await cleanup([repository, table], [author, gm])
