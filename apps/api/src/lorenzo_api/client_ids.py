"""Ids made by the client (ADR 0222, RFC 0039 W2).

A create that Bench queues takes an optional `id`, so a later command can name something an
earlier command, not yet sent, will make, and so a create that is sent twice is not made twice.

- A row with that id **visible in the caller's tenant** (row-level security decides what is
  visible) means the create was already done: the existing row is returned, with 200, and nothing
  is written.
- Otherwise the row is inserted with that id. If the id is taken by a row the caller cannot see,
  the insert fails on the primary key and the answer is a **generic 409**: it never says the id
  belongs to another tenant, so an id is not a way to find out what other tenants hold.
"""

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import ClientIdUnavailableError


async def existing_in_tenant[T](
    session: AsyncSession, model: type[T], row_id: uuid.UUID, tenant_id: uuid.UUID
) -> T | None:
    """The row with this id if the caller's tenant can see it, else None. The tenant is checked
    as well as the row-level policy, so a missing policy cannot make another tenant's row a
    replay."""
    row: Any = await session.get(model, row_id)
    if row is None or getattr(row, "tenant_id", tenant_id) != tenant_id:
        return None
    return row  # type: ignore[no-any-return]


async def insert_with_client_id(session: AsyncSession, row: object) -> None:
    """Adds and flushes the row, whose primary key the client chose. A clash on that key is the
    generic 409; any other integrity error is not ours to translate and is raised as it is."""
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError as error:
        if "pkey" not in str(error.orig):
            raise
        raise ClientIdUnavailableError(detail="That id is not available.") from error
