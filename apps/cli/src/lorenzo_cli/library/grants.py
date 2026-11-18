"""Grant rules and prerequisites as a document writes them (ADR 0488): stats by name, entries by
slug; and the API's the same way back."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from lorenzo_cli.client.models import GrantRuleIn, GrantRuleOut, GrantRuleUpdate
from lorenzo_cli.library.document import Comparison, Condition, GrantRuleRow


def comparison_to_api(row: Comparison, stat_id: Callable[[str], UUID]) -> dict[str, Any]:
    body: dict[str, Any] = {"stat_definition_id": stat_id(row.stat), "comparator": row.comparator}
    if row.value is not None:
        body["right_constant"] = row.value
    if row.right is not None:
        body["right_stat_definition_id"] = stat_id(row.right)
    if isinstance(row, Condition):
        body["subject"] = row.subject
    return body


def _number(value: Any) -> float | None:
    return None if value is None else float(value)


def comparison_from_api(out: Any) -> Comparison:
    return Comparison(
        stat=out.stat_name,
        comparator=out.comparator.value,
        value=_number(out.right_constant),
        right=out.right_stat_name,
    )


def condition_from_api(out: Any) -> Condition:
    return Condition(
        stat=out.stat_name,
        comparator=out.comparator.value,
        value=_number(out.right_constant),
        right=out.right_stat_name,
        subject=out.subject.value,
    )


def rule_body(
    row: GrantRuleRow,
    *,
    entry_id: Callable[[str], UUID],
    stat_id: Callable[[str], UUID],
    creating: bool,
) -> GrantRuleIn | GrantRuleUpdate:
    values: dict[str, Any] = {
        "label": row.label,
        "position": row.position,
        "mode": row.mode,
        "min_count": row.min,
        "max_count": row.max,
        "count_stat_definition_id": stat_id(row.count) if row.count else None,
        "options": [entry_id(slug) for slug in row.options],
        "option_category_entry_id": entry_id(row.option_category) if row.option_category else None,
        "lasts": row.lasts,
        "changeable": row.changeable,
        "conditions": [comparison_to_api(c, stat_id) for c in row.conditions],
    }
    values = {k: v for k, v in values.items() if v is not None}
    if creating:
        return GrantRuleIn(entry_id=entry_id(row.on), **values)
    return GrantRuleUpdate(**values)


def rule_from_out(out: GrantRuleOut, slug_of: Callable[[UUID], str]) -> GrantRuleRow:
    return GrantRuleRow(
        on=slug_of(out.entry_id),
        label=out.label or "",
        position=out.position,
        mode=out.mode.value,
        min=out.min_count or None,
        max=out.max_count,
        count=out.count_stat_name,
        options=[slug_of(o.id) for o in out.options if o.id is not None],
        option_category=slug_of(out.option_category.id)
        if out.option_category and out.option_category.id
        else None,
        lasts=out.lasts.value,
        changeable=out.changeable,
        conditions=[condition_from_api(c) for c in out.conditions],
    )


def same_rule(a: GrantRuleRow, b: GrantRuleRow) -> bool:
    """Whether two rules say the same; a position the document leaves out is the library's."""

    def plain(row: GrantRuleRow) -> dict[str, Any]:
        dumped = row.model_dump(exclude={"position"})
        dumped["min"] = row.min or 0
        return dumped

    same_place = a.position is None or b.position is None or a.position == b.position
    return same_place and plain(a) == plain(b)


def stats_named(row: GrantRuleRow) -> list[str]:
    found = [row.count] if row.count else []
    for condition in row.conditions:
        found.append(condition.stat)
        if condition.right:
            found.append(condition.right)
    return list(dict.fromkeys(found))
