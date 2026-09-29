"""Handing a pack out (RFC 0025 R7, ADR 0145): read the contents list from the pack's description,
create the container, then what is in it, each with its quantity.

This is client-side orchestration over routes that exist, not an `apps/api` capability: the pack
is data in the tenant (so it travels with a repository copy), and any client can read it the same
way.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from lorenzo_cli.client.models import ItemInstanceCreate
from lorenzo_cli.client.ops import CREATE_ITEM_INSTANCE
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer import tenant_view
from lorenzo_cli.importer.packs import PackLine, parse_description

# Several of one thing that are not in a container are each their own instance; this is a guard
# against a typo, not a rule.
MAX_LOOSE = 50


class PackError(Exception):
    """The pack can't be handed out as it is."""


@dataclass
class Group:
    """A line and what is inside it."""

    line: PackLine
    children: list[PackLine] = field(default_factory=list)


@dataclass(frozen=True)
class Given:
    text: str
    created: int


def groups_of(lines: list[PackLine]) -> list[Group]:
    groups: list[Group] = []
    for line in lines:
        if line.depth == 0 or not groups:
            groups.append(Group(line))
        else:
            groups[-1].children.append(line)
    return groups


def description_text(client: LorenzoClient, tenant_id: UUID, entity_id: UUID) -> str:
    detail = tenant_view.entity_detail(client, tenant_id, entity_id)
    texts: list[str] = []
    for information in detail.information:
        if information.type != "description":
            continue
        for payload in information.payloads:
            if payload.root.kind == "description":
                texts.append(payload.root.content)
    return "\n".join(texts)


def entity_id_of(client: LorenzoClient, tenant_id: UUID, reference: str, what: str) -> UUID:
    """An id, or a slug looked up in the tenant."""
    try:
        return UUID(reference)
    except ValueError:
        pass
    found = tenant_view.resolve_slugs(client, tenant_id, [reference])
    if reference not in found:
        raise PackError(f"There is no {what} “{reference}” in this tenant.")
    return found[reference].entity_id


def give_pack(
    client: LorenzoClient,
    tenant_id: UUID,
    pack: str,
    *,
    owner: UUID | None = None,
    into: UUID | None = None,
    dry_run: bool = False,
    say: Callable[[str], None] = lambda _: None,
) -> list[Given]:
    pack_id = entity_id_of(client, tenant_id, pack, "pack")
    lines = parse_description(description_text(client, tenant_id, pack_id))
    if not lines:
        raise PackError(
            f"“{pack}” has no contents list in its description, so there is nothing to hand out."
        )
    groups = groups_of(lines)

    linked = sorted({line.slug for line in lines if line.slug})
    found = tenant_view.resolve_slugs(client, tenant_id, linked)
    absent = [slug for slug in linked if slug not in found]
    if absent:
        raise PackError(
            "These items in the pack aren't in this tenant (was the whole import copied?): "
            + ", ".join(absent)
        )

    given: list[Given] = []

    def create(line: PackLine, container: UUID | None, quantity: int) -> UUID | None:
        assert line.slug is not None
        text = f"{quantity} x {line.label}"
        if dry_run:
            given.append(Given(text, quantity))
            say(f"would create {text}")
            return None
        fields: dict[str, object] = {
            "prototype_id": found[line.slug].entity_id,
            "quantity": quantity,
        }
        if container is not None:
            fields["container_entity_id"] = container
        if owner is not None:
            fields["owner_character_id"] = owner
        made = client.call(
            CREATE_ITEM_INSTANCE,
            path={"tenant_id": tenant_id},
            body=ItemInstanceCreate.model_validate(fields),
        ).value
        given.append(Given(text, quantity))
        say(f"created {text}")
        return made.entity_id

    for group in groups:
        top = group.line
        if top.slug is None:
            say(f"skipped {top.label}: it isn't a catalog item")
            continue
        if group.children:
            for _ in range(top.quantity):
                container = create(top, into, 1)
                for child in group.children:
                    if child.slug is None:
                        say(f"skipped {child.label}: it isn't a catalog item")
                        continue
                    create(child, container, child.quantity)
        elif into is not None:
            create(top, into, top.quantity)
        else:
            if top.quantity > MAX_LOOSE:
                raise PackError(f"{top.quantity} loose {top.label} is more than {MAX_LOOSE}.")
            for _ in range(top.quantity):
                create(top, None, 1)
    return given
