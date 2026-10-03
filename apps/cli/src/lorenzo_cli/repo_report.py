"""Showing repositories, copies and updates (`lorenzo repo`, ADR 0159 and 0160)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from rich.console import Console
from rich.table import Table

from lorenzo_cli.client.models import (
    ApplyUpdatesOut,
    CollisionOut,
    CopyOut,
    CopyPlanOut,
    CopyStepOut,
    SubscriberOut,
    SubscriptionOut,
    UpdatesOut,
)
from lorenzo_cli.repos import CleanUpdates, OfferResult, OfferState, has_published_since


def when(value: datetime | None) -> str:
    return "-" if value is None else value.strftime("%Y-%m-%d")


def print_repositories(console: Console, rows: Sequence[SubscriptionOut], tenant: str) -> None:
    if not rows:
        console.print(f"No repository is granted to “{tenant}” or copied by it yet.")
        return
    table = Table(box=None, pad_edge=False)
    for heading in ("repository", "name", "published", "granted", "copied", ""):
        table.add_column(heading, no_wrap=heading != "name")
    for row in rows:
        repository = row.repository
        table.add_row(
            repository.slug or "(deleted)",
            repository.name,
            "yes" if repository.published_at else "no",
            when(row.granted_at),
            when(row.copied_at),
            "[yellow]updated since[/yellow]" if has_published_since(row) else "",
        )
    console.print(table)


def print_subscribers(console: Console, rows: Sequence[SubscriberOut]) -> None:
    if not rows:
        console.print("This repository isn't granted to any tenant yet.")
        return
    table = Table(box=None, pad_edge=False)
    for heading in ("slug", "name", "granted", "id"):
        table.add_column(heading)
    for row in rows:
        table.add_row(row.slug, row.name, when(row.granted_at), str(row.tenant_id))
    console.print(table)


def print_collisions(console: Console, collisions: Sequence[CollisionOut]) -> None:
    for collision in collisions:
        choices = ", ".join(c.value for c in collision.choices)
        taken = f" (taken here by {collision.local_id})" if collision.local_id else " (taken here)"
        console.print(
            f"  {collision.kind.value} “{collision.name}”{taken}: choose {choices}. "
            f"Source id {collision.source_id}",
            highlight=False,
        )


def _step_line(step: CopyStepOut, *, verb: str | None = None) -> str:
    counts = (
        f"{step.entities} entities, {step.stat_groups} stat groups, "
        f"{step.stat_definitions} stat definitions, {step.information} pieces of information"
    )
    if verb is not None:
        return f"{verb} {step.name}: {counts}."
    flags = [
        "granted" if step.granted else "[red]not granted[/red]",
        "published" if step.published else "[red]not published[/red]",
    ]
    if step.already_copied:
        flags.append("already copied")
    return f"{step.name}: {counts} ({', '.join(flags)})."


def print_copy_plan(console: Console, plan: CopyPlanOut) -> None:
    for step in plan.steps:
        console.print(_step_line(step), highlight=False)
        for dropped in step.dropped:
            console.print(
                f"  leaves out {dropped.kind} {dropped.source_id}: {dropped.reason}",
                highlight=False,
            )
    if plan.collisions:
        console.print("These names are already in use here, and each needs a choice:")
        print_collisions(console, plan.collisions)


def print_copy_result(console: Console, out: CopyOut) -> None:
    verb = "Would copy" if out.dry_run else "Copied"
    for step in out.steps:
        console.print(_step_line(step, verb=verb), highlight=False)
        for dropped in step.dropped:
            console.print(
                f"  left out {dropped.kind} {dropped.source_id}: {dropped.reason}",
                highlight=False,
            )
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
                f"[yellow]Also removed with them, being attached to them: {extra}.[/yellow]"
            )


def print_updates(console: Console, name: str, updates: UpdatesOut) -> None:
    waiting = bool(updates.changed or updates.added or updates.removed)
    if not waiting:
        console.print(f"{name}: nothing new since this tenant copied or last synced it.")
    else:
        console.print(f"{name} has changed since this tenant copied or last synced it:")
    for row in updates.changed:
        console.print(f"  changed {row.kind.value} “{row.name}”", highlight=False)
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
        console.print(f"  added {added.kind.value} “{added.name}”{note}", highlight=False)
    for removed in updates.removed:
        console.print(f"  gone upstream: {removed.kind.value} “{removed.name}”", highlight=False)
    if updates.deleted_locally:
        console.print(f"  {len(updates.deleted_locally)} you deleted here (nothing to do).")


def print_left_for_a_decision(console: Console, chosen: CleanUpdates) -> None:
    if not chosen.left:
        return
    console.print("Left for a decision (name it in a file for --actions):")
    for row in chosen.conflicts:
        fields = ", ".join(f.label or f.field for f in row.fields if f.state.value == "conflict")
        console.print(
            f"  {row.kind.value} “{row.name}” conflicts with your own edit of {fields}",
            highlight=False,
        )
    for added in chosen.collisions:
        console.print(
            f"  {added.kind.value} “{added.name}” would collide with a name already here",
            highlight=False,
        )
    if chosen.removed:
        console.print(f"  {chosen.removed} gone upstream (detach is a decision)")


def print_applied(console: Console, out: ApplyUpdatesOut) -> None:
    verb = "Would take" if out.dry_run else "Took"
    console.print(f"{verb} {out.applied} changed, {out.added} added, {out.detached} detached.")
    for item in out.not_applied:
        console.print(
            f"[yellow]Couldn't apply {item.field} of {item.kind} {item.source_id}: "
            f"{item.reason}. It stays on offer.[/yellow]",
            highlight=False,
        )


def print_offer_state(console: Console, state: OfferState) -> None:
    repo, tenant = state.repository.slug, state.subscriber.slug
    console.print(f"Offering [bold]{repo}[/bold] to [bold]{tenant}[/bold]:")
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
