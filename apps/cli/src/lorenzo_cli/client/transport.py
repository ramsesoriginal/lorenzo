"""A thin httpx layer over apps/api (ADR 0137), mirroring packages/api-client.

- Bearer auth, and a `401` refreshes the token once and retries.
- `If-Match` from an entity's ETag; a `412` raises StaleResourceError, "re-read and re-plan".
- Only GET, PUT and DELETE are retried on a dropped connection or a 502/503/504, never POST:
  there is no idempotency key, so a repeated POST could create twice.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, Self
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from lorenzo_cli.client.errors import (
    LorenzoApiError,
    LorenzoConnectionError,
    LorenzoResponseError,
    StaleResourceError,
)
from lorenzo_cli.client.ops import Op

_RETRYABLE_METHODS = frozenset({"GET", "PUT", "DELETE"})
_RETRYABLE_STATUSES = frozenset({502, 503, 504})
_BACKOFF_SECONDS = 0.5

# What httpx accepts as a query value; None entries are dropped before sending.
type QueryValue = str | int | float | bool | Sequence[str | int | float | bool] | None


class TokenSource(Protocol):
    def token(self) -> str:
        """The access token to send."""
        ...

    def refresh(self) -> str | None:
        """A fresh token after a `401`, or None if this source can't refresh."""
        ...


@dataclass(frozen=True)
class Reply[T]:
    value: T
    etag: str | None = None


def problem_message(status: int, problem: dict[str, Any]) -> str:
    for key in ("detail", "title"):
        value = problem.get(key)
        if isinstance(value, str) and value:
            return value
    return f"Request failed ({status})"


def read_problem(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


class LorenzoClient:
    def __init__(
        self,
        base_url: str,
        tokens: TokenSource,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._tokens = tokens
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), transport=transport, timeout=timeout
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def call[T](
        self,
        op: Op[T],
        *,
        path: Mapping[str, object] | None = None,
        query: Mapping[str, QueryValue] | None = None,
        body: Any = None,
        if_match: str | None = None,
    ) -> Reply[T]:
        """Run one operation. `body` is a request model instance; only the fields set are sent."""
        response = self.send(
            op.method,
            self._url(op, path or {}),
            query=query,
            json_body=None if body is None else body.model_dump(mode="json", exclude_unset=True),
            if_match=if_match,
        )
        return self._reply(op, response)

    def send(
        self,
        method: str,
        url: str,
        *,
        query: Mapping[str, QueryValue] | None = None,
        json_body: Any = None,
        content: bytes | None = None,
        if_match: str | None = None,
    ) -> httpx.Response:
        """One request, answered whatever its status, with the rules every request gets: the
        bearer token, one renewal after a `401`, and retries of a safe method. `content` is a
        body sent as it is, as JSON (`lorenzo api`, ADR 0161); `json_body` is encoded here."""
        params = {k: v for k, v in (query or {}).items() if v is not None}
        headers = {"Authorization": f"Bearer {self._tokens.token()}"}
        if if_match is not None:
            headers["If-Match"] = if_match
        if content is not None:
            headers["Content-Type"] = "application/json"

        attempts = self._max_attempts if method in _RETRYABLE_METHODS else 1
        attempt = 1
        refreshed = False
        while True:
            try:
                response = self._http.request(
                    method,
                    url,
                    params=params or None,
                    headers=headers,
                    json=json_body,
                    content=content,
                )
            except httpx.TransportError as exc:
                if attempt >= attempts:
                    raise LorenzoConnectionError(
                        f"Couldn't reach the API for {method} {url}: {exc}"
                    ) from exc
                self._sleep(_BACKOFF_SECONDS * attempt)
                attempt += 1
                continue
            if response.status_code == 401 and not refreshed:
                refreshed = True
                fresh = self._tokens.refresh()
                if fresh is not None:
                    headers["Authorization"] = f"Bearer {fresh}"
                    continue
            if response.status_code in _RETRYABLE_STATUSES and attempt < attempts:
                self._sleep(_BACKOFF_SECONDS * attempt)
                attempt += 1
                continue
            return response

    @staticmethod
    def _url(op: Op[Any], path: Mapping[str, object]) -> str:
        try:
            return op.path.format(**{k: quote(str(v), safe="") for k, v in path.items()})
        except KeyError as exc:
            raise ValueError(f"{op.operation_id} needs the path parameter {exc}") from exc

    @staticmethod
    def _reply[T](op: Op[T], response: httpx.Response) -> Reply[T]:
        if response.is_error:
            problem = read_problem(response)
            message = problem_message(response.status_code, problem)
            error_type = StaleResourceError if response.status_code == 412 else LorenzoApiError
            raise error_type(message, response.status_code, problem)
        etag = response.headers.get("ETag")
        if op.adapter is None or not response.content:
            return Reply(None, etag)  # type: ignore[arg-type]
        try:
            return Reply(op.adapter.validate_json(response.content), etag)
        except ValidationError as exc:
            raise LorenzoResponseError(
                f"{op.operation_id} answered with a body the CLI doesn't understand "
                f"(is the CLI older or newer than the API?): {exc.error_count()} problem(s)"
            ) from exc
