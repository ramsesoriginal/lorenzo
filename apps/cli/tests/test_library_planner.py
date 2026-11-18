"""What applying a document would do to a library (ADR 0484), against libraries built by hand."""

from __future__ import annotations

import uuid

from test_library_document import SMALL

from lorenzo_cli.client.models import (
    StatDefinitionOut,
    StatGroupOut,
    StatValueType,
    SystemOut,
    TenantOut,
)
from lorenzo_cli.library.document import parse
from lorenzo_cli.library.planner import ENTRY, make_plan
from lorenzo_cli.library.state import EntryState, LibraryState

TENANT = TenantOut.model_construct(id=uuid.uuid4(), slug="table", name="Table")


def library() -> LibraryState:
    return LibraryState(tenant=TENANT)


def group(name: str, system: SystemOut | None = None, **extra: object) -> StatGroupOut:
    values = {"priority": 0, "mandatory": False, "position": 0, "role": None, **extra}
    return StatGroupOut.model_construct(
        id=uuid.uuid4(), name=name, system_id=system.id if system else None, **values
    )


def stat(name: str, of: StatGroupOut, kind: str = "int", **extra: object) -> StatDefinitionOut:
    values: dict[str, object] = {
        "role": None,
        "unit": None,
        "min_value": None,
        "max_value": None,
        "max_hint_id": None,
        "min_hint_id": None,
        "resolved_hint_id": None,
        "adjustable_in_play": False,
        "pin": False,
        "signed": False,
        "position": 0,
        "enum_values": [],
        **extra,
    }
    return StatDefinitionOut.model_construct(
        id=uuid.uuid4(), name=name, stat_group_id=of.id, value_type=StatValueType(kind), **values
    )


def entry(slug: str, *parents: EntryState, values: dict | None = None) -> EntryState:
    return EntryState(
        id=uuid.uuid4(),
        slug=slug,
        name=slug,
        kinds=["item"],
        parent_ids=[p.id for p in parents],
        values=values or {},
        information=[],
    )


def applied() -> LibraryState:
    """A library that holds SMALL exactly."""
    state = library()
    system = SystemOut.model_construct(id=uuid.uuid4(), slug="ds", name="Dust and Sun")
    vitals = group("ds_vitals", system)
    stamina = stat("ds_stamina", vitals, min_value=0.0, max_value=20.0)
    bite = stat("ds_bite", vitals, "dice")
    root = entry("ds-root")
    hunter = entry("ds-hunter", root, values={stamina.id: 12, bite.id: "1d6"})
    system.root_entry_id = root.id
    state.systems = {"ds": system}
    state.groups = {"ds_vitals": vitals}
    state.stats = {"ds_stamina": stamina, "ds_bite": bite}
    state.entries = {root.id: root, hunter.id: hunter}
    return state


def test_an_empty_library_gets_everything_in_dependency_order() -> None:
    plan = make_plan(parse(SMALL), library())

    assert plan.problems == []
    kinds = [(a.verb, a.kind, a.key) for a in plan.actions]
    assert ("create", "system", "ds") in kinds
    assert ("create", "group", "ds_vitals") in kinds
    assert ("create", "value", "ds-hunter: ds_bite") in kinds
    assert ("change", "root", "ds") in kinds
    levels = {a.key: a.level for a in plan.actions if a.kind == "entry"}
    assert levels == {"ds-root": ENTRY, "ds-hunter": ENTRY + 1}  # a parent before its child
    order = [a.kind for level in plan.levels() for a in level]
    assert order.index("system") < order.index("group") < order.index("stat") < order.index("entry")
    assert order.index("root") == len(order) - 1
    assert plan.exit_code() == 2


def test_a_library_that_holds_the_document_has_nothing_to_do() -> None:
    plan = make_plan(parse(SMALL), applied())

    assert plan.actions == [] and plan.problems == []
    assert plan.exit_code() == 0


def test_only_what_the_document_names_and_differs_is_changed() -> None:
    state = applied()
    state.stats["ds_stamina"].max_value = 10.0
    plan = make_plan(parse(SMALL.replace('type = "int"', 'type = "int"\nunit = "points"')), state)

    changes = [(a.kind, a.key, a.detail) for a in plan.actions]
    assert changes == [("stat", "ds_stamina", "unit, max")]


def test_a_type_or_group_the_library_has_otherwise_cannot_be_changed() -> None:
    state = applied()
    state.stats["ds_stamina"] = stat("ds_stamina", state.groups["ds_vitals"], "float")
    plan = make_plan(parse(SMALL), state)

    assert any("type can't change" in p for p in plan.problems)
    assert plan.exit_code() == 1


def test_a_stat_in_a_library_group_of_a_system_needs_its_prefix() -> None:
    state = applied()
    doc = parse(
        'format = 1\nname = "more"\n[[stat]]\nname = "luck"\ngroup = "ds_vitals"\ntype = "int"\n'
    )
    plan = make_plan(doc, state)

    assert any("ds_something" in p for p in plan.problems)


def test_a_role_another_stat_holds_is_a_problem() -> None:
    state = library()
    physical = group("physical")
    state.groups = {"physical": physical}
    state.stats = {"mass": stat("mass", physical, "float", role="weight")}
    doc = parse(
        'format = 1\nname = "n"\n[[stat]]\nname = "weight"\ngroup = "physical"\n'
        'type = "float"\nrole = "weight"\n'
    )
    plan = make_plan(doc, state)

    assert plan.problems == ["stat weight: the role weight is held by mass."]


def test_what_is_missing_is_named_with_what_the_document_requires() -> None:
    doc = parse(
        SMALL.replace('stats = { ds_stamina = 12, ds_bite = "1d6" }', 'tags = ["is_magical"]')
    )
    plan = make_plan(doc, library())

    assert any("no stat is_magical" in p and "requires neutral" in p for p in plan.problems)


def test_a_missing_parent_is_added_and_none_is_taken_away() -> None:
    state = applied()
    other = entry("ds-other")
    state.entries[other.id] = other
    doc = parse(SMALL.replace('parents = ["ds-root"]', 'parents = ["ds-root", "ds-other"]'))
    plan = make_plan(doc, state)

    assert [(a.kind, a.key, a.detail) for a in plan.actions] == [
        ("parents", "ds-hunter", "+ ds-other")
    ]


def test_prune_removes_only_the_systems_rows_the_document_no_longer_names() -> None:
    state = applied()
    vitals = state.groups["ds_vitals"]
    state.stats["ds_old"] = stat("ds_old", vitals)
    category = entry("ds-category", state.entry("ds-root"))
    leaf = entry("ds-imported-sword", category)  # content under the root: never pruned itself
    state.entries |= {category.id: category, leaf.id: leaf}
    plan = make_plan(parse(SMALL), state, prune=True)

    removed = [(a.kind, a.key) for a in plan.actions if a.verb == "remove"]
    assert ("stat", "ds_old") in removed
    assert any("ds-category would go" in p for p in plan.problems)  # the sword inherits from it


def test_prune_needs_a_system() -> None:
    plan = make_plan(parse('format = 1\nname = "n"\n'), library(), prune=True)

    assert any("has no [system]" in p for p in plan.problems)


def test_dice_are_the_same_however_they_are_written() -> None:
    from lorenzo_cli.library.planner import same

    assert same("d6", "1d6") and same("1W6", "1d6") and same("4d6dl1", "4D6DL1")
    assert not same("2d6", "1d6") and not same("d8", "d6")
