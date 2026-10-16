"""The bulk entity export (ADR 0262, RFC 0039 W3): the revision that is its ETag and the cursor
that pages it.

The ETag stands for the representation a caller gets, and that depends on two things: what is in
the tenant (`tenant.export_revision`, moved by deferred triggers on the tables the export shows)
and what this caller may read of it (the information visibility of ADR 0028, a function of
ownership, containment, group and campaign standing that no trigger of ours watches). So the token
is the revision joined to a short digest of the caller's resolved visibility: a change to either
makes a different token, and two callers who read differently never share one.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.etag import matches_if_none_match
from lorenzo_api.exceptions import InvalidExportCursorError
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Tenant

__all__ = [
    "decode_cursor",
    "encode_cursor",
    "etag_header",
    "export_token",
    "matches_if_none_match",
    "read_revision",
]


async def read_revision(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    """The tenant's revision. Read before the rows of the export, so that a write landing in
    between leaves the token older than the data and never newer: a client then fetches once more
    than it needed to, and never keeps a mirror a revision ahead of what it holds."""
    revision = await session.scalar(select(Tenant.export_revision).where(Tenant.id == tenant_id))
    return revision or 0


def _visibility_digest(visibility: InformationVisibility) -> str:
    parts = [
        f"admin={visibility.is_admin};author={visibility.author_sees_all}",
        *(f"{name}={sorted(map(str, ids))}" for name, ids in _id_sets(visibility)),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def _id_sets(visibility: InformationVisibility) -> list[tuple[str, frozenset[uuid.UUID]]]:
    return [
        ("players", visibility.player_ids),
        ("knowers", visibility.knower_entity_ids),
        ("gm", visibility.gm_reachable_entity_ids),
        ("hidden_entries", visibility.hidden_entry_ids),
        ("author_entries", visibility.author_entry_ids),
    ]


def export_token(revision: int, visibility: InformationVisibility) -> str:
    return f"{revision}.{_visibility_digest(visibility)}"


def etag_header(token: str) -> str:
    return f'W/"{token}"'


def encode_cursor(token: str, after: uuid.UUID) -> str:
    raw = json.dumps({"t": token, "a": str(after)}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    """The token the export began with and the last id it returned."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return str(data["t"]), uuid.UUID(data["a"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise InvalidExportCursorError(detail="This is not a cursor of this export") from exc
