"""What an import would make (ADR 0193), worked out before anything is written.

Everything that can be said about a file without making it is said here: what each line becomes,
what it cannot become, and why. `apply` then does what the plan says and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from lorenzo_cli.client.models import ItemInstanceOut, TenantOut
from lorenzo_cli.client.ops import LIST_ITEM_INSTANCES, LIST_ITEM_INSTANCES_OWNED_BY
from lorenzo_cli.client.paging import all_items
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.inventory.format import Inventory, Line, Remark
from lorenzo_cli.inventory.matching import Library, Match, match, read_library
from lorenzo_cli.inventory.preprocess import Table
from lorenzo_cli.self_service import SelfServiceError, resolve_owner

Section = Literal["equipped", "not_carried"]


@dataclass
class Step:
    """One line, with what it is matched to and what it sits in."""

    line: Line
    match: Match
    section: Section
    parent: Step | None = None


@dataclass(frozen=True)
class Doomed:
    """A thing `--replace` deletes (ADR 0232)."""

    entity_id: UUID
    name: str


@dataclass(frozen=True)
class Kept:
    """A thing of the being's that `--replace` leaves alone, and why (ADR 0232)."""

    name: str
    why: str


@dataclass
class Plan:
    tenant: TenantOut
    owner_id: UUID
    owner_name: str
    steps: list[Step] = field(default_factory=list)  # a container before what is in it
    problems: list[Remark] = field(default_factory=list)
    warnings: list[Remark] = field(default_factory=list)
    existing: int = 0
    add: bool = False
    replace: bool = False
    deleting: list[Doomed] = field(default_factory=list)  # deepest first, so a container is empty
    keeping: list[Kept] = field(default_factory=list)  # owned, but tied up with someone else's
    placeholder_id: UUID | None = None

    @property
    def placeholders(self) -> list[Step]:
        return [s for s in self.steps if s.match.via == "placeholder"]

    @property
    def moves(self) -> list[Step]:
        return [s for s in self.steps if s.match.via == "instance"]

    @property
    def makes(self) -> list[Step]:
        return [s for s in self.steps if s.match.via != "instance"]


def read_owned(
    client: LorenzoClient, tenant_id: UUID, owner_id: UUID
) -> tuple[list[ItemInstanceOut], dict[UUID, str]]:
    """What the owner owns that the caller can see, and the names of the containers it is in."""
    found = client.call(
        LIST_ITEM_INSTANCES_OWNED_BY, path={"tenant_id": tenant_id, "owner_entity_id": owner_id}
    ).value
    things = [item for group in found.groups for item in group.item_instances]
    names = {g.container.id: g.container.name for g in found.groups if g.container is not None}
    return things, names


def owned_things(client: LorenzoClient, tenant_id: UUID, owner_id: UUID) -> list[ItemInstanceOut]:
    return read_owned(client, tenant_id, owner_id)[0]


def owned_instances(client: LorenzoClient, tenant_id: UUID, owner_id: UUID) -> set[UUID]:
    return {item.entity_id for item in owned_things(client, tenant_id, owner_id)}


def foreign_contents(
    client: LorenzoClient, tenant_id: UUID, owner_id: UUID, things: list[ItemInstanceOut]
) -> dict[UUID, list[str]]:
    """For each container the owner owns: the titles of what is directly in it that someone else
    owns. Only what the caller can see is listed (ADR 0040)."""
    found: dict[UUID, list[str]] = {}
    for thing in things:
        if not thing.is_container:
            continue
        inside = all_items(
            client,
            LIST_ITEM_INSTANCES,
            path={"tenant_id": tenant_id},
            query={"container_id": thing.entity_id},
            of=ItemInstanceOut,
        )
        strangers = [i.title for i in inside if i.owner_entity_id != owner_id]
        if strangers:
            found[thing.entity_id] = strangers
    return found


def split_replacement(
    owner_id: UUID,
    things: list[ItemInstanceOut],
    container_names: dict[UUID, str],
    foreign_inside: dict[UUID, list[str]],
) -> tuple[list[Doomed], list[Kept]]:
    """What `--replace` deletes and what it leaves (ADR 0232). It deletes what the owner owns,
    except:

    - what is in a container someone else owns (even a thing of the owner's own), and what is
      in that, since the container they are all in is not the owner's to empty;
    - a container that holds something someone else owns, and every owned container around it,
      since deleting one would take it from where it is.
    """
    owned = {thing.entity_id: thing for thing in things}
    why: dict[UUID, str] = {}

    def above(thing: ItemInstanceOut) -> list[UUID]:
        """The owned containers around a thing, nearest first (bounded, so a loop ends)."""
        found: list[UUID] = []
        parent = thing.container_entity_id
        while parent in owned and len(found) <= len(owned):
            found.append(parent)
            parent = owned[parent].container_entity_id
        return found

    def stranger_above(thing: ItemInstanceOut) -> UUID | None:
        """The container someone else owns that this is in, at any depth."""
        chain = above(thing)
        top = owned[chain[-1]] if chain else thing
        parent = top.container_entity_id
        return None if parent is None or parent == owner_id or parent in owned else parent

    for thing in things:
        outer = stranger_above(thing)
        if outer is not None:
            name = container_names.get(outer, "something")
            why[thing.entity_id] = f"is in {name}, which isn't theirs"
    for container_id, strangers in foreign_inside.items():
        if container_id in owned:
            names = ", ".join(strangers[:2]) + (", …" if len(strangers) > 2 else "")
            why.setdefault(container_id, f"holds {names}, which isn't theirs")
    for kept_id in list(why):
        for around in above(owned[kept_id]):
            why.setdefault(around, "holds something that stays")

    order = deletion_order([t for t in things if t.entity_id not in why])
    kept = [Kept(owned[i].title, reason) for i, reason in why.items()]
    return order, sorted(kept, key=lambda k: k.name.lower())


