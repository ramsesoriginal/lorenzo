"""Adding a parent to an item that has some already (ADR 0172, 0181, 0182): the seed's
attachments, and the importer's system pass, both do it the one way."""

from __future__ import annotations

from uuid import UUID

from lorenzo_cli.client.models import SetPrototypesRequest
from lorenzo_cli.client.ops import GET_ITEM, REPLACE_ITEM_PROTOTYPES
from lorenzo_cli.client.transport import LorenzoClient


def add_parent(client: LorenzoClient, tenant_id: UUID, child_id: UUID, parent_id: UUID) -> bool:
    """Append `parent_id` to the child's parents unless it has it.

    The API replaces the set, so the child is read first and written back with its own parents and
    one more, with the ETag it came with: a change in between is a refusal, never a lost parent.
    Returns whether it was added.
    """
    path = {"tenant_id": tenant_id, "entity_id": child_id}
    current = client.call(GET_ITEM, path=path)
    have = list(current.value.prototype_ids)
    if parent_id in have:
        return False
    client.call(
        REPLACE_ITEM_PROTOTYPES,
        path=path,
        body=SetPrototypesRequest(prototype_ids=[*have, parent_id]),
        if_match=current.etag,
    )
    return True
