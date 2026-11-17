"""Showing repositories, copies and updates (`lorenzo repo`, ADR 0159 and 0160)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table

from lorenzo_cli.client.models import (
    ApplyUpdatesOut,
    CollisionOut,
    CopyOut,
    CopyPlanOut,
    CopyStepOut,
    CopyWarningOut,
    DroppedOut,
    ScaleOut,
    SubscriberOut,
    SubscriptionOut,
    UpdatesOut,
)
from lorenzo_cli.repo_contents import Contents
from lorenzo_cli.repos import (
    CleanUpdates,
    OfferResult,
    OfferState,
    has_published_since,
    updates_waiting,
)


def when(value: datetime | None) -> str:
    return "-" if value is None else value.strftime("%Y-%m-%d")


def _release_taken(row: SubscriptionOut) -> str:
    """The release a copy last took, and the repository's latest if it has moved on."""
    if row.synced_release is None:
        return "-"
    if row.current_release and row.current_release.id != row.synced_release.id:
        return f"{row.synced_release.label} ({row.current_release.label} is out)"
    return row.synced_release.label


def print_repositories(console: Console, rows: Sequence[SubscriptionOut], tenant: str) -> None:
    if not rows:
        console.print(f"No repository is granted to “{tenant}” or copied by it yet.")
        return
    table = Table(box=None, pad_edge=False)
    for heading in ("repository", "name", "published", "granted", "copied", "release", ""):
        table.add_column(heading, no_wrap=heading != "name")
    for row in rows:
        repository = row.repository
        table.add_row(
            repository.slug or "(deleted)",
            repository.name,
            "yes" if repository.published_at else "no",
            when(row.granted_at),
            when(row.copied_at),
            _release_taken(row),
            "[yellow]updated since[/yellow]" if has_published_since(row) else "",
        )
    console.print(table)


def print_subscribers(
    console: Console, rows: Sequence[SubscriberOut], *, public_copies: int = 0
) -> None:
    if not rows and not public_copies:
        console.print("This repository isn't granted to any tenant yet, and nobody has copied it.")
        return
    if not rows:
        _say_public_copies(console, public_copies)
        return
    table = Table(box=None, pad_edge=False)
    for heading in ("slug", "name", "granted", "copied", "release", "id"):
        table.add_column(heading, no_wrap=heading != "name")
    for row in rows:
        # A copy that outlived its invitation has no grant date (ADR 0204).
        table.add_row(
            row.slug,
            row.name,
            when(row.granted_at) if row.granted_at else "no longer",
            when(row.copied_at),
            row.synced_release.label if row.synced_release else "-",
            str(row.tenant_id),
        )
    console.print(table)
    if public_copies:
        _say_public_copies(console, public_copies)


def _say_public_copies(console: Console, count: int) -> None:
    """Libraries that copied a public repository by themselves are a number, never names."""
    libraries = "1 library" if count == 1 else f"{count} libraries"
    console.print(
        f"{libraries} copied it by {'itself' if count == 1 else 'themselves'} from Discover. "
        "Their names are not shown."
    )


def print_collisions(console: Console, collisions: Sequence[CollisionOut]) -> None:
    for collision in collisions:
        choices = ", ".join(c.value for c in collision.choices)
        taken = f" (taken here by {collision.local_id})" if collision.local_id else " (taken here)"
        console.print(
            f"  {_kind(collision.kind)} “{collision.name}”{taken}: choose {choices}. "
            f"Source id {collision.source_id}",
            highlight=False,
        )


def _step_line(step: CopyStepOut, *, verb: str | None = None) -> str:
    counts = (
        f"{step.entities} entities, {step.stat_groups} stat groups, "
        f"{step.stat_definitions} stat definitions, {step.information} pieces of information"
    )
    for count, one, many in (
        (step.systems or 0, "system", "systems"),
        (step.templates or 0, "template", "templates"),
    ):
        if count:
            # Said only when there are, like attachments (ADR 0492).
            counts += f", {count} {one if count == 1 else many}"
    if step.attachments:
        # The parents it adds to items copied from elsewhere (ADR 0172): said only when there are.
        counts += f", {step.attachments} attachment{'' if step.attachments == 1 else 's'}"
    if verb is not None:
        return f"{verb} {step.name}: {counts}."
    flags = [
        "granted" if step.granted else "[red]not granted[/red]",
        "published" if step.published else "[red]not published[/red]",
    ]
    if step.already_copied:
        flags.append("already copied")
    return f"{step.name}: {counts} ({', '.join(flags)})."