def deletion_order(things: list[ItemInstanceOut]) -> list[Doomed]:
    """What `--replace` deletes, deepest first: a container goes after what is in it, so it is
    deleted empty and the API has nothing to move out (ADR 0232)."""
    by_id = {thing.entity_id: thing for thing in things}

    def depth(thing: ItemInstanceOut) -> int:
        level, here = 0, thing
        while level <= len(by_id) and here.container_entity_id in by_id:  # bounded: a loop ends
            here = by_id[here.container_entity_id]
            level += 1
        return level

    ordered = sorted(things, key=lambda t: (-depth(t), t.title.lower(), str(t.entity_id)))
    return [Doomed(thing.entity_id, thing.title) for thing in ordered]


def _library_hint(inventory: Inventory, tenant: TenantOut) -> Remark | None:
    if inventory.library is None:
        return None
    wanted = inventory.library.strip().lower()
    if wanted in {str(tenant.id).lower(), tenant.slug.lower(), tenant.name.lower()}:
        return None
    return Remark(
        0, f"this file was written for “{inventory.library}”, and this library is “{tenant.slug}”"
    )


def build_plan(
    client: LorenzoClient,
    tenant: TenantOut,
    inventory: Inventory,
    *,
    owner: str | None,
    add: bool,
    table: Table,
    replace: bool = False,
) -> Plan:
    """Raises `SelfServiceError` when the owner cannot be picked."""
    if add and replace:
        raise SelfServiceError("--add and --replace are alternatives: choose one.")
    reference = owner or inventory.owner
    if reference is None:
        raise SelfServiceError(
            "Whose inventory is this? Name the character with --owner, "
            "or in the file's “owner:” line."
        )
    owner_id, owner_name = resolve_owner(client, tenant.id, reference)
    plan = Plan(tenant, owner_id, owner_name, add=add, replace=replace)
    plan.problems.extend(inventory.problems)
    plan.warnings.extend(inventory.warnings)
    hint = _library_hint(inventory, tenant)
    if hint is not None:
        plan.problems.append(hint)
    if plan.problems:
        return plan

    things, container_names = read_owned(client, tenant.id, owner_id)
    instances = {thing.entity_id for thing in things}
    plan.existing = len(instances)
    if instances and not (add or replace):
        plan.problems.append(
            Remark(
                0,
                f"{owner_name} already has {len(instances)} thing(s): import only makes, so add "
                "--add to bring more in, or --replace to start over",
            )
        )
        return plan
    if replace:
        # What is deleted cannot be moved, so no line may name one by its id (ADR 0232).
        plan.deleting, plan.keeping = split_replacement(
            owner_id,
            things,
            container_names,
            foreign_contents(client, tenant.id, owner_id, things),
        )
        instances = set()

    top: list[tuple[Line, Section]] = [(line, "equipped") for line in inventory.equipped]
    top += [(line, "not_carried") for line in inventory.not_carried]
    everything = _flat([line for line, _ in top])
    library = read_library(client, tenant.id, everything, instances)
    plan.placeholder_id = library.placeholder_id
    for line, section in top:
        _steps(plan, library, table, line, section, None)

    if plan.placeholders and plan.placeholder_id is None:
        plan.problems.append(
            Remark(
                0,
                f"{len(plan.placeholders)} line(s) match nothing here, and this library has no "
                "“unsorted” item to hold them: its GM runs `lorenzo seed --layer core` to add it",
            )
        )
    return plan


def _flat(lines: list[Line]) -> list[Line]:
    out: list[Line] = []
    for line in lines:
        out.append(line)
        out.extend(_flat(line.contents))
    return out


def _steps(
    plan: Plan, library: Library, table: Table, line: Line, section: Section, parent: Step | None
) -> None:
    found = match(line, library, table)
    step = Step(line, found, section, parent)
    plan.steps.append(step)
    if found.via == "placeholder" and found.note:
        plan.warnings.append(Remark(line.number, found.note))
    for child in line.contents:
        _steps(plan, library, table, child, section, step)
