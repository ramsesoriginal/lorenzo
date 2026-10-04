"""What the importer says about a plan (RFC 0025 R5, R6, ADR 0144): the plan as JSON, the review
queue of everything it would not guess at, and a snippet of map rows to paste in.

The importer never edits a map file. It emits `proposed.map.toml`; the person reads it, chooses,
and appends what they want, so a plan stays a pure function of its inputs.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lorenzo_cli.importer.plan import ImportPlan, PlannedItem

if TYPE_CHECKING:
    from lorenzo_cli.importer.apply import ApplyReport


def _issue_dict(item: PlannedItem) -> list[dict[str, str]]:
    return [
        {
            "kind": issue.kind,
            "attribute": issue.attribute,
            "value": issue.value,
            "reason": issue.reason,
            "suggestion": issue.suggestion,
        }
        for issue in item.draft.issues
    ]


def _unmapped_suggestion(list_name: str, attribute: str) -> str:
    return f'[attributes.{list_name}]\n{attribute} = "drop"   # or a transform: "text", "int", ...'


def plan_json(plan: ImportPlan) -> dict[str, Any]:
    """The plan as plain data, in a stable order, for a script to chain on."""
    tenant = plan.tenant
    return {
        "header": {
            "builtin_version": plan.loaded.builtin_version,
            "user_map_sha256": plan.loaded.user_map_sha256,
            "seed_version": plan.seed_version,
            "tenant": {
                "id": str(tenant.id),
                "slug": tenant.slug,
                "kind": tenant.kind.value,
                "published": tenant.published_at is not None,
            },
            "counts": {
                "create": plan.count("create"),
                "complete": plan.count("complete"),
                "exists": plan.count("exists"),
                "held": plan.count("held"),
                "moved": plan.count("moved"),
                "skipped": plan.count("skipped"),
                "would_change_parents": plan.reparent_count,
                "new_categories": len(plan.categories),
                "new_definitions": len(plan.definitions),
            },
        },
        "problems": plan.problems,
        "file_errors": plan.file_errors,
        "stubbed_sheet_names": plan.stubbed,
        "overrides": plan.overrides,
        "new_categories": [
            {"slug": c.slug, "name": c.name, "under": c.parent, "axis": c.axis}
            for c in plan.categories
        ],
        "new_definitions": [
            {"name": d.name, "group": d.group, "value_type": d.value_type} for d in plan.definitions
        ],
        "unmapped_attributes": [
            {
                "list": list_name,
                "attribute": attribute,
                "items": count,
                "suggestion": _unmapped_suggestion(list_name, attribute),
            }
            for (list_name, attribute), count in plan.unmapped().items()
        ],
        "items": [
            {
                "list": item.draft.list_name,
                "key": item.draft.key,
                "file": item.draft.file,
                "namespace": item.draft.namespace,
                "slug": item.slug,
                "status": item.status,
                "name": item.draft.name,
                "parents": item.draft.parents,
                "stats": item.draft.stats,
                "description": bool(item.draft.description),
                "information": [{"type": i.type, "title": i.title} for i in item.draft.information],
                "uncategorised": item.draft.uncategorised,
                "notes": item.draft.notes,
                "would_change_parents": item.reparent,
                "moved_from": item.moved_from,
                "skipped_because": item.draft.skip_reason,
                "pack": (
                    {
                        "lines": len(item.draft.pack_lines),
                        "unresolved": [u.name for u in item.draft.pack_unresolved],
                    }
                    if item.draft.list_name == "packs"
                    else None
                ),
                "issues": _issue_dict(item),
            }
            for item in plan.items
        ],
    }


def apply_json(plan: ImportPlan, report: ApplyReport | None, unresolved: bool) -> dict[str, Any]:
    """What `apply --json` prints (ADR 0156): the plan as `plan --json` gives it, and what was
    written, which is `None` when nothing was."""
    return {
        "plan": plan_json(plan),
        "applied": None
        if report is None
        else {
            "created": report.created,
            "completed": report.completed,
            "reparented": report.reparented,
            "categories": report.categories,
            "definitions": report.definitions,
        },
        "failures": [] if report is None else list(report.failures),
        "unresolved": unresolved,
    }


def review_queue(plan: ImportPlan) -> list[dict[str, Any]]:
    """Everything a person has to look at. Nothing here was imported."""
    queue: list[dict[str, Any]] = []
    for item in plan.items:
        for issue in item.draft.issues if item.status == "held" else []:
            queue.append(
                {
                    "kind": issue.kind,
                    "list": item.draft.list_name,
                    "key": item.draft.key,
                    "file": item.draft.file,
                    "attribute": issue.attribute,
                    "value": issue.value,
                    "reason": issue.reason,
                    "suggestion": issue.suggestion,
                }
            )
        if item.status == "moved":
            queue.append(
                {
                    "kind": "moved",
                    "list": item.draft.list_name,
                    "key": item.draft.key,
                    "file": item.draft.file,
                    "attribute": "",
                    "value": "",
                    "reason": f"was imported as {item.moved_from}, and would now be {item.slug}",
                    "suggestion": "Fix the namespace in the map, or run with --accept-moves.",
                }
            )
    for item, missing in plan.pack_unresolved():
        queue.append(
            {
                "kind": "pack",
                "list": "packs",
                "key": item.draft.key,
                "file": item.draft.file,
                "attribute": "items",
                "value": repr(missing.name),
                "reason": missing.reason,
                "suggestion": missing.suggestion,
            }
        )
    for (list_name, attribute), count in plan.unmapped().items():
        queue.append(
            {
                "kind": "attribute",
                "list": list_name,
                "key": "",
                "file": "",
                "attribute": attribute,
                "value": "",
                "reason": f"{count} item(s) have this attribute, and no rule says what it means",
                "suggestion": _unmapped_suggestion(list_name, attribute),
            }
        )
    return queue


def write_review_queue(path: Path, plan: ImportPlan) -> int:
    queue = review_queue(plan)
    path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(queue)


def proposed_map(plan: ImportPlan) -> str:
    """Map rows for everything unresolved, grouped so each value is asked about once."""
    sections: dict[str, list[str]] = defaultdict(list)
    for item in plan.items:
        if item.status != "held":
            continue
        for issue in item.draft.issues:
            if (
                issue.suggestion
                and issue.suggestion not in sections[issue.suggestion.split("\n")[0]]
            ):
                sections[issue.suggestion.split("\n")[0]].append(issue.suggestion)
    for _, missing in plan.pack_unresolved():
        header = missing.suggestion.split("\n")[0]
        if missing.suggestion not in sections[header]:
            sections[header].append(missing.suggestion)
    for (list_name, attribute), _ in plan.unmapped().items():
        header = f"[attributes.{list_name}]"
        row = _unmapped_suggestion(list_name, attribute)
        sections[header].append(row)
    lines = [
        "# Proposed map rows (lorenzo plan). Read them, choose, and paste what you want into your",
        "# map file. Nothing here has been applied.",
        "",
    ]
    for header, blocks in sorted(sections.items()):
        lines.append(header)
        for block in blocks:
            lines.extend(line for line in block.split("\n")[1:])
        lines.append("")
    return "\n".join(lines)
