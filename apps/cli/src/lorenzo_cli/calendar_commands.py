"""Reviewed native calendar imports over the atomic API (ADR 0311)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
from lorenzo_calendar import CalendarDefinition, Periodic, RecurrenceRule
from lorenzo_calendar.document import Annotation, CalendarDocument, parse_document
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lorenzo_cli.client import ops
from lorenzo_cli.client.models import CalendarImportApply, CalendarImportPlan, CalendarImportRequest
from lorenzo_cli.self_service import SelfServiceError
from lorenzo_cli.terminal_script import safe
from lorenzo_cli.vocabulary_commands import Json, Tenant, session

app = typer.Typer(help="Import and export authored calendar documents.", no_args_is_help=True)


class Choices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    annotations: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=1000)
    definition: CalendarDefinition | None = None
    accepted_warnings: list[str] = Field(default_factory=list, max_length=100)
    resolutions: dict[str, Literal["keep_local", "take_source"]] = Field(
        default_factory=dict, max_length=1001
    )
    is_public: bool | None = None
    period_is_public: bool | None = None


def read_file(file: Path, limit: int = 2_000_000) -> str:
    if file.stat().st_size > limit:
        raise ValueError("The calendar file is too large")
    return file.read_text(encoding="utf-8-sig")


def choose(document: CalendarDocument, choices: Choices) -> CalendarDocument:
    unknown = set(choices.annotations) - {a.key for a in document.annotations}
    if unknown:
        raise ValueError(
            "The choices file names unknown annotation keys: " + ", ".join(sorted(unknown))
        )
    values = document.model_dump(mode="json")
    values["annotations"] = [
        {**a.model_dump(mode="json"), **choices.annotations.get(a.key, {})}
        for a in document.annotations
    ]
    if choices.definition is not None:
        values["definition"] = choices.definition.model_dump(mode="json")
    for key in ["is_public", "period_is_public"]:
        if getattr(choices, key) is not None:
            values[key] = getattr(choices, key)
    return CalendarDocument.model_validate(values)


def review(document: CalendarDocument) -> CalendarDocument:
    annotations = []
    groups: dict[str, str] = {}
    for annotation in document.annotations:
        typer.echo(
            safe(
                f"{annotation.key}: {annotation.date.year} / {annotation.date.segment} / "
                f"{annotation.date.day}\n{annotation.text}"
            )
        )
        kind = typer.prompt("Kind [note/fact/event/observance]", default=annotation.classification)
        if kind not in {"note", "fact", "event", "observance"}:
            raise ValueError("Choose note, fact, event or observance")
        values = annotation.model_dump(mode="json")
        values.update(classification=kind, group=None, recurrence=None)
        if kind != "note":
            values["title"] = typer.prompt(
                "Entry name",
                default=annotation.title or annotation.text.strip().splitlines()[0][:200],
            )
        if kind == "event":
            group = typer.prompt(
                "Event group key (empty for a separate Event)", default="", show_default=False
            )
            if group:
                values["group"] = group
                values["title"] = groups.setdefault(group, values["title"])
        if kind == "observance":
            every = typer.prompt("Every N years", default=1, type=int)
            offset = typer.prompt("Year offset", default=0, type=int)
            values["recurrence"] = RecurrenceRule(
                segment=annotation.date.segment,
                day=annotation.date.day,
                when=Periodic(every=every, offset=offset),
            ).model_dump(mode="json")
        annotations.append(Annotation.model_validate(values))
    return CalendarDocument.model_validate(
        {
            **document.model_dump(mode="json"),
            "annotations": [a.model_dump(mode="json") for a in annotations],
        }
    )


def describe(plan: CalendarImportPlan) -> None:
    typer.echo(f"Calendar import: {safe(plan.source_key)}", err=True)
    for change in plan.changes:
        text = f"  {change.action}: {change.key}"
        if change.resolution:
            text += f" ({change.resolution})"
        if change.reason:
            text += f" — {change.reason}"
        typer.echo(safe(text), err=True)
    for warning in plan.unaccepted_warnings:
        typer.echo(f"  Review warning: {safe(warning)}", err=True)


@app.command("import")
def calendar_import(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    tenant: Tenant,
    choices_file: Annotated[
        Path | None, typer.Option("--choices", exists=True, dir_okay=False)
    ] = None,
    review_notes: Annotated[
        bool, typer.Option(help="Choose a classification for each source note")
    ] = False,
    accept_warnings: Annotated[
        bool, typer.Option(help="Acknowledge the warnings printed from this document")
    ] = False,
    dry_run: bool = False,
    plan_out: Annotated[
        Path | None, typer.Option(help="Save the exact request and reviewed plan")
    ] = None,
    apply_plan: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="Apply this saved plan only if file and choices still match",
        ),
    ] = None,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Apply a ready plan without a prompt")
    ] = False,
    as_json: Json = False,
) -> None:
    from lorenzo_cli.main import _reporting_errors

    with _reporting_errors():
        try:
            document = parse_document(read_file(file))
            choices = (
                Choices.model_validate_json(read_file(choices_file)) if choices_file else Choices()
            )
            document = choose(document, choices)
            if review_notes:
                if not ctx.obj.interactive:
                    raise ValueError("Interactive note review needs a terminal; use a choices file")
                document = review(document)
            for warning in document.warnings:
                typer.echo(safe(f"warning [{warning.key}]: {warning.message}"), err=True)
            accepted = sorted(
                {*choices.accepted_warnings, *(w.key for w in document.warnings if accept_warnings)}
            )
            request = CalendarImportRequest.model_validate(
                {
                    "document": document.model_dump(mode="json"),
                    "accepted_warnings": accepted,
                    "resolutions": choices.resolutions,
                }
            )
            saved = json.loads(read_file(apply_plan, 3_000_000)) if apply_plan else None
            if saved and saved.get("request") != request.model_dump(mode="json"):
                raise ValueError("The file or choices differ from the saved plan; plan them again")
        except (OSError, ValueError, ValidationError) as error:
            raise SelfServiceError(str(error)) from error
        with session(ctx, tenant, writes=not dry_run) as (client, tid):
            if saved:
                planned = CalendarImportPlan.model_validate(saved["plan"])
            else:
                planned = client.call(
                    ops.PLAN_CALENDAR_IMPORT, path={"tenant_id": tid}, body=request
                ).value
            describe(planned)
            if plan_out:
                plan_out.write_text(
                    json.dumps(
                        {
                            "request": request.model_dump(mode="json"),
                            "plan": planned.model_dump(mode="json"),
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            if dry_run:
                if as_json:
                    typer.echo(planned.model_dump_json(indent=2))
                return
            if not planned.ready:
                raise SelfServiceError(
                    "The plan needs warning acknowledgements or conflict choices; "
                    "no changes were applied"
                )
            if not yes:
                if as_json or not ctx.obj.interactive:
                    raise SelfServiceError(
                        "Review with --dry-run, then use --yes to apply a ready plan"
                    )
                if not typer.confirm("Apply this calendar import?", default=False):
                    raise typer.Exit(0)
            applied = client.call(
                ops.APPLY_CALENDAR_IMPORT,
                path={"tenant_id": tid},
                body=CalendarImportApply.model_validate(
                    {**request.model_dump(mode="json"), "token": planned.token}
                ),
            ).value
            if as_json:
                typer.echo(applied.model_dump_json(indent=2))
            else:
                typer.echo(
                    f"Imported {len(applied.created)} new units; changed {len(applied.changed)}, "
                    f"unchanged {len(applied.unchanged)}, kept local {len(applied.kept_local)}, "
                    f"retained {len(applied.retained)}."
                )


@app.command("export")
def calendar_export(
    ctx: typer.Context,
    source_key: str,
    tenant: Tenant,
    output: Annotated[Path | None, typer.Option("--output", "-O")] = None,
) -> None:
    with session(ctx, tenant) as (client, tid):
        document = client.call(
            ops.EXPORT_CALENDAR_IMPORT, path={"tenant_id": tid, "source_key": source_key}
        ).value
        rendered = document.model_dump_json(indent=2) + "\n"
        if output is None:
            typer.echo(rendered, nl=False)
        else:
            output.write_text(rendered, encoding="utf-8")
