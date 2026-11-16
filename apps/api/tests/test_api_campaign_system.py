"""ADR 0452: a campaign names one game system, and the sheet read draws from a template - the one
of the campaign's system that matches the being, or the one asked for - in place of the library's
sheet settings.
"""

import uuid

from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_api_being_sheet import _being, _definition, _equip, _group, _note

BASE = "/tenants/{t}"


async def _post(client: AsyncClient, url: str, body: dict) -> dict:
    response = await client.post(url, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def _campaign(client: AsyncClient, tenant_id: uuid.UUID, slug: str, **extra: object) -> dict:
    return await _post(
        client,
        f"/tenants/{tenant_id}/campaigns",
        {
            "name": slug.title(),
            "game_system": "free text",
            "slug": slug,
            "description": "a table",
            **extra,
        },
    )


async def _system(client: AsyncClient, tenant_id: uuid.UUID, slug: str) -> dict:
    return await _post(
        client, f"/tenants/{tenant_id}/systems", {"slug": slug, "name": slug.upper()}
    )


# --- the campaign names a system -----------------------------------------------------------------


async def test_a_campaign_names_a_game_system_changes_it_and_clears_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ds = await _system(client, tenant_id, "ds")
    pf = await _system(client, tenant_id, "pf")

    plain = await _campaign(client, tenant_id, "plain")
    named = await _campaign(client, tenant_id, "named", system_id=ds["id"])
    url = f"/tenants/{tenant_id}/campaigns/{named['id']}"
    changed = await client.patch(url, json={"system_id": pf["id"]})
    kept = await client.patch(url, json={"name": "Renamed"})
    cleared = await client.patch(url, json={"system_id": None})
    listed = (await client.get(f"/tenants/{tenant_id}/campaigns")).json()["items"]

    assert (plain["system_id"], named["system_id"]) == (None, ds["id"])
    assert named["game_system"] == "free text"  # the display name stays
    assert changed.json()["system_id"] == pf["id"]
    assert kept.json()["system_id"] == pf["id"]  # not sent, so kept
    assert cleared.json()["system_id"] is None
    assert {c["slug"]: c["system_id"] for c in listed} == {"plain": None, "named": None}
    await delete_tenant(tenant_id)


async def test_the_system_has_to_be_the_librarys_and_is_kept_while_a_campaign_names_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    foreign = await _system(client, other, "zz")
    ds = await _system(client, tenant_id, "ds")
    base = f"/tenants/{tenant_id}/campaigns"

    refused = [
        (
            await client.post(
                base,
                json={
                    "name": "x",
                    "game_system": "x",
                    "slug": f"x{i}",
                    "description": "x",
                    "system_id": system_id,
                },
            )
        ).status_code
        for i, system_id in enumerate((foreign["id"], str(uuid.uuid4())))
    ]
    campaign = await _campaign(client, tenant_id, "named", system_id=ds["id"])
    patched = await client.patch(f"{base}/{campaign['id']}", json={"system_id": foreign["id"]})
    in_use = await client.delete(f"/tenants/{tenant_id}/systems/{ds['id']}")
    await client.patch(f"{base}/{campaign['id']}", json={"system_id": None})
    freed = await client.delete(f"/tenants/{tenant_id}/systems/{ds['id']}")

    assert refused == [422, 422]
    assert patched.status_code == 422
    assert in_use.status_code == 409
    assert freed.status_code == 204
    await delete_tenant(tenant_id)
    await delete_tenant(other)


# --- the sheet ---


class Table:
    """A library with the settings set to one group and type, two groups and a note type a
    template could use instead, and a being that holds an axe."""

    async def build(self, client: AsyncClient, tenant_id: uuid.UUID) -> Table:
        self.tenant_id = tenant_id
        self.settings_group = await _group(client, tenant_id, "Library weapons")
        self.template_group = await _group(client, tenant_id, "Template weapons")
        self.abilities_group = await _group(client, tenant_id, "Abilities")
        self.library_stat = await _definition(
            client, tenant_id, self.settings_group["id"], "library_damage"
        )
        self.template_stat = await _definition(
            client, tenant_id, self.template_group["id"], "template_damage"
        )
        await client.patch(
            f"/tenants/{tenant_id}",
            json={
                "weapon_stat_group_id": self.settings_group["id"],
                "ability_information_type": "ability",
                "being_stat_group_id": self.abilities_group["id"],
            },
        )
        self.being = await _being(tenant_id)
        self.axe = await _equip(
            tenant_id,
            self.being,
            "Axe",
            {
                uuid.UUID(self.library_stat["id"]): 5,
                uuid.UUID(self.template_stat["id"]): 9,
            },
        )
        await _note(tenant_id, self.being, "Library ability", "ability", public=True)
        await _note(tenant_id, self.being, "Template feat", "feat", public=True)
        self.ds = await _system(client, tenant_id, "ds")
        self.pf = await _system(client, tenant_id, "pf")
        self.campaign = await _campaign(client, tenant_id, "table", system_id=self.ds["id"])
        return self

    def template(self, name: str, system: dict | None, **extra: object) -> dict:
        return {
            "name": name,
            "system_id": system["id"] if system else None,
            "required_kind": "being",
            "slots": [
                {"kind": "stats", "stat_group_id": self.template_group["id"]},
                {"kind": "held", "stat_group_id": self.template_group["id"]},
                {"kind": "information", "information_type": "feat"},
            ],
            **extra,
        }

    async def sheet(self, client: AsyncClient, **params: object) -> dict:
        response = await client.get(
            f"/tenants/{self.tenant_id}/beings/{self.being}/sheet", params=params
        )
        assert response.status_code == 200, response.text
        return response.json()


def _names(sheet: dict) -> tuple[list[str], list[str], list[str]]:
    return (
        [s["name"] for w in sheet["weapons"] for s in w["stats"]],
        [a["title"] for a in sheet["abilities"]],
        [t["name"] for t in sheet["templates"]],
    )


async def test_a_sheet_with_no_template_is_drawn_from_the_librarys_settings(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    table = await Table().build(client, tenant_id)
    await client.post(f"/tenants/{tenant_id}/templates", json=table.template("Other", table.pf))

    plain = await table.sheet(client)
    in_campaign = await table.sheet(client, campaign_id=table.campaign["id"])

    for sheet in (plain, in_campaign):
        assert _names(sheet) == (["library_damage"], ["Library ability"], [])
        assert sheet["template"] is None
        assert sheet["being_stat_group_id"] == table.abilities_group["id"]
    await delete_tenant(tenant_id)


async def test_the_one_template_of_the_campaigns_system_that_matches_draws_the_sheet(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    table = await Table().build(client, tenant_id)
    base = f"/tenants/{tenant_id}/templates"
    await client.post(base, json=table.template("Draw Steel sheet", table.ds))
    await client.post(base, json=table.template("Pathfinder sheet", table.pf))
    await client.post(base, json=table.template("Not a being", table.ds, required_kind="item"))

    sheet = await table.sheet(client, campaign_id=table.campaign["id"])

    assert _names(sheet) == (["template_damage"], ["Template feat"], ["Draw Steel sheet"])
    assert sheet["template"]["name"] == "Draw Steel sheet"
    assert sheet["template"]["system"] == "ds"
    assert sheet["being_stat_group_id"] == table.template_group["id"]
    assert (sheet["weapons_configured"], sheet["abilities_configured"]) == (True, True)
    await delete_tenant(tenant_id)


async def test_a_template_without_a_held_or_information_slot_leaves_those_sections_unset(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    table = await Table().build(client, tenant_id)
    await client.post(
        f"/tenants/{tenant_id}/templates",
        json={
            "name": "Stats only",
            "system_id": table.ds["id"],
            "slots": [{"kind": "stats", "stat_group_id": table.template_group["id"]}],
        },
    )

    sheet = await table.sheet(client, campaign_id=table.campaign["id"])

    assert sheet["template"]["name"] == "Stats only"
    assert (sheet["weapons_configured"], sheet["abilities_configured"]) == (False, False)
    assert (sheet["weapons"], sheet["abilities"]) == ([], [])
    await delete_tenant(tenant_id)


async def test_nothing_is_chosen_when_two_templates_match_and_one_can_be_asked_for(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    table = await Table().build(client, tenant_id)
    base = f"/tenants/{tenant_id}/templates"
    first = await _post(client, base, table.template("A sheet", table.ds))
    await _post(client, base, table.template("B sheet", table.ds))
    elsewhere = await _post(client, base, table.template("Pathfinder sheet", table.pf))
    item_template = await _post(
        client, base, {"name": "Items", "required_kind": "item", "system_id": table.ds["id"]}
    )

    ambiguous = await table.sheet(client, campaign_id=table.campaign["id"])
    asked = await table.sheet(client, campaign_id=table.campaign["id"], template_id=first["id"])
    other_system = await table.sheet(client, template_id=elsewhere["id"])
    wrong_kind = await client.get(
        f"/tenants/{tenant_id}/beings/{table.being}/sheet",
        params={"template_id": item_template["id"]},
    )
    unknown = await client.get(
        f"/tenants/{tenant_id}/beings/{table.being}/sheet",
        params={"template_id": str(uuid.uuid4())},
    )

    # Two match: the library's settings draw the sheet, and both are offered.
    assert _names(ambiguous) == (["library_damage"], ["Library ability"], ["A sheet", "B sheet"])
    assert ambiguous["template"] is None
    assert asked["template"]["name"] == "A sheet"
    assert _names(asked)[:2] == (["template_damage"], ["Template feat"])
    # A template asked for is used whatever system it belongs to.
    assert other_system["template"]["name"] == "Pathfinder sheet"
    assert (wrong_kind.status_code, unknown.status_code) == (409, 404)
    await delete_tenant(tenant_id)
