"""`lorenzo schema` (ADR 0495): the library document's JSON Schema, and the shape of a command's
`--json` output, so a script or an agent needs no README."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated, Any, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field, create_model

from lorenzo_cli import console
from lorenzo_cli.console import JSON_FORMAT

app = typer.Typer(help="JSON Schemas: the library document, and each command's --json output.")


class _Action(BaseModel):
    verb: Literal["create", "change", "remove"]
    kind: str
    key: str
    detail: str


class _Failure(_Action):
    reason: str


class _Result(BaseModel):
    done: list[_Action]
    failed: list[_Failure]
    skipped: list[_Action]


class _Plan(BaseModel):
    model_config = ConfigDict(title="lorenzo plan --json")
    format: Literal[1] = 1
    document: str
    library: str
    prune: bool
    counts: dict[Literal["create", "change", "remove"], int]
    actions: list[_Action]
    problems: list[str]
    notes: list[str]
    result: _Result | None = Field(None, description="Only from `apply`, once it has written.")


class _Error(BaseModel):
    status: int | None
    code: str
    message: str
    details: Any = None


class _Failed(BaseModel):
    model_config = ConfigDict(title="any command's --json failure")
    format: Literal[1] = 1
    error: _Error


def _listing(key: str, model: str) -> Callable[[], type[BaseModel]]:
    def build() -> type[BaseModel]:
        from lorenzo_cli.client import ops

        row: Any = ops.resolve(model)
        fields: dict[str, Any] = {"format": (Literal[1], JSON_FORMAT), key: (list[row], ...)}
        built: type[BaseModel] = create_model(f"{key}_listing", **fields)
        return built

    return build


def _single(model: str) -> Callable[[], type[BaseModel]]:
    def build() -> type[BaseModel]:
        from lorenzo_cli.client import ops

        found: Any = ops.resolve(model)
        fields: dict[str, Any] = {"format": (Literal[1], JSON_FORMAT)}
        built: type[BaseModel] = create_model(f"{model}_report", __base__=found, **fields)
        return built

    return build


OUTPUTS: dict[str, Callable[[], type[BaseModel]]] = {
    "plan": lambda: _Plan,
    "apply": lambda: _Plan,
    "error": lambda: _Failed,
    "tenant list": _listing("tenants", "TenantSummaryOut"),
    "tenant show": _single("TenantOut"),
    "system list": _listing("systems", "SystemOut"),
    "system show": _single("SystemOut"),
    "stat-group list": _listing("stat_groups", "StatGroupOut"),
    "stat-definition list": _listing("stat_definitions", "StatDefinitionOut"),
    "repo list": _listing("repositories", "SubscriptionOut"),
    "repo copy-plan": _single("CopyPlanOut"),
}


def _print(schema: dict[str, Any]) -> None:
    console.out.file.write(json.dumps(schema, indent=2) + "\n")


@app.command("document")
def schema_document() -> None:
    """The library document's JSON Schema (ADR 0498), for an editor to check a file against."""
    from lorenzo_cli.library.document import json_schema

    _print(json_schema())


@app.command("output")
def schema_output(
    command: Annotated[
        list[str] | None, typer.Argument(help="The command, as typed: `tenant list`, `plan`.")
    ] = None,
) -> None:
    """The shape of a command's --json output; without a command, the commands it knows."""
    if not command:
        for name in OUTPUTS:
            console.out.print(name)
        return
    name = " ".join(command)
    build = OUTPUTS.get(name)
    if build is None:
        console.error(f"No schema for `{name}` yet. Known: {', '.join(OUTPUTS)}.")
        raise typer.Exit(1)
    schema = build().model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    _print(schema)
