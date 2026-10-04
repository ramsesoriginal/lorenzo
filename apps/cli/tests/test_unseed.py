"""What `unseed` plans from what a tenant holds, and what it does with the API's answers
(ADR 0168), without a network."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from test_seed_plan import TENANT, definition, group
from test_transport import FixedToken

from lorenzo_cli.client.models import (
    EntitySummary,
    ResolvedSlugOut,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed import (
    LAYERS,
    UnseedState,
    apply_unseed,
    load_builtin,
    make_unseed_plan,
)

SPEC = load_builtin()


def held(
    *layers: str,
    tenant: tuple[str, ...] | None = None,
    inheritors: dict[str, list[EntitySummary]] | None = None,
    attached: bool = True,
) -> UnseedState:
    """What `unseed` reads when it takes `layers` out of a tenant that holds every group,
    definition and category of the `tenant` layers (the same ones, unless said), and, where
    `attached`, the attachments of the layers it holds."""
    holds = set(tenant or layers)
    ids = {n.slug: uuid.uuid4() for n in SPEC.nodes}

    def resolved(slug: str) -> ResolvedSlugOut:
        return ResolvedSlugOut.model_validate(
            {
                "slug": slug,
                "entity_id": ids[slug],
                "name": SPEC.node(slug).name,
                "kinds": ["item"],
            }
        )

    all_groups = {g.name: group(g.name) for g in SPEC.groups}
    nodes = {n.slug: resolved(n.slug) for n in SPEC.nodes if n.layer in set(layers) & holds}
    edges = [
        (a.child, a.parent)
        for a in SPEC.attachments
        if attached and a.layer in holds and a.child in ids and a.parent in ids
    ]
    relevant = [
        a
        for a in SPEC.attachments
        if (a.layer in layers or SPEC.node(a.parent).layer in layers)
        and SPEC.node(a.child).layer in holds
        and SPEC.node(a.parent).layer in holds
    ]
    # Who has a category as a parent in the tenant: the nodes under it and what is attached to it.
    children: dict[str, list[EntitySummary]] = {slug: [] for slug in nodes}
    for n in SPEC.nodes:
        if n.layer in holds:
            for parent in n.parents:
                if parent in children:
                    children[parent].append(EntitySummary(id=ids[n.slug], name=n.name))
    for child, parent in edges:
        if parent in children and SPEC.node(child).layer in holds:
            children[parent].append(EntitySummary(id=ids[child], name=SPEC.node(child).name))
    for slug, extra in (inheritors or {}).items():
        children[slug] = [*extra]
    return UnseedState(
        nodes=nodes,
        inheritors=children,
        definitions={
            d.name: definition(d.name, all_groups[d.group], d.value_type)
            for d in SPEC.definitions
            if d.layer in holds
        },
        groups={g.name: g for g in all_groups.values() if _group_layer(g.name) in holds},
        attachments={
            end: resolved(end) for a in relevant for end in (a.child, a.parent) if end in ids
        },
        attached={(a.child, a.parent) for a in relevant if (a.child, a.parent) in set(edges)},
    )


def _group_layer(name: str) -> str:
    return next(g.layer for g in SPEC.groups if g.name == name)


def counts(plan: Any) -> tuple[int, int, int]:
    return (len(plan.of("node")), len(plan.of("definition")), len(plan.of("group")))


def test_a_layer_is_planned_as_its_categories_then_definitions_then_groups() -> None:
    state = held("dnd5e", tenant=("core", "dnd5e"))

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.problems == []
    assert counts(plan) == (30, 30, 3)
    assert [t.kind for t in plan.targets] == ["node"] * 30 + ["definition"] * 30 + ["group"] * 3
    assert {t.layer for t in plan.targets} == {"dnd5e"}
    assert all(t.name.startswith("dnd5e-") for t in plan.of("node"))


def test_the_core_layer_takes_its_groups_too() -> None:
    plan = make_unseed_plan(SPEC, held("core"), TENANT, ("core",))

    assert counts(plan) == (1, 10, 3)


def test_the_equipment_layer_is_only_categories() -> None:
    plan = make_unseed_plan(
        SPEC, held("equipment", tenant=("core", "equipment")), TENANT, ("equipment",)
    )

    assert plan.problems == [] and counts(plan) == (32, 0, 0)


def test_only_what_the_tenant_has_is_planned() -> None:
    state = held("core", "equipment")
    del state.nodes["crossbow"], state.inheritors["crossbow"]
    for kids in state.inheritors.values():  # nothing in the tenant is under it either
        kids[:] = [kid for kid in kids if kid.name != "Crossbow"]
    del state.definitions["is_magical"]

    plan = make_unseed_plan(SPEC, state, TENANT, ("core", "equipment"))

    assert counts(plan) == (32, 9, 3)


def test_an_empty_tenant_has_nothing_to_remove() -> None:
    plan = make_unseed_plan(SPEC, UnseedState(), TENANT, LAYERS)

    assert plan.targets == [] and plan.problems == []


def test_things_outside_the_layer_under_its_categories_stop_everything() -> None:
    state = held("dnd5e")
    longsword = EntitySummary(id=uuid.uuid4(), name="Longsword")
    dagger = EntitySummary(id=uuid.uuid4(), name="Dagger")
    state.inheritors["dnd5e-martial"] = [longsword, dagger]
    state.inheritors["dnd5e-finesse"] = [dagger]

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.targets == []
    [problem] = plan.problems
    assert "dnd5e-martial (2)" in problem and "dnd5e-finesse (1)" in problem
    assert "2 thing(s)" in problem and "Dagger" in problem and "Longsword" in problem


def test_categories_of_the_layer_under_one_another_do_not_count() -> None:
    state = held("dnd5e")
    focus = state.nodes["dnd5e-spellcasting-focus"]
    arcane = state.nodes["dnd5e-arcane-focus"]
    state.inheritors["dnd5e-spellcasting-focus"] = [
        EntitySummary(id=arcane.entity_id, name=arcane.name)
    ]
    assert focus is not arcane

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.problems == [] and counts(plan) == (30, 30, 3)


# --- attachments (ADR 0175) ----------------------------------------------------------------------


def test_the_attachments_layer_takes_its_parents_out_and_nothing_else() -> None:
    state = held("dnd5e-equipment", tenant=LAYERS)

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e-equipment",))

    assert plan.problems == []
    assert counts(plan) == (0, 0, 0)
    attachments = plan.of("attachment")
    assert [t.name for t in attachments] == [
        f"{form}: dnd5e-economic-object"
        for form in ("weapon", "armor", "tool", "container", "consumable", "gear")
    ]
    assert {t.layer for t in attachments} == {"dnd5e-equipment"}
    # The target is the child, and carries the parent to drop.
    assert attachments[0].id == state.attachments["weapon"].entity_id
    assert attachments[0].parent_id == state.attachments["dnd5e-economic-object"].entity_id


def test_only_the_attachments_the_tenant_has_are_planned() -> None:
    state = held("dnd5e-equipment", tenant=LAYERS)
    state.attached.discard(("tool", "dnd5e-economic-object"))

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e-equipment",))

    assert [t.name.split(":")[0] for t in plan.of("attachment")] == [
        "weapon", "armor", "container", "consumable", "gear",
    ]  # fmt: skip


def test_a_tenant_without_the_attachments_has_none_to_remove() -> None:
    state = held("dnd5e-equipment", tenant=LAYERS, attached=False)

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e-equipment",))

    assert plan.targets == [] and plan.problems == []


def test_a_layer_whose_categories_attachments_point_at_is_refused_alone() -> None:
    state = held("dnd5e", tenant=LAYERS)

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.targets == []
    refusal, hint = plan.problems
    assert "dnd5e-economic-object (6)" in refusal and "Taking the categories out" in refusal
    assert "the dnd5e-equipment layer makes" in hint
    assert "--layer dnd5e --layer dnd5e-equipment" in hint


def test_taking_the_attachments_out_in_the_same_call_lifts_the_refusal() -> None:
    state = held("dnd5e", "dnd5e-equipment", tenant=LAYERS)

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e", "dnd5e-equipment"))

    assert plan.problems == []
    kinds = [t.kind for t in plan.targets]
    # The attachments go first, then the categories, so the parent is gone from the forms before
    # it is deleted.
    assert kinds == ["attachment"] * 6 + ["node"] * 30 + ["definition"] * 30 + ["group"] * 3


def test_something_else_under_the_economic_object_still_stops_it() -> None:
    state = held("dnd5e", "dnd5e-equipment", tenant=LAYERS)
    sword = EntitySummary(id=uuid.uuid4(), name="Longsword 5e")
    state.inheritors["dnd5e-economic-object"] = [
        *state.inheritors["dnd5e-economic-object"],
        sword,
    ]

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e", "dnd5e-equipment"))

    [problem] = plan.problems
    assert "dnd5e-economic-object (1)" in problem and "Longsword 5e" in problem
    assert plan.targets == []


def test_the_forms_go_with_their_edges_without_the_attachments_layer() -> None:
    state = held("equipment", tenant=LAYERS)

    plan = make_unseed_plan(SPEC, state, TENANT, ("equipment",))

    # Nothing is inherited from the forms by anything but the equipment itself, and their parent
    # edges go with them, so nothing refuses.
    assert plan.problems == [] and counts(plan) == (32, 0, 0)


def test_a_layer_something_is_built_on_is_refused() -> None:
    state = held("core", tenant=("core", "equipment"))

    plan = make_unseed_plan(SPEC, state, TENANT, ("core",))

    [problem] = plan.problems
    assert "physical-object (" in problem and "nothing was deleted" in problem


# --- doing it ------------------------------------------------------------------------------------


def api(
    seen: list[httpx.Request],
    *,
    refuse: dict[str, int] | None = None,
    prototypes: list[uuid.UUID] | None = None,
) -> LorenzoClient:
    """Answers every read with an ETag (and the item having `prototypes` as parents), every
    replaced set of prototypes with the item and every delete with 204, except the paths named in
    `refuse`, which get that status."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status = next(
            (s for tail, s in (refuse or {}).items() if request.url.path.endswith(tail)), None
        )
        if status is not None:
            body = {"title": "No", "detail": f"Refused with {status}."}
            return httpx.Response(status, json=body)
        if request.method == "GET":
            item = {**_item(), "prototype_ids": [str(p) for p in prototypes or []]}
            return httpx.Response(200, json=item, headers={"ETag": '"v1"'})
        if request.method == "PUT":
            return httpx.Response(200, json=_item(), headers={"ETag": '"v2"'})
        return httpx.Response(204)

    return LorenzoClient(
        "https://api.example/",
        FixedToken(),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )


