"""A character's inventory as a file (ADR 0193): what they own, where it is, and what was written
about it, in the shape `lorenzo inventory import --add` reads back.

An item's own id goes in `ref` (so a re-import moves it rather than making a second) and its
prototype's in `item`. What is written about it is read from the two notes an import writes,
"Note" and "Details".
"""

from __future__ import annotations

import re
from uuid import UUID

from lorenzo_cli.client.models import InformationOut, ItemInstanceOut, PayloadDescriptionOut
from lorenzo_cli.client.ops import LIST_ENTITY_INFORMATION, LIST_ITEM_INSTANCES_OWNED_BY
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.inventory.format import Inventory, Line

_WEIGHT = re.compile(r"^(\d+(?:\.\d+)?)\s*lb$")


def _text(info: InformationOut) -> str:
    return "\n".join(
        p.root.content for p in info.payloads if isinstance(p.root, PayloadDescriptionOut)
    )


def _read_notes(client: LorenzoClient, tenant_id: UUID, line: Line, instance_id: UUID) -> None:
    for info in all_items(
        client,
        LIST_ENTITY_INFORMATION,
        path={"tenant_id": tenant_id, "entity_id": instance_id},
        query={"type": "note"},
        of=InformationOut,
    ):
        text = _text(info)
        if info.title == "Note":
            line.note = text or None
        elif info.title == "Details":
            for row in text.splitlines():
                label, _, value = row.partition(":")
                value = value.strip()
                if label == "Weight" and (m := _WEIGHT.match(value)):
                    line.weight = float(m[1])
                elif label in ("Value", "Kind", "Place") and value:
                    setattr(line, label.lower(), value)


def export_inventory(
    client: LorenzoClient, tenant_id: UUID, owner_id: UUID, owner_name: str, library: str
) -> Inventory:
    found = client.call(
        LIST_ITEM_INSTANCES_OWNED_BY, path={"tenant_id": tenant_id, "owner_entity_id": owner_id}
    ).value
    instances: dict[UUID, ItemInstanceOut] = {}
    group_names: dict[UUID, str] = {}
    for group in found.groups:
        for instance in group.item_instances:
            instances[instance.entity_id] = instance
        if group.container is not None:
            group_names[group.container.id] = group.container.name

    lines: dict[UUID, Line] = {}
    for instance_id, instance in instances.items():
        line = Line(
            name=instance.title,
            quantity=instance.quantity or 1,
            ref=str(instance_id),
            item=str(instance.prototype_ids[0]) if instance.prototype_ids else None,
        )
        _read_notes(client, tenant_id, line, instance_id)
        lines[instance_id] = line

    inventory = Inventory(owner=owner_name, library=library)
    for instance_id, instance in sorted(instances.items(), key=lambda kv: kv[1].title.lower()):
        line, container = lines[instance_id], instance.container_entity_id
        if container is None:
            inventory.not_carried.append(line)
        elif container == owner_id:
            inventory.equipped.append(line)
        elif container in lines:
            lines[container].contents.append(line)
        else:
            # Inside something that is not the owner's own: it is theirs, and not with them.
            line.place = line.place or f"in {group_names.get(container, 'something else')}"
            inventory.not_carried.append(line)
    return inventory