def _kind(kind: Any) -> str:
    """A row's kind in words: `stat_role` is a role, `grant_rule` a grant rule."""
    value = str(getattr(kind, "value", kind))
    return {"stat_role": "role", "stat_definition": "stat"}.get(value, value.replace("_", " "))


def print_dropped(console: Console, dropped: Sequence[DroppedOut], *, verb: str) -> None:
    """What a step leaves out, counted by kind and reason (ADR 0492); `--json` has every id."""
    counted = Counter((_kind(row.kind), row.reason) for row in dropped)
    for (kind, reason), count in sorted(counted.items()):
        console.print(f"  {verb} {count} × {kind}: {reason}", highlight=False)


def _scale(scale: ScaleOut) -> str:
    unit = f"in {scale.unit}" if scale.unit else "with no unit"
    if scale.min_value is None and scale.max_value is None:
        return unit
    low = "…" if scale.min_value is None else f"{scale.min_value:g}"
    high = "…" if scale.max_value is None else f"{scale.max_value:g}"
    return f"{unit}, {low} to {high}"


def print_warnings(console: Console, warnings: Sequence[CopyWarningOut] | None) -> None:
    """A stat merged into one here whose unit or bounds differ: the library's own is kept."""
    for warning in warnings or []:
        console.print(
            f"[yellow]⚠ `{warning.name}`: here {_scale(warning.library)}, incoming "
            f"{_scale(warning.incoming)}; merged, yours kept[/yellow] (--strict-units makes it "
            "a name to answer)",
            highlight=False,
        )


def print_copy_plan(console: Console, plan: CopyPlanOut) -> None:
    for step in plan.steps:
        console.print(_step_line(step), highlight=False)
        print_dropped(console, step.dropped, verb="leaves out")
    print_warnings(console, plan.warnings)
    if plan.collisions:
        console.print("These names are already in use here, and each needs a choice:")
        print_collisions(console, plan.collisions)


def print_copy_result(console: Console, out: CopyOut) -> None:
    verb = "Would copy" if out.dry_run else "Copied"
    for step in out.steps:
        console.print(_step_line(step, verb=verb), highlight=False)
        print_dropped(console, step.dropped, verb="left out")
    print_warnings(console, out.warnings)
    if out.previous is not None:
        previous = out.previous
        kept = "kept as the tenant's own rows" if previous.mode.value == "keep" else "removed"
        console.print(
            f"The earlier copy: {previous.entities} entities, {previous.stat_groups} stat groups "
            f"and {previous.stat_definitions} stat definitions {kept}.",
            highlight=False,
        )
        if previous.also_removed:
            extra = ", ".join(f"{n} {kind}" for kind, n in sorted(previous.also_removed.items()))
            console.print(
                f"[yellow]⚠ Also removed with them, being attached to them: {extra}.[/yellow]"
            )


# Said of an attachment that can be taken: it is never taken with the rest (ADR 0208).
ATTACHMENT_REASON = (
    "it changes an item you already hold, so it is named in a file, not taken with the rest"
)


def _marks(row: Any, updates: UpdatesOut) -> str:
    """What the repository says of a row beside its name: edited since its latest release, and
    called breaking by a release since this tenant last updated, or, of an attachment, said to
    change what the item is (ADR 0208)."""
    said: list[str] = []
    if row.state is not None and row.state.value == "edited":
        release = f" {updates.release.label}" if updates.release else ""
        said.append(f"edited since release{release}")
    if row.breaking:
        said.append(f"breaking, release {row.breaking[0].release.label}")
    warnings = getattr(row, "warnings", None)
    if warnings:
        said.append(f"changes what the item is, release {warnings[0].release.label}")
    return f" ({'; '.join(said)})" if said else ""


