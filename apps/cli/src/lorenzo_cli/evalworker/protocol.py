"""The evaluation protocol (ADR 0138): one request in, one result out, as JSON.

`Engine` is the whole seam between the importer and a JavaScript engine: any object with an
`evaluate(request) -> result` method can stand in for the embedded V8, which is how a second
engine would be added without touching the importer.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

# The lists RFC 0025 imports. Everything else the files assign into is counted, not returned.
STANDARD_LISTS: tuple[str, ...] = (
    "WeaponsList",
    "ArmourList",
    "GearList",
    "PacksList",
    "ToolsList",
    "AmmoList",
    "SourceList",
)


class EvalError(Exception):
    """The evaluation itself failed: the worker died, timed out, or answered with garbage."""


class SourceFile(BaseModel):
    name: str
    source: str


class Limits(BaseModel):
    wall_seconds: float = 60.0
    file_seconds: float = 20.0
    max_memory_mb: int = 64
    # How many times a run is restarted to add a stub for a name the sheet supplies.
    max_stub_retries: int = 100


class EvalRequest(BaseModel):
    version: Literal[1] = 1
    # The sheet's own data (`Base_WeaponsList`...), evaluated first. Before the `files` run, every
    # list is reset to a copy of its `Base_` list, as the sheet does before user scripts. Empty
    # when only homebrew is imported.
    base: list[SourceFile] = Field(default_factory=list)
    files: list[SourceFile]
    lists: list[str] = Field(default_factory=lambda: list(STANDARD_LISTS))
    limits: Limits = Field(default_factory=Limits)


class FileResult(BaseModel):
    name: str
    role: Literal["base", "content"] = "content"
    status: Literal["ok", "error"]
    error: str | None = None


class StubInfo(BaseModel):
    name: str
    calls: int
    first_file: str


class StubInData(BaseModel):
    path: str
    stub: str


class EvalResult(BaseModel):
    version: Literal[1] = 1
    # False when the run couldn't finish (the stub-retry bound was hit); per-file errors don't
    # set it, they are in `files`.
    ok: bool
    error: str | None = None
    # Tagged JSON: {"$re": [source, flags]}, {"$fn": text}, {"$stub": name}, {"$num": "NaN"}.
    lists: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    # For each returned list, the file each entry came from ("" if unknown): the last file that
    # put a new object under the key, or the base file that defined it.
    origins: dict[str, dict[str, str]] = Field(default_factory=dict)
    files: list[FileResult] = Field(default_factory=list)
    stubs: list[StubInfo] = Field(default_factory=list)
    # Places a stubbed sheet call's result ended up inside the returned data.
    stubs_in_data: list[StubInData] = Field(default_factory=list)
    restarts: int = 0
    # V8's live heap once the run finished: what `Limits.max_memory_mb` is measured against.
    heap_used_mb: float = 0.0


class Engine(Protocol):
    def evaluate(self, request: EvalRequest) -> EvalResult: ...
