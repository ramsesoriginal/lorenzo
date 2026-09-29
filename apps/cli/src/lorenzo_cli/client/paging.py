"""Walking a paginated list (`Page_X_`: items, total, page, size, pages)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from lorenzo_cli.client.ops import Op
from lorenzo_cli.client.transport import LorenzoClient

PAGE_SIZE = 100


def all_items[T](
    client: LorenzoClient,
    op: Op[Any],
    *,
    path: Mapping[str, object] | None = None,
    query: Mapping[str, Any] | None = None,
    of: type[T],
) -> Iterator[T]:
    """Every item of every page of a list operation. `of` is only for the type checker."""
    page = 1
    while True:
        result = client.call(
            op, path=path, query={**(query or {}), "page": page, "size": PAGE_SIZE}
        ).value
        yield from result.items
        if page >= result.pages:
            return
        page += 1
