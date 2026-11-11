"""ADR 0443: a chain of formulas, one reading the next, is read without failing the read, and a
write that would make one longer than 200 is refused."""

import uuid
from decimal import Decimal

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    ComputedStat,
    ComputedStatLinear,
    Entity,
    EntityStat,
    StatDefinition,
    StatGroup,
    StatValueType,
)
from lorenzo_api.stat_evaluation import MAX_FORMULA_CHAIN, longest_formula_chain


async def _chain(tenant_id: uuid.UUID, formulas: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """An entity with `formulas` + 1 stats `s0..s{n}`: `s{n}` holds 1 and each `s{i}` is a formula
    reading `s{i+1}` as it is. Inserted around the API, as a chain stored before the limit was."""
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant_id, name="chain")
        entity = Entity(tenant_id=tenant_id, name="Holder")
        session.add_all([group, entity])
        await session.flush()
        stats = [
            StatDefinition(
                tenant_id=tenant_id,
                stat_group_id=group.id,
                name=f"s{i}",
                value_type=StatValueType.INT,
            )
            for i in range(formulas + 1)
        ]
        session.add_all(stats)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=entity.id,
                stat_definition_id=stats[-1].id,
                tenant_id=tenant_id,
                value_int=1,
            )
        )
        session.add_all(
            ComputedStat(entity_id=entity.id, stat_definition_id=stats[i].id, tenant_id=tenant_id)
            for i in range(formulas)
        )
        await session.flush()
        session.add_all(
            ComputedStatLinear(
                entity_id=entity.id,
                stat_definition_id=stats[i].id,
                tenant_id=tenant_id,
                source_stat_definition_id=stats[i + 1].id,
                multiplier=Decimal(1),
                offset=Decimal(0),
                round_mode="none",
            )
            for i in range(formulas)
        )
        await session.commit()
        return entity.id, [s.id for s in stats]


async def _entity(tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


async def _new_stat(client: AsyncClient, tenant_id: uuid.UUID, name: str) -> str:
    groups = (await client.get(f"/tenants/{tenant_id}/stat-groups")).json()["items"]
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": groups[0]["id"], "name": name, "value_type": "int"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _reads(source: object) -> dict:
    return {
        "kind": "linear",
        "source_stat_definition_id": str(source),
        "multiplier": 1,
        "offset": 0,
        "round_mode": "none",
    }


async def _values(client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> dict:
    response = await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")
    assert response.status_code == 200, response.text
    return {s["name"]: s["value"] for s in response.json()["stats"]}


# --- reading ---------------------------------------------------------------------


async def test_a_chain_of_150_formulas_is_read_through_to_its_end(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity, _ = await _chain(tenant_id, 150)

    values = await _values(client, tenant_id, entity)

    assert len(values) == 151
    assert values["s0"] == values["s75"] == values["s150"] == 1
    await delete_tenant(tenant_id)


async def test_a_chain_of_600_formulas_is_read_and_its_far_end_has_no_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity, _ = await _chain(tenant_id, 600)

    response = await client.get(f"/tenants/{tenant_id}/entities/{entity}")

    assert response.status_code == 200, response.text  # it used to be a 500
    values = {s["name"]: s["value"] for s in response.json()["stats"]}
    assert values["s600"] == 1  # the stored value is still there
    assert "s0" not in values  # a chain too long to follow leaves its top without a value
    # Reading the listing of entries goes through the same evaluation.
    assert (await client.get(f"/tenants/{tenant_id}/entities")).status_code == 200
    await delete_tenant(tenant_id)


# --- writing ---------------------------------------------------------------------


async def test_a_write_that_makes_the_chain_longer_than_200_is_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity, stats = await _chain(tenant_id, MAX_FORMULA_CHAIN - 1)
    base = f"/tenants/{tenant_id}/entities/{entity}/computed-stats"
    top = await _new_stat(client, tenant_id, "top")
    over = await _new_stat(client, tenant_id, "over")
    below = await _new_stat(client, tenant_id, "below")

    reaching_200 = await client.put(f"{base}/{top}", json=_reads(stats[0]))
    reaching_201 = await client.put(f"{base}/{over}", json=_reads(top))
    previewed = await client.post(f"{base}/{over}/preview", json={"formula": _reads(top)})
    # A formula at the foot of the chain lengthens it as much as one on top. The graph is the
    # tenant's, so another entity's formula for the stat that holds the value counts.
    other = await _entity(tenant_id, "Other")
    foot = await client.put(
        f"/tenants/{tenant_id}/entities/{other}/computed-stats/{stats[-1]}", json=_reads(below)
    )

    assert reaching_200.status_code == 200, reaching_200.text
    assert reaching_201.status_code == 422, reaching_201.text
    assert reaching_201.json()["type"].endswith("formula-chain-too-deep")
    assert "201" in reaching_201.json()["detail"]
    assert previewed.status_code == 422, previewed.text
    assert foot.status_code == 422, foot.text
    names = {c["stat_definition_id"] for c in (await client.get(base)).json()}
    assert over not in names and stats[-1] not in names
    await delete_tenant(tenant_id)


async def test_a_chain_stored_beyond_the_limit_stays_and_other_formulas_are_not_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entity, stats = await _chain(tenant_id, 250)
    base = f"/tenants/{tenant_id}/entities/{entity}/computed-stats"
    left = await _new_stat(client, tenant_id, "left")
    right = await _new_stat(client, tenant_id, "right")

    unrelated = await client.put(f"{base}/{left}", json=_reads(right))
    other = await _entity(tenant_id, "Other")
    inside = await client.put(
        f"/tenants/{tenant_id}/entities/{other}/computed-stats/{stats[100]}", json=_reads(right)
    )
    lengthened = await client.put(f"{base}/{left}", json=_reads(stats[0]))

    assert unrelated.status_code == 200, unrelated.text  # not a chain through the long one
    assert inside.status_code == 422  # a write into it is a write to a chain beyond the limit
    assert lengthened.status_code == 422
    await delete_tenant(tenant_id)


def test_the_longest_chain_through_a_stat_counts_formulas_above_and_below() -> None:
    a, b, c, d, e, side = (uuid.uuid4() for _ in range(6))
    #  a reads b reads c reads d; e reads c; side reads nothing.
    edges = {a: {b}, b: {c}, c: {d}, e: {c}}
    assert longest_formula_chain(edges, a) == 3
    assert longest_formula_chain(edges, c) == 3  # a-b-c-d, 3 formulas
    assert longest_formula_chain(edges, e) == 2
    assert longest_formula_chain(edges, d) == 3
    assert longest_formula_chain(edges, side) == 0
    # A loop that slipped past the write-time check adds nothing and does not hang.
    assert longest_formula_chain({a: {b}, b: {a}, c: {d}}, c) == 1
