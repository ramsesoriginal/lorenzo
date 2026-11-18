"""Options shared by several command groups."""

from __future__ import annotations

from typing import Annotated

import typer

from lorenzo_cli import completers

TenantOption = Annotated[
    str,
    typer.Option(
        "--tenant",
        "-t",
        envvar="LORENZO_TENANT",
        autocompletion=completers.library,
        help="The repository tenant's id or slug.",
    ),
]
ItemTenant = Annotated[
    str,
    typer.Option(
        "--tenant",
        "-t",
        envvar="LORENZO_TENANT",
        autocompletion=completers.library,
        help="The library: its id or slug.",
    ),
]
