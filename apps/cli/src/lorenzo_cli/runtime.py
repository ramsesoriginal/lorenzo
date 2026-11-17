"""What every command runs against: the consoles, the Runtime, the API client, and how an expected
failure is reported. Imported by the root, so it imports nothing a command group needs only for
itself: the HTTP stack, the token sources and the MPMB engine load when they are first used
(ADR 0483)."""

from __future__ import annotations

import functools
import os
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

import typer
from rich.console import Console

from lorenzo_cli.auth import store as credentials
from lorenzo_cli.auth.store import CredentialsFile
from lorenzo_cli.config import Settings, SettingsFile, default_config_path, load_settings

if TYPE_CHECKING:
    import httpx

    from lorenzo_cli.client.transport import LorenzoClient
    from lorenzo_cli.evalworker import Engine, EvalRequest, EvalResult

_out = Console()
_err = Console(stderr=True)


def _warn(message: str) -> None:
    _err.print(f"[yellow]{message}[/yellow]")


class _WorkerOnUse:
    """The worker subprocess engine, imported and made the first time something is evaluated."""

    def __init__(self) -> None:
        self._engine: Engine | None = None

    def evaluate(self, request: EvalRequest) -> EvalResult:
        if self._engine is None:
            from lorenzo_cli.evalworker import WorkerEngine

            self._engine = WorkerEngine()
        return self._engine.evaluate(request)


@dataclass
class Runtime:
    """What a command runs against. Tests hand one in instead of the real environment."""

    env: Mapping[str, str]
    stdin: TextIO
    store: CredentialsFile
    transport: httpx.BaseTransport | None = None
    # Whether someone can be asked; None means: whether stdin is a terminal.
    interactive_override: bool | None = None
    # Evaluates MPMB files; the worker subprocess unless a test hands in another.
    engine: Engine = field(default_factory=_WorkerOnUse)
    api_url: str | None = None
    token_stdin: bool = False
    # What `login` remembered (ADR 0157); None means there is no file to read, as in most tests.
    config: SettingsFile | None = None
    # Waits between polls of `login --token`; tests hand in one that approves instead of waiting.
    sleep: Callable[[float], None] = time.sleep

    @property
    def interactive(self) -> bool:
        if self.interactive_override is not None:
            return self.interactive_override
        return self.stdin.isatty()

    @property
    def settings(self) -> Settings:
        return self.resolve_settings()

    def resolve_settings(
        self, *, issuer: str | None = None, client_id: str | None = None
    ) -> Settings:
        """Flag, then environment, then the remembered file (ADR 0157)."""
        remembered = self.config.load(warn=_warn) if self.config else {}
        return load_settings(
            self.env,
            api_url=self.api_url,
            issuer=issuer,
            client_id=client_id,
            remembered=remembered,
        )


def default_runtime() -> Runtime:
    env = dict(os.environ)
    return Runtime(
        env=env,
        stdin=sys.stdin,
        store=CredentialsFile(Path(credentials.default_path(env))),
        config=SettingsFile(default_config_path(env)),
    )


@functools.cache
def _expected() -> tuple[type[BaseException], ...]:
    """The failures that are shown as one line, not a traceback. Imported when something failed,
    so that no command pays for the modules of the others."""
    from lorenzo_cli.auth.device import DeviceLoginError
    from lorenzo_cli.auth.login import LoginError
    from lorenzo_cli.auth.tokens import NotLoggedInError
    from lorenzo_cli.client.errors import LorenzoConnectionError, LorenzoResponseError
    from lorenzo_cli.config import ConfigError
    from lorenzo_cli.evalworker import EvalError
    from lorenzo_cli.importer.give import PackError
    from lorenzo_cli.importer.mapping import MappingError
    from lorenzo_cli.repos import RepoError
    from lorenzo_cli.self_service import SelfServiceError
    from lorenzo_cli.tenants import TenantNotFoundError, WrongTenantKindError

    return (
        ConfigError,
        NotLoggedInError,
        LoginError,
        DeviceLoginError,
        EvalError,
        MappingError,
        PackError,
        WrongTenantKindError,
        TenantNotFoundError,
        LorenzoConnectionError,
        LorenzoResponseError,
        RepoError,
        SelfServiceError,
    )


@contextmanager
def _reporting_errors() -> Iterator[None]:
    """Show an expected failure as one line on stderr and exit 1, not as a traceback."""
    try:
        yield
    except Exception as exc:
        from lorenzo_cli.client.errors import LorenzoApiError

        if isinstance(exc, _expected()):
            _err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        if isinstance(exc, LorenzoApiError):
            from lorenzo_cli import repos

            _err.print(f"[red]{repos.in_words(exc)} (HTTP {exc.status})[/red]", highlight=False)
            raise typer.Exit(1) from exc
        raise


@contextmanager
def _client(runtime: Runtime, *, writes: bool = False) -> Iterator[LorenzoClient]:
    """The API client; a command that writes says so when it is the official default (ADR 0164)."""
    import httpx

    from lorenzo_cli.auth.tokens import resolve_token_source
    from lorenzo_cli.client.transport import LorenzoClient

    settings = runtime.settings
    base_url = settings.require_api_url()
    with httpx.Client(transport=runtime.transport, timeout=30.0) as auth_http:
        tokens = resolve_token_source(
            token_stdin=runtime.token_stdin,
            stdin=runtime.stdin,
            env=runtime.env,
            store=runtime.store,
            http=auth_http,
        )
        if writes and settings.defaulted:
            _err.print(
                f"Using the official Lorenzo at {base_url}.", highlight=False, soft_wrap=True
            )
        with LorenzoClient(base_url, tokens, transport=runtime.transport) as client:
            yield client
