"""The operations the CLI calls (ADR 0137): `operationId` to method, path and models.

A test checks every entry against apps/api's dumped OpenAPI document, which gives the
path-level safety packages/api-client gets from its generated types. Add an operation here when
a command first needs it, not before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, TypeAdapter

from lorenzo_cli.client.models import PageTenantSummaryOut, TenantOut


@dataclass(frozen=True)
class Op[T]:
    """One API operation. `response_type` is a model class, `list[Model]`, or None (no body)."""

    operation_id: str
    method: str
    path: str
    request_type: type[BaseModel] | None = None
    response_type: Any = None
    adapter: TypeAdapter[T] | None = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.response_type is not None:
            object.__setattr__(self, "adapter", TypeAdapter(self.response_type))


GET_TENANT: Op[TenantOut] = Op("get_tenant", "GET", "/tenants/{tenant_id}", response_type=TenantOut)
LIST_TENANTS: Op[PageTenantSummaryOut] = Op(
    "list_tenants", "GET", "/tenants", response_type=PageTenantSummaryOut
)

ALL_OPS: tuple[Op[Any], ...] = (GET_TENANT, LIST_TENANTS)
