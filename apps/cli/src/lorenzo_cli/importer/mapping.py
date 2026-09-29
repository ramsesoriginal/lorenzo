"""The mapping file (RFC 0025 R5, ADR 0144): one `schema = 1` TOML file over a built-in one.

The mapping is data with a documented schema, so a homebrew author's new category, currency or
attribute is a row and not a code change. Everything is validated when it is loaded, so a bad
map fails before anything is read from a tenant or written to one.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from importlib import resources
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from lorenzo_cli.seed import load_builtin

LIST_NAMES = ("weapons", "armour", "gear", "tools", "ammo", "packs")
AXES = ("form", "proficiency", "tier")
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
_NAMESPACE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DEFAULT_NAMESPACE = "basic"
# `regex_extract` input is capped: homebrew strings run through these patterns inside the
# process that holds the token (RFC 0025 R5).
REGEX_INPUT_CAP = 300

# The transforms an attribute rule may name. Closed on purpose: no expression language, no
# plugins. The first group needs no parameters; the second is parameterised.
PLAIN_TRANSFORMS = frozenset(
    {
        "drop", "name", "sourcebook", "description", "own_weight", "damage", "range", "armor",
        "classify", "name_and_price", "pack_contents",
    }
)  # fmt: skip
PARAM_TRANSFORMS = frozenset(
    {
        "int",
        "float",
        "text",
        "bool",
        "denomination_sum",
        "regex_extract",
        "keyword_flag",
        "first_of",
    }
)


class MappingError(Exception):
    """The mapping file is wrong. The message says where."""


class Row(BaseModel):
    """What a classification value means. A list of parent slugs is shorthand for `map`."""

    model_config = ConfigDict(extra="forbid")

    disposition: Literal["map", "skip", "attach-form-only", "create-under", "fail"] = "map"
    parents: list[str] = Field(default_factory=list)
    replace_form: bool = False
    axis: Literal["form", "proficiency", "tier"] | None = None
    slug: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Row:
        if self.disposition == "create-under":
            if not (self.axis and self.slug and self.name):
                raise ValueError("create-under needs axis, slug and name")
            if not _SLUG.match(self.slug):
                raise ValueError(f"slug {self.slug!r} is not a valid slug")
            if self.parents:
                raise ValueError("create-under takes no parents: it makes the parent")
        elif self.axis or self.slug or self.name:
            raise ValueError("axis, slug and name belong to create-under only")
        if self.disposition != "map" and self.parents:
            raise ValueError(f"{self.disposition} takes no parents")
        return self


class Rule(BaseModel):
    """What an attribute becomes: a transform and its parameters."""

    model_config = ConfigDict(extra="allow")

    transform: str

    @model_validator(mode="after")
    def _known(self) -> Rule:
        if self.transform not in PLAIN_TRANSFORMS | PARAM_TRANSFORMS:
            raise ValueError(
                f"unknown transform {self.transform!r}; "
                f"choose from {', '.join(sorted(PLAIN_TRANSFORMS | PARAM_TRANSFORMS))}"
            )
        return self

    @property
    def params(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class ListSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form: list[str] = Field(default_factory=list)
    roots: dict[str, str] = Field(default_factory=dict)
    # Weapons must come out either melee or ranged (or say they are neither, by a row).
    reach_required: bool = False


class NameRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_list: str
    starts_with: list[str]
    parents: list[str]


class Mapping(BaseModel):
    """The merged mapping."""

    version: str
    currencies: dict[str, int]
    lists: dict[str, ListSpec]
    classify: dict[str, dict[str, dict[str, Row]]]
    name_rules: list[NameRule]
    attributes: dict[str, dict[str, Rule]]
    namespaces: dict[str, str]
    # A pack item's display name (lower-cased) -> "list:key", or "text" for not-a-catalog-item.
    pack_items: dict[str, str]

    def namespace_for(self, file_name: str) -> str:
        return self.namespaces.get(file_name, DEFAULT_NAMESPACE)


class LoadedMapping(BaseModel):
    mapping: Mapping
    builtin_version: str
    # Hash of the project file's exact bytes, or "" when there is none: the plan header carries
    # both, so a changed map is visible in the plan.
    user_map_sha256: str


def _row(value: Any) -> Row:
    if isinstance(value, list):
        return Row(parents=[str(v) for v in value])
    if isinstance(value, str):
        return Row(disposition=value)
    if isinstance(value, dict):
        return Row.model_validate(value)
    raise ValueError(f"a row is a list of parents, a disposition, or a table; got {value!r}")


def _rule(value: Any) -> Rule:
    if isinstance(value, str):
        return Rule(transform=value)
    if isinstance(value, dict):
        return Rule.model_validate(value)
    raise ValueError(f"a rule is a transform's name or a table; got {value!r}")


def _read_builtin() -> dict[str, Any]:
    text = resources.files("lorenzo_cli.importer").joinpath("builtin_map.toml").read_text("utf-8")
    return tomllib.loads(text)


def _merge(builtin: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    """The user's rows win, key by key; nothing of the built-in map is lost by omission."""
    merged: dict[str, Any] = {
        "version": builtin.get("version", "0"),
        "currencies": {**builtin.get("currencies", {}), **user.get("currencies", {})},
        "namespaces": dict(user.get("namespaces", {})),
        "lists": {},
        "classify": {},
        "attributes": {},
        # The project's rules first: the first matching rule of a list wins.
        "name_rule": [*user.get("name_rule", []), *builtin.get("name_rule", [])],
        "pack_items": {
            **{str(k).lower(): v for k, v in builtin.get("pack_items", {}).items()},
            **{str(k).lower(): v for k, v in user.get("pack_items", {}).items()},
        },
    }
    for name in {*builtin.get("lists", {}), *user.get("lists", {})}:
        merged["lists"][name] = {
            **builtin.get("lists", {}).get(name, {}),
            **user.get("lists", {}).get(name, {}),
            "roots": {
                **builtin.get("lists", {}).get(name, {}).get("roots", {}),
                **user.get("lists", {}).get(name, {}).get("roots", {}),
            },
        }
    for source in (builtin, user):
        for list_name, sections in source.get("classify", {}).items():
            target = merged["classify"].setdefault(list_name, {})
            for attribute, rows in sections.items():
                target.setdefault(attribute, {}).update(
                    {str(k).lower(): v for k, v in rows.items()}
                )
        for list_name, rules in source.get("attributes", {}).items():
            merged["attributes"].setdefault(list_name, {}).update(rules)
    return merged


