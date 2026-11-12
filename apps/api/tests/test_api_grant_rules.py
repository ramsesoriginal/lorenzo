"""ADR 0455: grant rules and the prerequisites of a feature - authoring (what must resolve, the
shape of each mode, the order), what a stat that a rule reads protects, and what a copy brings.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from _repository_fixtures import seed_every_content_table
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from test_api_computed_stats import _sheet

from lorenzo_api.models import (
    Entity,
    FeaturePrerequisite,
    GrantRule,
    GrantRuleCondition,
    GrantRuleOption,
    StatDefinition,
    StatValueType,
)


async def _entry(client: AsyncClient, tenant_id: uuid.UUID, name: str, **body: Any) -> uuid.UUID:
    response = await client.post(f"/tenants/{tenant_id}/entities", json={"name": name, **body})
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _feature(client: AsyncClient, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    return await _entry(client, tenant_id, name, kinds=["feature"])


def _rule(**body: Any) -> dict[str, Any]:
    return {"mode": "all", **body}


async def _post(client: AsyncClient, tenant_id: uuid.UUID, entry: uuid.UUID, **body: Any):  # type: ignore[no-untyped-def]
    return await client.post(
        f"/tenants/{tenant_id}/grant-rules", json={"entry_id": str(entry), **_rule(**body)}
    )


# --- authoring -----------------------------------------------------------------


async def test_a_rule_of_each_mode_is_made_read_listed_replaced_and_deleted(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, level=StatValueType.INT, picks=StatValueType.INT)
    fighter = await _entry(client, tenant_id, "Fighter")
    spells = await _entry(client, tenant_id, "Spells")
    second_wind = await _feature(client, tenant_id, "Second Wind")
    action_surge = await _feature(client, tenant_id, "Action Surge")

    every = await _post(
        client,
        tenant_id,
        fighter,
        label="Level 1",
        options=[str(second_wind), str(action_surge)],
        conditions=[
            {
                "stat_definition_id": str(sheet["level"]),
                "comparator": "ge",
                "right_constant": "1",
            }
        ],
    )
    assert every.status_code == 201, every.text
    body = every.json()
    assert (body["mode"], body["label"], body["position"], body["lasts"]) == (
        "all",
        "Level 1",
        0,
        "while_source",
    )
    assert [o["name"] for o in body["options"]] == ["Second Wind", "Action Surge"]
    assert body["conditions"][0]["stat_name"] == "level"
    assert body["conditions"][0]["subject"] == "holder"
    assert every.headers["location"].endswith(f"/tenants/{tenant_id}/grant-rules/{body['id']}")

    pick = await _post(
        client,
        tenant_id,
        fighter,
        mode="choose",
        min_count=1,
        count_stat_definition_id=str(sheet["picks"]),
        option_category_entry_id=str(spells),
        lasts="permanent",
        changeable=True,
        conditions=[
            {
                "subject": "source",
                "stat_definition_id": str(sheet["level"]),
                "comparator": "lt",
                "right_stat_definition_id": str(sheet["picks"]),
            }
        ],
    )
    assert pick.status_code == 201, pick.text
    assert pick.json()["position"] == 1
    assert pick.json()["option_category"]["name"] == "Spells"
    assert (pick.json()["count_stat_name"], pick.json()["max_count"]) == ("picks", None)

    listed = await client.get(
        f"/tenants/{tenant_id}/grant-rules", params={"entry_id": str(fighter)}
    )
    assert [r["mode"] for r in listed.json()["items"]] == ["all", "choose"]
    other = await client.get(f"/tenants/{tenant_id}/grant-rules", params={"entry_id": str(spells)})
    assert other.json()["items"] == []

    # A replace keeps the source and changes the rest, and `position` moves the rule.
    replaced = await client.put(
        f"/tenants/{tenant_id}/grant-rules/{pick.json()['id']}",
        json={**_rule(mode="all", options=[str(second_wind)]), "position": 0},
    )
    assert replaced.status_code == 200, replaced.text
    assert (
        replaced.json()["mode"],
        replaced.json()["position"],
        replaced.json()["conditions"],
    ) == (
        "all",
        0,
        [],
    )
    listed = await client.get(
        f"/tenants/{tenant_id}/grant-rules", params={"entry_id": str(fighter)}
    )
    assert [r["label"] for r in listed.json()["items"]] == [None, "Level 1"]
    assert [r["position"] for r in listed.json()["items"]] == [0, 1]

    assert (
        await client.delete(f"/tenants/{tenant_id}/grant-rules/{body['id']}")
    ).status_code == 204
    assert (await client.get(f"/tenants/{tenant_id}/grant-rules/{body['id']}")).status_code == 404
    async with admin_session_factory() as session:
        left = list(await session.scalars(select(GrantRuleOption.rule_id)))
        assert uuid.UUID(body["id"]) not in left
    await delete_tenant(tenant_id)


async def test_what_a_rule_names_must_resolve_and_its_shape_must_fit_its_mode(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, level=StatValueType.INT, note=StatValueType.TEXT, picks=StatValueType.TEXT
    )
    source = await _entry(client, tenant_id, "Fighter")
    feature = await _feature(client, tenant_id, "Second Wind")
    plain = await _entry(client, tenant_id, "Plain")

    # An option that is no feature, an unknown source, an unknown stat, a text stat.
    assert (await _post(client, tenant_id, source, options=[str(plain)])).status_code == 422
    assert (await _post(client, tenant_id, uuid.uuid4(), options=[str(feature)])).status_code == 422
    unknown = {"stat_definition_id": str(uuid.uuid4()), "comparator": "ge", "right_constant": "1"}
    assert (
        await _post(client, tenant_id, source, options=[str(feature)], conditions=[unknown])
    ).status_code == 422
    text = {"stat_definition_id": str(sheet["note"]), "comparator": "ge", "right_constant": "1"}
    assert (
        await _post(client, tenant_id, source, options=[str(feature)], conditions=[text])
    ).status_code == 422
    # A count that is text.
    assert (
        await _post(
            client,
            tenant_id,
            source,
            mode="choose",
            count_stat_definition_id=str(sheet["picks"]),
            options=[str(feature)],
        )
    ).status_code == 422
    # The shape: options or a category, not both and not neither; `all` has no count; a choose
    # rule needs one maximum; a right side is one of two; `changeable` is for choose.
    for bad in (
        {"options": []},
        {"options": [str(feature)], "option_category_entry_id": str(plain)},
        {"options": [str(feature)], "max_count": 1},
        {"options": [str(feature)], "changeable": True},
        {"options": [str(feature), str(feature)]},
        {"mode": "choose", "options": [str(feature)]},
        {"mode": "choose", "options": [str(feature)], "max_count": 1, "min_count": 2},
        {
            "options": [str(feature)],
            "conditions": [
                {
                    "stat_definition_id": str(sheet["level"]),
                    "comparator": "ge",
                    "right_constant": "1",
                    "right_stat_definition_id": str(sheet["level"]),
                }
            ],
        },
        {
            "options": [str(feature)],
            "conditions": [{"stat_definition_id": str(sheet["level"]), "comparator": "ge"}],
        },
    ):
        refused = await _post(client, tenant_id, source, **bad)
        assert refused.status_code == 422, (bad, refused.text)
    await delete_tenant(tenant_id)


async def test_a_stat_a_rule_or_a_feature_reads_is_not_deleted(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, level=StatValueType.INT, picks=StatValueType.INT, size=StatValueType.INT
    )
    source = await _entry(client, tenant_id, "Fighter")
    feature = await _feature(client, tenant_id, "Second Wind")
    made = await _post(
        client,
        tenant_id,
        source,
        options=[str(feature)],
        conditions=[
            {"stat_definition_id": str(sheet["level"]), "comparator": "ge", "right_constant": "1"}
        ],
    )
    assert made.status_code == 201, made.text
    counted = await _post(
        client,
        tenant_id,
        source,
        mode="choose",
        count_stat_definition_id=str(sheet["picks"]),
        options=[str(feature)],
    )
    assert counted.status_code == 201
    needs = await client.put(
        f"/tenants/{tenant_id}/features/prototypes/{feature}/prerequisites",
        json={
            "prerequisites": [
                {
                    "stat_definition_id": str(sheet["size"]),
                    "comparator": "gt",
                    "right_constant": "2",
                }
            ]
        },
    )
    assert needs.status_code == 200, needs.text

    for stat in ("level", "picks", "size"):
        refused = await client.delete(f"/tenants/{tenant_id}/stat-definitions/{sheet[stat]}")
        assert refused.status_code == 409, (stat, refused.text)
    await client.delete(f"/tenants/{tenant_id}/grant-rules/{made.json()['id']}")
    assert (
        await client.delete(f"/tenants/{tenant_id}/stat-definitions/{sheet['level']}")
    ).status_code == 204
    await delete_tenant(tenant_id)


async def test_a_rule_goes_with_its_source_and_an_option_with_its_entry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    source = await _entry(client, tenant_id, "Fighter")
    first = await _feature(client, tenant_id, "Second Wind")
    second = await _feature(client, tenant_id, "Action Surge")
    made = await _post(client, tenant_id, source, options=[str(first), str(second)])
    assert made.status_code == 201

    assert (await client.delete(f"/tenants/{tenant_id}/entities/{first}")).status_code == 204
    read = await client.get(f"/tenants/{tenant_id}/grant-rules/{made.json()['id']}")
    assert [o["name"] for o in read.json()["options"]] == ["Action Surge"]
    assert (await client.delete(f"/tenants/{tenant_id}/entities/{source}")).status_code == 204
    assert (
        await client.get(f"/tenants/{tenant_id}/grant-rules/{made.json()['id']}")
    ).status_code == 404
    await delete_tenant(tenant_id)


# --- prerequisites -------------------------------------------------------------


async def test_the_prerequisites_of_a_feature_are_replaced_whole(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, strength=StatValueType.INT, note=StatValueType.TEXT)
    feature = await _feature(client, tenant_id, "Great Weapon Master")
    plain = await _entry(client, tenant_id, "Plain")
    url = f"/tenants/{tenant_id}/features/prototypes/{feature}/prerequisites"

    assert (await client.get(url)).json() == {"feature_id": str(feature), "prerequisites": []}
    two = {
        "prerequisites": [
            {
                "stat_definition_id": str(sheet["strength"]),
                "comparator": "ge",
                "right_constant": "13",
            },
            {
                "stat_definition_id": str(sheet["strength"]),
                "comparator": "ne",
                "right_constant": "15",
            },
        ]
    }
    put = await client.put(url, json=two)
    assert put.status_code == 200, put.text
    assert [
        (p["stat_name"], p["comparator"], p["right_constant"]) for p in put.json()["prerequisites"]
    ] == [
        ("strength", "ge", "13"),
        ("strength", "ne", "15"),
    ]
    one = {"prerequisites": two["prerequisites"][1:]}
    assert len((await client.put(url, json=one)).json()["prerequisites"]) == 1
    assert (await client.put(url, json={"prerequisites": []})).json()["prerequisites"] == []

    text = {
        "prerequisites": [
            {"stat_definition_id": str(sheet["note"]), "comparator": "eq", "right_constant": "1"}
        ]
    }
    assert (await client.put(url, json=text)).status_code == 422
    not_a_feature = f"/tenants/{tenant_id}/features/prototypes/{plain}/prerequisites"
    assert (await client.get(not_a_feature)).status_code == 404
    assert (await client.put(not_a_feature, json=two)).status_code == 404
    await delete_tenant(tenant_id)


# --- a copy --------------------------------------------------------------------


async def test_a_copy_brings_the_rules_and_the_prerequisites(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await author.create_tenant("Rules Core", kind="repository")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, repository)
        await session.commit()
    table = await gm.create_tenant("My Table")
    try:
        await _share(author, repository, table)

        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
        assert copied.status_code == 201, copied.text
        assert copied.json()["steps"][0]["dropped"] == []

        async with admin_session_factory() as session:
            names = {
                e.id: e.name
                for e in await session.scalars(select(Entity).where(Entity.tenant_id == table))
            }
            stats = {
                d.id: d.name
                for d in await session.scalars(
                    select(StatDefinition).where(StatDefinition.tenant_id == table)
                )
            }
            (rule,) = list(
                await session.scalars(select(GrantRule).where(GrantRule.tenant_id == table))
            )
            (condition,) = list(
                await session.scalars(
                    select(GrantRuleCondition).where(GrantRuleCondition.tenant_id == table)
                )
            )
            (option,) = list(
                await session.scalars(
                    select(GrantRuleOption).where(GrantRuleOption.tenant_id == table)
                )
            )
            (prerequisite,) = list(
                await session.scalars(
                    select(FeaturePrerequisite).where(FeaturePrerequisite.tenant_id == table)
                )
            )
        assert names[rule.entry_id] == "Harpers"
        assert (rule.label, rule.mode, rule.max_count) == ("Fixture rule", "choose", 1)
        assert names[option.option_entry_id] == "Fixture feature"
        assert (stats[condition.stat_definition_id], condition.comparator) == ("Strength", "ge")
        assert str(condition.right_constant) == "10"
        assert names[prerequisite.feature_id] == "Fixture feature"
        assert stats[prerequisite.stat_definition_id] == "Strength"
        # The library reads them through its own routes, and its rules are not the repository's.
        listed = await gm.get(f"/tenants/{table}/grant-rules")
        assert listed.status_code == 200, listed.text
        assert [r["label"] for r in listed.json()["items"]] == ["Fixture rule"]
    finally:
        await cleanup([repository, table], [author, gm])


async def _share(author: Actor, repository: uuid.UUID, *subscribers: uuid.UUID) -> None:
    for subscriber in subscribers:
        response = await author.put(f"/tenants/{repository}/subscribers/{subscriber}")
        assert response.status_code in (200, 201), response.text
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
