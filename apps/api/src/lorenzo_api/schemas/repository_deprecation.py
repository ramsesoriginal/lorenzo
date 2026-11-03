"""Retiring a repository - ADR 0383, RFC 0038 section 7."""

from pydantic import BaseModel, ConfigDict, field_validator

from lorenzo_api.schemas.repository_profiles import DEPRECATION_MESSAGE_MAX

__all__ = ["DeprecateRequest", "UndeprecatedOut"]


class DeprecateRequest(BaseModel):
    """`PUT .../deprecation`: the optional message the libraries that hold the repository read,
    1 to `DEPRECATION_MESSAGE_MAX` characters when given. Whitespace at the ends is dropped and
    line breaks are kept, since a message is a few sentences; `null` or no body is no message."""

    model_config = ConfigDict(extra="forbid")

    message: str | None = None

    @field_validator("message")
    @classmethod
    def _message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("A message can't be empty; leave it out to retire without one")
        if len(text) > DEPRECATION_MESSAGE_MAX:
            raise ValueError(f"A message is at most {DEPRECATION_MESSAGE_MAX} characters")
        if any(not ch.isprintable() and ch not in "\n\t" for ch in text):
            raise ValueError("Use plain text, without control characters")
        return text


class UndeprecatedOut(BaseModel):
    """`DELETE .../deprecation`: whether the repository was retired (`false`: nothing changed)."""

    undeprecated: bool
