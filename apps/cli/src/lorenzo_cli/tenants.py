"""Finding a tenant by id or by slug.

`GET /tenants/{id}` takes only an id, and no endpoint looks a tenant up by slug (ADR 0135), so a
slug is found among the caller's own tenants, the list `GET /tenants` returns.
"""

from __future__ import annotations

from uuid import UUID

from lorenzo_cli.client.models import TenantOut
from lorenzo_cli.client.ops import GET_TENANT, LIST_TENANTS
from lorenzo_cli.client.transport import LorenzoClient

_PAGE_SIZE = 100


class TenantNotFoundError(Exception):
    """No tenant of yours has that id or slug."""


def _as_uuid(reference: str) -> UUID | None:
    try:
        return UUID(reference)
    except ValueError:
        return None


def resolve_tenant(client: LorenzoClient, reference: str) -> TenantOut:
    tenant_id = _as_uuid(reference)
    if tenant_id is None:
        tenant_id = _id_from_slug(client, reference)
    return client.call(GET_TENANT, path={"tenant_id": tenant_id}).value


def _id_from_slug(client: LorenzoClient, slug: str) -> UUID:
    page = 1
    while True:
        result = client.call(LIST_TENANTS, query={"page": page, "size": _PAGE_SIZE}).value
        for summary in result.items:
            if summary.slug == slug:
                return summary.id
        if page >= result.pages:
            raise TenantNotFoundError(f"There's no tenant “{slug}” among the ones you belong to.")
        page += 1