def load_mapping(user_text: str | None = None, *, taught: str = "") -> LoadedMapping:
    """`taught` are classification rows answered in this run (teach.py); they lay over the file
    and are not part of its hash."""
    builtin = _read_builtin()
    try:
        user = tomllib.loads(user_text) if user_text else {}
        extra = tomllib.loads(taught) if taught else {}
    except tomllib.TOMLDecodeError as exc:
        raise MappingError(f"The map file isn't valid TOML: {exc}") from exc
    if user and user.get("schema") != 1:
        raise MappingError("The map file needs `schema = 1` on its first line.")
    for list_name, sections in extra.get("classify", {}).items():
        for attribute, rows in sections.items():
            target = user.setdefault("classify", {}).setdefault(list_name, {})
            target.setdefault(attribute, {}).update(rows)
    if extra and not user.get("schema"):
        user["schema"] = 1
    unknown = set(user) - {
        "schema", "version", "currencies", "namespaces", "lists", "classify", "attributes",
        "name_rule", "pack_items",
    }  # fmt: skip
    if unknown:
        raise MappingError(f"Unknown top-level keys in the map file: {', '.join(sorted(unknown))}")

    merged = _merge(builtin, user)
    try:
        mapping = Mapping(
            version=str(merged["version"]),
            currencies={str(k).lower(): _positive(k, v) for k, v in merged["currencies"].items()},
            lists={name: ListSpec.model_validate(spec) for name, spec in merged["lists"].items()},
            classify={
                list_name: {
                    attribute: {value: _row(row) for value, row in rows.items()}
                    for attribute, rows in sections.items()
                }
                for list_name, sections in merged["classify"].items()
            },
            name_rules=[NameRule.model_validate(r) for r in merged["name_rule"]],
            attributes={
                list_name: {attribute: _rule(rule) for attribute, rule in rules.items()}
                for list_name, rules in merged["attributes"].items()
            },
            namespaces={str(k): str(v) for k, v in merged["namespaces"].items()},
            pack_items={str(k): str(v) for k, v in merged["pack_items"].items()},
        )
    except (ValidationError, ValueError) as exc:
        raise MappingError(f"The map isn't valid: {exc}") from exc
    _check(mapping)
    digest = hashlib.sha256(user_text.encode()).hexdigest() if user_text else ""
    return LoadedMapping(
        mapping=mapping, builtin_version=str(builtin.get("version", "0")), user_map_sha256=digest
    )


def _positive(unit: object, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"currency {unit!r} must be a whole number of copper pieces, at least 1")
    return value


