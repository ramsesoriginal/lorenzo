"""The stored login: a `0600` file under `$XDG_CONFIG_HOME/lorenzo/` (ADR 0137).

A file rather than the OS keychain because a headless WSL has no Secret Service to talk to.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredLogin:
    issuer: str
    client_id: str
    access_token: str
    refresh_token: str | None = None
    # Epoch seconds at which the access token stops working, if the issuer said.
    expires_at: float | None = None


def default_path(env: Mapping[str, str]) -> Path:
    base = env.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "lorenzo" / "credentials.json"


class CredentialsFile:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> StoredLogin | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return StoredLogin(**data)
        except FileNotFoundError:
            return None
        except ValueError, TypeError:
            # Unreadable or from another version: treat as not logged in, don't crash.
            return None

    def save(self, login: StoredLogin) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.unlink(missing_ok=True)
        # Created 0600 from the start, so the token is never readable by anyone else, even briefly.
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(asdict(login), handle)
        temporary.replace(self.path)

    def delete(self) -> bool:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True
