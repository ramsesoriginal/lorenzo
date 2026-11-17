"""`lorenzo api`: one authenticated request for a script (ADR 0161)."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from lorenzo_cli import rawapi
from lorenzo_cli.runtime import (
    Runtime,
    _client,
    _err,
    _reporting_errors,
)

app = typer.Typer()


@app.command("api")
def api_request(
    ctx: typer.Context,
    method: Annotated[str, typer.Argument(help="GET, POST, PUT, PATCH or DELETE.")],
    path: Annotated[
        str, typer.Argument(help="A path on the API, like /tenants. Never a full address.")
    ],
    data: Annotated[
        str | None,
        typer.Option(
            "--data", "-d", help="The JSON body: text, @file, or - for stdin (POST, PUT, PATCH)."
        ),
    ] = None,
    query: Annotated[
        list[str] | None,
        typer.Option("--query", "-q", help="A query parameter, KEY=VALUE. Repeat for more."),
    ] = None,
    if_match: Annotated[
        str | None,
        typer.Option("--if-match", help="Send If-Match: an ETag from an earlier read."),
    ] = None,
    include: Annotated[
        bool,
        typer.Option("--include", "-i", help="Print the status line and the headers first."),
    ] = False,
    paginate: Annotated[
        bool,
        typer.Option("--paginate", help="GET only: walk every page and print one array of items."),
    ] = False,
    raw: Annotated[bool, typer.Option("--raw", help="Print the body exactly as it came.")] = False,
) -> None:
    """Make one authenticated request to the API, and print its answer.

    The body goes to stdout. Exit 0 for a 2xx answer, 1 for anything else (the API's own
    explanation is still printed, and its status goes to stderr).
    """
    runtime: Runtime = ctx.obj
    try:
        verb = rawapi.check_method(method)
        target = rawapi.check_path(path)
        pairs = rawapi.parse_query(query or [])
        if paginate and verb != "GET":
            raise rawapi.RequestUsageError("--paginate only walks a GET.", "--paginate")
        if paginate and include:
            raise rawapi.RequestUsageError(
                "--include shows one response; --paginate makes many.", "--paginate"
            )
        body = rawapi.read_body(data, verb, runtime.stdin)
    except rawapi.RequestUsageError as exc:
        raise typer.BadParameter(str(exc), param_hint=exc.hint) from exc

    with _reporting_errors(), _client(runtime, writes=verb != "GET") as client:
        items: list[object] | None = None
        if paginate:
            response, items = rawapi.paginate(client, target, query=pairs)
        else:
            response = rawapi.send(client, verb, target, query=pairs, body=body, if_match=if_match)

    if include:
        typer.echo(rawapi.status_line(response))
        for line in rawapi.header_lines(response):
            typer.echo(line)
        typer.echo("")
    if items is not None:
        typer.echo(json.dumps(items, indent=2, ensure_ascii=False))
    elif response.content:
        typer.echo(response.content if raw else rawapi.pretty(response.content), nl=False)
    if response.is_error:
        _err.print(f"[red]{rawapi.failure_summary(response)}[/red]", highlight=False)
        raise typer.Exit(1)


# --- lorenzo repo (ADR 0159, 0160) ------------------------------------------------------------
