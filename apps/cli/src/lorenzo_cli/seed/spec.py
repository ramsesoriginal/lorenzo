"""The built-in seed as data (ADR 0143, 0175): groups, stat definitions, taxonomy nodes, the
attachments between layers and the weight recipe, each with a layer. Loaded from `builtin.toml` and
validated, so a typo in the seed is a test failure and never a half-seeded tenant."""

from __future__ import annotations

import re
import tomllib
from importlib import resources
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Layer = Literal["core", "equipment", "dnd5e", "dnd5e-equipment"]
# In dependency order: a layer comes after every layer it is built on.
LAYERS: tuple[Layer, ...] = ("core", "equipment", "dnd5e", "dnd5e-equipment")
# What a layer is built on, directly (ADR 0175). An entry may name its own layer's entries and
# those of the layers it is built on, through the layers they are built on in turn.
BUILT_ON: dict[Layer, tuple[Layer, ...]] = {
    "core": (),
    "equipment": ("core",),
    "dnd5e": ("core",),
    "dnd5e-equipment": ("equipment", "dnd5e"),
}
# The slug prefix of a layer's categories; a layer with none has bare slugs.
SLUG_PREFIX: dict[Layer, str] = {"dnd5e": "dnd5e-", "dnd5e-equipment": "dnd5e-"}
ValueType = Literal["int", "float", "text", "bool"]
StatValue = int | float | str | bool

# The entity slug grammar (RFC 0027, ADR 0107): what POST /items accepts.
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GroupSpec(_Strict):
    name: str
    layer: Layer


class DefinitionSpec(_Strict):
    name: str
    group: str
    value_type: ValueType
    layer: Layer


class NodeSpec(_Strict):
    slug: str
    name: str
    layer: Layer
    parents: list[str] = Field(default_factory=list)
    # Bool stats set to true on this node (tags), inherited by everything under it.
    tags: list[str] = Field(default_factory=list)
    # Other stat values set on this node, inherited the same way. A node that carries one adds
    # the stat's group to everything under it (RFC 0033, section 3).
    stats: dict[str, StatValue] = Field(default_factory=dict)
    # What the category means, written as its public description: every item under it shows it.
    description: str = ""


class RecipeSpec(_Strict):
    """A computed stat on a node: `contents(source)` or `sum(terms...)`."""

    node: str
    stat: str
    kind: Literal["contents", "sum"]
    source: str | None = None
    terms: list[str] = Field(default_factory=list)
    layer: Layer


class AttachmentSpec(_Strict):
    """A parent added to a category of another layer: what a repository that holds copies of both
    does (ADR 0172, 0175). `layer` is the layer that makes it, built on both categories'."""

    child: str
    parent: str
    layer: Layer


