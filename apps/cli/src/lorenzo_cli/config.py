"""Settings: from a flag, the environment, or the file `login` remembered (ADR 0157).

Where none of them names anything other than the official Lorenzo, the official values are the
default, together (ADR 0164). The README lists them.
"""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from lorenzo_cli.defaults import OFFICIAL_API_URL, OFFICIAL_CLIENT_ID, OFFICIAL_ISSUER

# The three settings a person would otherwise export in every shell, by their key in the file.
SETTING_KEYS = ("api_url", "issuer", "client_id")


class ConfigError(Exception):
    """A setting the command needs is missing."""


_LABELS = {"api_url": "API URL", "issuer": "issuer", "client_id": "client id"}


@dataclass(frozen=True)
class Settings:
    api_url: str | None
    issuer: str | None
    client_id: str | None
    # The official Lorenzo is in use because nothing else was named (ADR 0164).
    defaulted: bool = False
    # The settings named as something other than the official value: why no default applies.
    named_elsewhere: tuple[str, ...] = ()

    def require_api_url(self) -> str:
        if not self.api_url:
            raise ConfigError(
                "Say which API to talk to: set LORENZO_API_URL or pass --api-url, or run "
                "`lorenzo login --api-url ...` once to remember it." + self._why_no_default()
            )
        return self.api_url

    def _why_no_default(self) -> str:
        if not self.named_elsewhere:
            return ""
        named = " and ".join(_LABELS[key] for key in self.named_elsewhere)
        return (
            " The official Lorenzo is the default only while the API URL, the issuer and the "
            f"client id are all unnamed or official, and the {named} here names another."
        )


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

    def delete(self) -> bool:
        """Forget everything remembered; whether there was a file to forget."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True

    def save(self, values: Mapping[str, str]) -> None:
        """Remember `values`, keeping any of the other settings already remembered."""
        merged = {**self.load(), **{k: v for k, v in values.items() if k in SETTING_KEYS and v}}
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        # JSON's string escapes are valid in a TOML basic string, so no TOML writer is needed.
        lines = [f"{key} = {json.dumps(merged[key])}\n" for key in SETTING_KEYS if key in merged]
        temporary.write_text("".join(lines), encoding="utf-8")
        os.replace(temporary, self.path)


def _is_official(value: str, official: str) -> bool:
    return value.rstrip("/") == official.rstrip("/")


def load_settings(
    env: Mapping[str, str],
    *,
    api_url: str | None = None,
    issuer: str | None = None,
    client_id: str | None = None,
    remembered: Mapping[str, str] | None = None,
) -> Settings:
    """Each setting from a flag first, then its environment variable, then the remembered file.

    If none of them names anything other than the official value, the official three are the
    settings (ADR 0164). If any does, nothing is filled in for the others: a token must not go
    to one party under another's issuer.
    """
    saved = remembered or {}
    named_api_url = api_url or env.get("LORENZO_API_URL") or saved.get("api_url") or None
    named_issuer = issuer or env.get("LORENZO_AUTHGEAR_ISSUER") or saved.get("issuer") or None
    named_client_id = (
        client_id or env.get("LORENZO_AUTHGEAR_CLIENT_ID") or saved.get("client_id") or None
    )
    named = {"api_url": named_api_url, "issuer": named_issuer, "client_id": named_client_id}
    official = {
        "api_url": OFFICIAL_API_URL,
        "issuer": OFFICIAL_ISSUER,
        "client_id": OFFICIAL_CLIENT_ID,
    }
    elsewhere = tuple(
        key for key, value in named.items() if value and not _is_official(value, official[key])
    )
    if elsewhere:
        return Settings(named_api_url, named_issuer, named_client_id, named_elsewhere=elsewhere)
    return Settings(OFFICIAL_API_URL, OFFICIAL_ISSUER, OFFICIAL_CLIENT_ID, defaulted=True)
