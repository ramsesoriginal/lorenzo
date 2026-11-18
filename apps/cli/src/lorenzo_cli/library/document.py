"""The library document's tables and the checks that need no library (ADR 0498).

A row names others by name (a group, a stat) or by slug (an entry, a system), never by id, so one
document applies to any library and a second apply finds what the first made.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

FORMAT = 1
SYSTEM_SLUG = r"^[a-z][a-z0-9]{0,31}$"
ENTRY_SLUG = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
DOCUMENT_NAME = r"^[a-z0-9][a-z0-9-]*$"

StatType = Literal["int", "float", "text", "bool", "enum", "dice"]
StatRole = Literal[
    "weight",
    "height",
    "price",
    "rarity",
    "hp",
    "armor",
    "size",
    "carry_capacity",
    "containment_capacity",
    "max_item_size",
    "binding",
    "is_container",
]
GroupRole = Literal["physical", "economic", "destroyable", "damaging", "tags"]
EntryKind = Literal["item", "being", "fact", "event", "feature"]
Value = bool | int | float | str


class DocumentError(Exception):
    """The file is not a library document this CLI can read; the message says where."""


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemRow(_Row):
    slug: str = Field(
        pattern=SYSTEM_SLUG, description="The system's slug, the prefix of its stats."
    )
    name: str = Field(min_length=1, max_length=200)
    root: str | None = Field(
        None, description="The slug of the entry everything of it descends from."
    )


class GroupRow(_Row):
    name: str = Field(min_length=1)
    system: bool = Field(False, description="True: the group belongs to the document's system.")
    role: GroupRole | None = None
    priority: int | None = None
    mandatory: bool | None = None
    position: int | None = None


class StatRow(_Row):
    name: str = Field(min_length=1)
    group: str = Field(min_length=1)
    type: StatType
    values: list[str] | None = Field(None, description="An enum's values, in order.")
    unit: str | None = Field(None, min_length=1, max_length=32)
    role: StatRole | None = None
    min: float | None = None
    max: float | None = None
    max_hint: str | None = None
    min_hint: str | None = None
    resolved_hint: str | None = None
    adjustable_in_play: bool | None = None
    pin: bool | None = None
    signed: bool | None = None
    position: int | None = None


def _item() -> list[EntryKind]:
    return ["item"]


class EntryRow(_Row):
    slug: str = Field(pattern=ENTRY_SLUG, max_length=100)
    name: str = Field(min_length=1)
    kinds: list[EntryKind] = Field(default_factory=_item)
    parents: list[str] = Field(default_factory=list, description="Slugs, in order.")
    public: bool = False
    stats: dict[str, Value] = Field(default_factory=dict, description="Own values by stat name.")
    tags: list[str] = Field(default_factory=list, description="Tag stats set to true.")
    description: str | None = Field(None, description="Its public description.")
    repeatable: bool | None = None
    starts_inactive: bool | None = None
    prerequisites: list[Comparison] | None = Field(
        None, description="A feature's prerequisites, as a whole list."
    )


class FormulaRow(BaseModel):
    """A formula on an entry (ADR 0500): `on` the entry's slug, `stat` the stat it computes, `kind`,
    and that kind's fields as `library.formulas` names them."""

    model_config = ConfigDict(extra="allow")

    on: str = Field(pattern=ENTRY_SLUG, max_length=100)
    stat: str = Field(min_length=1)
    kind: str

    @model_validator(mode="after")
    def _its_kind_accepts_it(self) -> FormulaRow:
        from lorenzo_cli.library.formulas import FormulaError, check

        try:
            check(self.kind, self.fields())
        except FormulaError as exc:
            raise ValueError(f"formula {self.stat} on {self.on}: {exc}") from exc
        return self

    def fields(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


SlotKind = Literal["stats", "information", "held", "tags", "features"]
TemplateKind = Literal[
    "item", "item_instance", "being", "character", "fact", "feature", "feature_instance", "event"
]


class SlotStat(_Row):
    stat: str
    label: str | None = Field(None, min_length=1, max_length=200)


class SlotRow(_Row):
    """One slot of a template (ADR 0451): what a sheet shows, in order."""

    kind: SlotKind
    label: str | None = Field(None, min_length=1, max_length=200)
    group: str | None = Field(None, description="A stats slot's stat group, by name.")
    stats: list[str | SlotStat] | None = Field(None, description="Or the stats, by name, in order.")
    exclude: list[str] | None = Field(None, description="Stats of the group left out.")
    information_type: str | None = Field(None, min_length=1, max_length=200)
    held_order: Literal["name", "prototype"] | None = None

    def stat_rows(self) -> list[SlotStat]:
        return [s if isinstance(s, SlotStat) else SlotStat(stat=s) for s in self.stats or []]


class TemplateRow(_Row):
    """A template (ADR 0451, ADR 0452): what an entry of a kind, under an ancestor, is shown as."""

    name: str = Field(min_length=1, max_length=200)
    system: bool | str = Field(
        False, description="True: the document's system; a slug: that system; false: none."
    )
    kind: TemplateKind | None = Field(None, description="Only entries of this kind match.")
    ancestor: str | None = Field(None, description="Only entries under this entry match (a slug).")
    slot: list[SlotRow] = Field(default_factory=list, max_length=50)


Comparator = Literal["lt", "le", "eq", "ne", "ge", "gt"]


class Comparison(_Row):
    """A stat compared with a number (`value`) or with another stat (`right`)."""

    stat: str
    comparator: Comparator
    value: float | None = None
    right: str | None = None

    @model_validator(mode="after")
    def _one_right_side(self) -> Comparison:
        if (self.value is None) == (self.right is None):
            raise ValueError(
                f"{self.stat} {self.comparator}: compare with a `value` or a `right` stat"
            )
        return self


class Condition(Comparison):
    """A grant rule's condition: on the holder (the default) or on the source."""

    subject: Literal["holder", "source"] = "holder"


class GrantRuleRow(_Row):
    """A grant rule (ADR 0455): on an entry, what it gives whoever has it, all or by choice."""

    on: str = Field(pattern=ENTRY_SLUG, max_length=100)
    label: str = Field(min_length=1, description="With `on`, what the rule is found by.")
    position: int | None = None
    mode: Literal["all", "choose"]
    min: int | None = Field(None, ge=0)
    max: int | None = Field(None, ge=1)
    count: str | None = Field(None, description="A stat whose value is how many may be chosen.")
    options: list[str] = Field(default_factory=list, description="Features, by slug.")
    option_category: str | None = Field(None, description="Or every feature under this entry.")
    lasts: Literal["while_source", "permanent"] = "while_source"
    changeable: bool = False
    conditions: list[Condition] = Field(default_factory=list)


class AttachRow(_Row):
    """A parent added to an entry another document owns (ADR 0172)."""

    entry: str
    parent: str


class Document(_Row):
    format: Literal[1] = Field(description="The document format; this CLI reads 1.")
    name: str = Field(pattern=DOCUMENT_NAME, description="How another document requires it.")
    requires: list[str] = Field(default_factory=list)
    system: SystemRow | None = None
    group: list[GroupRow] = Field(default_factory=list)
    stat: list[StatRow] = Field(default_factory=list)
    entry: list[EntryRow] = Field(default_factory=list)
    formula: list[FormulaRow] = Field(default_factory=list)
    template: list[TemplateRow] = Field(default_factory=list)
    grant_rule: list[GrantRuleRow] = Field(default_factory=list)
    attach: list[AttachRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Document:
        for what, keys in (
            ("group", [g.name for g in self.group]),
            ("stat", [s.name for s in self.stat]),
            ("entry", [e.slug for e in self.entry]),
            ("formula", [f"{f.stat} on {f.on}" for f in self.formula]),
            ("template", [t.name for t in self.template]),
            ("grant rule", [f"{r.label} on {r.on}" for r in self.grant_rule]),
        ):
            twice = sorted(k for k, n in Counter(keys).items() if n > 1)
            if twice:
                raise ValueError(f"more than one {what} called {', '.join(twice)}")
        groups = {g.name: g for g in self.group}
        if self.system is None and any(g.system for g in self.group):
            raise ValueError("a group says `system = true`, but the document has no [system]")
        if self.system is None and any(t.system is True for t in self.template):
            raise ValueError("a template says `system = true`, but the document has no [system]")
        for group in self.group:
            if group.system and group.role is not None:
                raise ValueError(
                    f"group {group.name}: a role is held by a group of no system (ADR 0449)"
                )
        for stat in self.stat:
            of = groups.get(stat.group)
            if of is not None and of.system and self.system is not None:
                prefix = f"{self.system.slug}_"
                if not stat.name.startswith(prefix):
                    raise ValueError(
                        f"stat {stat.name}: a stat of a group of {self.system.slug} is named "
                        f"{prefix}something, as {prefix}{stat.name} (ADR 0448)"
                    )
                if stat.role is not None:
                    raise ValueError(
                        f"stat {stat.name}: a role is held by a stat of no system (ADR 0449)"
                    )
            if stat.type == "enum" and not stat.values:
                raise ValueError(f"stat {stat.name}: an enum needs its `values`")
            if stat.type != "enum" and stat.values:
                raise ValueError(f"stat {stat.name}: only an enum has `values`")
            if stat.type == "dice" and stat.unit is not None:
                raise ValueError(f"stat {stat.name}: a dice stat has no unit")
            bounded = stat.min is not None or stat.max is not None
            if bounded and stat.type not in ("int", "float"):
                raise ValueError(f"stat {stat.name}: only an int or a float has bounds")
            if stat.min is not None and stat.max is not None and stat.min > stat.max:
                raise ValueError(f"stat {stat.name}: min is above max")
        return self

    def entry_named(self, slug: str) -> EntryRow | None:
        return next((e for e in self.entry if e.slug == slug), None)


def parse(text: str, *, source: str = "the document") -> Document:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise DocumentError(f"{source} is not TOML: {exc}") from exc
    try:
        return Document.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'document'}: {e['msg']}" for e in exc.errors()
        )
        raise DocumentError(f"{source}: {problems}") from exc


def load(path: Path) -> Document:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DocumentError(f"Couldn't read {path}: {exc.strerror}") from exc
    return parse(text, source=str(path))


def json_schema() -> dict[str, object]:
    """The document's JSON Schema (`lorenzo schema document`), for an editor to check a file."""
    schema = Document.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "Lorenzo library document"
    return schema


# Rows defined above the tables they use are completed once everything is defined.
EntryRow.model_rebuild()