def _item() -> dict[str, Any]:
    return {
        "entity_id": str(uuid.uuid4()),
        "title": "x",
        "weight": None,
        "height": None,
        "price": None,
        "rarity": None,
        "hp": None,
        "armor": None,
        "container_entity_id": None,
        "prototype_ids": [],
        "is_container": None,
        "descriptions": [],
        "pictures": [],
        "physical_stats": [],
        "economic_stats": [],
        "destroyable_stats": [],
        "damaging_stats": [],
        "tags": [],
        "quantity": None,
        "created_by": None,
        "updated_by": None,
        "updated_at": "2026-10-04T00:00:00Z",
        "in_public_catalog": False,
    }


def test_categories_go_first_then_definitions_then_groups_each_item_with_its_etag() -> None:
    plan = make_unseed_plan(SPEC, held("core", "equipment"), TENANT, ("core", "equipment"))
    seen: list[httpx.Request] = []

    with api(seen) as client:
        result = apply_unseed(client, plan)

    deletes = [r for r in seen if r.method == "DELETE"]
    kinds = [r.url.path.split("/")[3] for r in deletes]
    assert kinds == ["items"] * 33 + ["stat-definitions"] * 10 + ["stat-groups"] * 3
    assert all(r.headers["If-Match"] == '"v1"' for r in deletes if "/items/" in r.url.path)
    assert len(result.deleted) == 46 and result.kept == []


