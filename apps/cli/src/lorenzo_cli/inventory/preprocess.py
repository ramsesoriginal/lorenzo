"""Other ways to write a name (ADR 0193): what is tried when a name matches no item.

From one name, in order and without repeats: the name without a bracket or a length, as a singular,
then each of those through the table of whole names and the table of words. Nothing is guessed
that the tables do not say.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

_BRACKETS = re.compile(r"\s*[(\[][^)\]]*[)\]]\s*")
_LENGTH = re.compile(r"\s+\d+(?:[.,]\d+)?\s*(?:ft\.?|feet|foot|m|meter|metres?)\b", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


def _clean(name: str) -> str:
    return _SPACES.sub(" ", name).strip().lower()


def _singular(name: str) -> str | None:
    if name.endswith("ies") and len(name) > 4:
        return name[:-3] + "y"
    if name.endswith(("ches", "shes", "sses", "xes", "zes")):
        return name[:-2]
    if name.endswith("s") and not name.endswith("ss") and len(name) > 3:
        return name[:-1]
    return None


@dataclass
class Table:
    names: dict[str, str] = field(default_factory=dict)
    words: dict[str, str] = field(default_factory=dict)

    def merged(self, other: Table) -> Table:
        return Table({**self.names, **other.names}, {**self.words, **other.words})

    def alternatives(self, name: str) -> list[str]:
        """Other ways to write `name`, most likely first, never the name itself."""
        start = _clean(name)
        stems = [start]
        for stem in (_clean(_LENGTH.sub("", _BRACKETS.sub(" ", name))),):
            if stem and stem not in stems:
                stems.append(stem)
        for stem in list(stems):
            singular = _singular(stem)
            if singular and singular not in stems:
                stems.append(singular)
        out: list[str] = []

        def add(candidate: str) -> None:
            if candidate and candidate != start and candidate not in out:
                out.append(candidate)

        for stem in stems:
            add(stem)

        def translated(candidate: str) -> None:
            add(candidate)
            singular = _singular(candidate)
            if singular:
                add(singular)

        for stem in stems:
            if stem in self.names:
                translated(self.names[stem])
            words = stem.split(" ")
            if any(word in self.words for word in words):
                translated(" ".join(self.words.get(word, word) for word in words))
        return out


def _table(text: str) -> Table:
    data = tomllib.loads(text)
    return Table(
        {_clean(k): _clean(v) for k, v in data.get("names", {}).items()},
        {_clean(k): _clean(v) for k, v in data.get("words", {}).items()},
    )


def builtin() -> Table:
    text = resources.files("lorenzo_cli.inventory").joinpath("preprocess.toml").read_text("utf-8")
    return _table(text)


def load(path: Path | None = None) -> Table:
    """The built-in table, with one of the user's on top."""
    table = builtin()
    return table.merged(_table(path.read_text("utf-8"))) if path is not None else table
