from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from lorenzo_cli.client.models import TenantOut
from lorenzo_cli.importer.draft import ItemDraft, NewCategory
from lorenzo_cli.importer.manifest import Manifest, default_path
from lorenzo_cli.importer.mapping import load_mapping
from lorenzo_cli.importer.plan import ImportPlan, NewDefinition, PlannedItem, Status
from lorenzo_cli.importer.review import plan_json, proposed_map, review_queue, write_review_queue
from lorenzo_cli.importer.transforms import Issue
from lorenzo_cli.report import import_exit_code

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


def item(
    key: str,
    status: Status,
    issues: list[Issue] | None = None,
    unmapped: list[str] | None = None,
    list_name: str = "weapons",
    **fields: Any,
) -> PlannedItem:
    draft = ItemDraft(list_name, key, "f.js", "basic", name=key.title(), unmapped=unmapped or [])
    draft.issues = issues or []
    planned = PlannedItem(draft, slug=f"basic-{list_name}-{key}", status=status, **fields)
    return planned


def make_plan(*items: PlannedItem, **fields: Any) -> ImportPlan:
    plan = ImportPlan(tenant=TENANT, loaded=load_mapping(), seed_version="1", **fields)
    plan.items = list(items)
    return plan


VALUE = Issue(
    "value",
    "type",
    "'Exotic'",
    "the map has no row for this weapons type",
    '[classify.weapons.type]\n"exotic" = "attach-form-only"   # or ["parent-slug"], "skip"',
)


def test_a_plan_with_nothing_to_do_and_nothing_unresolved_exits_zero() -> None:
    plan = make_plan(item("a", "exists"), item("b", "skipped"))

    assert import_exit_code(plan, strict=False, reconcile=False) == 0


def test_pending_work_exits_two_and_a_held_item_beats_it() -> None:
    assert import_exit_code(make_plan(item("a", "create")), strict=False, reconcile=False) == 2
    assert import_exit_code(make_plan(item("a", "complete")), strict=False, reconcile=False) == 2
    both = make_plan(item("a", "create"), item("b", "held", [VALUE]))
    assert import_exit_code(both, strict=False, reconcile=False) == 1


def test_a_problem_or_a_file_that_stopped_is_unresolved() -> None:
    assert import_exit_code(make_plan(problems=["not seeded"]), strict=False, reconcile=False) == 1
    assert (
        import_exit_code(make_plan(file_errors=["x.js: boom"]), strict=False, reconcile=False) == 1
    )


def test_a_moved_item_is_unresolved_until_someone_decides() -> None:
    plan = make_plan(item("a", "moved", moved_from="hb-old-weapons-a"))

    assert import_exit_code(plan, strict=False, reconcile=False) == 1


def test_unmapped_attributes_only_count_when_strict() -> None:
    plan = make_plan(item("a", "exists", unmapped=["flavour"]))

    assert import_exit_code(plan, strict=False, reconcile=False) == 0
    assert import_exit_code(plan, strict=True, reconcile=False) == 1


def test_changed_parents_are_pending_only_when_reconciling() -> None:
    plan = make_plan(item("a", "exists", reparent=True))

    assert import_exit_code(plan, strict=False, reconcile=False) == 0
    assert import_exit_code(plan, strict=False, reconcile=True) == 2


def test_the_plan_document_has_a_header_a_script_can_chain_on() -> None:
    plan = make_plan(
        item("a", "create"),
        item("b", "held", [VALUE]),
        item("c", "skipped"),
        categories=[NewCategory("hb-x", "X", "dnd5e-weapon-proficiency", "proficiency")],
        definitions=[NewDefinition("flavour_text", "lore", "text")],
    )

    document = plan_json(plan)

    header = document["header"]
    assert header["tenant"] == {
        "id": str(uuid.UUID(int=1)),
        "slug": "repo",
        "kind": "repository",
        "published": False,
    }
    assert (header["builtin_version"], header["user_map_sha256"], header["seed_version"]) == (
        "2",
        "",
        "1",
    )
    assert header["counts"]["create"] == 1 and header["counts"]["held"] == 1
    assert header["counts"]["skipped"] == 1 and header["counts"]["new_categories"] == 1
    assert document["new_definitions"] == [
        {"name": "flavour_text", "group": "lore", "value_type": "text"}
    ]
    assert json.loads(json.dumps(document)) == document  # plain data


def test_the_review_queue_lists_held_values_moves_and_unmapped_attributes_once_each() -> None:
    plan = make_plan(
        item("whip", "held", [VALUE]),
        item("sword", "moved", moved_from="hb-old-weapons-sword"),
        item("a", "exists", unmapped=["flavour"]),
        item("b", "create", unmapped=["flavour", "mood"]),
    )

    queue = review_queue(plan)

    kinds = sorted((q["kind"], q["attribute"]) for q in queue)
    assert kinds == [
        ("attribute", "flavour"),
        ("attribute", "mood"),
        ("moved", ""),
        ("value", "type"),
    ]
    flavour = next(q for q in queue if q["attribute"] == "flavour")
    assert "2 item(s)" in flavour["reason"]
    assert 'flavour = "drop"' in flavour["suggestion"]
    moved = next(q for q in queue if q["kind"] == "moved")
    assert "hb-old-weapons-sword" in moved["reason"] and "--accept-moves" in moved["suggestion"]


def test_the_review_queue_is_written_as_json(tmp_path: Path) -> None:
    plan = make_plan(item("whip", "held", [VALUE]))

    count = write_review_queue(tmp_path / "queue.json", plan)

    assert count == 1
    assert json.loads((tmp_path / "queue.json").read_text())[0]["value"] == "'Exotic'"


def test_the_proposed_map_asks_about_each_value_once() -> None:
    plan = make_plan(
        item("whip", "held", [VALUE]),
        item("flail", "held", [VALUE]),
        item("a", "create", unmapped=["flavour"]),
    )

    text = proposed_map(plan)

    assert text.count('"exotic" = "attach-form-only"') == 1
    assert text.count("[classify.weapons.type]") == 1
    assert "[attributes.weapons]" in text and 'flavour = "drop"' in text
    assert text.startswith("# Proposed map rows")


def test_the_manifest_remembers_a_slug_per_key_and_survives_being_lost(tmp_path: Path) -> None:
    path = default_path({"XDG_STATE_HOME": str(tmp_path)}, uuid.UUID(int=7))
    manifest = Manifest.load(path)
    assert manifest.slug_for("weapons", "longsword") is None

    manifest.record("weapons", "longsword", "basic-weapons-longsword")
    manifest.save()

    assert path.parent == tmp_path / "lorenzo" and path.name == f"import-{uuid.UUID(int=7)}.json"
    again = Manifest.load(path)
    assert again.slug_for("weapons", "longsword") == "basic-weapons-longsword"
    assert again.slug_for("gear", "longsword") is None
    path.write_text("{ not json")
    assert Manifest.load(path).slug_for("weapons", "longsword") is None  # a cache that isn't there
