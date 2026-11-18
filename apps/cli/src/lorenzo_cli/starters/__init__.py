"""The library documents that ship with the CLI (ADR 0505): one TOML file each in this package,
named by its file. `lorenzo starter list|show` reads them without a login; `--starter NAME` on
`plan` and `apply` stands for one."""

from __future__ import annotations

from importlib import resources

from lorenzo_cli.library.document import Document, DocumentError, parse


def names() -> list[str]:
    files = resources.files(__name__)
    return sorted(f.name.removesuffix(".toml") for f in files.iterdir() if f.name.endswith(".toml"))


def text(name: str) -> str:
    if name not in names():
        shipped = ", ".join(names()) or "none yet"
        raise DocumentError(f"No starter called {name} (this version ships: {shipped}).")
    return resources.files(__name__).joinpath(f"{name}.toml").read_text("utf-8")


def load(name: str) -> Document:
    return parse(text(name), source=f"the {name} starter")
