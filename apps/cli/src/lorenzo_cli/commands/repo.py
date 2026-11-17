"""`lorenzo repo`: publish, grant, copy and update repositories (ADR 0159, 0163, 0174, 0386)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, cast
from uuid import UUID

import typer

from lorenzo_cli import console, repo_report, repos, vocabulary_commands
from lorenzo_cli.client.models import (
    PublishRequest,
)
from lorenzo_cli.client.ops import (
    GRANT_REPOSITORY,
    LIST_REPOSITORY_UPDATES,
    PLAN_REPOSITORY_COPY,
    PUBLISH_REPOSITORY,
    REVOKE_REPOSITORY,
    UNPUBLISH_REPOSITORY,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer.tenant_view import resolve_slugs
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _err,
    _out,
    _reporting_errors,
    may_write,
)
from lorenzo_cli.seed import (
    load_builtin,
    read_contents,
)
from lorenzo_cli.self_service import (
    SelfServiceError,
)
from lorenzo_cli.tenants import (
    resolve_tenant,
)

app = typer.Typer(
    help="Publish a repository, grant it, copy it into a tenant, and take its updates.",
    no_args_is_help=True,
)
repo_app = app


class OnCollision(StrEnum):
    merge = "merge"
    skip = "skip"


class Again(StrEnum):
    keep = "keep"
    purge = "purge"


RepositoryTenant = Annotated[
    str,
    typer.Option("--tenant", "-t", envvar="LORENZO_TENANT", help="The repository: its id or slug."),
]
DrawingTenant = Annotated[
    str,
    typer.Option(
        "--tenant",
        "-t",
        envvar="LORENZO_TENANT",
        help="The tenant that draws on the repository, and copies it: its id or slug.",
    ),
]
RepositoryArgument = Annotated[
    str,
    typer.Argument(help="The repository: its id, or its slug among those granted to or copied."),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print the answer as JSON.")]
YesOption = Annotated[bool, typer.Option("--yes", help="Don't ask before writing.")]
OnCollisionOption = Annotated[
    OnCollision | None,
    typer.Option(
        "--on-collision",
        help="Answer every name already in use here that allows it: merge into the local one, or "
        "skip. A slug can only be skipped or renamed.",
    ),
]
ChoicesOption = Annotated[
    Path | None,
    typer.Option(
        "--choices",
        exists=True,
        dir_okay=False,
        help="A JSON file of choices (kind, source_id, action, name), as copy-plan --json lists "
        "the collisions.",
    ),
]


def _may_write(
    runtime: Runtime, *, yes: bool, as_json: bool, prompt: str, default: bool = False
) -> None:
    """The write contract (ADR 0482): `--yes` writes, a terminal is asked, anything else exits 2."""
    del as_json  # the console knows a `--json` run
    may_write(runtime, yes=yes, question=prompt, default=default)


def _echo_json(value: dict[str, object]) -> None:
    console.emit(value)


@repo_app.command("publish")
def repo_publish(
    ctx: typer.Context,
    tenant: RepositoryTenant,
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            help="What to call this release, in your own words (1.3, Spring errata). "
            "Without one it is called by its number.",
        ),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", help="What this release is, for the people who read about it."),
    ] = None,
    breaking: Annotated[
        bool,
        typer.Option(
            "--breaking",
            help="Say that libraries built on this repository should look before they update.",
        ),
    ] = False,
    acknowledge_breaking: Annotated[
        bool,
        typer.Option(
            "--acknowledge-breaking",
            help="Publish although the release removes or changes things libraries already hold, "
            "which is otherwise refused with the list of them.",
        ),
    ] = False,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Publish a repository as a release, or as a new one if it already is.

    Only its owners can. Until the first publish no library it is invited to can see anything of
    it; every release tells each of them what it is called and what its notes say.
    """
    runtime: Runtime = ctx.obj
    said = {
        "label": label,
        "notes": notes,
        "breaking": breaking or None,
        "acknowledge_breaking": acknowledge_breaking or None,
    }
    body = PublishRequest(**{key: value for key, value in said.items() if value is not None})
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="published")
        was_published = repository.published_at is not None
        next_release = "a new release" if was_published else "its first release"
        _may_write(
            runtime,
            yes=yes,
            as_json=as_json,
            prompt=f"Publish {repository.slug} as {next_release}?",
            default=True,
        )
        published = client.call(
            PUBLISH_REPOSITORY,
            path={"tenant_id": repository.id},
            body=body if body.model_fields_set else None,
        ).value
    if as_json:
        console.emit(published.model_dump(mode="json"))
        return
    release = published.release
    flag = " It is marked breaking." if release.breaking else ""
    if release.warning_rows:
        flag += (
            f" It adds {len(release.warning_rows)} parent(s) to items libraries already hold: "
            "each library names them before it takes them."
        )
    if was_published:
        _out.print(
            f"Published release {release.label} of {published.slug}: "
            f"the libraries it is invited to have been told.{flag}"
        )
    else:
        _out.print(
            f"{published.slug} is published as release {release.label}. "
            f"The libraries it is invited to have been told.{flag}"
        )


