"""Making your own items from the command line (ADR 0190): finding an item and a character by
name, and one `POST .../item-instances`.

Everything about who may is the API's (ADR 0186), answered in its own words. What this checks
itself is only what it can say before asking: a count needs a container, and a name that matches
more than one item is never guessed.
"""

from __future__ import annotations

from uuid import UUID

from lorenzo_cli.client.errors import LorenzoApiError
from lorenzo_cli.client.models import (
    BeingSummaryOut,
    CharacterSummaryOut,
    ItemInstanceCreate,
    ItemInstanceOut,
    ItemOut,
)
from lorenzo_cli.client.ops import (
    CREATE_ITEM_INSTANCE,
    GET_ITEM,
    LIST_BEINGS,
    LIST_CHARACTERS,
    LIST_ITEMS,
)
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer import tenant_view


class SelfServiceError(Exception):
    """A name that doesn't pick exactly one, or a request the API would only refuse."""


def _uuid(reference: str) -> UUID | None:
    try:
        return UUID(reference)
    except ValueError:
        return None


def catalog(client: LorenzoClient, tenant_id: UUID, query: str | None = None) -> list[ItemOut]:
    """The items the caller may list: a player's is the public catalog (ADR 0116)."""
    return list(
        all_items(
            client,
            LIST_ITEMS,
            path={"tenant_id": tenant_id},
            query={"q": query or None},
            of=ItemOut,
        )
    )


def characters(
    client: LorenzoClient, tenant_id: UUID, *, mine: bool = True
) -> list[CharacterSummaryOut]:
    """The caller's own characters, or the library's."""
    return list(
        all_items(
            client,
            LIST_CHARACTERS,
            path={"tenant_id": tenant_id},
            query={"mine": True if mine else None},
            of=CharacterSummaryOut,
        )
    )


def _candidates(found: list[ItemOut]) -> str:
    return "".join(f"\n  - {item.title}  {item.entity_id}" for item in found)


def resolve_item(client: LorenzoClient, tenant_id: UUID, reference: str) -> ItemOut:
    """An item by id, by slug, or by its exact title (case-insensitive)."""
    item_id = _uuid(reference)
    if item_id is None:
        found = tenant_view.resolve_slugs(client, tenant_id, [reference])
        if reference in found:
            item_id = found[reference].entity_id
    if item_id is not None:
        return client.call(GET_ITEM, path={"tenant_id": tenant_id, "entity_id": item_id}).value

    named = [
        item
        for item in catalog(client, tenant_id, reference)
        if item.title.lower() == reference.lower()
    ]
    if len(named) == 1:
        return named[0]
    if not named:
        raise SelfServiceError(
            f"There's no item “{reference}” you can add here. "
            "`lorenzo item list` shows what you can."
        )
    raise SelfServiceError(
        f"More than one item is called “{reference}”: name it by id.{_candidates(named)}"
    )


def beings_named(client: LorenzoClient, tenant_id: UUID, name: str) -> list[BeingSummaryOut]:
    """The beings called exactly `name` (any case) that the caller may list: every being for a
    library's administrators, those in their reach for a GM (ADR 0173). Anyone else is answered
    `404`, and for them there are none (ADR 0232)."""
    try:
        found = list(
            all_items(
                client,
                LIST_BEINGS,
                path={"tenant_id": tenant_id},
                query={"q": name},
                of=BeingSummaryOut,
            )
        )
    except LorenzoApiError as error:
        if error.status in (403, 404):
            return []
        raise
    return [being for being in found if being.name.lower() == name.lower()]


def resolve_owner(
    client: LorenzoClient, tenant_id: UUID, reference: str | None
) -> tuple[UUID, str]:
    """The being to add to, and what to call it: one of your own characters by id or name, or
    your only one when none is named; a GM's or an administrator's, any being they may list by
    its exact name (ADR 0232). Another being's id is passed on, for the API to judge."""
    mine = characters(client, tenant_id)
    if reference is None:
        if len(mine) == 1:
            return mine[0].entity_id, mine[0].name
        if not mine:
            raise SelfServiceError(
                "You don't control any character here: name one with --owner, "
                "or ask your GM for a seat."
            )
        names = "".join(f"\n  - {c.name}  {c.entity_id}" for c in mine)
        raise SelfServiceError(f"You have more than one character: pick one with --owner.{names}")

    owner_id = _uuid(reference)
    for character in mine:
        if character.entity_id == owner_id or character.name.lower() == reference.lower():
            return character.entity_id, character.name
    if owner_id is not None:
        return owner_id, reference
    named = beings_named(client, tenant_id, reference)
    if len(named) == 1:
        return named[0].entity_id, named[0].name
    if named:
        names = "".join(f"\n  - {b.name}  {b.entity_id}" for b in named)
        raise SelfServiceError(
            f"More than one being is called “{reference}”: name it by id.{names}"
        )
    raise SelfServiceError(
        f"None of your characters here is called “{reference}”. "
        "`lorenzo character list` shows them."
    )


def resolve_container(client: LorenzoClient, tenant_id: UUID, reference: str) -> UUID:
    """A container instance, by id or by slug."""
    container_id = _uuid(reference)
    if container_id is not None:
        return container_id
    found = tenant_view.resolve_slugs(client, tenant_id, [reference])
    if reference not in found:
        raise SelfServiceError(
            f"There's no container “{reference}”: "
            "name it by id (`lorenzo item add --json` prints it)."
        )
    return found[reference].entity_id


def add_item(
    client: LorenzoClient,
    tenant_id: UUID,
    item: ItemOut,
    owner_id: UUID,
    *,
    name: str | None = None,
    quantity: int = 1,
    into: UUID | None = None,
) -> ItemInstanceOut:
    """One instance of `item` for `owner_id`: in no container, or `quantity` of it in `into`."""
    if quantity < 1:
        raise SelfServiceError("--quantity must be at least 1.")
    if quantity > 1 and into is None:
        raise SelfServiceError(
            "A stack of more than one needs a container to hold its count: "
            "add --into <container>, or add the item once for each."
        )
    return client.call(
        CREATE_ITEM_INSTANCE,
        path={"tenant_id": tenant_id},
        body=ItemInstanceCreate(
            prototype_id=item.entity_id,
            owner_character_id=owner_id,
            container_entity_id=into,
            quantity=quantity,
            name=name or None,
        ),
    ).value
