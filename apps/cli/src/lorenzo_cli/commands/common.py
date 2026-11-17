"""Options shared by several command groups."""

from __future__ import annotations

from typing import Annotated

import typer

TenantOption = Annotated[
    str,
    typer.Option(
        "--tenant", "-t", envvar="LORENZO_TENANT", help="The repository tenant's id or slug."
    ),
]
ItemTenant = Annotated[
    str,
    typer.Option("--tenant", "-t", envvar="LORENZO_TENANT", help="The library: its id or slug."),
]