class SeedSpec(_Strict):
    schema_version: Literal[1] = Field(alias="schema")
    version: str
    groups: list[GroupSpec] = Field(alias="group")
    definitions: list[DefinitionSpec] = Field(alias="definition")
    nodes: list[NodeSpec] = Field(alias="node")
    recipes: list[RecipeSpec] = Field(alias="recipe")
    attachments: list[AttachmentSpec] = Field(default_factory=list, alias="attachment")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        groups = {g.name: g for g in self.groups}
        _unique([g.name for g in self.groups], "group")
        defs = {d.name: d for d in self.definitions}
        _unique([d.name for d in self.definitions], "definition")
        for definition in self.definitions:
            if definition.group not in groups:
                raise ValueError(f"definition {definition.name!r}: no group {definition.group!r}")
            _may_name(
                f"definition {definition.name!r}",
                definition.layer,
                f"group {definition.group!r}",
                groups[definition.group].layer,
            )

        seen: dict[str, NodeSpec] = {}
        last_layer = -1
        for node in self.nodes:
            if not _SLUG.match(node.slug):
                raise ValueError(f"node slug {node.slug!r} is not a valid slug")
            if node.slug in seen:
                raise ValueError(f"node {node.slug!r} is listed twice")
            what = f"node {node.slug!r}"
            for parent in node.parents:
                # Parents first, so the file order is a valid creation order and cycles can't exist.
                if parent not in seen:
                    raise ValueError(f"{what}: parent {parent!r} must be listed first")
                _may_name(what, node.layer, f"parent {parent!r}", seen[parent].layer)
            for tag in node.tags:
                if tag not in defs or defs[tag].value_type != "bool":
                    raise ValueError(f"{what}: tag {tag!r} is not a bool definition")
                _may_name(what, node.layer, f"tag {tag!r}", defs[tag].layer)
            for stat, value in node.stats.items():
                if stat not in defs:
                    raise ValueError(f"{what}: no definition {stat!r} for its value")
                if not _fits(defs[stat].value_type, value):
                    raise ValueError(
                        f"{what}: {stat!r} is a {defs[stat].value_type} stat, "
                        f"and {value!r} is not one"
                    )
                _may_name(what, node.layer, f"stat {stat!r}", defs[stat].layer)
            _slug_follows_layer(node.slug, node.layer)
            # Layers in dependency order, so the file order is a valid creation order. Groups and
            # definitions are made all together before any node, so their order doesn't matter.
            if LAYERS.index(node.layer) < last_layer:
                raise ValueError(f"{what} ({node.layer}) is listed after a later layer's")
            last_layer = LAYERS.index(node.layer)
            seen[node.slug] = node

        for recipe in self.recipes:
            what = f"recipe {recipe.stat!r}"
            if recipe.node not in seen:
                raise ValueError(f"{what}: no node {recipe.node!r}")
            if recipe.stat not in defs:
                raise ValueError(f"recipe on {recipe.node!r}: no definition {recipe.stat!r}")
            referenced = [recipe.source] if recipe.source else recipe.terms
            for name in referenced:
                if name not in defs:
                    raise ValueError(f"{what}: no definition {name!r}")
            if recipe.kind == "contents" and (recipe.source is None or recipe.terms):
                raise ValueError(f"{what}: contents takes a source, no terms")
            if recipe.kind == "sum" and (recipe.source is not None or not recipe.terms):
                raise ValueError(f"{what}: sum takes terms, no source")
            _may_name(what, recipe.layer, f"node {recipe.node!r}", seen[recipe.node].layer)
            for name in [recipe.stat, *referenced]:
                _may_name(what, recipe.layer, f"definition {name!r}", defs[name].layer)

        pairs: set[tuple[str, str]] = set()
        for attachment in self.attachments:
            what = f"attachment {attachment.child!r} to {attachment.parent!r}"
            for end in (attachment.child, attachment.parent):
                if end not in seen:
                    raise ValueError(f"{what}: no node {end!r}")
                _may_name(what, attachment.layer, f"node {end!r}", seen[end].layer)
            if attachment.child == attachment.parent:
                raise ValueError(f"{what}: a node can't be its own parent")
            if attachment.parent in seen[attachment.child].parents:
                raise ValueError(f"{what}: {attachment.child!r} has it as a parent already")
            if (attachment.child, attachment.parent) in pairs:
                raise ValueError(f"{what}: listed twice")
            pairs.add((attachment.child, attachment.parent))
        return self

    def node(self, slug: str) -> NodeSpec:
        return next(n for n in self.nodes if n.slug == slug)


def _unique(names: list[str], what: str) -> set[str]:
    if len(set(names)) != len(names):
        raise ValueError(f"a {what} name is listed twice")
    return set(names)


def available(layer: Layer) -> set[Layer]:
    """The layer and every layer it is built on, however far down."""
    found: set[Layer] = {layer}
    for below in BUILT_ON[layer]:
        found |= available(below)
    return found


def _may_name(by: str, layer: Layer, what: str, in_layer: Layer) -> None:
    """An entry names entries of its own layer or of a layer it is built on, never a sibling's."""
    if in_layer not in available(layer):
        raise ValueError(f"{by} ({layer}) names {what}, which is in layer {in_layer!r}")


def _slug_follows_layer(slug: str, layer: Layer) -> None:
    """A layer's slug prefix is on its categories and on no other layer's, so an item slug never
    has the shape of a taxonomy slug."""
    prefix = SLUG_PREFIX.get(layer)
    if prefix is not None and not slug.startswith(prefix):
        raise ValueError(f"node {slug!r}: slugs of layer {layer} start with {prefix!r}")
    if prefix is None and any(slug.startswith(other) for other in set(SLUG_PREFIX.values())):
        raise ValueError(
            f"node {slug!r}: only slugs of a layer with a prefix start with one, and {layer} "
            "has none"
        )


def _fits(value_type: str, value: StatValue) -> bool:
    """Whether a TOML value can be a stat of this type. A bool is not a number here."""
    if value_type == "bool":
        return isinstance(value, bool)
    if isinstance(value, bool):
        return False
    if value_type == "int":
        return isinstance(value, int)
    if value_type == "float":
        return isinstance(value, int | float)
    return isinstance(value, str)


def load_builtin() -> SeedSpec:
    text = resources.files("lorenzo_cli.seed").joinpath("builtin.toml").read_text("utf-8")
    return SeedSpec.model_validate(tomllib.loads(text))
