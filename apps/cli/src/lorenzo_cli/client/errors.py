"""The errors the client raises (ADR 0137), shaped like packages/api-client's."""

from __future__ import annotations

from typing import Any


class LorenzoApiError(Exception):
    """apps/api answered with an error status.

    Every apps/api error is an RFC 9457 `application/problem+json` body (ADR 0020); the message
    is its `detail`, then its `title`, then `Request failed (N)`, and the whole body is kept.
    """

    def __init__(self, message: str, status: int, problem: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.problem: dict[str, Any] = problem or {}

    @property
    def problem_type(self) -> str | None:
        value = self.problem.get("type")
        return value if isinstance(value, str) else None


class StaleResourceError(LorenzoApiError):
    """`412`: the resource changed since it was read. Re-read it and re-plan."""


class LorenzoConnectionError(Exception):
    """The API couldn't be reached (after the retries a safe method gets)."""


class LorenzoResponseError(Exception):
    """The API answered with a body the CLI's models don't accept.

    Usually the CLI is older or newer than the API: upgrade it, or regenerate the models.
    """
