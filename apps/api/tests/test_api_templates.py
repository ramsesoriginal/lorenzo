"""ADR 0451: templates - authoring (the slots, what must resolve, what a template uses),
the filter (kind and ancestor, the system), and reading an entry through one (every kind of slot,
what the caller may read, an entry the template is not for).
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_opted_out_admin, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import (
    Being,
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    Information,
    ItemInstance,
    Template,
)


async def _post(client: AsyncClient, url: str, body: dict) -> dict:
    response = await client.post(url, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _stat(
    client: AsyncClient, tenant_id: uuid.UUID, group: dict, name: str, value_type: str = "int"
) -> dict:
    return await _post(
        client,
        f"/tenants/{tenant_id}/stat-definitions",
        {"stat_group_id": group["id"], "name": name, "value_type": value_type},
    )


async def _entity(tenant_id: uuid.UUID, name: str, *, being: bool = False) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        if being:
            session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _under(tenant_id: uuid.UUID, entity_id: uuid.UUID, prototype: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        session.add(
            EntityPrototype(entity_id=entity_id, prototype_id=prototype, tenant_id=tenant_id)
        )
        await session.commit()


async def _values(tenant_id: uuid.UUID, entity_id: uuid.UUID, **by_stat: tuple[uuid.UUID, object]):
    async with admin_session_factory() as session:
        for definition_id, value in by_stat.values():
            session.add(
                EntityStat(
                    entity_id=entity_id,
                    stat_definition_id=definition_id,
                    tenant_id=tenant_id,
                    value_int=value
                    if isinstance(value, int) and not isinstance(value, bool)
                    else None,
                    value_bool=value if isinstance(value, bool) else None,
                )
            )
        await session.commit()


async def _hold(
    tenant_id: uuid.UUID, holder: uuid.UUID, name: str, stats: dict[uuid.UUID, int]
) -> uuid.UUID:
    async with admin_session_factory() as session:
        item = Entity(tenant_id=tenant_id, name=name)
        session.add(item)
        await session.flush()
        session.add(ItemInstance(entity_id=item.id, tenant_id=tenant_id))
        await session.flush()
        session.add(
            Containment(child_entity_id=item.id, parent_entity_id=holder, tenant_id=tenant_id)
        )
        for definition_id, value in stats.items():
            session.add(
                EntityStat(
                    entity_id=item.id,
                    stat_definition_id=definition_id,
                    tenant_id=tenant_id,
                    value_int=value,
                )
            )
        await session.commit()
        return item.id


async def _note(tenant_id: uuid.UUID, entity_id: uuid.UUID, title: str, *, public: bool) -> None:
    async with admin_session_factory() as session:
        session.add(
            Information(
                tenant_id=tenant_id,
                entity_id=entity_id,
                title=title,
                type="note",
                is_public=public,
            )
        )
        await session.commit()


class World:
    """Two game systems; a being under a system root, with values, notes and two weapons held."""

    def __init__(self) -> None:
        self.stats: dict[str, dict] = {}
        self.groups: dict[str, dict] = {}


async def _world(client: AsyncClient, tenant_id: uuid.UUID) -> World:
    base = f"/tenants/{tenant_id}"
    w = World()
    w.system = await _post(client, f"{base}/systems", {"slug": "ds", "name": "Draw Steel"})
    w.other = await _post(client, f"{base}/systems", {"slug": "pf", "name": "Pathfinder"})
    for key, name in (("abilities", "Abilities"), ("weapons", "Weapons"), ("states", "States")):
        w.groups[key] = await _post(client, f"{base}/stat-groups", {"name": name})
    for name, group in (
        ("might", "abilities"),
        ("agility", "abilities"),
        ("lore", "abilities"),
        ("damage", "weapons"),
        ("reach", "weapons"),
    ):
        w.stats[name] = await _stat(client, tenant_id, w.groups[group], name)
    for name in ("prone", "stunned"):
        w.stats[name] = await _stat(client, tenant_id, w.groups["states"], name, "bool")
    w.root = await _entity(tenant_id, "Hero Base")
    w.hero = await _entity(tenant_id, "Brannoch", being=True)
    await _under(tenant_id, w.hero, w.root)
    ids = {k: uuid.UUID(v["id"]) for k, v in w.stats.items()}
    await _values(
        tenant_id,
        w.hero,
        a=(ids["might"], 12),
        b=(ids["agility"], 8),
        c=(ids["lore"], 3),
        d=(ids["prone"], True),
        e=(ids["stunned"], False),
    )
    zebra = await _entity(tenant_id, "Zebra Sword")
    aardvark = await _entity(tenant_id, "Aardvark Bow")
    w.axe = await _hold(tenant_id, w.hero, "Axe", {ids["damage"]: 7, ids["reach"]: 1})
    w.bow = await _hold(tenant_id, w.hero, "Bow", {ids["damage"]: 4})
    await _under(tenant_id, w.axe, zebra)
    await _under(tenant_id, w.bow, aardvark)
    return w


def _body(w: World, **extra: object) -> dict:
    return {
        "name": "Sheet",
        "system_id": w.system["id"],
        "required_kind": "being",
        "required_ancestor_entry_id": str(w.root),
        "slots": [
            {
                "kind": "stats",
                "label": "Abilities",
                "stat_group_id": w.groups["abilities"]["id"],
                "exclude": [w.stats["lore"]["id"]],
            },
            {
                "kind": "stats",
                "label": "Picked",
                "stats": [
                    {"stat_definition_id": w.stats["lore"]["id"], "label": "Knowledge"},
                    {"stat_definition_id": w.stats["might"]["id"]},
                ],
            },
            {"kind": "tags", "stat_group_id": w.groups["states"]["id"]},
            {"kind": "information", "label": "Notes", "information_type": "note"},
            {"kind": "held", "label": "Weapons", "stat_group_id": w.groups["weapons"]["id"]},
        ],
        **extra,
    }


# --- authoring ---


async def test_a_template_is_authored_read_listed_replaced_and_deleted(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    base = f"/tenants/{tenant_id}/templates"

    made = await client.post(base, json=_body(w))
    template = made.json()
    fetched = (await client.get(f"{base}/{template['id']}")).json()
    neutral = await client.post(base, json={"name": "Anything"})
    listed = (await client.get(base)).json()["items"]
    of_ds = (await client.get(base, params={"system": "ds"})).json()["items"]
    of_pf = (await client.get(base, params={"system": "pf"})).json()["items"]
    replaced = await client.put(
        f"{base}/{template['id']}",
        json={"name": "Renamed", "slots": [{"kind": "information", "information_type": "x"}]},
    )
    deleted = await client.delete(f"{base}/{template['id']}")
    gone = await client.get(f"{base}/{template['id']}")

    assert made.status_code == 201, made.text
    assert made.headers["location"].endswith(template["id"])
    assert fetched == template
    assert (template["system"], template["required_kind"]) == ("ds", "being")
    assert [s["position"] for s in template["slots"]] == [0, 1, 2, 3, 4]
    assert template["slots"][0]["exclude"] == [w.stats["lore"]["id"]]
    assert template["slots"][1]["stats"][0]["label"] == "Knowledge"
    assert template["slots"][4]["held_order"] == "name"
    assert neutral.status_code == 201
    assert [t["name"] for t in listed] == ["Anything", "Sheet"]
    assert [t["name"] for t in of_ds] == ["Anything", "Sheet"]
    assert [t["name"] for t in of_pf] == ["Anything"]
    assert replaced.status_code == 200, replaced.text
    assert (replaced.json()["name"], replaced.json()["system"]) == ("Renamed", None)
    assert [s["kind"] for s in replaced.json()["slots"]] == ["information"]
    assert (deleted.status_code, gone.status_code) == (204, 404)
    await delete_tenant(tenant_id)


async def test_a_slot_has_to_fit_its_kind(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    group, stat = w.groups["abilities"]["id"], w.stats["might"]["id"]
    bad = [
        {"kind": "stats"},
        {"kind": "stats", "stat_group_id": group, "stats": [{"stat_definition_id": stat}]},
        {"kind": "stats", "stats": [{"stat_definition_id": stat}], "exclude": [stat]},
        {"kind": "held"},
        {"kind": "information"},
        {"kind": "information", "information_type": "n", "stat_group_id": group},
        {"kind": "tags", "stats": [{"stat_definition_id": stat}]},
        {"kind": "tags", "information_type": "n"},
        {"kind": "stats", "stat_group_id": group, "held_order": "name"},
        {"kind": "held", "stat_group_id": group, "held_order": "random"},
        {"kind": "sidebar"},
    ]

    answers = [
        (
            await client.post(
                f"/tenants/{tenant_id}/templates", json={"name": f"t{i}", "slots": [slot]}
            )
        ).status_code
        for i, slot in enumerate(bad)
    ]

    assert answers == [422] * len(bad)
    await delete_tenant(tenant_id)


async def test_what_a_template_names_has_to_be_the_librarys(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    foreign_group = await _post(client, f"/tenants/{other}/stat-groups", {"name": "Elsewhere"})
    foreign_system = await _post(client, f"/tenants/{other}/systems", {"slug": "zz", "name": "ZZ"})
    ghost = str(uuid.uuid4())
    base = f"/tenants/{tenant_id}/templates"
    first = await client.post(base, json={"name": "Taken"})

    async def post(body: dict) -> int:
        return (await client.post(base, json=body)).status_code

    results = {
        "system": await post({"name": "a", "system_id": foreign_system["id"]}),
        "ghost system": await post({"name": "b", "system_id": ghost}),
        "ancestor": await post({"name": "c", "required_ancestor_entry_id": ghost}),
        "group": await post(
            {"name": "d", "slots": [{"kind": "stats", "stat_group_id": foreign_group["id"]}]}
        ),
        "stat": await post(
            {"name": "e", "slots": [{"kind": "stats", "stats": [{"stat_definition_id": ghost}]}]}
        ),
        "twice": await post(
            {
                "name": "f",
                "slots": [
                    {
                        "kind": "stats",
                        "stats": [
                            {"stat_definition_id": w.stats["might"]["id"]},
                            {"stat_definition_id": w.stats["might"]["id"], "label": "again"},
                        ],
                    }
                ],
            }
        ),
        "exclusion elsewhere": await post(
            {
                "name": "g",
                "slots": [
                    {
                        "kind": "stats",
                        "stat_group_id": w.groups["abilities"]["id"],
                        "exclude": [w.stats["damage"]["id"]],
                    }
                ],
            }
        ),
        "name taken": await post({"name": "Taken"}),
    }

    assert first.status_code == 201
    assert results == {
        "system": 422,
        "ghost system": 422,
        "ancestor": 422,
        "group": 422,
        "stat": 422,
        "twice": 422,
        "exclusion elsewhere": 422,
        "name taken": 409,
    }
    await delete_tenant(tenant_id)
    await delete_tenant(other)


# --- the filter ---


async def test_a_template_matches_by_kind_and_ancestor_and_nothing_is_chosen_for_the_caller(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    base = f"/tenants/{tenant_id}/templates"
    other_root = await _entity(tenant_id, "Other Root")
    await client.post(base, json={**_body(w), "name": "A both"})
    await client.post(base, json={"name": "B kind only", "required_kind": "being"})
    await client.post(
        base,
        json={"name": "C ancestor only", "required_ancestor_entry_id": str(w.root)},
    )
    await client.post(base, json={"name": "D wrong kind", "required_kind": "item"})
    await client.post(
        base, json={"name": "E wrong ancestor", "required_ancestor_entry_id": str(other_root)}
    )
    await client.post(base, json={"name": "F anything"})
    await client.post(
        base, json={"name": "G pathfinder", "system_id": w.other["id"], "required_kind": "being"}
    )
    url = f"/tenants/{tenant_id}/entities/{w.hero}/matching-templates"

    matching = (await client.get(url)).json()
    of_ds = (await client.get(url, params={"system": "ds"})).json()
    root_itself = (
        await client.get(f"/tenants/{tenant_id}/entities/{w.root}/matching-templates")
    ).json()
    unknown = await client.get(url, params={"system": "nope"})
    no_entity = await client.get(f"/tenants/{tenant_id}/entities/{uuid.uuid4()}/matching-templates")

    assert [t["name"] for t in matching] == [
        "A both",
        "B kind only",
        "C ancestor only",
        "F anything",
        "G pathfinder",
    ]
    assert [t["name"] for t in of_ds] == ["A both", "B kind only", "C ancestor only", "F anything"]
    # An ancestor is strictly above the entry, and the root is not a being.
    assert [t["name"] for t in root_itself] == ["F anything"]
    assert (unknown.status_code, no_entity.status_code) == (404, 404)
    await delete_tenant(tenant_id)


# --- reading through a template ---


async def test_reading_through_a_template_assembles_every_kind_of_slot(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    await _note(tenant_id, w.hero, "Public note", public=True)
    template = (await client.post(f"/tenants/{tenant_id}/templates", json=_body(w))).json()

    response = await client.get(
        f"/tenants/{tenant_id}/entities/{w.hero}/templates/{template['id']}"
    )
    view = response.json()
    slots = view["slots"]

    assert response.status_code == 200, response.text
    assert (view["template"]["name"], view["entity"]["name"]) == ("Sheet", "Brannoch")
    assert [(s["position"], s["kind"], s["label"]) for s in slots] == [
        (0, "stats", "Abilities"),
        (1, "stats", "Picked"),
        (2, "tags", None),
        (3, "information", "Notes"),
        (4, "held", "Weapons"),
    ]
    # A group, with a stat left out.
    assert sorted((s["name"], s["label"], s["value"]) for s in slots[0]["stats"]) == [
        ("agility", "agility", 8),
        ("might", "might", 12),
    ]
    # A list, in the order written, with its labels.
    assert [(s["name"], s["label"], s["value"]) for s in slots[1]["stats"]] == [
        ("lore", "Knowledge", 3),
        ("might", "might", 12),
    ]
    # The bool stats that are true, as bools.
    assert [(s["name"], s["value"]) for s in slots[2]["tags"]] == [("prone", True)]
    assert [i["title"] for i in slots[3]["information"]] == ["Public note"]
    # The things held, a column for each stat of the group and a typed cell for each.
    assert [c["name"] for c in slots[4]["columns"]] == ["damage", "reach"]
    rows = {r["entity"]["name"]: [c["value"] for c in r["cells"]] for r in slots[4]["rows"]}
    assert rows == {"Axe": [7, 1], "Bow": [4, None]}
    assert [r["entity"]["name"] for r in slots[4]["rows"]] == ["Axe", "Bow"]
    await delete_tenant(tenant_id)


async def test_held_things_are_ordered_by_name_or_by_prototype(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    base = f"/tenants/{tenant_id}/templates"

    async def order(held_order: str) -> list[str]:
        made = await client.post(
            base,
            json={
                "name": held_order,
                "slots": [
                    {
                        "kind": "held",
                        "stats": [{"stat_definition_id": w.stats["damage"]["id"]}],
                        "held_order": held_order,
                    }
                ],
            },
        )
        view = await client.get(
            f"/tenants/{tenant_id}/entities/{w.hero}/templates/{made.json()['id']}"
        )
        return [r["entity"]["name"] for r in view.json()["slots"][0]["rows"]]

    assert await order("name") == ["Axe", "Bow"]
    # The axe's prototype is the Zebra Sword and the bow's the Aardvark Bow.
    assert await order("prototype") == ["Bow", "Axe"]
    await delete_tenant(tenant_id)


async def test_a_template_is_not_read_for_an_entry_it_is_not_for(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    template = (
        await client.post(
            f"/tenants/{tenant_id}/templates", json={"name": "Items", "required_kind": "item"}
        )
    ).json()

    refused = await client.get(f"/tenants/{tenant_id}/entities/{w.hero}/templates/{template['id']}")
    missing = await client.get(f"/tenants/{tenant_id}/entities/{w.hero}/templates/{uuid.uuid4()}")

    assert refused.status_code == 409
    assert refused.json()["type"].endswith("template-does-not-match")
    assert missing.status_code == 404
    await delete_tenant(tenant_id)


async def test_a_note_the_caller_may_not_read_is_not_in_the_view(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    await _note(tenant_id, w.hero, "Public note", public=True)
    await _note(tenant_id, w.hero, "GM only", public=False)
    template = (
        await client.post(
            f"/tenants/{tenant_id}/templates",
            json={"name": "Notes", "slots": [{"kind": "information", "information_type": "note"}]},
        )
    ).json()
    url = f"/tenants/{tenant_id}/entities/{w.hero}/templates/{template['id']}"

    full = (await client.get(url)).json()["slots"][0]["information"]
    await make_opted_out_admin(tenant_id, test_user_id)  # no information bypass (ADR 0096)
    narrowed = (await client.get(url)).json()["slots"][0]["information"]

    assert sorted(i["title"] for i in full) == ["GM only", "Public note"]
    assert [i["title"] for i in narrowed] == ["Public note"]
    await delete_tenant(tenant_id)


# --- what a template uses ---


async def test_what_a_template_uses_is_not_deleted_and_its_ancestor_takes_it_along(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    base = f"/tenants/{tenant_id}"
    template = (await client.post(f"{base}/templates", json=_body(w))).json()
    # The group of the second system is used by no template.
    spare = await _post(client, f"{base}/stat-groups", {"name": "Spare"})

    group = await client.delete(f"{base}/stat-groups/{w.groups['abilities']['id']}")
    states = await client.delete(f"{base}/stat-groups/{w.groups['states']['id']}")
    listed = await client.delete(f"{base}/stat-definitions/{w.stats['lore']['id']}")
    system = await client.delete(f"{base}/systems/{w.system['id']}")
    unused = await client.delete(f"{base}/stat-groups/{spare['id']}")

    assert (group.status_code, states.status_code) == (409, 409)
    assert "template slot" in group.json()["detail"]
    assert listed.status_code == 409
    assert system.status_code == 409
    assert unused.status_code == 204

    async with admin_session_factory() as session:
        entry = await session.get_one(Entity, w.root)
        await session.delete(entry)
        await session.commit()
        left = await session.scalar(
            select(Template.id).where(Template.id == uuid.UUID(template["id"]))
        )
    assert left is None
    await delete_tenant(tenant_id)


async def test_templates_belong_to_their_library(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    w = await _world(client, tenant_id)
    theirs = (await client.post(f"/tenants/{other}/templates", json={"name": "Theirs"})).json()

    through_ours = await client.get(f"/tenants/{tenant_id}/templates/{theirs['id']}")
    read = await client.get(f"/tenants/{tenant_id}/entities/{w.hero}/templates/{theirs['id']}")
    ours = (await client.get(f"/tenants/{tenant_id}/templates")).json()["items"]

    assert (through_ours.status_code, read.status_code) == (404, 404)
    assert ours == []
    await delete_tenant(tenant_id)
    await delete_tenant(other)
