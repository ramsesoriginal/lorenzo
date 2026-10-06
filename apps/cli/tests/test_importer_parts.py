"""The importer's two halves (ADR 0182): what each pass of an item is made of, how the map says it,
and what the plan of each pass decides, without a network."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from test_transport import FixedToken
from test_unseed import _item

from lorenzo_cli.client.models import TenantOut
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.evalworker import EvalResult
from lorenzo_cli.importer.apply import ApplyOptions, apply_import
from lorenzo_cli.importer.draft import Ancestry, ItemDraft, draft_item, part_view
from lorenzo_cli.importer.manifest import Manifest
from lorenzo_cli.importer.mapping import Mapping, MappingError, load_mapping
from lorenzo_cli.importer.parts import Parts
from lorenzo_cli.importer.plan import ImportPlan, Options, build_plan
from lorenzo_cli.seed import load_builtin

SEED = load_builtin()
PARTS = Parts(SEED)
BUILTIN = load_mapping().mapping


def draft(
    list_name: str,
    key: str,
    entry: dict[str, Any],
    mapping: Mapping = BUILTIN,
    file: str = "ListsGear.js",
) -> ItemDraft:
    return draft_item(list_name, key, entry, file, mapping, Ancestry(SEED), PARTS)


LONGSWORD = {
    "name": "Longsword",
    "source": [["SRD", 66], ["P", 149]],
    "list": "melee",
    "ability": 1,
    "type": "Martial",
    "damage": [1, 8, "slashing"],
    "range": "Melee",
    "weight": 3,
    "description": "Versatile (1d10)",
    "abilitytodamage": True,
    "tooltip": "Hit hard.",
    "nameAlt": ["Long sword"],
}
LONGBOW = {
    "name": "Longbow",
    "source": [["SRD", 68]],
    "list": "ranged",
    "type": "Martial",
    "damage": [1, 8, "piercing"],
    "range": "150/600 ft",
    "weight": 2,
    "description": "Ammunition, heavy, two-handed",
}
CHAIN_MAIL = {
    "name": "Chain mail",
    "source": [["SRD", 70]],
    "type": "heavy",
    "ac": 16,
    "strReq": 13,
    "stealthdis": True,
    "weight": 55,
}


def halves(item: ItemDraft) -> tuple[ItemDraft, ItemDraft]:
    return part_view(item, "neutral", PARTS), part_view(item, "system", PARTS)


# --- what each half is --------------------------------------------------------------------------


def test_the_seeds_layers_say_whose_each_stat_and_category_is() -> None:
    assert PARTS.stat("own_weight") == "neutral" and PARTS.stat("sourcebook") == "neutral"
    assert PARTS.stat("price") == "system" and PARTS.stat("damage_die") == "system"
    assert PARTS.node("melee-weapon") == "neutral" and PARTS.node("silvered") == "neutral"
    assert PARTS.node("dnd5e-martial") == "system" and PARTS.node("dnd5e-system") == "system"
    assert PARTS.stat("flavour_text") is None and PARTS.node("hb-anything") is None


def test_a_weapon_is_a_neutral_item_and_a_system_prototype() -> None:
    neutral, system = halves(draft("weapons", "longsword", LONGSWORD))

    assert neutral.name == "Longsword" and neutral.namespace == "basic"
    assert neutral.parents == ["blade", "melee-weapon"]
    assert neutral.stats == {"sourcebook": "SRD 66, P 149", "own_weight": 3.0}
    assert neutral.description is None
    assert [(i.type, i.content) for i in neutral.information] == [("alias", "Long sword")]

    assert system.name == "Longsword (D&D 5e)" and system.neutral_name == "Longsword"
    assert system.namespace == "srd5e" and system.neutral_namespace == "basic"
    assert system.parents == ["dnd5e-martial", "dnd5e-versatile"]
    assert system.stats == {
        "damage_dice_count": 1,
        "damage_die": 8,
        "damage_type": "slashing",
        "damage_versatile_die": 10,
        "attack_ability": "Strength",
        "ability_to_damage": True,
    }
    # The property list and the special rules are D&D's, as the RFC has them.
    assert system.description == "Versatile (1d10)"
    assert [(i.type, i.title) for i in system.information] == [("note", "Special rules")]
    assert system.skip_reason is None


def test_one_rule_writing_both_halves_is_divided_not_split() -> None:
    # `range` gives the reach (neutral) and the distances in feet (the system's).
    neutral, system = halves(draft("weapons", "longbow", LONGBOW))

    # A bow is ranged by being a bow, so the reach is its form's, and neutral.
    assert neutral.parents == ["bow"] and "bow" not in system.parents
    assert "range_normal" not in neutral.stats and system.stats["range_normal"] == 150
    assert system.stats["range_long"] == 600
    assert "dnd5e-heavy" in system.parents and "dnd5e-two-handed" in system.parents


def test_armour_numbers_and_tier_are_the_systems_and_its_form_is_neutral() -> None:
    neutral, system = halves(draft("armour", "chain-mail", CHAIN_MAIL))

    assert neutral.parents == ["armor"]
    assert neutral.stats == {"sourcebook": "SRD 70", "own_weight": 55.0}
    assert system.parents == ["dnd5e-heavy-armor"]
    assert system.stats == {"armor": 16, "strength_required": 13, "stealth_disadvantage": True}


def test_a_price_is_the_systems_and_the_name_and_kind_of_gear_are_neutral() -> None:
    neutral, system = halves(
        draft("gear", "backpack", {"infoname": "Backpack [2 gp]", "weight": 5})
    )

    assert neutral.name == "Backpack" and neutral.parents == ["container", "gear"]
    assert neutral.stats == {"own_weight": 5.0}
    assert system.stats == {"price": 200} and system.parents == []
    assert system.name == "Backpack (D&D 5e)"


def test_the_kinds_of_gear_the_system_names_go_on_its_prototype() -> None:
    neutral, system = halves(
        draft("gear", "component-pouch", {"infoname": "Component pouch [25 gp]", "weight": 2})
    )

    assert "container" in neutral.parents and "dnd5e-spellcasting-focus" not in neutral.parents
    assert system.parents == ["dnd5e-spellcasting-focus"]


def test_what_has_nothing_of_the_systems_gets_no_prototype() -> None:
    neutral, system = halves(
        draft(
            "ammo", "arrow", {"name": "Arrow", "source": [["SRD", 74]], "weight": 0.05}, file="a.js"
        )
    )

    assert neutral.skip_reason is None
    assert system.skip_reason == "nothing of it is the system's"


def test_the_two_halves_together_are_the_draft_that_is_written_today() -> None:
    entries = [
        ("weapons", "longsword", LONGSWORD),
        ("weapons", "longbow", LONGBOW),
        ("armour", "chain-mail", CHAIN_MAIL),
        ("gear", "backpack", {"infoname": "Backpack [2 gp]", "weight": 5}),
    ]
    for list_name, key, entry in entries:
        whole = draft(list_name, key, entry)
        neutral, system = halves(whole)

        assert {**neutral.stats, **system.stats} == whole.stats, key
        assert not set(neutral.stats) & set(system.stats), key
        assert sorted([*neutral.parents, *system.parents]) == sorted(whole.parents), key
        assert len(neutral.information) + len(system.information) == len(whole.information), key
        # A description is written once, by one half.
        assert [neutral.description, system.description].count(None) >= 1, key


def test_a_minted_category_has_the_part_of_its_axis() -> None:
    mapping = load_mapping(
        "schema = 1\n[classify.weapons.type]\n"
        'legendary = { disposition = "create-under", axis = "form", slug = "hb-legendary", '
        'name = "Legendary" }\n'
        'mythic = { disposition = "create-under", axis = "proficiency", slug = "hb-mythic", '
        'name = "Mythic" }\n'
    ).mapping
    base = {"name": "Thing", "list": "melee", "range": "Melee", "damage": [1, 6, "slashing"]}

    form = halves(draft("weapons", "a", {**base, "type": "Legendary"}, mapping))
    proficiency = halves(draft("weapons", "b", {**base, "type": "Mythic"}, mapping))

    assert "hb-legendary" in form[0].parents and [c.slug for c in form[0].categories] == [
        "hb-legendary"
    ]
    assert not form[1].categories and "hb-legendary" not in form[1].parents
    assert "hb-mythic" in proficiency[1].parents and [
        c.slug for c in proficiency[1].categories
    ] == ["hb-mythic"]
    assert not proficiency[0].categories


# --- what a row can say ---------------------------------------------------------------------------


def test_a_row_says_whose_a_stat_the_seed_does_not_have_is() -> None:
    mapping = load_mapping(
        "schema = 1\n[attributes.weapons]\n"
        'flavour = { transform = "text", stat = "flavour_text", group = "lore" }\n'
        'rules = { transform = "text", stat = "house_rule", group = "lore", part = "system" }\n'
    ).mapping
    entry = {"name": "Thing", "list": "melee", "range": "Melee", "flavour": "Hm", "rules": "No"}

    neutral, system = halves(draft("weapons", "a", {**entry, "type": "Martial"}, mapping))

    assert neutral.stats["flavour_text"] == "Hm" and "house_rule" not in neutral.stats
    assert system.stats["house_rule"] == "No" and "flavour_text" not in system.stats


def test_a_row_says_whose_a_parent_the_seed_does_not_have_is() -> None:
    mapping = load_mapping(
        'schema = 1\n[classify.weapons.type]\nhomebrew = { parents = ["hb-rules"], part = "system" }\n'
    ).mapping

    neutral, system = halves(
        draft(
            "weapons",
            "a",
            {"name": "T", "list": "melee", "range": "Melee", "type": "homebrew"},
            mapping,
        )
    )

    assert "hb-rules" in system.parents and "hb-rules" not in neutral.parents


def test_a_text_rule_takes_a_part_and_defaults_to_neutral() -> None:
    mapping = load_mapping(
        'schema = 1\n[attributes.gear]\nlore = { transform = "information", type = "note", '
        'title = "Lore", part = "system" }\nflavour = { transform = "information", type = "note", '
        'title = "Flavour" }\n'
    ).mapping

    neutral, system = halves(
        draft("gear", "a", {"infoname": "Thing [1 gp]", "lore": "L", "flavour": "F"}, mapping)
    )

    assert [i.title for i in neutral.information] == ["Flavour"]
    assert [i.title for i in system.information] == ["Lore"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            '[attributes.weapons]\nweight = { transform = "float", stat = "own_weight", '
            'part = "system" }',
            "whose output the seed already says",
        ),
        ('[attributes.weapons]\nweight = { transform = "own_weight", part = "system" }', "part = "),
        (
            '[classify.weapons.type]\nfoo = { parents = ["dnd5e-martial"], part = "neutral" }',
            "every parent is one of the seed's",
        ),
        (
            '[[name_rule]]\nin_list = "weapons"\nwords = ["x"]\nparents = ["silvered"]\n'
            'part = "system"',
            "every parent is one of the seed's",
        ),
        (
            '[classify.weapons.type]\nfoo = { disposition = "skip", part = "system" }',
            "part belongs to a row with parents",
        ),
        ('[system]\nlabel = ""', "label must be some text"),
        ('[system]\nflavour = "x"', "unknown keys in"),
        ('[system_namespaces]\n"a.js" = "Not Valid"', "Namespace"),
    ],
)
def test_a_part_the_seed_contradicts_or_a_bad_system_setting_is_a_map_error(
    text: str, message: str
) -> None:
    with pytest.raises(MappingError, match=message):
        load_mapping("schema = 1\n" + text)


def test_the_prototypes_namespace_and_label_come_from_the_map() -> None:
    mapping = load_mapping(
        'schema = 1\n[namespaces]\n"hb.js" = "hb-alice"\n"other.js" = "other"\n'
        '[system_namespaces]\n"other.js" = "mine"\n[system]\nlabel = " Pathfinder "\n'
    ).mapping

    assert mapping.system_namespace_for("ListsGear.js") == "srd5e"  # the sheet's own data
    assert mapping.system_namespace_for("hb.js") == "hb-alice-5e"
    assert mapping.system_namespace_for("other.js") == "mine"
    assert mapping.system_label == "Pathfinder"
    assert draft("gear", "a", {"infoname": "Thing [1 gp]"}, mapping).system_label == "Pathfinder"
    assert BUILTIN.system_label == "D&D 5e"


def test_the_built_in_map_needs_a_part_for_a_weapons_text_only() -> None:
    said = [
        (list_name, attribute, rule.transform)
        for list_name, rules in BUILTIN.attributes.items()
        for attribute, rule_list in rules.items()
        for rule in rule_list
        if rule.part
    ]

    assert said == [
        ("weapons", "description", "description"),
        ("weapons", "tooltip", "information"),
    ]
    assert all(
        rule.part == "system"
        for rules in BUILTIN.attributes["weapons"].values()
        for rule in rules
        if rule.part
    )


# --- what held means in each pass -----------------------------------------------------------------


def test_an_unreadable_price_holds_the_system_pass_and_the_neutral_one_imports() -> None:
    neutral, system = halves(draft("gear", "thing", {"infoname": "Thing [???]", "weight": 1}))

    assert not neutral.issues
    assert [i.kind for i in system.issues] == ["price"]


def test_a_weight_that_is_not_a_number_holds_the_neutral_pass_only() -> None:
    neutral, system = halves(
        draft("gear", "thing", {"infoname": "Thing [1 gp]", "weight": "heavy"})
    )

    assert [i.kind for i in neutral.issues] == ["weight"]
    assert not system.issues


def test_a_value_no_row_knows_holds_both_passes() -> None:
    entry = {"name": "Odd", "list": "melee", "range": "Melee", "type": "Never heard of it"}

    neutral, system = halves(draft("weapons", "odd", entry))

    assert [i.kind for i in neutral.issues] == ["value"] == [i.kind for i in system.issues]


def test_a_name_that_is_missing_holds_both_passes() -> None:
    neutral, system = halves(draft("weapons", "odd", {"list": "melee", "range": "Melee"}))

    assert [i.kind for i in neutral.issues] == ["name"] == [i.kind for i in system.issues]


def test_not_knowing_if_it_is_melee_or_ranged_holds_the_neutral_pass() -> None:
    entry = {"name": "Odd", "type": "Martial", "damage": [1, 4, "slashing"]}

    neutral, system = halves(draft("weapons", "odd", entry))

    assert [i.kind for i in neutral.issues] == ["reach"] and not system.issues


# --- the plan of each pass -------------------------------------------------------------------------

TENANT = TenantOut.model_validate(
    {
        "id": uuid.UUID(int=1),
        "slug": "repo",
        "name": "Repo",
        "description": "",
        "kind": "repository",
        "published_at": None,
        "npcs_shared_with_gms": True,
        "created_by": None,
        "updated_by": None,
    }
)
NOW = datetime(2026, 10, 4, tzinfo=UTC).isoformat()


class FakeTenant:
    """A tenant that answers the reads a plan makes: slugs, stat definitions, an entity's parents."""

    def __init__(self) -> None:
        self.ids: dict[str, uuid.UUID] = {}
        self.parents: dict[str, list[str]] = {}
        self.definitions = {d.name: uuid.uuid4() for d in SEED.definitions}
        for node in SEED.nodes:
            self.add(node.slug, node.parents)

    def add(self, slug: str, parents: list[str] = (), **_: Any) -> uuid.UUID:  # type: ignore[assignment]
        self.ids[slug] = uuid.uuid4()
        self.parents[slug] = list(parents)
        return self.ids[slug]

    def detail(self, slug: str, entity_id: uuid.UUID | None = None) -> dict[str, Any]:
        """An entity as the API shows it; one that isn't in the tenant yet has no parents."""
        return {
            "id": str(entity_id or self.ids[slug]),
            "name": slug,
            "slug": slug,
            "created_at": NOW,
            "updated_at": NOW,
            "stats": [],
            "stat_groups": [],
            "information": [],
            "prototypes": [{"id": str(self.ids[p]), "name": p} for p in self.parents.get(slug, [])],
            "instances": [],
            "parent": None,
            "quantity": None,
            "children": [],
        }

    def slug_of(self, entity_id: str) -> str:
        return next(slug for slug, i in self.ids.items() if str(i) == entity_id)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/entities/resolve"):
            wanted = request.url.params.get_list("slug")
            return httpx.Response(
                200,
                json=[
                    {"slug": s, "entity_id": str(self.ids[s]), "name": s, "kinds": ["item"]}
                    for s in wanted
                    if s in self.ids
                ],
            )
        if path.endswith("/stat-definitions"):
            group = {"id": str(uuid.uuid4())}
            rows = [
                {
                    "id": str(self.definitions[d.name]),
                    "name": d.name,
                    "stat_group_id": group["id"],
                    "value_type": d.value_type,
                    "enum_values": [],
                    "created_at": NOW,
                    "updated_at": NOW,
                }
                for d in SEED.definitions
            ]
            return httpx.Response(
                200, json={"items": rows, "total": len(rows), "page": 1, "size": 100, "pages": 1}
            )
        if "/entities/" in path:
            slug = self.slug_of(path.rsplit("/", 1)[1])
            return httpx.Response(200, json=self.detail(slug))
        return httpx.Response(404, json={"title": "Not Found", "detail": path})

    def client(self) -> LorenzoClient:
        return LorenzoClient(
            "https://api.example/",
            FixedToken(),
            transport=httpx.MockTransport(self.handler),
            sleep=lambda _: None,
        )


