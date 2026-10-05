"""Carrying out a seed plan (ADR 0143, 0181), in dependency order: groups, definitions, nodes
(parents first) with their tags and values, attachments, recipes.

Nothing is undone on failure. Every step is find-or-create, and a node is created and named in
one request (ADR 0139), so running the seed again picks up exactly where it stopped.
"""

from __future__ import annotations

from uuid import UUID

from lorenzo_cli import descriptions
from lorenzo_cli.client.models import (
    ContentsFormulaBody,
    InformationCreate,
    ItemCreate,
    SetEntityStatRequest,
    StatDefinitionCreate,
    StatGroupCreate,
    StatValueType,
    SumFormulaBodyInput,
    SumTermBodyInput,
)
from lorenzo_cli.client.ops import (
    CREATE_INFORMATION,
    CREATE_ITEM,
    CREATE_STAT_DEFINITION,
    CREATE_STAT_GROUP,
    SET_COMPUTED_STAT,
    SET_ENTITY_STAT,
    SET_ENTITY_TAG,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.prototypes import add_parent
from lorenzo_cli.seed.plan import SeedPlan, TenantState
from lorenzo_cli.seed.spec import SeedSpec


def apply_plan(client: LorenzoClient, spec: SeedSpec, plan: SeedPlan, state: TenantState) -> None:
    if plan.problems:
        raise ValueError("A plan with problems is never applied.")
    tenant = {"tenant_id": plan.tenant.id}
    groups: dict[str, UUID] = {name: g.id for name, g in state.groups.items()}
    definitions: dict[str, UUID] = {name: d.id for name, d in state.definitions.items()}
    nodes: dict[str, UUID] = {slug: n.entity_id for slug, n in state.nodes.items()}

    for action in plan.actions:
        if action.kind == "group":
            created = client.call(
                CREATE_STAT_GROUP, path=tenant, body=StatGroupCreate(name=action.name)
            )
            groups[action.name] = created.value.id
        elif action.kind == "definition":
            definition = next(d for d in spec.definitions if d.name == action.name)
            created_def = client.call(
                CREATE_STAT_DEFINITION,
                path=tenant,
                body=StatDefinitionCreate(
                    name=definition.name,
                    stat_group_id=groups[definition.group],
                    value_type=StatValueType(definition.value_type),
                ),
            )
            definitions[action.name] = created_def.value.id
        elif action.kind == "node":
            node = spec.node(action.name)
            created_node = client.call(
                CREATE_ITEM,
                path=tenant,
                body=ItemCreate(
                    name=node.name,
                    slug=node.slug,
                    prototype_ids=[nodes[parent] for parent in node.parents],
                    # Taxonomy nodes are vocabulary for the tenant's authors, not catalog entries.
                    in_public_catalog=False,
                ),
            )
            nodes[node.slug] = created_node.value.entity_id
        elif action.kind == "description":
            node = spec.node(action.name)
            client.call(
                CREATE_INFORMATION,
                path={**tenant, "entity_id": nodes[node.slug]},
                body=InformationCreate(
                    title=node.name,
                    type="description",
                    is_public=True,
                    content=node.description,
                    locale="en-US",
                ),
            )
        elif action.kind == "retitle":
            # A 412 (it changed since it was read) stops the run, as any API error does; the
            # next run finds what is left.
            information_id, title = state.retitles[action.name]
            descriptions.retitle(client, plan.tenant.id, information_id, title)
        elif action.kind == "tag":
            slug, tag = action.name.split(": ")
            client.call(
                SET_ENTITY_TAG,
                path={**tenant, "entity_id": nodes[slug], "stat_definition_id": definitions[tag]},
            )
        elif action.kind == "stat":
            slug, stat = action.name.split(": ")
            # The stat's group is acquired with the value: a prototype adds a group to everything
            # under it by carrying a value in it (RFC 0033, section 3).
            client.call(
                SET_ENTITY_STAT,
                path={**tenant, "entity_id": nodes[slug], "stat_definition_id": definitions[stat]},
                body=SetEntityStatRequest(value=spec.node(slug).stats[stat], acquire_group=True),
            )
        elif action.kind == "attach":
            child, parent = action.name.split(": ")
            add_parent(client, plan.tenant.id, nodes[child], nodes[parent])
        else:
            recipe = next(r for r in spec.recipes if f"{r.node}: {r.stat}" == action.name)
            # `kind` is set explicitly: a defaulted field isn't sent, and the API needs it.
            body: ContentsFormulaBody | SumFormulaBodyInput
            if recipe.kind == "contents":
                assert recipe.source is not None
                body = ContentsFormulaBody(
                    kind="contents", source_stat_definition_id=definitions[recipe.source]
                )
            else:
                body = SumFormulaBodyInput(
                    kind="sum",
                    terms=[
                        SumTermBodyInput(stat_definition_id=definitions[t]) for t in recipe.terms
                    ],
                )
            client.call(
                SET_COMPUTED_STAT,
                path={
                    **tenant,
                    "entity_id": nodes[recipe.node],
                    "stat_definition_id": definitions[recipe.stat],
                },
                body=body,
            )
