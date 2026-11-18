"""Tab completion of names (ADR 0507): each completer reads the private cache, never the API.

Typer reads these functions' annotations to hand them the context, so this module does not
postpone them (no `from __future__ import annotations`). It imports only what the root already
has loaded, and the cache module, which is standard library only.
"""

import os
from collections.abc import Callable
from typing import Any

import typer

from lorenzo_cli import completion


def _cached(ctx: typer.Context) -> dict[str, Any]:
    from lorenzo_cli.auth.store import default_path
    from lorenzo_cli.config import SettingsFile, default_config_path, load_settings

    env = dict(os.environ)
    api_url = ctx.find_root().params.get("api_url")
    try:
        remembered = SettingsFile(default_config_path(env)).load()
    except Exception:  # a broken settings file only means nothing to complete
        remembered = {}
    settings = load_settings(env, api_url=api_url, remembered=remembered)
    account = completion.account_of(completion.stored_token(env, default_path(env)))
    if not settings.api_url or account is None:
        return {}
    return completion.load(completion.cache_path(env, settings.api_url, account))


def _tenant(ctx: typer.Context) -> str | None:
    tenant = ctx.params.get("tenant")
    return str(tenant) if tenant else os.environ.get("LORENZO_TENANT")


def library(ctx: typer.Context, incomplete: str) -> list[str]:
    return completion.library_slugs(_cached(ctx), incomplete)


def _of(category: str) -> Callable[[typer.Context, str], list[str]]:
    def complete(ctx: typer.Context, incomplete: str) -> list[str]:
        return completion.names(_cached(ctx), _tenant(ctx), category, incomplete)

    return complete


system = _of("systems")
stat_group = _of("stat_groups")
stat = _of("stats")
template = _of("templates")
feature = _of("features")
campaign = _of("campaigns")


def starter(incomplete: str) -> list[str]:
    from lorenzo_cli import starters

    return [name for name in starters.names() if name.startswith(incomplete)]
