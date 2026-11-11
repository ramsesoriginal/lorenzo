from __future__ import annotations

import json
from uuid import UUID

import httpx
from plain import plain
from test_cli_self_service import ASHFANG, ROPE, TENANT, World, item, page, run

STAMP = "2026-10-15T00:00:00Z"


def detail(eid, kind, name):
    return dict(
        id=str(eid),
        name=name,
        slug=None,
        created_at=STAMP,
        updated_at=STAMP,
        stats=[],
        stat_groups=[],
        information=[],
        kinds=[kind],
        prototypes=[],
        instances=[],
        parent=None,
        quantity=None,
        children=[],
    )


class ReadWorld(World):
    def __init__(self):
        super().__init__()
        self.entity = detail(ROPE, "item", "Rope")
        self.sheet = dict(
            weapons_configured=False, abilities_configured=False, weapons=[], abilities=[]
        )
        self.denied = False

    def handler(self, request):
        base = f"/tenants/{TENANT}"
        if request.url.path == f"{base}/entities/{self.entity['id']}":
            self.seen.append(request)
            return (
                httpx.Response(404, json={"detail": "No such entry."})
                if self.denied
                else httpx.Response(200, json=self.entity)
            )
        if request.url.path.endswith("/sheet"):
            self.seen.append(request)
            return httpx.Response(200, json=self.sheet)
        if request.url.path in (base + "/stat-definitions", base + "/stat-groups"):
            return httpx.Response(200, json=page([]))
        if request.url.path == f"{base}/item-instances/{self.entity['id']}":
            found = item(UUID(self.entity["id"]), "Old rope")
            found.update(owner_entity_id=str(ASHFANG), slug=None, bound=False, active=True)
            return httpx.Response(200, json=found)
        return super().handler(request)


def test_item_show_json_is_unrendered_and_read_only(tmp_path):
    world = ReadWorld()
    result = run(world, tmp_path, "item", "show", "Rope", "-t", "table-one", "--json")
    assert result.exit_code == 0, result.output
    body = json.loads(result.stdout)
    assert body["entry"]["id"] == str(ROPE) and body["item"]["title"] == "Rope"
    assert all(request.method == "GET" for request in world.seen)


def test_being_sheet_and_instance_show(tmp_path):
    world = ReadWorld()
    world.entity = detail(ASHFANG, "being", "Ashfang")
    result = run(world, tmp_path, "being", "show", "Ashfang", "-t", "table-one")
    assert result.exit_code == 0, result.output
    assert "Weapon stat group is not set" in result.stdout
    assert "Ability information type is not set" in result.stdout
    world.entity = detail(ROPE, "item_instance", "Old rope")
    result = run(world, tmp_path, "item-instance", "show", str(ROPE), "-t", "table-one", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["item_instance"]["owner_entity_id"] == str(ASHFANG)


def test_wrong_kind_and_unreadable_entry_are_refused(tmp_path):
    world = ReadWorld()
    result = run(world, tmp_path, "being", "show", str(ROPE), "-t", "table-one")
    assert result.exit_code == 1 and "not a being" in result.output
    world.denied = True
    result = run(world, tmp_path, "item", "show", "Rope", "-t", "table-one")
    assert result.exit_code == 1 and "HTTP 404" in result.output


def test_stat_numbers_do_not_lose_precision() -> None:
    from lorenzo_cli.entry_commands import formatted

    assert formatted(123456789) == "123456789"
    assert formatted(1.23456789) == "1.23456789"


LONGSWORD = {
    "id": "00000000-0000-0000-0000-0000000000aa",
    "name": "Longsword",
    "slug": "longsword",
    "kinds": ["item"],
}


def described(*texts: dict) -> ReadWorld:
    """A rope whose read gives these descriptions, as the API sends them."""
    world = ReadWorld()
    found = item(ROPE, "Rope")
    found["descriptions"] = [{"locale": "en", **text} for text in texts]
    world.catalog = [found]
    return world


def shown(tmp_path, world: ReadWorld) -> str:
    result = run(world, tmp_path, "item", "show", "Rope", "-t", "table-one")
    assert result.exit_code == 0, result.output
    return plain(result.stdout)


def test_a_description_of_a_hidden_entry_is_inherited_and_not_named(tmp_path):
    world = described({"content": "A coil of rope.", "from_entity": None, "from_hidden": True})
    text = shown(tmp_path, world)
    assert "Description · from a hidden entry · en" in text
    assert "A coil of rope." in text
    assert "Description · en" not in text


def test_a_description_with_no_source_flag_is_still_the_entrys_own(tmp_path):
    for flag in ({}, {"from_hidden": None}, {"from_hidden": False}):
        world = described({"content": "A coil of rope.", "from_entity": None, **flag})
        text = shown(tmp_path, world)
        assert "Description · en" in text
        assert "hidden" not in text


def test_a_named_inherited_description_is_still_named(tmp_path):
    world = described({"content": "A blade.", "from_entity": LONGSWORD})
    assert "Description · from Longsword · en" in shown(tmp_path, world)


def test_own_and_hidden_descriptions_read_apart(tmp_path):
    world = described(
        {"content": "Mine.", "from_entity": None},
        {"content": "Theirs.", "from_entity": None, "from_hidden": True},
    )
    text = shown(tmp_path, world)
    assert "Description · en Mine." in text
    assert "Description · from a hidden entry · en Theirs." in text


def test_the_json_read_keeps_the_flag(tmp_path):
    world = described({"content": "x", "from_entity": None, "from_hidden": True})
    result = run(world, tmp_path, "item", "show", "Rope", "-t", "table-one", "--json")
    body = json.loads(result.stdout)
    assert body["item"]["descriptions"][0]["from_hidden"] is True
    assert body["item"]["descriptions"][0]["from_entity"] is None