def _check(mapping: Mapping) -> None:
    """Things only the whole map can get wrong."""
    for list_name in (*mapping.lists, *mapping.classify, *mapping.attributes):
        if list_name not in LIST_NAMES:
            raise MappingError(
                f"“{list_name}” is not a list; the lists are {', '.join(LIST_NAMES)}"
            )
    for file_name, namespace in mapping.namespaces.items():
        if not _NAMESPACE.match(namespace):
            raise MappingError(
                f"Namespace {namespace!r} for {file_name} must be lower-case letters, digits "
                "and single hyphens."
            )
    for name, target in mapping.pack_items.items():
        list_name, _, key = target.partition(":")
        if target != "text" and not (list_name in LIST_NAMES and key):
            raise MappingError(
                f"pack_items.{name!r} is {target!r}: say 'text', or 'list:key' with a list from "
                f"{', '.join(LIST_NAMES)}."
            )
    for name_rule in mapping.name_rules:
        if name_rule.in_list not in LIST_NAMES:
            raise MappingError(
                f"A name_rule names the list “{name_rule.in_list}”, which doesn't exist."
            )
    for list_name, rules in mapping.attributes.items():
        for attribute, rule in rules.items():
            where = f"attributes.{list_name}.{attribute}"
            if rule.transform == "classify" and attribute not in mapping.classify.get(
                list_name, {}
            ):
                raise MappingError(
                    f"{where} is `classify`, but there is no [classify.{list_name}.{attribute}]."
                )
            _check_params(where, rule)
    for list_name, sections in mapping.classify.items():
        for attribute, rows in sections.items():
            for value, row in rows.items():
                _check_row(mapping, f"classify.{list_name}.{attribute}.{value}", list_name, row)


def _check_row(mapping: Mapping, where: str, list_name: str, row: Row) -> None:
    if row.disposition != "create-under":
        return
    assert row.axis is not None and row.slug is not None
    if row.slug in {node.slug for node in load_builtin().nodes}:
        raise MappingError(f"{where}: {row.slug} is already one of the seed's own categories.")
    roots = mapping.lists.get(list_name, ListSpec()).roots
    if row.axis not in roots:
        raise MappingError(f"{where}: the list {list_name} has no {row.axis} axis to create under.")
    # A category under a game system's axis must say which system it is not part of: a bare slug
    # is a core form, and `dnd5e-` is D&D's own (RFC 0025 R5). `hb-`, or any other prefix, is yours.
    system_axis = row.axis != "form"
    if row.slug.startswith("dnd5e-") and not system_axis:
        raise MappingError(f"{where}: a dnd5e- slug can't go under the form axis.")
    if system_axis and "-" not in row.slug:
        raise MappingError(
            f"{where}: a category under the {row.axis} axis needs a prefix that says whose it is, "
            f"like hb-{row.slug}; a bare slug looks like a core form."
        )


def _check_params(where: str, rule: Rule) -> None:
    params = rule.params
    transform = rule.transform
    if transform in PLAIN_TRANSFORMS and params:
        raise MappingError(f"{where}: {transform} takes no parameters ({', '.join(params)}).")
    if transform in {"int", "float", "text", "bool", "keyword_flag", "first_of", "regex_extract",
                     "denomination_sum"} and not params.get("stat"):  # fmt: skip
        raise MappingError(f"{where}: {transform} needs `stat`, the stat to write.")
    if transform == "regex_extract":
        _check_regex(where, params)
    if transform == "keyword_flag" and not params.get("keywords"):
        raise MappingError(f"{where}: keyword_flag needs `keywords`.")
    if transform == "first_of" and not params.get("of"):
        raise MappingError(f"{where}: first_of needs `of`, the attributes to try in order.")


def _check_regex(where: str, params: dict[str, Any]) -> None:
    pattern = params.get("pattern")
    if not isinstance(pattern, str):
        raise MappingError(f"{where}: regex_extract needs a `pattern`.")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise MappingError(f"{where}: the pattern doesn't compile: {exc}") from exc
    if compiled.groups < int(params.get("group", 1)):
        raise MappingError(f"{where}: the pattern has no group {params.get('group', 1)}.")
    examples = params.get("examples")
    if not examples:
        raise MappingError(
            f"{where}: regex_extract needs `examples` (input and expected output), which run when "
            "the map is loaded."
        )
    for example in examples:
        text = str(example.get("input", ""))
        match = compiled.search(text[:REGEX_INPUT_CAP])
        got = match.group(int(params.get("group", 1))) if match else None
        if str(got) != str(example.get("output")):
            raise MappingError(
                f"{where}: the example {text!r} should give {example.get('output')!r}, "
                f"and gives {got!r}."
            )
