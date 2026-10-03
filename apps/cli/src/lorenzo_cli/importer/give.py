"""Handing a pack out (RFC 0032, ADR 0150): one call to the API, which reads the pack's list from
its public description and creates what it names in one transaction (ADR 0149).

The CLI no longer reads the list or creates anything itself: all it does is turn the two names it
was given into ids, make the call, and put the API's refusals into words.
"""

from __future__ import annotations

from uuid import UUID

from lorenzo_cli.client.errors import LorenzoApiError
from lorenzo_cli.client.models import GivePackRequest, PackGivenOut, PackItemOut
from lorenzo_cli.client.ops import CREATE_ITEM_INSTANCES_FROM_PACK
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer import tenant_view


class PackError(Exception):
    """The pack can't be handed out as it is."""


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
    owner: str,
    *,
    override: bool = False,
    dry_run: bool = False,
) -> PackGivenOut:
    """What the API made for `owner` (a being or group) from `pack`, or with `dry_run` would."""
    pack_id = entity_id_of(client, tenant_id, pack, "pack")
    owner_id = entity_id_of(client, tenant_id, owner, "being or group")
    try:
        return client.call(
            CREATE_ITEM_INSTANCES_FROM_PACK,
            path={"tenant_id": tenant_id},
            query={"dry_run": True if dry_run else None},
            body=GivePackRequest(pack_id=pack_id, owner_entity_id=owner_id, override=override),
        ).value
    except LorenzoApiError as exc:
        raise _in_words(exc, pack) from exc


def _in_words(error: LorenzoApiError, pack: str) -> Exception:
    """The API's refusals that have something to say beyond their status, as the CLI says them."""
    if error.problem_type == "not-a-pack":
        return PackError(
            f"“{pack}” isn't a pack: it has no contents list in its public description, so "
            "there is nothing to hand out."
        )
    lines = error.problem.get("lines")
    if error.problem_type == "pack-list" and isinstance(lines, list):
        listed = "".join(f"\n  - {line}" for line in lines)
        return PackError(f"“{pack}” can't be handed out as it is:{listed}")
    return error


def tree_lines(given: PackGivenOut) -> list[str]:
    """One line for each instance, indented by what it is inside, as `5 x Rations` where it has a
    count and by name alone where it doesn't (the top of a group's pack)."""
    lines: list[str] = []

    def walk(entries: list[PackItemOut], depth: int) -> None:
        for entry in entries:
            made = entry.item_instance
            count = f"{made.quantity} x " if made.quantity is not None else ""
            lines.append(f"{'  ' * depth}{count}{made.title}")
            walk(entry.children, depth + 1)

    walk(given.created, 0)
    return lines


def count_instances(given: PackGivenOut) -> int:
    def walk(entries: list[PackItemOut]) -> int:
        return sum(1 + walk(entry.children) for entry in entries)

    return walk(given.created)