def sheet(**lists: dict[str, dict[str, Any]]) -> EvalResult:
    return EvalResult(
        ok=True,
        lists={f"{name.capitalize()}List": entries for name, entries in lists.items()},
        origins={
            f"{name.capitalize()}List": dict.fromkeys(entries, "ListsGear.js")
            for name, entries in lists.items()
        },
    )


def planned(
    tenant: FakeTenant, result: EvalResult, part: str | None, manifest: Manifest | None = None
) -> ImportPlan:
    options = Options(part=part)  # type: ignore[arg-type]
    return build_plan(
        tenant.client(),
        TENANT,
        load_mapping(),
        result,
        SEED,
        manifest or Manifest(Path("unused")),
        options,
    )


def only(plan: ImportPlan) -> Any:
    [item] = [i for i in plan.items if i.status != "skipped"] or plan.items[:1]
    return item


def test_the_neutral_pass_plans_the_item_under_its_forms() -> None:
    plan = planned(FakeTenant(), sheet(weapons={"longsword": LONGSWORD}), "neutral")

    item = only(plan)
    assert plan.part == "neutral" and plan.problems == []
    assert (item.status, item.slug) == ("create", "basic-weapons-longsword")
    assert item.draft.parents == ["blade", "melee-weapon"]
    assert "damage_die" not in item.draft.stats


