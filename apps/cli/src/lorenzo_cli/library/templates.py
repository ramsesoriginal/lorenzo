"""Templates as a document writes them (ADR 0487): stat groups and stats by name, the ancestor by
slug, the system by slug or as the document's own; and the API's template the same way back."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from lorenzo_cli.client.models import TemplateIn, TemplateOut
from lorenzo_cli.library.document import SlotRow, SlotStat, TemplateRow


def system_slug(row: TemplateRow, doc_system: str | None) -> str | None:
    """The slug of the system a template belongs to, or None for a template of no system."""
    if row.system is True:
        return doc_system
    if row.system is False:
        return None
    return str(row.system)


def to_body(
    row: TemplateRow,
    *,
    doc_system: str | None,
    system_id: Callable[[str], UUID],
    group_id: Callable[[str], UUID],
    stat_id: Callable[[str], UUID],
    entry_id: Callable[[str], UUID],
) -> TemplateIn:
    slug = system_slug(row, doc_system)
    slots: list[dict[str, Any]] = []
    for slot in row.slot:
        values: dict[str, Any] = {
            "kind": slot.kind,
            "label": slot.label,
            "stat_group_id": group_id(slot.group) if slot.group else None,
            "stats": [
                {"stat_definition_id": stat_id(s.stat), "label": s.label} for s in slot.stat_rows()
            ]
            or None,
            "exclude": [stat_id(name) for name in slot.exclude] if slot.exclude else None,
            "information_type": slot.information_type,
            "held_order": slot.held_order,
        }
        slots.append({k: v for k, v in values.items() if v is not None})
    values = {
        "name": row.name,
        "system_id": system_id(slug) if slug else None,
        "required_kind": row.kind,
        "required_ancestor_entry_id": entry_id(row.ancestor) if row.ancestor else None,
        "slots": slots,
    }
    return TemplateIn(**{k: v for k, v in values.items() if v is not None})


def from_out(
    out: TemplateOut,
    *,
    doc_system: str | None,
    group_name: Callable[[UUID], str],
    stat_name: Callable[[UUID], str],
    entry_slug: Callable[[UUID], str],
) -> TemplateRow:
    slots = []
    for slot in out.slots:
        stats: list[str | SlotStat] = [
            SlotStat(stat=stat_name(s.stat_definition_id), label=s.label)
            if s.label
            else stat_name(s.stat_definition_id)
            for s in slot.stats
        ]
        slots.append(
            SlotRow(
                kind=slot.kind.value,
                label=slot.label,
                group=group_name(slot.stat_group_id) if slot.stat_group_id else None,
                stats=stats or None,
                exclude=[stat_name(i) for i in slot.exclude] or None,
                information_type=slot.information_type,
                held_order=slot.held_order.value if slot.held_order else None,
            )
        )
    system: bool | str = False
    if out.system is not None:
        system = True if out.system == doc_system else out.system
    return TemplateRow(
        name=out.name,
        system=system,
        kind=out.required_kind.value if out.required_kind else None,
        ancestor=entry_slug(out.required_ancestor_entry_id)
        if out.required_ancestor_entry_id
        else None,
        slot=slots,
    )


def same(a: TemplateRow, b: TemplateRow, doc_system: str | None) -> bool:
    """Whether two templates say the same: a stat written alone or with no label is one thing."""

    def plain(row: TemplateRow) -> dict[str, Any]:
        dumped = row.model_dump(exclude_none=True)
        dumped["system"] = system_slug(row, doc_system)
        dumped["slot"] = [
            {
                **{k: v for k, v in slot.model_dump(exclude_none=True).items() if k != "stats"},
                "stats": [s.model_dump(exclude_none=True) for s in slot.stat_rows()],
            }
            for slot in row.slot
        ]
        return dumped

    return plain(a) == plain(b)


def stats_named(row: TemplateRow) -> list[str]:
    found = [s.stat for slot in row.slot for s in slot.stat_rows()]
    found += [name for slot in row.slot for name in slot.exclude or []]
    return list(dict.fromkeys(found))
