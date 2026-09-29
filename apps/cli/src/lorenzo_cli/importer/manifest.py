"""The run manifest: a disposable cache of what this machine imported (RFC 0025 R4).

It exists for one purpose, noticing that a namespace has changed since an item was imported, so
the plan can say "moved from A to B" instead of silently making a second item. It is never the
authority: the tenant is. Losing it costs that one warning; a second machine simply doesn't have
it, and behaves the same otherwise.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID


def default_path(env: Mapping[str, str], tenant_id: UUID) -> Path:
    base = env.get("XDG_STATE_HOME")
    root = Path(base) if base else Path.home() / ".local" / "state"
    return root / "lorenzo" / f"import-{tenant_id}.json"


class Manifest:
    def __init__(self, path: Path, entries: dict[str, str] | None = None) -> None:
        self.path = path
        self._entries = entries or {}

    @classmethod
    def load(cls, path: Path) -> Manifest:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = {str(k): str(v) for k, v in data["slugs"].items()}
        except OSError, ValueError, KeyError, AttributeError:
            entries = {}  # missing or garbled: a cache that isn't there
        return cls(path, entries)

    @staticmethod
    def _key(list_token: str, key: str) -> str:
        return f"{list_token}:{key}"

    def slug_for(self, list_token: str, key: str) -> str | None:
        return self._entries.get(self._key(list_token, key))

    def record(self, list_token: str, key: str, slug: str) -> None:
        self._entries[self._key(list_token, key)] = slug

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps({"slugs": self._entries}, indent=1, sort_keys=True))
        temporary.replace(self.path)
