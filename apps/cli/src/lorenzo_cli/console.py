"""Everything `lorenzo` prints goes through here (ADR 0481).

- stdout carries the result and nothing else; notices, warnings, errors, questions and progress
  go to stderr.
- Progress animates only when stderr is a terminal and neither `--quiet`, `--no-progress`, `--json`
  nor `NO_COLOR` says otherwise; otherwise a wait is one plain line, and under `--quiet` nothing.
- A status is a symbol and a word as well as a colour, so it reads the same without colour.
- A `--json` report is one object on stdout with a `format` number. File formats a command writes
  (a calendar, a ledger) and `lorenzo api`'s passthrough are not reports and keep their own shape.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.text import Text

# The format of every `--json` report. Raised when a report's shape changes incompatibly.
JSON_FORMAT = 1

out = Console(highlight=False)
err = Console(stderr=True, highlight=False)


@dataclass
class Settings:
    quiet: bool = False
    no_progress: bool = False
    json: bool = False


settings = Settings()

# kind: (symbol, word, style)
STATUS: dict[str, tuple[str, str, str]] = {
    "done": ("✓", "done", "green"),
    "create": ("+", "create", "green"),
    "change": ("~", "change", "yellow"),
    "remove": ("-", "remove", "red"),
    "warning": ("⚠", "warning", "yellow"),
    "refused": ("✗", "refused", "red"),
    "error": ("✗", "error", "red"),
    "note": ("·", "note", "cyan"),
}


def configure(
    *, quiet: bool | None = None, no_progress: bool | None = None, json: bool | None = None
) -> None:
    if quiet is not None:
        settings.quiet = quiet
    if no_progress is not None:
        settings.no_progress = no_progress
    if json is not None:
        settings.json = json


def reset() -> None:
    """Back to the defaults (a test, or a second command in one process)."""
    configure(quiet=False, no_progress=False, json=False)


def animated() -> bool:
    """Whether progress may move: stderr is a terminal and nothing asked for quiet."""
    return (
        err.is_terminal
        and not settings.quiet
        and not settings.no_progress
        and not settings.json
        and "NO_COLOR" not in os.environ
    )


def status(kind: str, text: str | Text = "") -> Text:
    """`✓ done` and the text, the symbol and the word in the status's colour."""
    symbol, word, style = STATUS[kind]
    label = Text(f"{symbol} {word}", style=style)
    if text:
        label.append(": " if isinstance(text, str) else " ")
        label.append(text if isinstance(text, Text) else Text(text))
    return label


def notice(text: str | Text) -> None:
    """A line for a person on stderr; gone under `--quiet`."""
    if not settings.quiet:
        err.print(text if isinstance(text, Text) else Text(text), soft_wrap=True)


def warning(text: str) -> None:
    err.print(status("warning", text), soft_wrap=True)


def error(text: str) -> None:
    err.print(status("error", text), soft_wrap=True)


def emit(document: Mapping[str, Any]) -> None:
    """One `--json` report on stdout, with the format first."""
    out.file.write(json.dumps({"format": JSON_FORMAT, **document}, indent=2) + "\n")
    out.file.flush()


def emit_error(status_code: int | None, code: str, message: str, details: Any = None) -> None:
    """A failure under `--json`: one object on stdout, so a script reads one document either way."""
    emit({"error": {"status": status_code, "code": code, "message": message, "details": details}})


# --- Progress -------------------------------------------------------------------------------

_live_lock = threading.Lock()
_busy: _Busy | None = None


class _Busy:
    """A spinner that appears only when a wait passes a short delay, so quick commands show none."""

    DELAY = 0.3

    def __init__(self, text: str) -> None:
        self.text = text
        self._status: Any = None
        self._timer: threading.Timer | None = None
        self._paused = 0

    def start(self) -> None:
        self._timer = threading.Timer(self.DELAY, self._show)
        self._timer.daemon = True
        self._timer.start()

    def _show(self) -> None:
        with _live_lock:
            if self._paused or self._status is not None:
                return
            self._status = err.status(self.text, spinner="dots")
            self._status.start()

    def _hide(self) -> None:
        with _live_lock:
            if self._status is not None:
                self._status.stop()
                self._status = None

    def pause(self) -> None:
        self._paused += 1
        if self._timer is not None:
            self._timer.cancel()
        self._hide()

    def resume(self) -> None:
        self._paused -= 1
        if not self._paused:
            self.start()

    def stop(self) -> None:
        self._paused += 1
        if self._timer is not None:
            self._timer.cancel()
        self._hide()


@contextmanager
def busy(text: str = "Working") -> Iterator[None]:
    """A spinner on stderr while the API is asked, shown only after a short delay and only when
    progress may move. Prompts and bars pause it (`paused`)."""
    global _busy
    if not animated() or _busy is not None:
        yield
        return
    _busy = _Busy(text)
    _busy.start()
    try:
        yield
    finally:
        _busy.stop()
        _busy = None


@contextmanager
def paused() -> Iterator[None]:
    """Nothing animates inside: for a question, or for a bar of its own."""
    if _busy is None:
        yield
        return
    _busy.pause()
    try:
        yield
    finally:
        _busy.resume()


@contextmanager
def waiting(text: str) -> Iterator[None]:
    """A wait of unknown length: a spinner with the elapsed time, or one plain line."""
    if not animated():
        notice(f"{text}…")
        yield
        return
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    with (
        paused(),
        Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            console=err,
            transient=True,
        ) as progress,
    ):
        progress.add_task(text, total=None)
        yield


class Steps:
    """What a batch reports as it goes: a step done, and what it is doing now."""

    def __init__(
        self,
        advance: Callable[[int], None] = lambda n: None,
        describe: Callable[[str], None] = lambda text: None,
    ) -> None:
        self._advance = advance
        self._describe = describe

    def advance(self, n: int = 1) -> None:
        self._advance(n)

    def describe(self, text: str) -> None:
        self._describe(text)


@contextmanager
def counting(text: str, total: int) -> Iterator[Steps]:
    """A batch of `total` steps: a bar with "N of M", or one plain line."""
    if not animated():
        notice(f"{text}: {total}…")
        yield Steps()
        return
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Column

    with (
        paused(),
        Progress(
            SpinnerColumn(),
            TextColumn("{task.description}", table_column=Column(width=44, no_wrap=True)),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=err,
            transient=True,
        ) as progress,
    ):
        task = progress.add_task(text, total=total)
        yield Steps(
            lambda n: progress.advance(task, n),
            lambda label: progress.update(task, description=label),
        )
