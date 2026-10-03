"""`lorenzo api METHOD PATH`: one authenticated request, for scripts (ADR 0161).

The rules that matter are the ones that keep it safe: it takes a path, never a URL, so the token
goes only to the API the person named; and it sends the body exactly as written, once it has been
checked to be JSON.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import parse_qsl, urlsplit

import httpx

from lorenzo_cli.client.transport import LorenzoClient, problem_message, read_problem

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
_BODY_METHODS = ("POST", "PUT", "PATCH")
_PAGE_SIZE = 100


class RequestUsageError(Exception):
    """The request as asked for can't be made; `hint` names the argument or option at fault."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.hint = hint


def check_method(method: str) -> str:
    upper = method.upper()
    if upper not in METHODS:
        raise RequestUsageError(f"“{method}” isn't one of {', '.join(METHODS)}.", "METHOD")
    return upper


def check_path(path: str) -> str:
    """A path on the API: it starts with one slash and names no scheme and no host."""
    parts = urlsplit(path)
    if not path.startswith("/") or path.startswith("//") or parts.scheme or parts.netloc:
        raise RequestUsageError(
            "Give a path on the API, like /tenants. The CLI only talks to the API you named, so "
            "a full address is refused.",
            "PATH",
        )
    if any(ord(character) < 0x20 or character == "\x7f" for character in path):
        raise RequestUsageError("That path has a control character in it.", "PATH")
    return path


def read_body(data: str | None, method: str, stdin: TextIO) -> bytes | None:
    """The request body: JSON text, `@file`, or `-` for stdin; checked to be JSON before sending."""
    if data is None:
        return None
    if method not in _BODY_METHODS:
        raise RequestUsageError(f"{method} takes no body: use POST, PUT or PATCH.", "--data")
    if data == "-":
        text = stdin.read()
    elif data.startswith("@"):
        try:
            text = Path(data[1:]).read_text(encoding="utf-8")
        except OSError as exc:
            raise RequestUsageError(f"Couldn't read {data[1:]}: {exc.strerror}.", "--data") from exc
    else:
        text = data
    try:
        json.loads(text)
    except ValueError as exc:
        raise RequestUsageError(f"The body isn't valid JSON: {exc}.", "--data") from exc
    return text.encode("utf-8")


def parse_query(pairs: Sequence[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key:
            raise RequestUsageError(f"“{pair}” should be KEY=VALUE.", "--query")
        parsed.append((key, value))
    return parsed


def send(
    client: LorenzoClient,
    method: str,
    path: str,
    *,
    query: Sequence[tuple[str, str]] = (),
    body: bytes | None = None,
    if_match: str | None = None,
) -> httpx.Response:
    # httpx replaces a URL's own query when it is given parameters, so the path's is read out and
    # joined to the rest here, and the path is sent without it.
    parts = urlsplit(path)
    pairs = [*parse_qsl(parts.query, keep_blank_values=True), *query]
    # Grouped, because the client's mapping form would keep only the last of a repeated key.
    grouped: dict[str, list[str]] = {}
    for key, value in pairs:
        grouped.setdefault(key, []).append(value)
    return client.send(
        method,
        parts.path,
        query={k: v if len(v) > 1 else v[0] for k, v in grouped.items()},
        content=body,
        if_match=if_match,
    )


def paginate(
    client: LorenzoClient, path: str, *, query: Sequence[tuple[str, str]] = ()
) -> tuple[httpx.Response, list[Any] | None]:
    """Every item of every page of a list, as one array.

    Returns the last response read, and the items; the items are None when the answer isn't a
    page (or a page was refused), and then the response is what to print, as it came.
    """
    items: list[Any] = []
    page = 1
    while True:
        response = send(
            client,
            "GET",
            path,
            query=[*query, ("page", str(page)), ("size", str(_PAGE_SIZE))],
        )
        if response.is_error:
            return response, None
        try:
            body = response.json()
        except ValueError:
            return response, None
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            return response, None
        items.extend(body["items"])
        pages = body.get("pages")
        if not isinstance(pages, int) or page >= pages:
            return response, items
        page += 1


def status_line(response: httpx.Response) -> str:
    version = response.http_version.removeprefix("HTTP/")
    return f"HTTP/{version} {response.status_code} {response.reason_phrase}"


def header_lines(response: httpx.Response) -> list[str]:
    return [f"{name}: {value}" for name, value in response.headers.multi_items()]


def pretty(content: bytes) -> bytes:
    """JSON re-indented; anything else, or JSON that doesn't parse, exactly as it came."""
    try:
        parsed = json.loads(content)
    except ValueError:
        return content
    return (json.dumps(parsed, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def failure_summary(response: httpx.Response) -> str:
    detail = problem_message(response.status_code, read_problem(response))
    return f"HTTP {response.status_code}: {detail}"
