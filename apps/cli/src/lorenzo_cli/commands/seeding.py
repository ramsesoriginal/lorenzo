"""`seed` and `unseed` (ADR 0143, 0168, 0181)."""

from __future__ import annotations

from typing import Annotated

import typer

from lorenzo_cli import console
from lorenzo_cli.commands.common import TenantOption
from lorenzo_cli.report import (
    print_libraries_held,
    print_seed_list,
    print_seed_plan,
    print_unseed_plan,
    print_unseed_result,
    seed_list_json,
    seed_plan_json,
    unseed_counts,
    unseed_plan_json,
    unseed_result_json,
)
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _err,
    _out,
    _reporting_errors,
    may_write,
)
from lorenzo_cli.seed import (
    LAYERS,
    UnseedPlan,
    UnseedResult,
    apply_plan,
    apply_unseed,
    libraries_holding,
    load_builtin,
    make_plan,
    make_unseed_plan,
    read_state,
    read_unseed_state,
)
from lorenzo_cli.tenants import (
    require_repository,
    resolve_tenant,
)

app = typer.Typer()


@app.command()
def seed(
    ctx: typer.Context,
    tenant: Annotated[
        str | None,
        typer.Option(
            "--tenant", "-t", envvar="LORENZO_TENANT", help="The repository tenant's id or slug."
        ),
    ] = None,
    layers: Annotated[
        list[str] | None,
        typer.Option(
            "--layer",
            help=f"Only these layers of the seed ({', '.join(LAYERS)}). Without it, every layer "
            "is seeded, unless the tenant holds one and not another (name the layers then).",
        ),
    ] = None,
    list_seed: Annotated[
        bool,
        typer.Option(
            "--list",
            help="Only list what the seed makes, per layer. Needs no login and no tenant.",
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be created; exit 2 if anything.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")] = False,
    allow_play_tenant: Annotated[
        bool,
        typer.Option(
            "--allow-play-tenant", help="Write to a play tenant, whose content can't be published."
        ),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the plan as JSON.")] = False,
) -> None:
    """Create the item taxonomy and the stat definitions in a tenant; safe to run again.

    Finds or creates by name and slug, and never changes or removes anything (`unseed` takes a
    layer out). The dnd5e-equipment layer is made of attachments: parents it adds to categories of
    the equipment layer. `--list` only prints what the seed makes. Exit codes: 0 done or nothing to
    do, 2 with --dry-run when there is something to create, 1 on a problem.
    """
    runtime: Runtime = ctx.obj
    chosen = tuple(layers) if layers else LAYERS
    unknown = [layer for layer in chosen if layer not in LAYERS]
    if unknown:
        raise typer.BadParameter(f"{', '.join(unknown)}: choose from {', '.join(LAYERS)}")
    spec = load_builtin()
    if list_seed:
        writing = [
            flag
            for flag, given in (
                ("--dry-run", dry_run),
                ("--yes", yes),
                ("--allow-play-tenant", allow_play_tenant),
            )
            if given
        ]
        if writing:
            raise typer.BadParameter(
                f"--list only reads the seed, so it can't go with {', '.join(writing)}."
            )
        if as_json:
            console.emit(seed_list_json(spec, chosen))
        else:
            print_seed_list(_out, spec, chosen)
        return
    if tenant is None:
        raise typer.BadParameter("Name the repository with --tenant (or LORENZO_TENANT).")
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        target = resolve_tenant(client, tenant)
        require_repository(target, allow_play=allow_play_tenant)
        state = read_state(client, target.id, spec)
        plan = make_plan(spec, state, target, chosen, explicit=layers is not None)
        if as_json:
            console.emit(seed_plan_json(plan))
        else:
            print_seed_plan(_out, plan)
            if layers is None and any(a.kind != "retitle" for a in plan.actions):
                _err.print(
                    "[dim]Every layer is going into this one repository, which is fine for your "
                    "own use. To publish them as separate repositories, seed each layer into its "
                    "own with --layer (README, ADR 0162, 0181).[/dim]"
                )
        if plan.problems:
            raise typer.Exit(1)
        if dry_run:
            raise typer.Exit(2 if plan.actions else 0)
        if not plan.actions:
            return
        may_write(runtime, yes=yes, question="Create these?")
        with console.counting("Creating", len(plan.actions)) as steps:
            apply_plan(client, spec, plan, state, advance=steps.advance)
    if not as_json:
        _out.print(
            f"Created {len(plan.actions)}. Run it again to check: it should find nothing to do."
        )


@app.command()
def unseed(
    ctx: typer.Context,
    tenant: TenantOption,
    layers: Annotated[
        list[str],
        typer.Option(
            "--layer",
            help=f"A layer of the seed to take out ({', '.join(LAYERS)}). Required; repeat for "
            "more.",
        ),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would be removed; exit 2 if anything.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Don't ask before deleting.")] = False,
    allow_play_tenant: Annotated[
        bool,
        typer.Option("--allow-play-tenant", help="Work on a play tenant, as seed does there."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print the plan and what was removed as JSON. Needs --yes."),
    ] = False,
) -> None:
    """Take a layer of the seed out of a tenant.

    Removes its attachments (the parent a layer adds to a category of another
    layer, which leaves the category itself alone), categories, stat
    definitions and stat groups, and only those the built-in seed names. It
    asks first.

    A category that something outside the layer inherits from stops it, with
    nothing deleted: that includes a category the dnd5e-equipment layer
    attaches, unless you take that layer out in the same call. A stat
    definition that is in use is kept and listed.

    Exit codes: 0 done or nothing to remove, 2 with --dry-run when there is
    something to remove, 1 on a problem, when something was kept, or when you
    said no.
    """
    runtime: Runtime = ctx.obj
    unknown = [layer for layer in layers if layer not in LAYERS]
    if unknown:
        raise typer.BadParameter(f"{', '.join(unknown)}: choose from {', '.join(LAYERS)}")
    chosen = tuple(dict.fromkeys(layers))
    spec = load_builtin()

    def emit(plan: UnseedPlan, result: UnseedResult | None) -> None:
        if as_json:
            document = {
                "plan": unseed_plan_json(plan),
                "result": None if result is None else unseed_result_json(result),
            }
            console.emit(document)

    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        target = resolve_tenant(client, tenant)
        require_repository(target, allow_play=allow_play_tenant)
        plan = make_unseed_plan(
            spec, read_unseed_state(client, target.id, spec, chosen), target, chosen
        )
        if not as_json:
            print_unseed_plan(_out, plan)
        if plan.problems:
            emit(plan, None)
            raise typer.Exit(1)
        if not plan.targets:
            emit(plan, None)
            return
        held = (
            libraries_holding(client, target.id, plan) if target.kind.value == "repository" else {}
        )
        if held and not as_json:
            print_libraries_held(_out, held, len(plan.targets))
        if dry_run:
            emit(plan, None)
            raise typer.Exit(2)
        question = (
            f"Delete {unseed_counts(plan)} of the {' and '.join(chosen)} layer from "
            f"{target.slug}? The stat definitions can't be restored."
        )
        may_write(runtime, yes=yes, question=question)
        result = apply_unseed(client, plan)
    emit(plan, result)
    if not as_json:
        print_unseed_result(_out, result)
    if result.kept:
        raise typer.Exit(1)