@repo_app.command("unpublish")
def repo_unpublish(
    ctx: typer.Context,
    tenant: RepositoryTenant,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Back to a draft: nobody it is granted to can browse it, copy it or check its updates.

    What they already copied stays theirs.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="unpublished")
        _may_write(
            runtime,
            yes=yes,
            as_json=as_json,
            prompt=f"Make {repository.slug} a draft again?",
            default=True,
        )
        withdrawn = client.call(UNPUBLISH_REPOSITORY, path={"tenant_id": repository.id}).value
    if as_json:
        console.emit(withdrawn.model_dump(mode="json"))
        return
    _out.print(f"{withdrawn.slug} is a draft again. Copies tenants already made stay theirs.")


@repo_app.command("grant")
def repo_grant(
    ctx: typer.Context,
    subscriber: Annotated[
        str,
        typer.Argument(help="The tenant to give access to: its id, or its slug if it is yours."),
    ],
    tenant: RepositoryTenant,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Give a tenant access to a repository. Only its owners can; the tenant's members are told.

    A tenant that isn't yours can only be named by its id, which its members can give you.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="granted")
        subscriber_id = repos.resolve_subscriber_to_grant(client, subscriber)
        _may_write(
            runtime,
            yes=yes,
            as_json=as_json,
            prompt=f"Grant {repository.slug} to {subscriber}?",
            default=True,
        )
        reply = client.call(
            GRANT_REPOSITORY,
            path={"tenant_id": repository.id, "subscriber_tenant_id": subscriber_id},
        )
    granted = reply.value
    if as_json:
        console.emit(granted.model_dump(mode="json"))
        return
    if reply.status != 201:
        _out.print(f"{granted.slug} already had access to {repository.slug}.")
        return
    _out.print(f"Granted {repository.slug} to {granted.slug}; its members have been told.")
    if repository.published_at is None:
        _out.print(
            f"It isn't published yet, so nothing is visible to them: "
            f"lorenzo repo publish --tenant {repository.slug}"
        )


@repo_app.command("revoke")
def repo_revoke(
    ctx: typer.Context,
    subscriber: Annotated[str, typer.Argument(help="The tenant: its id or slug, as listed.")],
    tenant: RepositoryTenant,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Take a tenant's access back. What it already copied stays its own."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=True) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="revoked")
        held = repos.resolve_subscriber_to_revoke(client, repository.id, subscriber)
        _may_write(
            runtime,
            yes=yes,
            as_json=as_json,
            prompt=f"Take {held.slug}'s access to {repository.slug} back?",
            default=True,
        )
        client.call(
            REVOKE_REPOSITORY,
            path={"tenant_id": repository.id, "subscriber_tenant_id": held.tenant_id},
        )
    if as_json:
        _echo_json({"revoked": held.model_dump(mode="json")})
        return
    _out.print(f"{held.slug} can no longer reach {repository.slug}. What it copied stays its own.")


@repo_app.command("subscribers")
def repo_subscribers(
    ctx: typer.Context, tenant: RepositoryTenant, as_json: JsonOption = False
) -> None:
    """List the tenants a repository is granted to, with each one's id, and say how many copied it
    by themselves from Discover: their names are never shown to a repository."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="granted")
        rows = repos.list_subscribers(client, repository.id)
        public_copies = repos.subscribers_summary(client, repository.id).public_copies
    if as_json:
        _echo_json({"subscribers": [row.model_dump(mode="json") for row in rows]})
        return
    repo_report.print_subscribers(_out, rows, public_copies=public_copies)


@repo_app.command("libraries")
def repo_libraries(
    ctx: typer.Context,
    tenant: RepositoryTenant,
    entry: Annotated[
        str | None, typer.Option("--entry", help="An entry of the repository: its id or link name.")
    ] = None,
    stat: Annotated[
        str | None, typer.Option("--stat", help="A stat of the repository: its id or name.")
    ] = None,
    stat_group: Annotated[
        str | None, typer.Option("--stat-group", help="A stat group: its id or name.")
    ] = None,
    as_json: JsonOption = False,
) -> None:
    """Say how many libraries have copied an entry, a stat or a stat group of a repository.

    What deleting it would mean to them: they see it as removed upstream and keep their copy. A
    number, never which libraries. Nothing here blocks a delete.
    """
    given = [
        (kind, ref)
        for kind, ref in (("entry", entry), ("stat", stat), ("stat-group", stat_group))
        if ref
    ]
    if len(given) != 1:
        _err.print("[red]✗ Name exactly one of --entry, --stat and --stat-group.[/red]")
        raise typer.Exit(2)
    (kind, ref), runtime = given[0], cast(Runtime, ctx.obj)
    with _reporting_errors(), _client(runtime) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="inspected")
        try:
            source_id = UUID(ref)  # an id is passed through: the API checks it is this tenant's
        except ValueError:
            if kind == "entry":
                hits = resolve_slugs(client, repository.id, [ref])
                if ref not in hits:
                    raise SelfServiceError(f"No entry with the link name “{ref}” here.") from None
                source_id = hits[ref].entity_id
            else:
                rows = vocabulary_commands.vocabulary(
                    client, repository.id, groups=kind == "stat-group"
                )
                source_id = vocabulary_commands.resolve(rows, ref, kind)
        count = repos.library_count(client, repository.id, kind, source_id)  # type: ignore[arg-type]
    if as_json:
        _echo_json({"kind": kind, "id": str(source_id), "count": count})
        return
    _out.print(repos.libraries_sentence(count, "this"))


@repo_app.command("contents")
def repo_contents(
    ctx: typer.Context, tenant: RepositoryTenant, as_json: JsonOption = False
) -> None:
    """Show what a repository holds and how much of each seed layer it has.

    Whether it is published and who it is granted to, which repositories it is built on, how many
    stat groups, stat definitions and items it holds, how much of each layer of the seed is in it
    (its categories and the attachments it has), and what the seed doesn't name.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        repository = resolve_tenant(client, tenant)
        repos.require_repository_tenant(repository, what="inspected")
        contents = read_contents(client, repository, load_builtin())
    if as_json:
        _echo_json(repo_report.contents_json(contents))
        return
    repo_report.print_contents(_out, contents)


@repo_app.command("list")
def repo_list(ctx: typer.Context, tenant: DrawingTenant, as_json: JsonOption = False) -> None:
    """List the repositories granted to a tenant or copied by it, and whether any has changed."""
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        drawing = resolve_tenant(client, tenant)
        rows = repos.list_repositories(client, drawing.id)
    if as_json:
        _echo_json({"repositories": [row.model_dump(mode="json") for row in rows]})
        return
    repo_report.print_repositories(_out, rows, drawing.slug)


@repo_app.command("copy-plan")
def repo_copy_plan(
    ctx: typer.Context,
    repository: RepositoryArgument,
    tenant: DrawingTenant,
    as_json: JsonOption = False,
) -> None:
    """Say what copying a repository into a tenant would do, and write nothing.

    Exit codes: 0 the copy could go ahead as it stands, 2 it needs a choice for some names, 1 it
    would be refused (not granted, not published, or already copied).
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime) as client:
        drawing = resolve_tenant(client, tenant)
        repository_id = repos.resolve_repository(client, drawing, repository)
        plan = client.call(
            PLAN_REPOSITORY_COPY, path={"tenant_id": drawing.id, "repository_id": repository_id}
        ).value
    code = repos.copy_plan_exit_code(plan, repository_id)
    if as_json:
        console.emit(plan.model_dump(mode="json"))
        raise typer.Exit(code)
    repo_report.print_copy_plan(_out, plan)
    for blocker in repos.copy_plan_blockers(plan, repository_id):
        _out.print(f"[red]✗ {blocker}[/red]")
    if code == 2:
        _out.print(
            "Give a choice for each with `lorenzo repo copy --choices FILE`, or answer them all "
            "with --on-collision merge|skip."
        )
    raise typer.Exit(code)


@repo_app.command("copy")
def repo_copy(
    ctx: typer.Context,
    repository: RepositoryArgument,
    tenant: DrawingTenant,
    on_collision: OnCollisionOption = None,
    choices: ChoicesOption = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Do every check and say what would be copied.")
    ] = False,
    again: Annotated[
        Again | None,
        typer.Option(
            "--again",
            help="Copy afresh a repository already copied: keep leaves the earlier copy as the "
            "tenant's own rows, purge deletes what it created and what hangs off it.",
        ),
    ] = None,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Copy a repository into a tenant: its content becomes the tenant's own.

    A name already in use here needs a choice (rename, merge or skip) before anything is written;
    one that has none stops it with nothing copied (exit 2). Exit 1 if it is refused.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        explicit = repos.read_choices(choices) if choices else []
        drawing = resolve_tenant(client, tenant)
        repository_id = repos.resolve_repository(client, drawing, repository)
        name = repos.repository_name(client, drawing, repository_id)
        if not dry_run and not yes:
            if not as_json and again is None:
                plan = client.call(
                    PLAN_REPOSITORY_COPY,
                    path={"tenant_id": drawing.id, "repository_id": repository_id},
                ).value
                repo_report.print_copy_plan(_out, plan)
            prompt = f"Copy {name} into {drawing.slug}?"
            if again == Again.purge:
                prompt = (
                    "This deletes what the earlier copy created, and whatever hangs off it in "
                    f"{drawing.slug}. --dry-run shows how much. Copy {name} afresh?"
                )
            _may_write(runtime, yes=yes, as_json=as_json, prompt=prompt)
        outcome = repos.copy_with_choices(
            client,
            drawing.id,
            repository_id,
            explicit=explicit,
            on_collision=on_collision.value if on_collision else None,
            dry_run=dry_run,
            again=again.value if again else None,
        )
    if isinstance(outcome, repos.NeedsChoices):
        if as_json:
            _echo_json({"open_collisions": [c.model_dump(mode="json") for c in outcome.collisions]})
        else:
            _out.print(
                "Nothing was copied: these names are already in use here, and need a choice."
            )
            repo_report.print_collisions(_out, outcome.collisions)
            _out.print("Use --choices FILE, or --on-collision merge|skip.")
        raise typer.Exit(2)
    if as_json:
        console.emit(outcome.model_dump(mode="json"))
        return
    repo_report.print_copy_result(_out, outcome)


@repo_app.command("updates")
def repo_updates(
    ctx: typer.Context,
    repository: RepositoryArgument,
    tenant: DrawingTenant,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Take what needs no decision: changes that don't touch your own edits, "
            "additions that collide with nothing, and the attachments that can be applied.",
        ),
    ] = False,
    actions: Annotated[
        Path | None,
        typer.Option(
            "--actions",
            exists=True,
            dir_okay=False,
            help="A JSON file of the API's own actions (apply with keep_local and take_upstream, "
            "add with a resolution, detach), to decide row by row; or "
            '{"actions": [...], "attachments": [...]} to name attachments to add or detach too.',
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="With --apply or --actions: apply it all, then roll back."),
    ] = False,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Show what a copied repository changed since the copy, row by row; or take it.

    Alone it only shows (exit 0 nothing new, 2 there is something). With --apply or --actions it
    writes, in one transaction. A change to something you also changed is never taken without your
    naming it.
    """
    runtime: Runtime = ctx.obj
    if apply and actions is not None:
        raise typer.BadParameter("--apply and --actions can't be used together.")
    if dry_run and not (apply or actions):
        raise typer.BadParameter("--dry-run is for --apply or --actions.")
    writes = (apply or actions is not None) and not dry_run
    with _reporting_errors(), _client(runtime, writes=writes) as client:
        explicit = repos.read_decisions(actions) if actions else None
        drawing = resolve_tenant(client, tenant)
        repository_id = repos.resolve_repository(client, drawing, repository)
        updates = client.call(
            LIST_REPOSITORY_UPDATES,
            path={"tenant_id": drawing.id, "repository_id": repository_id},
        ).value
        if not (apply or actions):
            if as_json:
                console.emit(updates.model_dump(mode="json"))
            else:
                name = repos.repository_name(client, drawing, repository_id)
                repo_report.print_updates(_out, name, updates)
                if repos.updates_waiting(updates):
                    _out.print(
                        f"`lorenzo repo updates {repository} --tenant {drawing.slug} --apply` "
                        "takes what needs no decision."
                    )
            raise typer.Exit(2 if repos.updates_waiting(updates) else 0)
        chosen = repos.clean_updates(updates)
        wanted = explicit if explicit is not None else repos.Decisions(chosen.actions, [])
        if not wanted.count:
            result = None
        else:
            if not dry_run and not yes:
                if not as_json:
                    name = repos.repository_name(client, drawing, repository_id)
                    repo_report.print_updates(_out, name, updates)
                _may_write(
                    runtime,
                    yes=yes,
                    as_json=as_json,
                    prompt=f"Take {wanted.count} update(s) into {drawing.slug}?",
                )
            result = repos.apply_updates(
                client,
                drawing.id,
                repository_id,
                wanted.actions,
                dry_run=dry_run,
                attachments=wanted.attachments,
            )
    left = chosen.left and explicit is None
    if as_json:
        _echo_json(
            {
                "result": result.model_dump(mode="json") if result else None,
                "left": {
                    "conflicts": [
                        {"kind": r.kind.value, "source_id": str(r.source_id), "name": r.name}
                        for r in chosen.conflicts
                    ],
                    "collisions": [
                        {"kind": a.kind.value, "source_id": str(a.source_id), "name": a.name}
                        for a in chosen.collisions
                    ],
                    "breaking": [
                        {"kind": r.kind.value, "source_id": str(r.source_id), "name": r.name}
                        for r in chosen.breaking
                    ],
                    "edited_since_the_release": [
                        {"kind": r.kind.value, "source_id": str(r.source_id), "name": r.name}
                        for r in chosen.edited
                    ],
                    "removed": chosen.removed,
                    "attachments_waiting": [
                        {
                            "child_source_id": str(a.child_source_id),
                            "parent_source_id": str(a.parent_source_id),
                            "reason": a.reason or repo_report.ATTACHMENT_REASON,
                        }
                        for a in chosen.attachments_waiting
                    ],
                    "attachments_removed": chosen.attachments_removed,
                }
                if explicit is None
                else None,
            }
        )
    else:
        if result is None:
            _out.print("Nothing to take that needs no decision.")
        else:
            repo_report.print_applied(_out, result)
        if explicit is None:
            repo_report.print_left_for_a_decision(_out, chosen)
    raise typer.Exit(2 if left else 0)


@repo_app.command("offer")
def repo_offer(
    ctx: typer.Context,
    subscriber: Annotated[
        str,
        typer.Argument(help="The tenant to offer it to: its id, or its slug if it is yours."),
    ],
    tenant: RepositoryTenant,
    on_collision: OnCollisionOption = None,
    choices: ChoicesOption = None,
    apply_updates: Annotated[
        bool,
        typer.Option(
            "--apply-updates",
            help="If the tenant already has a copy, take the updates that need no decision.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Write nothing, the grant included; say what would be done."
        ),
    ] = False,
    yes: YesOption = False,
    as_json: JsonOption = False,
) -> None:
    """Offer a repository to a tenant: grant it, then copy it in. Safe to run again.

    For whoever owns the repository and belongs to the tenant. It refuses a repository that isn't
    published, grants (an existing grant is fine), and copies; a tenant that already has a copy is
    a success. Exit 2 if names need a choice, or with --dry-run if there is something to do.
    """
    runtime: Runtime = ctx.obj
    with _reporting_errors(), _client(runtime, writes=not dry_run) as client:
        explicit = repos.read_choices(choices) if choices else []
        repository = resolve_tenant(client, tenant)
        receiving = resolve_tenant(client, subscriber)
        state = repos.read_offer_state(client, repository, receiving)
        if dry_run:
            _offer_dry_run(client, state, apply_updates=apply_updates, as_json=as_json)
            return
        if not as_json:
            repo_report.print_offer_state(_out, state)
        if state.steps or apply_updates:
            _may_write(
                runtime,
                yes=yes,
                as_json=as_json,
                prompt=f"Offer {repository.slug} to {receiving.slug}?",
            )
        result = repos.perform_offer(
            client,
            state,
            explicit=explicit,
            on_collision=on_collision.value if on_collision else None,
            apply_clean_updates=apply_updates,
        )
    if as_json:
        _echo_json(
            {
                "repository": repository.slug,
                "subscriber": receiving.slug,
                "granted": result.granted if not state.granted else "existing",
                "dependencies": result.dependencies,
                "copied": result.copied,
                "copy": result.copy.model_dump(mode="json") if result.copy else None,
                "updates": {
                    "applied": (
                        result.updates_applied.model_dump(mode="json")
                        if result.updates_applied
                        else None
                    ),
                    "waiting": result.updates_waiting,
                },
                "open_collisions": [c.model_dump(mode="json") for c in result.needs_choices],
            }
        )
    else:
        repo_report.print_offer_result(_out, state, result)
    raise typer.Exit(2 if result.needs_choices else 0)


def _offer_dry_run(
    client: LorenzoClient, state: repos.OfferState, *, apply_updates: bool, as_json: bool
) -> None:
    """What an offer would do, read without writing, grant included (ADR 0160)."""
    plan = None
    updates = None
    if state.granted and not state.copied:
        plan = client.call(
            PLAN_REPOSITORY_COPY,
            path={"tenant_id": state.subscriber.id, "repository_id": state.repository.id},
        ).value
    if state.copied and apply_updates:
        updates = client.call(
            LIST_REPOSITORY_UPDATES,
            path={"tenant_id": state.subscriber.id, "repository_id": state.repository.id},
        ).value
    takes = repos.clean_updates(updates).takes if updates is not None else 0
    something = bool(state.steps or takes)
    if as_json:
        _echo_json(
            {
                "dry_run": True,
                "steps": state.steps,
                "dependencies": {
                    d.repository.slug: (
                        "copied"
                        if d.copied
                        else "granted"
                        if d.granted
                        else "unknown"
                        if d.granted is None
                        else "needs-grant"
                    )
                    for d in state.dependencies
                },
                "granted": state.granted,
                "copied": state.copied,
                "collisions": [c.model_dump(mode="json") for c in plan.collisions] if plan else [],
                "clean_updates": takes,
            }
        )
    else:
        repo_report.print_offer_state(_out, state)
        if plan is not None:
            repo_report.print_copy_plan(_out, plan)
        elif not state.granted:
            _out.print("  (The copy can only be planned once the tenant is granted it.)")
        if updates is not None:
            _out.print(f"  updates: {takes} take(s) need no decision.")
        _out.print("Dry run: nothing was written." if something else "Nothing to do.")
    raise typer.Exit(2 if something else 0)
