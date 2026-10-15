"""Optimistic concurrency via If-Match - see ADR 0032/RFC 0005. Every table
already carries `updated_at` (ADR 0018); a weak ETag derived from it costs
no new column. Deliberately optional on every write route that accepts it:
a caller that doesn't send If-Match gets last-write-wins, same as before
this existed - one that does gets a real guard against clobbering a
concurrent edit.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import TypeAdapter

from lorenzo_api.exceptions import PreconditionFailedError

# The token holds `updated_at` exactly as a JSON response body writes it, so a
# client can build If-Match from a read as well as echo an ETag header back
# (ADR 0101/0108). isoformat() used to write `+00:00` where the body says `Z`.
_TIMESTAMP = TypeAdapter(datetime)


def etag_for(updated_at: datetime) -> str:
    return f'W/"{_TIMESTAMP.dump_python(updated_at, mode="json")}"'


def check_if_match(if_match: str | None, *, updated_at: datetime) -> None:
    if if_match is not None and if_match != etag_for(updated_at):
        raise PreconditionFailedError(
            detail="Resource has been modified since If-Match's ETag was computed"
        )


def matches_if_none_match(if_none_match: str | None, token: str) -> bool:
    """Whether `If-None-Match` names this token (weak comparison, RFC 9110: `W/` is ignored), or
    is `*`."""
    if if_none_match is None:
        return False
    for candidate in if_none_match.split(","):
        candidate = candidate.strip()
        if candidate == "*" or candidate.removeprefix("W/").strip('"') == token:
            return True
    return False