def print_updates(console: Console, name: str, updates: UpdatesOut) -> None:
    if not updates_waiting(updates):
        console.print(f"{name}: nothing new since this tenant copied or last synced it.")
    else:
        console.print(f"{name} has changed since this tenant copied or last synced it:")
    for row in updates.changed:
        console.print(
            f"  changed {_kind(row.kind)} “{row.name}”{_marks(row, updates)}", highlight=False
        )
        for field in row.fields:
            detail = field.state.value.replace("_", " ")
            if field.added or field.removed:
                detail += f" (+{len(field.added or [])} −{len(field.removed or [])})"
            console.print(f"    {field.label or field.field}: {detail}", highlight=False)
    for added in updates.added:
        note = (
            f", but “{added.collision.name}” is already in use here"
            if added.collision is not None
            else ""
        )
        console.print(
            f"  added {_kind(added.kind)} “{added.name}”{note}{_marks(added, updates)}",
            highlight=False,
        )
    for removed in updates.removed:
        console.print(
            f"  gone upstream: {_kind(removed.kind)} “{removed.name}”{_marks(removed, updates)}",
            highlight=False,
        )
    for attachment in updates.attachments_added:
        note = f", but it waits: {attachment.reason}" if not attachment.applicable else ""
        console.print(
            f"  added attachment “{attachment.parent_name}” on “{attachment.child_name}”{note}"
            f"{_marks(attachment, updates)}",
            highlight=False,
        )
    for gone in updates.attachments_removed:
        console.print(
            f"  gone upstream: attachment “{gone.parent_name}” on “{gone.child_name}”",
            highlight=False,
        )
    if updates.deleted_locally:
        console.print(f"  {len(updates.deleted_locally)} you deleted here (nothing to do).")
    if updates.attachments_deleted_locally:
        console.print(
            f"  {len(updates.attachments_deleted_locally)} attachment(s) you removed here "
            "(nothing to do)."
        )


def print_left_for_a_decision(console: Console, chosen: CleanUpdates) -> None:
    if not chosen.left:
        return
    console.print("Left for a decision (name it in a file for --actions):")
    for row in chosen.conflicts:
        fields = ", ".join(f.label or f.field for f in row.fields if f.state.value == "conflict")
        console.print(
            f"  {_kind(row.kind)} “{row.name}” conflicts with your own edit of {fields}",
            highlight=False,
        )
    for added in chosen.collisions:
        console.print(
            f"  {_kind(added.kind)} “{added.name}” would collide with a name already here",
            highlight=False,
        )
    for row in chosen.breaking:
        notes = "; ".join(f"{n.detail} (release {n.release.label})" for n in row.breaking)
        console.print(
            f"  {_kind(row.kind)} “{row.name}” is marked breaking: {notes}. "
            'Name it in a file with "confirm": true to take it',
            highlight=False,
        )
    for edited in chosen.edited:
        console.print(
            f"  {_kind(edited.kind)} “{edited.name}” was edited after the release, "
            "so it is not taken with the rest",
            highlight=False,
        )
    if chosen.removed:
        console.print(f"  {chosen.removed} gone upstream (detach is a decision)")
    for attachment in chosen.attachments_waiting:
        console.print(
            f"  attachment “{attachment.parent_name}” on “{attachment.child_name}” "
            f"waits: {attachment.reason or ATTACHMENT_REASON}",
            highlight=False,
        )
    if chosen.attachments_removed:
        console.print(
            f"  {chosen.attachments_removed} attachment(s) gone upstream (detach is a decision)"
        )


def print_applied(console: Console, out: ApplyUpdatesOut) -> None:
    verb = "Would take" if out.dry_run else "Took"
    console.print(f"{verb} {out.applied} changed, {out.added} added, {out.detached} detached.")
    if out.attachments_added or out.attachments_detached:
        console.print(
            f"Attachments: {out.attachments_added} added, {out.attachments_detached} detached."
        )
    for item in out.not_applied:
        what = (
            f"an attachment on {item.source_id}"
            if item.kind == "attachment"
            else f"{item.field} of {_kind(item.kind)} {item.source_id}"
        )
        console.print(
            f"[yellow]⚠ Couldn't apply {what}: {item.reason}. It stays on offer.[/yellow]",
            highlight=False,
        )


def print_offer_state(console: Console, state: OfferState) -> None:
    repo, tenant = state.repository.slug, state.subscriber.slug
    console.print(f"Offering [bold]{repo}[/bold] to [bold]{tenant}[/bold]:")
    for dependency in state.dependencies:
        if dependency.copied:
            how = "already copied there"
        elif dependency.granted:
            how = "already granted"
        elif dependency.granted is None:
            how = "to be granted, by you if you own it"
        else:
            how = "to be granted (its members are told)"
        console.print(f"  grant {dependency.repository.slug}, which {repo} builds on: {how}")
    console.print(
        f"  grant: {'already granted' if state.granted else 'to be granted (its members are told)'}"
    )
    if state.copied:
        since = "; it has published since" if state.published_since else ""
        console.print(f"  copy: already copied{since}")
    else:
        console.print("  copy: to be copied into it")


