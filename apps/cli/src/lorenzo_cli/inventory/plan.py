"""What an import would make (ADR 0193), worked out before anything is written.

Everything that can be said about a file without making it is said here: what each line becomes,
what it cannot become, and why. `apply` then does what the plan says and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from lorenzo_cli.client.models import TenantOut
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


def owned_instances(client: LorenzoClient, tenant_id: UUID, owner_id: UUID) -> set[UUID]:
    found = client.call(
        LIST_ITEM_INSTANCES_OWNED_BY, path={"tenant_id": tenant_id, "owner_entity_id": owner_id}
    ).value
    return {item.entity_id for group in found.groups for item in group.item_instances}


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
) -> Plan:
    """Raises `SelfServiceError` when the owner cannot be picked."""
    reference = owner or inventory.owner
    if reference is None:
        raise SelfServiceError(
            "Whose inventory is this? Name the character with --owner, "
            "or in the file's “owner:” line."
        )
    owner_id, owner_name = resolve_owner(client, tenant.id, reference)
    plan = Plan(tenant, owner_id, owner_name, add=add)
    plan.problems.extend(inventory.problems)
    plan.warnings.extend(inventory.warnings)
    hint = _library_hint(inventory, tenant)
    if hint is not None:
        plan.problems.append(hint)
    if plan.problems:
        return plan

    instances = owned_instances(client, tenant.id, owner_id)
    plan.existing = len(instances)
    if instances and not add:
        plan.problems.append(
            Remark(
                0,
                f"{owner_name} already has {len(instances)} thing(s): "
                "import only makes, so add --add to bring more in",
            )
        )
        return plan

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