def test_the_system_pass_plans_a_prototype_for_the_item_it_finds() -> None:
    tenant = FakeTenant()
    item_id = tenant.add("basic-weapons-longsword", ["blade", "melee-weapon"])

    plan = planned(tenant, sheet(weapons={"longsword": LONGSWORD}), "system")

    item = only(plan)
    assert plan.part == "system" and plan.problems == []
    assert (item.status, item.slug) == ("create", "srd5e-weapons-longsword")
    assert item.neutral_slug == "basic-weapons-longsword" and item.neutral_id == item_id
    assert item.draft.name == "Longsword (D&D 5e)"
    assert item.draft.parents == ["dnd5e-martial", "dnd5e-versatile"]
    assert plan.categories == []


def test_the_system_pass_holds_an_item_whose_neutral_one_is_not_in_the_tenant() -> None:
    plan = planned(FakeTenant(), sheet(weapons={"longsword": LONGSWORD}), "system")

    item = only(plan)
    assert item.status == "held" and plan.held == [item]
    [issue] = item.draft.issues
    assert issue.kind == "neutral-item" and "basic-weapons-longsword" in issue.reason
    assert "lorenzo apply --part neutral" in issue.suggestion


def test_the_system_pass_skips_what_has_nothing_of_the_systems() -> None:
    tenant = FakeTenant()
    tenant.add("basic-ammo-arrow")
    arrow = {"name": "Arrow", "source": [["SRD", 74]], "weight": 0.05}

    plan = planned(tenant, sheet(ammo={"arrow": arrow}), "system")

    [item] = plan.items
    assert item.status == "skipped" and item.draft.skip_reason == "nothing of it is the system's"
    assert not plan.pending


