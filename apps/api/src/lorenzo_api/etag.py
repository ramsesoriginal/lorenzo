"""Optimistic concurrency via If-Match - see ADR 0032/RFC 0005. Every table
already carries `updated_at` (ADR 0018); a weak ETag derived from it costs
no new column. Deliberately optional on every write route that accepts it:
a caller that doesn't send If-Match gets last-write-wins, same as before
this existed - one that does gets a real guard against clobbering a
concurrent edit.
"""

from __future__ import annotations

from datetime import datetime

from lorenzo_api.exceptions import PreconditionFailedError


def etag_for(updated_at: datetime) -> str:
    return f'W/"{updated_at.isoformat()}"'


def check_if_match(if_match: str | None, *, updated_at: datetime) -> None:
    if if_match is not None and if_match != etag_for(updated_at):
        raise PreconditionFailedError(
            detail="Resource has been modified since If-Match's ETag was computed"
        )
