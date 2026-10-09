"""What an import would make (ADR 0193), worked out before anything is written.

Everything that can be said about a file without making it is said here: what each line becomes,
what it cannot become, and why. `apply` then does what the plan says and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from lorenzo_cli.client.models import ItemInstanceOut, TenantOut
from lorenzo_cli.client.ops import LIST_ITEM_INSTANCES_OWNED_BY
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


def owned_things(client: LorenzoClient, tenant_id: UUID, owner_id: UUID) -> list[ItemInstanceOut]:
    found = client.call(
        LIST_ITEM_INSTANCES_OWNED_BY, path={"tenant_id": tenant_id, "owner_entity_id": owner_id}
    ).value
    return [item for group in found.groups for item in group.item_instances]


def owned_instances(client: LorenzoClient, tenant_id: UUID, owner_id: UUID) -> set[UUID]:
    return {item.entity_id for item in owned_things(client, tenant_id, owner_id)}


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

    things = owned_things(client, tenant.id, owner_id)
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
        plan.deleting = deletion_order(things)
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
