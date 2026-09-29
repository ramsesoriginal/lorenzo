"""The importer's reads from a tenant: which slugs exist, which stat definitions, what an existing
item holds."""

from __future__ import annotations

from uuid import UUID

from lorenzo_cli.client.models import (
    EntityDetailOut,
    ResolvedSlugOut,
    StatDefinitionOut,
    StatGroupOut,
)
from lorenzo_cli.client.ops import (
    GET_ENTITY,
    LIST_STAT_DEFINITIONS,
    LIST_STAT_GROUPS,
    RESOLVE_SLUGS,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient

_RESOLVE_BATCH = 100  # GET .../entities/resolve takes at most this many slugs (ADR 0107)


def resolve_slugs(
    client: LorenzoClient, tenant_id: UUID, slugs: list[str]
) -> dict[str, ResolvedSlugOut]:
    found: dict[str, ResolvedSlugOut] = {}
    unique = sorted(set(slugs))
    for start in range(0, len(unique), _RESOLVE_BATCH):
        batch = unique[start : start + _RESOLVE_BATCH]
        for hit in client.call(
            RESOLVE_SLUGS, path={"tenant_id": tenant_id}, query={"slug": batch}
        ).value:
            found[hit.slug] = hit
    return found


def stat_definitions(client: LorenzoClient, tenant_id: UUID) -> dict[str, StatDefinitionOut]:
    path = {"tenant_id": tenant_id}
    return {
        d.name: d for d in all_items(client, LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut)
    }


def stat_groups(client: LorenzoClient, tenant_id: UUID) -> dict[str, StatGroupOut]:
    path = {"tenant_id": tenant_id}
    return {g.name: g for g in all_items(client, LIST_STAT_GROUPS, path=path, of=StatGroupOut)}


def entity_detail(client: LorenzoClient, tenant_id: UUID, entity_id: UUID) -> EntityDetailOut:
    return client.call(GET_ENTITY, path={"tenant_id": tenant_id, "entity_id": entity_id}).value
