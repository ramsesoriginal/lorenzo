"""A command group whose commands are imported only when one is run or its own help is shown
(ADR 0483). The root and the `import` and `export` groups are such groups; each lists its commands
in a registry, with the short help its listing and a completion show without importing anything."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, ClassVar

import typer
from typer import _click as click  # typer vendors its own click; its classes are these
from typer.core import TyperCommand, TyperGroup


@dataclass(frozen=True)
class Entry:
    """Where a command lives: a module and the Typer app in it, and the command's short help.
    `command` names one command of that app; None means the app is the group."""

    module: str
    app: str
    help: str
    command: str | None = None


class LazyGroup(TyperGroup):
    """Lists its commands from `registry` and imports one only to run it or show its own help:
    while its help or a completion lists them, each is a stand-in with the short help alone."""

    registry: ClassVar[dict[str, Entry]] = {}
    _listing = False

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.registry)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        entry = self.registry.get(cmd_name)
        if entry is None:
            return None
        if self._listing:
            return TyperCommand(cmd_name, help=entry.help, short_help=entry.help)
        return load(cmd_name, entry)

    @contextmanager
    def _only_listing(self) -> Iterator[None]:
        self._listing = True
        try:
            yield
        finally:
            self._listing = False

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        with self._only_listing():
            super().format_help(ctx, formatter)

    def shell_complete(self, ctx: click.Context, incomplete: str) -> list[Any]:
        with self._only_listing():
            return super().shell_complete(ctx, incomplete)


def load(name: str, entry: Entry) -> click.Command:
    """The real command or group of an entry, with its module imported."""
    found = getattr(importlib.import_module(entry.module), entry.app)
    group = typer.main.get_group(found)
    if entry.command is None:
        group.name = name
        return group
    command = group.commands[entry.command]
    command.name = name
    return command