def test_a_definition_the_api_refuses_is_kept_with_its_reason_and_the_rest_goes_on() -> None:
    state = held("dnd5e")
    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))
    used = state.definitions["is_finesse"].id
    seen: list[httpx.Request] = []

    with api(seen, refuse={f"/stat-definitions/{used}": 409}) as client:
        result = apply_unseed(client, plan)

    assert [(k.kind, k.name) for k in result.kept] == [("definition", "is_finesse")]
    assert "Refused with 409" in result.kept[0].reason
    assert len(result.deleted) == 30 + 29 + 3


def test_something_already_gone_counts_as_removed() -> None:
    state = held("dnd5e")
    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))
    gone = state.definitions["damage_die"].id

    with api([], refuse={f"/stat-definitions/{gone}": 404}) as client:
        result = apply_unseed(client, plan)

    assert result.kept == [] and len(result.deleted) == 63


def test_an_attachment_drops_the_parent_and_keeps_the_childs_other_parents() -> None:
    state = held("dnd5e-equipment", tenant=LAYERS)
    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e-equipment",))
    other = uuid.uuid4()
    parent = plan.of("attachment")[0].parent_id
    assert parent is not None
    seen: list[httpx.Request] = []

    with api(seen, prototypes=[other, parent]) as client:
        result = apply_unseed(client, plan)

    puts = [r for r in seen if r.method == "PUT"]
    assert len(puts) == 6 and not [r for r in seen if r.method == "DELETE"]
    assert all(r.url.path.endswith("/prototypes") for r in puts)
    assert all(r.headers["If-Match"] == '"v1"' for r in puts)
    assert json.loads(puts[0].content) == {"prototype_ids": [str(other)]}
    assert len(result.deleted) == 6 and result.kept == []


def test_an_attachment_the_child_no_longer_has_is_removed_without_a_write() -> None:
    state = held("dnd5e-equipment", tenant=LAYERS)
    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e-equipment",))
    seen: list[httpx.Request] = []

    with api(seen, prototypes=[uuid.uuid4()]) as client:
        result = apply_unseed(client, plan)

    assert [r.method for r in seen] == ["GET"] * 6
    assert len(result.deleted) == 6


def test_a_child_the_api_refuses_to_read_is_kept_and_the_rest_goes_on() -> None:
    state = held("dnd5e-equipment", tenant=LAYERS)
    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e-equipment",))
    tool = state.attachments["tool"].entity_id

    with api([], refuse={f"/items/{tool}": 403}) as client:
        result = apply_unseed(client, plan)

    assert [(k.kind, k.name) for k in result.kept] == [
        ("attachment", "tool: dnd5e-economic-object")
    ]
    assert "Refused with 403" in result.kept[0].reason
    assert len(result.deleted) == 5
