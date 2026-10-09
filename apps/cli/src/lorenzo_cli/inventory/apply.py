"""Making what a plan says (ADR 0193, 0226): each line as an instance, notes written and told to the
owner's character, what the file puts in the hands picked up, and what it names by id moved.

A line that fails does not stop the rest: it is reported, and what was to go inside it is skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from lorenzo_cli.client.errors import LorenzoApiError
from lorenzo_cli.client.models import (
    InformationCreate,
    ItemInstanceCreate,
    SetContainerRequest,
)
from lorenzo_cli.client.ops import (
    ADD_INFORMATION_KNOWER,
    CLEAR_ITEM_INSTANCE_CONTAINER,
    CREATE_INFORMATION,
    CREATE_ITEM_INSTANCE,
    SET_ITEM_INSTANCE_CONTAINER,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.inventory.format import Line, Remark
from lorenzo_cli.inventory.plan import Plan, Step


@dataclass
class Applied:
    made: int = 0
    moved: int = 0
    placeholders: int = 0
    failed: list[Remark] = field(default_factory=list)
    ids: dict[int, UUID] = field(default_factory=dict)  # file line -> the instance


def details(line: Line) -> str | None:
    """The weight, value, kind and place of a line, as a note for a person to read."""
    rows = []
    if line.weight is not None:
        rows.append(f"Weight: {line.weight:g} lb")
    for label, value in (("Value", line.value), ("Kind", line.kind), ("Place", line.place)):
        if value is not None:
            rows.append(f"{label}: {value}")
    return "\n".join(rows) or None


def _write_note(
    client: LorenzoClient, plan: Plan, instance_id: UUID, title: str, content: str
) -> None:
    """A private note on the instance, then told to the owner's character, which is how a
    player reads what they wrote (ADR 0192)."""
    tenant = {"tenant_id": plan.tenant.id}
    made = client.call(
        CREATE_INFORMATION,
        path={**tenant, "entity_id": instance_id},
        body=InformationCreate(title=title, type="note", is_public=False, content=content),
    ).value
    client.call(
        ADD_INFORMATION_KNOWER,
        path={**tenant, "information_id": made.id, "knower_entity_id": plan.owner_id},
    )


def _place(
    client: LorenzoClient, plan: Plan, step: Step, instance_id: UUID, parent: UUID | None
) -> None:
    """Where the line says it is: in its container, in the hands, or in none (not carried)."""
    path = {"tenant_id": plan.tenant.id, "entity_id": instance_id}
    if parent is not None:
        target = parent
    elif step.section == "equipped":
        target = plan.owner_id
    else:
        if step.match.via == "instance":
            client.call(CLEAR_ITEM_INSTANCE_CONTAINER, path=path)
        return
    client.call(
        SET_ITEM_INSTANCE_CONTAINER, path=path, body=SetContainerRequest(container_entity_id=target)
    )


def apply(
    client: LorenzoClient, plan: Plan, *, progress: Callable[[Step], None] | None = None
) -> Applied:
    done = Applied()
    made: dict[int, UUID | None] = {}  # id(step) -> its instance, or None where it failed

    for step in plan.steps:
        line = step.line
        if progress is not None:
            progress(step)
        parent = made.get(id(step.parent)) if step.parent is not None else None
        if step.parent is not None and parent is None:
            made[id(step)] = None
            done.failed.append(
                Remark(line.number, f"{line.name}: not made, since what it goes in was not")
            )
            continue
        try:
            instance_id = _do(client, plan, step, parent)
        except LorenzoApiError as exc:
            made[id(step)] = None
            done.failed.append(Remark(line.number, f"{line.name}: {exc}"))
            continue
        made[id(step)] = instance_id
        done.ids[line.number] = instance_id
        if step.match.via == "instance":
            done.moved += 1
        else:
            done.made += 1
            done.placeholders += step.match.via == "placeholder"
        # A note that cannot be written leaves the item made, which is worth reporting but not
        # worth undoing.
        for title, content in (
            ("Note", line.note),
            ("Description", line.description),
            ("Details", details(line)),
        ):
            if content is None or step.match.via == "instance":
                continue
            try:
                _write_note(client, plan, instance_id, title, content)
            except LorenzoApiError as exc:
                done.failed.append(
                    Remark(line.number, f"{line.name}: the {title.lower()} was not saved: {exc}")
                )
    return done


def _do(client: LorenzoClient, plan: Plan, step: Step, parent: UUID | None) -> UUID:
    line = step.line
    if step.match.via == "instance":
        assert step.match.instance_id is not None
        _place(client, plan, step, step.match.instance_id, parent)
        return step.match.instance_id
    prototype = step.match.item.entity_id if step.match.item is not None else plan.placeholder_id
    assert prototype is not None
    created = client.call(
        CREATE_ITEM_INSTANCE,
        path={"tenant_id": plan.tenant.id},
        body=ItemInstanceCreate(
            prototype_id=prototype,
            owner_character_id=plan.owner_id,
            container_entity_id=parent,
            quantity=line.quantity if parent is not None else 1,
            name=line.name,
        ),
    ).value
    if parent is None and step.section == "equipped":
        _place(client, plan, step, created.entity_id, None)
    return created.entity_id
