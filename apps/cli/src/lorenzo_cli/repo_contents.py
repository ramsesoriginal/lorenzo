"""What a repository tenant holds (ADR 0169, ADR 0492): whether it is published and to whom it is
granted, what it is built on, and how much of each kind of row it holds."""

from __future__ import annotations

from dataclasses import dataclass

from lorenzo_cli import repos
from lorenzo_cli.client.models import (
    PageItemOut,
    StatDefinitionOut,
    StatGroupOut,
    SubscriptionOut,
    TenantOut,
)
from lorenzo_cli.client.ops import (
    LIST_ATTACHMENTS,
    LIST_ITEMS,
    LIST_STAT_DEFINITIONS,
    LIST_STAT_GROUPS,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient


@dataclass(frozen=True)
class Contents:
    tenant: TenantOut
    granted_to: int
    # The repositories it has copied: what it is built on (ADR 0120).
    built_on: list[SubscriptionOut]
    stat_groups: int
    stat_definitions: int
    # Every item, the categories included.
    items: int
    # The parents it adds to items copied from elsewhere (ADR 0172, 0174).
    attachments: int


def read_contents(client: LorenzoClient, repository: TenantOut) -> Contents:
    path = {"tenant_id": repository.id}
    groups = list(all_items(client, LIST_STAT_GROUPS, path=path, of=StatGroupOut))
    definitions = list(all_items(client, LIST_STAT_DEFINITIONS, path=path, of=StatDefinitionOut))
    # One request for each total, however many rows there are.
    page: PageItemOut = client.call(LIST_ITEMS, path=path, query={"page": 1, "size": 1}).value
    attached = client.call(LIST_ATTACHMENTS, path=path, query={"page": 1, "size": 1}).value
    subscribers = repos.list_subscribers(client, repository.id)
    built_on = [row for row in repos.list_repositories(client, repository.id) if row.copied_at]
    return Contents(
        tenant=repository,
        granted_to=len(subscribers),
        built_on=built_on,
        stat_groups=len(groups),
        stat_definitions=len(definitions),
        items=page.total,
        attachments=attached.total,
    )
