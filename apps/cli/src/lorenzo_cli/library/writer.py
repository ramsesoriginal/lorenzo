"""Carrying a plan out (ADR 0483, ADR 0484): level by level, up to four requests at a time within a
level, and the result listed in the plan's order whatever order the requests finished in. A failure
stops the levels after its own; what was written stays, and the next apply finds it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from lorenzo_cli.client import ops
from lorenzo_cli.client.errors import LorenzoApiError, LorenzoConnectionError
from lorenzo_cli.client.models import (
    EntityCreate,
    EntityParentsRequest,
    InformationCreate,
    SetEntityStatRequest,
    StatDefinitionCreate,
    StatDefinitionUpdate,
    StatGroupCreate,
    StatGroupUpdate,
    StatValueType,
    SystemCreate,
    SystemUpdate,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.library import formulas, templates
from lorenzo_cli.library.document import Document
from lorenzo_cli.library.planner import Action, Plan
from lorenzo_cli.library.state import LibraryState

CONCURRENCY = 4


@dataclass
class Result:
    done: list[Action] = field(default_factory=list)
    failed: list[tuple[Action, str]] = field(default_factory=list)
    skipped: list[Action] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "done": [a.as_json() for a in self.done],
            "failed": [{**a.as_json(), "reason": why} for a, why in self.failed],
            "skipped": [a.as_json() for a in self.skipped],
        }


class _Ids:
    """What exists, by name and slug, as the writes make more of it."""

    def __init__(self, state: LibraryState) -> None:
        self._lock = threading.Lock()
        self.systems = {slug: s.id for slug, s in state.systems.items()}
        self.groups = {name: g.id for name, g in state.groups.items()}
        self.stats = {name: s.id for name, s in state.stats.items()}
        self.entries = {e.slug: e.id for e in state.entries.values() if e.slug}
        self.templates = {name: t.id for name, t in state.templates.items()}

    def put(self, table: str, key: str, value: UUID) -> None:
        with self._lock:
            getattr(self, table)[key] = value


class _Writer:
    def __init__(self, client: LorenzoClient, plan: Plan, state: LibraryState) -> None:
        self.client = client
        self.doc: Document = plan.document
        self.path = {"tenant_id": plan.tenant.id}
        self.ids = _Ids(state)

    def run(self, action: Action) -> None:
        getattr(self, f"_{action.verb}_{action.kind}")(action, dict(action.fields))

    # --- systems --------------------------------------------------------------------------

    def _create_system(self, action: Action, _: dict[str, Any]) -> None:
        row = self.doc.system
        assert row is not None
        made = self.client.call(
            ops.CREATE_SYSTEM, path=self.path, body=SystemCreate(slug=row.slug, name=row.name)
        ).value
        self.ids.put("systems", row.slug, made.id)

    def _change_system(self, action: Action, fields: dict[str, Any]) -> None:
        self.client.call(
            ops.UPDATE_SYSTEM,
            path={**self.path, "system_id": self.ids.systems[action.key]},
            body=SystemUpdate(name=fields["name"]),
        )

    def _change_root(self, action: Action, fields: dict[str, Any]) -> None:
        self.client.call(
            ops.UPDATE_SYSTEM,
            path={**self.path, "system_id": self.ids.systems[action.key]},
            body=SystemUpdate(root_entry_id=self.ids.entries[fields["root"]]),
        )

    # --- the vocabulary -------------------------------------------------------------------

    def _system_id(self, group_system: bool) -> UUID | None:
        if group_system and self.doc.system is not None:
            return self.ids.systems[self.doc.system.slug]
        return None

    def _create_group(self, action: Action, _: dict[str, Any]) -> None:
        row = next(g for g in self.doc.group if g.name == action.key)
        values: dict[str, Any] = {"name": row.name, "system_id": self._system_id(row.system)}
        values |= {f: getattr(row, f) for f in ("role", "priority", "mandatory", "position")}
        made = self.client.call(
            ops.CREATE_STAT_GROUP,
            path=self.path,
            body=StatGroupCreate(**{k: v for k, v in values.items() if v is not None}),
        ).value
        self.ids.put("groups", row.name, made.id)

    def _change_group(self, action: Action, fields: dict[str, Any]) -> None:
        body = dict(fields)
        if "system" in body:
            body["system_id"] = self.ids.systems[body.pop("system")]
        self.client.call(
            ops.UPDATE_STAT_GROUP,
            path={**self.path, "stat_group_id": self.ids.groups[action.key]},
            body=StatGroupUpdate(**body),
        )

    def _create_stat(self, action: Action, _: dict[str, Any]) -> None:
        row = next(s for s in self.doc.stat if s.name == action.key)
        values: dict[str, Any] = {
            "name": row.name,
            "stat_group_id": self.ids.groups[row.group],
            "value_type": StatValueType(row.type),
            "role": row.role,
            "enum_values": row.values,
            "unit": row.unit,
            "adjustable_in_play": row.adjustable_in_play,
            "pin": row.pin,
            "signed": row.signed,
            "position": row.position,
            "min_value": row.min,
            "max_value": row.max,
        }
        made = self.client.call(
            ops.CREATE_STAT_DEFINITION,
            path=self.path,
            body=StatDefinitionCreate(**{k: v for k, v in values.items() if v is not None}),
        ).value
        self.ids.put("stats", row.name, made.id)

    def _change_stat(self, action: Action, fields: dict[str, Any]) -> None:
        body: dict[str, Any] = {}
        for name, value in fields.items():
            if name.endswith("_hint"):
                body[f"{name}_id"] = self.ids.stats[value]
            else:
                body[{"min": "min_value", "max": "max_value"}.get(name, name)] = value
        self.client.call(
            ops.UPDATE_STAT_DEFINITION,
            path={**self.path, "stat_definition_id": self.ids.stats[action.key]},
            body=StatDefinitionUpdate(**body),
        )

    # --- entries ---------------------------------------------------------------------------

    def _create_entry(self, action: Action, _: dict[str, Any]) -> None:
        row = next(e for e in self.doc.entry if e.slug == action.key)
        values: dict[str, Any] = {
            "name": row.name,
            "slug": row.slug,
            "kinds": row.kinds,
            "parents": [self.ids.entries[p] for p in row.parents],
            "in_public_catalog": row.public if "item" in row.kinds else None,
            "repeatable": row.repeatable,
            "starts_inactive": row.starts_inactive,
        }
        made = self.client.call(
            ops.CREATE_ENTITY,
            path=self.path,
            body=EntityCreate(**{k: v for k, v in values.items() if v is not None}),
        ).value
        self.ids.put("entries", row.slug, made.id)

    def _add_parent(self, slug: str, parent: str) -> None:
        path = {**self.path, "entity_id": self.ids.entries[slug]}
        current = self.client.call(ops.GET_ENTITY, path=path)
        have = [p.id for p in current.value.prototypes]
        wanted = self.ids.entries[parent]
        if wanted in have:
            return
        self.client.call(
            ops.REPLACE_ENTITY_PARENTS,
            path=path,
            body=EntityParentsRequest(parent_ids=[*have, wanted]),
            if_match=current.etag,
        )

    def _change_parents(self, action: Action, fields: dict[str, Any]) -> None:
        self._add_parent(action.key, fields["parent"])

    def _create_attach(self, action: Action, _: dict[str, Any]) -> None:
        entry, parent = action.key.split(": ")
        self._add_parent(entry, parent)

    def _set_value(self, action: Action) -> None:
        slug, stat = action.key.split(": ")
        row = next(e for e in self.doc.entry if e.slug == slug)
        self.client.call(
            ops.SET_ENTITY_STAT,
            path={
                **self.path,
                "entity_id": self.ids.entries[slug],
                "stat_definition_id": self.ids.stats[stat],
            },
            # A prototype adds a group to everything under it by carrying a value in it.
            body=SetEntityStatRequest(value=row.stats[stat], acquire_group=True),
        )

    def _create_value(self, action: Action, _: dict[str, Any]) -> None:
        self._set_value(action)

    def _change_value(self, action: Action, _: dict[str, Any]) -> None:
        self._set_value(action)

    def _create_tag(self, action: Action, _: dict[str, Any]) -> None:
        slug, stat = action.key.split(": ")
        self.client.call(
            ops.SET_ENTITY_TAG,
            path={
                **self.path,
                "entity_id": self.ids.entries[slug],
                "stat_definition_id": self.ids.stats[stat],
            },
        )

    def _create_description(self, action: Action, _: dict[str, Any]) -> None:
        row = next(e for e in self.doc.entry if e.slug == action.key)
        assert row.description is not None
        self.client.call(
            ops.CREATE_INFORMATION,
            path={**self.path, "entity_id": self.ids.entries[row.slug]},
            # A description is titled with its entry's name (ADR 0165).
            body=InformationCreate(
                title=row.name,
                type="description",
                is_public=True,
                content=row.description,
                locale="en-US",
            ),
        )

    # --- formulas ----------------------------------------------------------------------------

    def _set_formula(self, action: Action) -> None:
        slug, stat = action.key.split(": ")
        row = next(f for f in self.doc.formula if f.on == slug and f.stat == stat)
        self.client.call(
            ops.SET_COMPUTED_STAT,
            path={
                **self.path,
                "entity_id": self.ids.entries[slug],
                "stat_definition_id": self.ids.stats[stat],
            },
            body=formulas.body(row.kind, row.fields(), lambda name: self.ids.stats[name]),
        )

    def _create_formula(self, action: Action, _: dict[str, Any]) -> None:
        self._set_formula(action)

    def _change_formula(self, action: Action, _: dict[str, Any]) -> None:
        self._set_formula(action)

    def _remove_formula(self, action: Action, _: dict[str, Any]) -> None:
        slug, stat = action.key.split(": ")
        self.client.call(
            ops.DELETE_COMPUTED_STAT,
            path={
                **self.path,
                "entity_id": self.ids.entries[slug],
                "stat_definition_id": self.ids.stats[stat],
            },
        )

    # --- templates ---------------------------------------------------------------------------

    def _template_body(self, name: str) -> Any:
        row = next(t for t in self.doc.template if t.name == name)
        return templates.to_body(
            row,
            doc_system=self.doc.system.slug if self.doc.system else None,
            system_id=lambda slug: self.ids.systems[slug],
            group_id=lambda group: self.ids.groups[group],
            stat_id=lambda stat: self.ids.stats[stat],
            entry_id=lambda slug: self.ids.entries[slug],
        )

    def _create_template(self, action: Action, _: dict[str, Any]) -> None:
        made = self.client.call(
            ops.CREATE_TEMPLATE, path=self.path, body=self._template_body(action.key)
        ).value
        self.ids.put("templates", action.key, made.id)

    def _change_template(self, action: Action, _: dict[str, Any]) -> None:
        self.client.call(
            ops.REPLACE_TEMPLATE,
            path={**self.path, "template_id": self.ids.templates[action.key]},
            body=self._template_body(action.key),
        )

    def _remove_template(self, action: Action, _: dict[str, Any]) -> None:
        self.client.call(
            ops.DELETE_TEMPLATE,
            path={**self.path, "template_id": self.ids.templates[action.key]},
        )

    # --- pruning ---------------------------------------------------------------------------

    def _remove_stat(self, action: Action, _: dict[str, Any]) -> None:
        self.client.call(
            ops.DELETE_STAT_DEFINITION,
            path={**self.path, "stat_definition_id": self.ids.stats[action.key]},
        )

    def _remove_group(self, action: Action, _: dict[str, Any]) -> None:
        self.client.call(
            ops.DELETE_STAT_GROUP,
            path={**self.path, "stat_group_id": self.ids.groups[action.key]},
        )

    def _remove_entry(self, action: Action, _: dict[str, Any]) -> None:
        path = {**self.path, "entity_id": self.ids.entries[action.key]}
        current = self.client.call(ops.GET_ENTITY, path=path)
        self.client.call(ops.DELETE_ENTITY, path=path, if_match=current.etag)


def apply(
    client: LorenzoClient,
    plan: Plan,
    state: LibraryState,
    *,
    advance: Callable[[], None] = lambda: None,
    describe: Callable[[str], None] = lambda text: None,
) -> Result:
    """Write the plan. A plan with problems is never applied."""
    if plan.problems:
        raise ValueError("A plan with problems is never applied.")
    writer = _Writer(client, plan, state)
    result = Result()
    levels = plan.levels()

    def one(action: Action) -> str | None:
        """None when it was written, else why not."""
        describe(f"{action.verb} {action.kind} {action.key}")
        try:
            writer.run(action)
            return None
        except (LorenzoApiError, LorenzoConnectionError) as exc:
            return str(exc)
        except Exception as exc:  # reported with the action, not lost in a worker thread
            return f"{type(exc).__name__}: {exc}"
        finally:
            advance()

    def in_turn(actions: list[Action]) -> list[str | None]:
        return [one(action) for action in actions]

    for index, level in enumerate(levels):
        # Writes to one row run one after another; different rows run side by side. Two values
        # written to one entry at once would both add its stat group, and the API refuses one.
        by_row: dict[str, list[Action]] = {}
        for action in level:
            by_row.setdefault(action.key.split(": ")[0], []).append(action)
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            answers = list(pool.map(in_turn, by_row.values()))
        why_not = {
            id(action): why
            for actions, whys in zip(by_row.values(), answers, strict=True)
            for action, why in zip(actions, whys, strict=True)
        }
        outcomes = [why_not[id(action)] for action in level]
        for action, why in zip(level, outcomes, strict=True):
            if why is None:
                result.done.append(action)
            else:
                result.failed.append((action, why))
        if result.failed:
            result.skipped = [a for later in levels[index + 1 :] for a in later]
            break
    return result
