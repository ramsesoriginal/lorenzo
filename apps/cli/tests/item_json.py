"""An item as the API answers it, for the fakes that stand in for the API."""

from __future__ import annotations

import uuid
from typing import Any


def item_json() -> dict[str, Any]:
    return {
        "entity_id": str(uuid.uuid4()),
        "title": "x",
        "weight": None,
        "height": None,
        "price": None,
        "rarity": None,
        "hp": None,
        "armor": None,
        "container_entity_id": None,
        "prototype_ids": [],
        "is_container": None,
        "descriptions": [],
        "pictures": [],
        "physical_stats": [],
        "economic_stats": [],
        "destroyable_stats": [],
        "damaging_stats": [],
        "tags": [],
        "quantity": None,
        "created_by": None,
        "updated_by": None,
        "updated_at": "2026-10-04T00:00:00Z",
        "in_public_catalog": False,
        "starts_inactive": False,
    }
