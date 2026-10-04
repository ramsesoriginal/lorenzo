"""Running the worker from the CLI (ADR 0138).

The worker is a plain subprocess, not `multiprocessing`: forking a process that has asyncio
threads is unsafe, and a subprocess is the same on every start method. Its environment is built
from scratch, so nothing the CLI holds (LORENZO_TOKEN, the stored login) can reach it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import ValidationError

from lorenzo_cli.evalworker.protocol import EvalError, EvalRequest, EvalResult, SourceFile

# All the worker needs to find its interpreter's libraries and to run.
_KEPT_ENV = ("PATH", "LANG", "LC_ALL", "SYSTEMROOT")


def worker_env(parent: Mapping[str, str]) -> dict[str, str]:
    return {key: parent[key] for key in _KEPT_ENV if key in parent}


class WorkerEngine:
    """An `Engine` that runs the evaluation in a disposable subprocess."""

    def __init__(self, python: str = sys.executable) -> None:
        self._python = python

    def evaluate(self, request: EvalRequest) -> EvalResult:
        # -I: ignore PYTHON* variables and the user site, so the worker is the installed code.
        command = [self._python, "-I", "-m", "lorenzo_cli.evalworker"]
        try:
            completed = subprocess.run(  # noqa: S603 - our own interpreter and module
                command,
                input=request.model_dump_json().encode(),
                capture_output=True,
                timeout=request.limits.wall_seconds,
                env=worker_env(os.environ),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EvalError(
                f"The JavaScript worker was stopped after {request.limits.wall_seconds:g}s."
            ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.decode(errors="replace").strip().splitlines()
            raise EvalError(
                f"The JavaScript worker failed (exit {completed.returncode})"
                + (f": {detail[-1]}" if detail else ".")
            )
        try:
            return EvalResult.model_validate_json(completed.stdout)
        except ValidationError as exc:
            raise EvalError("The JavaScript worker answered with something unreadable.") from exc


def read_sources(paths: Iterable[Path]) -> list[SourceFile]:
    """Read source files in the order given (a later file may refer to an earlier one)."""
    files: list[SourceFile] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise EvalError(f"{path} isn't UTF-8 text.") from exc
        files.append(SourceFile(name=path.name, source=text))
    return files
