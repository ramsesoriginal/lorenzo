"""The worker: `python -m lorenzo_cli.evalworker` reads one request on stdin, writes one result
on stdout (ADR 0138). It is started before login and is given no credentials."""

from __future__ import annotations

import math
import os
import sys

from pydantic import ValidationError

from lorenzo_cli.evalworker.protocol import EvalRequest, EvalResult
from lorenzo_cli.evalworker.v8engine import V8Engine


def _limit_cpu(seconds: float) -> None:
    """A backstop under the parent's wall-clock kill. Linux only; RLIMIT_AS is deliberately not
    set, since V8 reserves address space it never uses."""
    try:
        import resource
    except ImportError:  # not Linux/POSIX: the parent's wall-clock kill is all there is
        return
    cpu = math.ceil(seconds) + 2
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))


def main() -> int:
    try:
        request = EvalRequest.model_validate_json(sys.stdin.buffer.read())
    except ValidationError as exc:
        sys.stderr.write(f"Bad request: {exc}\n")
        return 2
    _limit_cpu(request.limits.wall_seconds)
    result: EvalResult = V8Engine().evaluate(request)
    sys.stdout.write(result.model_dump_json())
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    code = main()
    sys.stderr.flush()
    # A disposable worker: skip interpreter teardown, where mini-racer's event-loop thread
    # would otherwise report a finalization error on stderr.
    os._exit(code)