def print_offer_result(console: Console, state: OfferState, result: OfferResult) -> None:
    repo, tenant = state.repository.slug, state.subscriber.slug
    for slug, how in result.dependencies.items():
        if how == "new":
            console.print(
                f"Granted {slug} to {tenant}, which {repo} builds on; its members have been told."
            )
    console.print(
        f"Granted {repo} to {tenant}; its members have been told."
        if result.granted == "new"
        else f"{tenant} already had access to {repo}."
    )
    if result.needs_choices:
        console.print(
            "Not copied yet: these names are already in use there, and each needs a choice "
            "(the grant stays, and running offer again picks up from here):"
        )
        print_collisions(console, result.needs_choices)
        return
    if result.copy is not None:
        print_copy_result(console, result.copy)
    else:
        console.print(f"{tenant} already has a copy of {repo}.")
    if result.updates_applied is not None:
        print_applied(console, result.updates_applied)
    if result.updates_waiting:
        console.print(
            f"{result.updates_waiting} update(s) wait for a decision: "
            f"lorenzo repo updates {repo} --tenant {tenant}"
        )


def contents_json(contents: Contents) -> dict[str, object]:
    """What a repository holds as plain data for `--json`."""
    tenant = contents.tenant
    return {
        "tenant": {
            "id": str(tenant.id),
            "slug": tenant.slug,
            "name": tenant.name,
            "kind": tenant.kind.value,
            "published_at": tenant.published_at.isoformat() if tenant.published_at else None,
        },
        "granted_to": contents.granted_to,
        "built_on": [
            {
                "slug": row.repository.slug,
                "name": row.repository.name,
                "copied_at": row.copied_at.isoformat() if row.copied_at else None,
                "updated_since": has_published_since(row),
            }
            for row in contents.built_on
        ],
        "systems": [{"slug": s.slug, "name": s.name, "root": s.root} for s in contents.systems],
        "templates": [
            {
                "name": t.name,
                "system": t.system,
                "kind": t.required_kind.value if t.required_kind else None,
            }
            for t in contents.templates
        ],
        "roles": [
            {"role": r.role, "holder": r.holder, "name": r.name, "system": r.system}
            for r in contents.roles
        ],
        "by_system": {
            system: {
                "stat_groups": contents.stat_groups_by_system.get(system, 0),
                "stat_definitions": contents.stat_definitions_by_system.get(system, 0),
            }
            for system in _systems_counted(contents)
        },
        "holds": {
            "systems": len(contents.systems),
            "templates": len(contents.templates),
            "stat_groups": contents.stat_groups,
            "stat_definitions": contents.stat_definitions,
            "entries": contents.entries,
            "items": contents.items,
            "features": contents.features,
            "grant_rules": contents.grant_rules,
            "attachments": contents.attachments,
        },
    }


def _systems_counted(contents: Contents) -> list[str]:
    return sorted(set(contents.stat_groups_by_system) | set(contents.stat_definitions_by_system))


def print_contents(console: Console, contents: Contents) -> None:
    tenant = contents.tenant
    state = f"published {when(tenant.published_at)}" if tenant.published_at else "a draft"
    console.print(
        f"[bold]{tenant.slug}[/bold] ({tenant.name}) is a repository, {state}, granted to "
        f"{contents.granted_to} tenant(s).",
        highlight=False,
    )
    if contents.built_on:
        for row in contents.built_on:
            changed = (
                " [yellow]and has published since[/yellow]" if has_published_since(row) else ""
            )
            console.print(
                f"Built on {row.repository.slug or '(deleted)'}, copied {when(row.copied_at)}"
                f"{changed}.",
                highlight=False,
            )
    else:
        console.print("Built on nothing: it has copied no repository.")
    for held in contents.systems:
        root = f", root {held.root}" if held.root else ", no root"
        console.print(f"System {held.slug} ({held.name}){root}.", highlight=False)
    for system in _systems_counted(contents):
        console.print(
            f"  {system}: {contents.stat_groups_by_system.get(system, 0)} stat groups, "
            f"{contents.stat_definitions_by_system.get(system, 0)} stats",
            highlight=False,
        )
    if contents.roles:
        said = ", ".join(
            f"{r.role} ({r.name}{'' if r.system == 'neutral' else ', ' + r.system})"
            for r in contents.roles
        )
        console.print(f"Roles: {said}.", highlight=False)
    if contents.templates:
        said = ", ".join(f"{t.name} ({t.system or 'no system'})" for t in contents.templates)
        console.print(f"Templates: {said}.", highlight=False)
    console.print(
        f"Holds {contents.entries} entries, {contents.items} of them items (categories "
        f"included) and {contents.features} features, and {contents.grant_rules} grant rules.",
        highlight=False,
    )
    if contents.attachments:
        console.print(
            f"Attaches {contents.attachments} parent(s) to items it copied, which a tenant copying "
            "it takes along.",
            highlight=False,
        )