def test_a_prototype_that_is_attached_is_there_and_one_that_is_not_is_finished() -> None:
    tenant = FakeTenant()
    tenant.add("basic-weapons-longsword", ["blade", "melee-weapon"])
    prototype = tenant.add("srd5e-weapons-longsword", ["dnd5e-martial", "dnd5e-versatile"])
    del prototype

    unattached = only(planned(tenant, sheet(weapons={"longsword": LONGSWORD}), "system"))
    tenant.parents["basic-weapons-longsword"].append("srd5e-weapons-longsword")
    attached = only(planned(tenant, sheet(weapons={"longsword": LONGSWORD}), "system"))

    assert (unattached.status, unattached.attached) == ("complete", False)
    assert (attached.status, attached.attached) == ("exists", True)


def test_a_prototype_attached_to_an_item_is_not_a_wrong_parent_in_the_neutral_pass() -> None:
    tenant = FakeTenant()
    tenant.add("srd5e-weapons-longsword")
    tenant.add("basic-weapons-longsword", ["blade", "melee-weapon", "srd5e-weapons-longsword"])
    result = sheet(weapons={"longsword": LONGSWORD})

    plan = planned(tenant, result, "neutral")
    tenant.parents["basic-weapons-longsword"] = ["blade", "weapon"]
    wrong = planned(tenant, result, "neutral")

    assert only(plan).reparent is False
    assert only(wrong).reparent is True  # a parent the importer places is different


