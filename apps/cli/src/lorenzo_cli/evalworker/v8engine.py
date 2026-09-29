"""The embedded V8 engine (`mini-racer`), ADR 0138. Runs inside the worker, never in the CLI."""

from __future__ import annotations

import json
import re
from importlib import resources
from typing import Literal

from py_mini_racer import JSEvalException, JSOOMException, JSTimeoutException, MiniRacer

from lorenzo_cli.evalworker.protocol import (
    EvalRequest,
    EvalResult,
    FileResult,
    Limits,
    SourceFile,
)

_UNDEFINED_NAME = re.compile(r"ReferenceError: ([A-Za-z_$][\w$]*) is not defined")


def _prelude() -> str:
    return resources.files("lorenzo_cli.evalworker").joinpath("prelude.js").read_text("utf-8")


class _MissingName(Exception):
    """A file read a name the sheet supplies and this host doesn't: restart with a stub."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class V8Engine:
    """Evaluates the base files, resets the lists from them, then the content files, all in one
    ordered context, adding a stub whenever a file reads a name the sheet supplies and this
    host doesn't.

    A stub can't be added to a context that already threw, so the run restarts in a fresh
    context with the stub seeded. That is bounded by `limits.max_stub_retries` and reported.
    """

    def evaluate(self, request: EvalRequest) -> EvalResult:
        limits = request.limits
        prelude = _prelude()
        stubbed: list[str] = []
        for restarts in range(limits.max_stub_retries + 1):
            context = MiniRacer()
            context.eval(prelude)
            context.eval(f"__lorenzo.seedStubs({json.dumps(stubbed)})")
            files: list[FileResult] = []
            try:
                for source_file in request.base:
                    files.append(_run(context, source_file, "base", "Base_", limits, stubbed))
                context.eval("__lorenzo.initiateLists()")
                for source_file in request.files:
                    files.append(_run(context, source_file, "content", "", limits, stubbed))
            except _MissingName as missing:
                stubbed.append(missing.name)
                continue
            snapshot = json.loads(
                str(context.eval(f"__lorenzo.snapshot({json.dumps(request.lists)})"))
            )
            heap_mb = int(context.heap_stats()["used_heap_size"]) / (1024 * 1024)
            return EvalResult(
                ok=True, files=files, restarts=restarts, heap_used_mb=round(heap_mb, 1), **snapshot
            )
        return EvalResult(
            ok=False,
            error=(
                f"Gave up after {limits.max_stub_retries} restarts adding stubs for names the "
                f"sheet supplies (the last was {stubbed[-1]})."
            ),
            restarts=limits.max_stub_retries,
        )


def _run(
    context: MiniRacer,
    source_file: SourceFile,
    role: Literal["base", "content"],
    prefix: str,
    limits: Limits,
    stubbed: list[str],
) -> FileResult:
    context.eval(f"__lorenzo.setFile({json.dumps(source_file.name)})")
    try:
        context.eval(
            source_file.source,
            timeout_sec=limits.file_seconds,
            max_memory=limits.max_memory_mb * 1024 * 1024,
        )
    except JSEvalException as exc:
        match = _UNDEFINED_NAME.search(str(exc))
        if match and match.group(1) not in stubbed:
            raise _MissingName(match.group(1)) from exc
        result = FileResult(
            name=source_file.name, role=role, status="error", error=_first_line(exc)
        )
    except JSTimeoutException:
        result = FileResult(name=source_file.name, role=role, status="error", error="timed out")
    except JSOOMException:
        result = FileResult(name=source_file.name, role=role, status="error", error="out of memory")
    else:
        result = FileResult(name=source_file.name, role=role, status="ok")
    # Even a file that failed part-way has changed some lists; say which file did.
    context.eval(f"__lorenzo.noteOrigins({json.dumps(prefix)}, {json.dumps(source_file.name)})")
    return result


def _first_line(exc: Exception) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__
