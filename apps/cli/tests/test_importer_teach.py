from __future__ import annotations

import tomllib
import uuid
from collections.abc import Callable

from lorenzo_cli.client.models import TenantOut
from lorenzo_cli.importer.draft import ItemDraft
from lorenzo_cli.importer.mapping import load_mapping
from lorenzo_cli.importer.plan import ImportPlan, PlannedItem
from lorenzo_cli.importer.teach import Unknown, ask, rows_toml, unknown_values
from lorenzo_cli.importer.transforms import Issue

MAPPING = load_mapping().mapping
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


def held(key: str, attribute: str, value: str, list_name: str = "weapons") -> PlannedItem:
    draft = ItemDraft(list_name, key, "f.js", "basic", name=key.title())
    draft.issues = [Issue("value", attribute, repr(value), "no row")]
    return PlannedItem(draft, slug=key, status="held")


def plan_of(*items: PlannedItem) -> ImportPlan:
    plan = ImportPlan(tenant=TENANT, loaded=load_mapping(), seed_version="1")
    plan.items = list(items)
    return plan


def scripted(*answers: str) -> Callable[[str, str], str]:
    remaining = list(answers)

    def prompt(text: str, default: str) -> str:
        return remaining.pop(0) if remaining else default

    return prompt


UNKNOWN = Unknown("weapons", "type", "Exotic", "exotic", ("Moon whip",))


def test_each_unknown_value_is_asked_about_once_however_many_items_have_it() -> None:
    plan = plan_of(
        held("whip", "type", "Exotic"),
        held("flail", "type", "exotic"),
        held("net", "type", "Net"),
        held("rope", "type", "Exotic", list_name="gear"),
    )

    unknowns = unknown_values(plan)

    assert [(u.list_name, u.attribute, u.key, len(u.items)) for u in unknowns] == [
        ("gear", "type", "exotic", 1),
        ("weapons", "type", "exotic", 2),
        ("weapons", "type", "net", 1),
    ]


def test_only_unknown_values_are_asked_about_not_other_problems() -> None:
    item = held("whip", "type", "Exotic")
    item.draft.issues.append(Issue("price", "infoname", "'x'", "no price"))
    item.draft.issues[0] = Issue("reach", "list", "None", "no reach")

    assert unknown_values(plan_of(item)) == []


def test_each_answer_is_a_row_of_the_map() -> None:
    say = lambda _: None  # noqa: E731

    assert ask(UNKNOWN, MAPPING, scripted("a"), say) == '"exotic" = "attach-form-only"'
    assert ask(UNKNOWN, MAPPING, scripted("s"), say) == '"exotic" = "skip"'
    assert ask(UNKNOWN, MAPPING, scripted("f"), say) == '"exotic" = "fail"'
    assert ask(UNKNOWN, MAPPING, scripted("m", "dnd5e-martial, melee-weapon"), say) == (
        '"exotic" = ["dnd5e-martial", "melee-weapon"]'
    )
    assert ask(
        UNKNOWN, MAPPING, scripted("c", "proficiency", "hb-exotic", "Exotic weapon"), say
    ) == (
        '"exotic" = { disposition = "create-under", axis = "proficiency", '
        'slug = "hb-exotic", name = "Exotic weapon" }'
    )


def test_leaving_a_value_alone_is_the_default_and_answers_nothing() -> None:
    say = lambda _: None  # noqa: E731

    assert ask(UNKNOWN, MAPPING, scripted(), say) is None
    assert ask(UNKNOWN, MAPPING, scripted("l"), say) is None
    assert ask(UNKNOWN, MAPPING, scripted("???"), say) is None


def test_the_question_shows_what_the_value_is_and_which_items_have_it() -> None:
    said: list[str] = []

    ask(
        Unknown("weapons", "type", "Exotic", "exotic", ("A", "B", "C", "D")),
        MAPPING,
        scripted(),
        said.append,
    )

    assert "weapons.type = 'Exotic' (4 item(s): A, B, C ...)" in said[0]
    assert "[a]ttach" in said[1]


def test_a_quote_in_a_value_cannot_break_the_row() -> None:
    row = ask(
        Unknown("gear", "type", 'Say "hi"', 'say "hi"', ("x",)),
        MAPPING,
        scripted("s"),
        lambda _: None,
    )

    assert row is not None
    parsed = tomllib.loads(f"[classify.gear.type]\n{row}\n")
    assert parsed["classify"]["gear"]["type"] == {'say "hi"': "skip"}


def test_the_answers_are_valid_toml_that_the_mapping_accepts() -> None:
    rows = {
        ("weapons", "type"): [
            '"exotic" = "attach-form-only"',
            '"net" = { disposition = "create-under", axis = "proficiency", slug = "hb-net", name = "Net" }',
        ],
        ("gear", "type"): ['"rope" = ["container"]'],
    }

    text = rows_toml(rows)
    loaded = load_mapping("schema = 1\n", taught=text).mapping

    assert loaded.classify["weapons"]["type"]["exotic"].disposition == "attach-form-only"
    assert loaded.classify["weapons"]["type"]["net"].slug == "hb-net"
    assert loaded.classify["gear"]["type"]["rope"].parents == ["container"]
    assert loaded.classify["weapons"]["type"]["martial"].parents == ["dnd5e-martial"]  # kept


def test_taught_rows_do_not_change_the_hash_of_the_file() -> None:
    text = "schema = 1\n[currencies]\nmark = 250\n"

    plain = load_mapping(text)
    taught = load_mapping(text, taught='[classify.weapons.type]\n"exotic" = "skip"\n')

    assert plain.user_map_sha256 == taught.user_map_sha256
    assert taught.mapping.classify["weapons"]["type"]["exotic"].disposition == "skip"


def test_taught_rows_win_over_the_files_and_work_without_a_file() -> None:
    taught = '[classify.weapons.type]\nmartial = ["hb-x"]\n'

    with_file = load_mapping(
        'schema = 1\n[classify.weapons.type]\nmartial = ["hb-y"]\n', taught=taught
    )
    without = load_mapping(None, taught=taught)

    assert with_file.mapping.classify["weapons"]["type"]["martial"].parents == ["hb-x"]
    assert without.mapping.classify["weapons"]["type"]["martial"].parents == ["hb-x"]
    assert without.user_map_sha256 == ""