def test_the_neutral_passes_slug_is_the_one_the_system_pass_looks_for() -> None:
    tenant = FakeTenant()
    neutral = only(planned(tenant, sheet(weapons={"longsword": LONGSWORD}), "neutral"))
    tenant.add(neutral.slug)

    system = only(planned(tenant, sheet(weapons={"longsword": LONGSWORD}), "system"))

    assert system.neutral_slug == neutral.slug


def test_the_system_passes_slugs_are_kept_apart_in_the_manifest() -> None:
    tenant = FakeTenant()
    tenant.add("basic-weapons-longsword")
    tenant.add("srd5e-old-weapons-longsword")
    manifest = Manifest(Path("unused"), {"system:weapons:longsword": "srd5e-old-weapons-longsword"})

    moved = only(planned(tenant, sheet(weapons={"longsword": LONGSWORD}), "system", manifest))

    assert moved.status == "moved" and moved.moved_from == "srd5e-old-weapons-longsword"


def test_without_a_part_the_plan_is_the_one_item_with_both_halves() -> None:
    plan = planned(FakeTenant(), sheet(weapons={"longsword": LONGSWORD}), None)

    item = only(plan)
    assert plan.part is None and item.slug == "basic-weapons-longsword"
    assert item.draft.parents == ["blade", "dnd5e-martial", "dnd5e-versatile", "melee-weapon"]
    assert item.draft.stats["damage_die"] == 8 and item.draft.stats["own_weight"] == 3.0


