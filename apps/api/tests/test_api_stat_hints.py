"""ADR 0279: a maximum, a minimum and a resolved-value hint on a stat
definition: links to other definitions that are clues, never limits.
"""

import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from lorenzo_api.models import StatDefinition, StatGroup, StatValueType, User


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str = "Vitals") -> str:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _definition(
    client: AsyncClient,
    tenant_id: uuid.UUID,
    group_id: str,
    name: str,
    value_type: str = "int",
    **extra: object,
) -> dict:
    body: dict = {"stat_group_id": group_id, "name": name, "value_type": value_type, **extra}
    if value_type == "enum":
        body["enum_values"] = ["a", "b"]
    response = await client.post(f"/tenants/{tenant_id}/stat-definitions", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _url(tenant_id: uuid.UUID, definition_id: str) -> str:
    return f"/tenants/{tenant_id}/stat-definitions/{definition_id}"


async def test_a_definition_takes_its_hints_on_create_and_patch(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    maximum = await _definition(client, tenant_id, group, "max_stress")
    modifier = await _definition(client, tenant_id, group, "strength_modifier")
    stress = await _definition(client, tenant_id, group, "stress", max_hint_id=maximum["id"])
    strength = await _definition(client, tenant_id, group, "strength")

    assert stress["max_hint_id"] == maximum["id"]
    assert stress["min_hint_id"] is None
    assert strength["resolved_hint_id"] is None

    patched = await client.patch(
        _url(tenant_id, strength["id"]), json={"resolved_hint_id": modifier["id"]}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["resolved_hint_id"] == modifier["id"]
    fetched = (await client.get(_url(tenant_id, strength["id"]))).json()
    assert fetched["resolved_hint_id"] == modifier["id"]

    cleared = await client.patch(_url(tenant_id, strength["id"]), json={"resolved_hint_id": None})
    assert cleared.json()["resolved_hint_id"] is None
    await delete_tenant(tenant_id)


async def test_a_hint_must_be_another_definition_of_this_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other_tenant = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    foreign_group = await _group(client, other_tenant)
    foreign = await _definition(client, other_tenant, foreign_group, "elsewhere")
    stress = await _definition(client, tenant_id, group, "stress")

    for body in (
        {"max_hint_id": stress["id"]},  # itself
        {"max_hint_id": str(uuid.uuid4())},  # nothing
        {"resolved_hint_id": foreign["id"]},  # another tenant's
    ):
        response = await client.patch(_url(tenant_id, stress["id"]), json=body)
        assert response.status_code == 422, (body, response.text)
        assert response.json()["title"] == "That stat cannot be used as a hint here"
    created = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={
            "stat_group_id": group,
            "name": "new",
            "value_type": "int",
            "min_hint_id": foreign["id"],
        },
    )
    assert created.status_code == 422
    await delete_tenant(tenant_id)
    await delete_tenant(other_tenant)


async def test_a_minimum_or_maximum_must_be_a_number_a_resolved_hint_may_be_anything(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    text = await _definition(client, tenant_id, group, "name_of_class", "text")
    flag = await _definition(client, tenant_id, group, "is_blessed", "bool")
    real = await _definition(client, tenant_id, group, "reach", "float")
    stress = await _definition(client, tenant_id, group, "stress")
    url = _url(tenant_id, stress["id"])

    assert (await client.patch(url, json={"max_hint_id": text["id"]})).status_code == 422
    assert (await client.patch(url, json={"min_hint_id": flag["id"]})).status_code == 422
    assert (await client.patch(url, json={"max_hint_id": real["id"]})).status_code == 200
    assert (await client.patch(url, json={"resolved_hint_id": text["id"]})).status_code == 200
    await delete_tenant(tenant_id)


async def test_deleting_the_hinted_definition_clears_the_hint_and_keeps_the_rest(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The key is ON DELETE SET NULL (hint), not SET NULL: that would try to null tenant_id."""
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    maximum = await _definition(client, tenant_id, group, "max_stress")
    stress = await _definition(client, tenant_id, group, "stress", max_hint_id=maximum["id"])

    deleted = await client.delete(_url(tenant_id, maximum["id"]))

    assert deleted.status_code == 204, deleted.text
    kept = (await client.get(_url(tenant_id, stress["id"]))).json()
    assert kept["max_hint_id"] is None
    assert kept["name"] == "stress"
    await delete_tenant(tenant_id)


async def test_a_tenant_with_hints_can_be_deleted(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    maximum = await _definition(client, tenant_id, group, "max_stress")
    await _definition(client, tenant_id, group, "stress", max_hint_id=maximum["id"])
    await _definition(client, tenant_id, group, "other", resolved_hint_id=maximum["id"])

    await delete_tenant(tenant_id)  # raises if the cascade meets the hint keys badly


async def test_the_database_refuses_a_hint_into_another_tenant() -> None:
    """Whatever the code does, the composite key makes it impossible (ADR 0117)."""
    user_a, user_b = await _user_id(), await _user_id()
    tenant_a = await make_tenant(user_a)
    tenant_b = await make_tenant(user_b)
    async with admin_session_factory() as session:
        group_a = StatGroup(tenant_id=tenant_a, name="g")
        group_b = StatGroup(tenant_id=tenant_b, name="g")
        session.add_all([group_a, group_b])
        await session.flush()
        target = StatDefinition(
            tenant_id=tenant_b, stat_group_id=group_b.id, name="t", value_type=StatValueType.INT
        )
        session.add(target)
        await session.flush()
        session.add(
            StatDefinition(
                tenant_id=tenant_a,
                stat_group_id=group_a.id,
                name="s",
                value_type=StatValueType.INT,
                max_hint_id=target.id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)
    async with admin_session_factory() as session:
        for user_id in (user_a, user_b):
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def _user_id() -> uuid.UUID:
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|hints-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        return user.id
