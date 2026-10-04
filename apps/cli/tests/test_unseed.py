"""What `unseed` plans from what a tenant holds, and what it does with the API's answers
(ADR 0168), without a network."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from test_seed_plan import TENANT, definition, group
from test_transport import FixedToken

from lorenzo_cli.client.models import (
    EntitySummary,
    ResolvedSlugOut,
    StatDefinitionOut,
    StatGroupOut,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.seed import (
    UnseedState,
    apply_unseed,
    load_builtin,
    make_unseed_plan,
)

SPEC = load_builtin()


def held(*layers: str, inheritors: dict[str, list[EntitySummary]] | None = None) -> UnseedState:
    """A tenant holding every group, definition and category of the given layers."""
    groups: dict[str, StatGroupOut] = {g.name: group(g.name) for g in SPEC.groups}
    definitions: dict[str, StatDefinitionOut] = {
        d.name: definition(d.name, groups[d.group], d.value_type)
        for d in SPEC.definitions
        if d.layer in layers
    }
    nodes = {
        n.slug: ResolvedSlugOut.model_validate(
            {"slug": n.slug, "entity_id": uuid.uuid4(), "name": n.name, "kinds": ["item"]}
        )
        for n in SPEC.nodes
        if n.layer in layers
    }
    return UnseedState(
        nodes=nodes,
        inheritors={slug: (inheritors or {}).get(slug, []) for slug in nodes},
        definitions=definitions,
        groups={g.name: g for g in groups.values() if g.name in {x.name for x in SPEC.groups}}
        if "core" in layers
        else {},
    )


def counts(plan: Any) -> tuple[int, int, int]:
    return (len(plan.of("node")), len(plan.of("definition")), len(plan.of("group")))


def test_a_layer_is_planned_as_its_categories_then_definitions_then_groups() -> None:
    state = held("core", "dnd5e")

    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))

    assert plan.problems == []
    assert counts(plan) == (28, 22, 0)
    assert [t.kind for t in plan.targets] == ["node"] * 28 + ["definition"] * 22
    assert {t.layer for t in plan.targets} == {"dnd5e"}
    assert all(t.name.startswith("dnd5e-") for t in plan.of("node"))


def test_the_core_layer_takes_its_groups_too() -> None:
    plan = make_unseed_plan(SPEC, held("core"), TENANT, ("core",))

    assert counts(plan) == (33, 18, 6)


def test_only_what_the_tenant_has_is_planned() -> None:
    state = held("core")
    del state.nodes["crossbow"], state.inheritors["crossbow"]
    del state.definitions["price"]

    plan = make_unseed_plan(SPEC, state, TENANT, ("core",))

    assert counts(plan) == (32, 17, 6)


def test_an_empty_tenant_has_nothing_to_remove() -> None:
    plan = make_unseed_plan(SPEC, UnseedState(), TENANT, ("core", "dnd5e"))

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

    assert plan.problems == [] and counts(plan) == (28, 22, 0)


# --- doing it ------------------------------------------------------------------------------------


def api(seen: list[httpx.Request], *, refuse: dict[str, int] | None = None) -> LorenzoClient:
    """Answers every read with an ETag and every delete with 204, except the paths named in
    `refuse`, which get that status."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=_item(), headers={"ETag": '"v1"'})
        status = next(
            (s for tail, s in (refuse or {}).items() if request.url.path.endswith(tail)), 204
        )
        if status == 204:
            return httpx.Response(204)
        return httpx.Response(status, json={"title": "No", "detail": f"Refused with {status}."})

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
    plan = make_unseed_plan(SPEC, held("core"), TENANT, ("core",))
    seen: list[httpx.Request] = []

    with api(seen) as client:
        result = apply_unseed(client, plan)

    deletes = [r for r in seen if r.method == "DELETE"]
    kinds = [r.url.path.split("/")[3] for r in deletes]
    assert kinds == ["items"] * 33 + ["stat-definitions"] * 18 + ["stat-groups"] * 6
    assert all(r.headers["If-Match"] == '"v1"' for r in deletes if "/items/" in r.url.path)
    assert len(result.deleted) == 57 and result.kept == []


def test_a_definition_the_api_refuses_is_kept_with_its_reason_and_the_rest_goes_on() -> None:
    state = held("dnd5e")
    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))
    used = state.definitions["is_finesse"].id
    seen: list[httpx.Request] = []

    with api(seen, refuse={f"/stat-definitions/{used}": 409}) as client:
        result = apply_unseed(client, plan)

    assert [(k.kind, k.name) for k in result.kept] == [("definition", "is_finesse")]
    assert "Refused with 409" in result.kept[0].reason
    assert len(result.deleted) == 28 + 21


def test_something_already_gone_counts_as_removed() -> None:
    state = held("dnd5e")
    plan = make_unseed_plan(SPEC, state, TENANT, ("dnd5e",))
    gone = state.definitions["damage_die"].id

    with api([], refuse={f"/stat-definitions/{gone}": 404}) as client:
        result = apply_unseed(client, plan)

    assert result.kept == [] and len(result.deleted) == 50
