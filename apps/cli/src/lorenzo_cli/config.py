"""Settings: from a flag, the environment, or the file `login` remembered (ADR 0157).

The README lists them.
"""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

# The three settings a person would otherwise export in every shell, by their key in the file.
SETTING_KEYS = ("api_url", "issuer", "client_id")


class ConfigError(Exception):
    """A setting the command needs is missing."""


@dataclass(frozen=True)
class Settings:
    api_url: str | None
    issuer: str | None
    client_id: str | None

    def require_api_url(self) -> str:
        # No default on purpose: a token must never go to a host nobody named.
        if not self.api_url:
            raise ConfigError(
                "Say which API to talk to: set LORENZO_API_URL or pass --api-url, or run "
                "`lorenzo login --api-url ...` once to remember it."
            )
        return self.api_url


def default_config_path(env: Mapping[str, str]) -> Path:
    base = env.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "lorenzo" / "config.toml"


class SettingsFile:
    """What `lorenzo login` remembers: the API URL, the issuer and the client id (ADR 0157).

    Nothing in it is secret, so it is an ordinary file, written whole and replaced atomically.
    Only `login` writes it; every other command reads it.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, warn: Callable[[str], None] | None = None) -> dict[str, str]:
        """The remembered values; unknown keys are ignored and a garbled file reads as empty."""
        try:
            data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
            if warn is not None:
                warn(f"Ignoring {self.path}: it isn't valid TOML ({exc}).")
            return {}
        return {k: v for k in SETTING_KEYS if isinstance(v := data.get(k), str) and v}

    def save(self, values: Mapping[str, str]) -> None:
        """Remember `values`, keeping any of the other settings already remembered."""
        merged = {**self.load(), **{k: v for k, v in values.items() if k in SETTING_KEYS and v}}
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        # JSON's string escapes are valid in a TOML basic string, so no TOML writer is needed.
        lines = [f"{key} = {json.dumps(merged[key])}\n" for key in SETTING_KEYS if key in merged]
        temporary.write_text("".join(lines), encoding="utf-8")
        os.replace(temporary, self.path)


def load_settings(
    env: Mapping[str, str],
    *,
    api_url: str | None = None,
    issuer: str | None = None,
    client_id: str | None = None,
    remembered: Mapping[str, str] | None = None,
) -> Settings:
    """Each setting from a flag first, then its environment variable, then the remembered file."""
    saved = remembered or {}
    return Settings(
        api_url=api_url or env.get("LORENZO_API_URL") or saved.get("api_url") or None,
        issuer=issuer or env.get("LORENZO_AUTHGEAR_ISSUER") or saved.get("issuer") or None,
        client_id=(
            client_id or env.get("LORENZO_AUTHGEAR_CLIENT_ID") or saved.get("client_id") or None
        ),
    )
