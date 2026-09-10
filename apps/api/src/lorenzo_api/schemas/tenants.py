import uuid
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import Tenant

__all__ = ["TenantOut", "TenantRole", "TenantSummaryOut"]

TenantRole = Literal["owner", "orga", "participant"]


class TenantSummaryOut(BaseModel):
    """One row of `GET /tenants` - every tenant the caller belongs to in
    any capacity. `role` is derived, not a plain column, so this needs an
    explicit constructor rather than `from_attributes=True` alone (ADR
    0020's own precedent for anything needing data beyond a bare ORM
    attribute copy). See ADR 0030/RFC 0003.
    """

    id: uuid.UUID
    slug: str
    name: str
    role: TenantRole

    @classmethod
    def from_tenant(cls, tenant: Tenant, *, role: TenantRole) -> Self:
        return cls(id=tenant.id, slug=tenant.slug, name=tenant.name, role=role)


class TenantOut(BaseModel):
    """GET /tenants/{id} - the full detail shape. No role here: the caller
    already knows they're at least a tenant-wide member, since
    get_tenant_context gates this route."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str
