"""Settings read from the environment (README lists them)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


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
            raise ConfigError("Say which API to talk to: set LORENZO_API_URL or pass --api-url.")
        return self.api_url


def load_settings(env: Mapping[str, str], *, api_url: str | None = None) -> Settings:
    return Settings(
        api_url=api_url or env.get("LORENZO_API_URL") or None,
        issuer=env.get("LORENZO_AUTHGEAR_ISSUER") or None,
        client_id=env.get("LORENZO_AUTHGEAR_CLIENT_ID") or None,
    )