# --- what the system pass writes --------------------------------------------------------------------


class RecordingTenant(FakeTenant):
    """A tenant that also takes the writes of an import, and remembers them."""

    def __init__(self) -> None:
        super().__init__()
        self.writes: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method != "GET":
            self.writes.append(request)
            if request.method == "POST" and path.endswith("/items"):
                return httpx.Response(201, json={**_item(), "entity_id": str(uuid.uuid4())})
            if request.method == "POST":
                return httpx.Response(
                    201,
                    json={
                        "id": str(uuid.uuid4()),
                        "title": "t",
                        "type": "description",
                        "is_public": True,
                        "order": 0,
                        "updated_at": NOW,
                        "payloads": [],
                    },
                )
            if path.endswith("/prototypes"):
                return httpx.Response(200, json=_item(), headers={"ETag": '"v8"'})
            return httpx.Response(200, json=self.detail("new", uuid.uuid4()))
        if "/items/" in path:
            slug = self.slug_of(path.rsplit("/", 1)[1])
            ids = [str(self.ids[p]) for p in self.parents[slug]]
            return httpx.Response(
                200, json={**_item(), "prototype_ids": ids}, headers={"ETag": '"v7"'}
            )
        return super().handler(request)


def test_the_system_pass_writes_a_prototype_that_is_not_public_and_attaches_it_last() -> None:
    tenant = RecordingTenant()
    item_id = tenant.add("basic-weapons-longsword", ["blade", "melee-weapon"])
    plan = planned(tenant, sheet(weapons={"longsword": LONGSWORD}), "system")
    manifest = Manifest(Path("unused"))

    with tenant.client() as client:
        # Even asked for, a prototype is never public: that is the neutral pass's.
        report = apply_import(client, plan, manifest, ApplyOptions(public_catalog=True))

    assert (report.created, report.attached, report.failures) == (1, 1, [])
    created = json.loads(tenant.writes[0].content)
    assert tenant.writes[0].method == "POST" and tenant.writes[0].url.path.endswith("/items")
    assert created["slug"] == "srd5e-weapons-longsword"
    assert created["name"] == "Longsword (D&D 5e)"
    assert created["in_public_catalog"] is False
    assert created["prototype_ids"] == [
        str(tenant.ids["dnd5e-martial"]),
        str(tenant.ids["dnd5e-versatile"]),
    ]
    # The attachment is the last thing written, and keeps the item's own parents.
    last = tenant.writes[-1]
    assert last.method == "PUT" and last.url.path.endswith(f"/items/{item_id}/prototypes")
    assert last.headers["If-Match"] == '"v7"'
    sent = json.loads(last.content)["prototype_ids"]
    assert (
        sent[:2] == [str(tenant.ids["blade"]), str(tenant.ids["melee-weapon"])] and len(sent) == 3
    )
    assert manifest.slug_for("system:weapons", "longsword") == "srd5e-weapons-longsword"
    stats = [r for r in tenant.writes if "/stats/" in r.url.path]
    assert stats and all(json.loads(r.content)["acquire_group"] is True for r in stats)
    # Only the system's stats are written on the prototype, none of the neutral half.
    by_id = {str(i): name for name, i in tenant.definitions.items()}
    assert {by_id[r.url.path.rsplit("/", 1)[1]] for r in stats} == {
        "damage_dice_count",
        "damage_die",
        "damage_type",
        "damage_versatile_die",
        "attack_ability",
        "ability_to_damage",
    }


def test_the_neutral_pass_is_public_only_when_asked_and_attaches_nothing() -> None:
    tenant = RecordingTenant()
    result = sheet(weapons={"longsword": LONGSWORD})

    with tenant.client() as client:
        plan = planned(tenant, result, "neutral")
        report = apply_import(
            client, plan, Manifest(Path("unused")), ApplyOptions(public_catalog=True)
        )
        quiet = apply_import(
            client, planned(tenant, result, "neutral"), Manifest(Path("unused")), ApplyOptions()
        )

    assert (report.created, report.attached) == (1, 0)
    posts = [json.loads(r.content) for r in tenant.writes if r.url.path.endswith("/items")]
    assert [p["in_public_catalog"] for p in posts] == [True, False]
    assert quiet.created == 1
    assert not [r for r in tenant.writes if r.url.path.endswith("/prototypes")]
