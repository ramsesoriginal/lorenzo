"""The built-in seed as data (ADR 0143): groups, stat definitions, taxonomy nodes and the weight
recipe, each with a layer. Loaded from `builtin.toml` and validated, so a typo in the seed is a
test failure and never a half-seeded tenant."""

from __future__ import annotations

import re
import tomllib
from importlib import resources
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Layer = Literal["core", "dnd5e"]
LAYERS: tuple[Layer, ...] = ("core", "dnd5e")
ValueType = Literal["int", "float", "text", "bool"]

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


class RecipeSpec(_Strict):
    """A computed stat on a node: `contents(source)` or `sum(terms...)`."""

    node: str
    stat: str
    kind: Literal["contents", "sum"]
    source: str | None = None
    terms: list[str] = Field(default_factory=list)
    layer: Layer


class SeedSpec(_Strict):
    schema_version: Literal[1] = Field(alias="schema")
    version: str
    groups: list[GroupSpec] = Field(alias="group")
    definitions: list[DefinitionSpec] = Field(alias="definition")
    nodes: list[NodeSpec] = Field(alias="node")
    recipes: list[RecipeSpec] = Field(alias="recipe")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        groups = _unique([g.name for g in self.groups], "group")
        defs = {d.name: d for d in self.definitions}
        _unique([d.name for d in self.definitions], "definition")
        for definition in self.definitions:
            if definition.group not in groups:
                raise ValueError(f"definition {definition.name!r}: no group {definition.group!r}")

        seen: dict[str, NodeSpec] = {}
        for node in self.nodes:
            if not _SLUG.match(node.slug):
                raise ValueError(f"node slug {node.slug!r} is not a valid slug")
            if node.slug in seen:
                raise ValueError(f"node {node.slug!r} is listed twice")
            for parent in node.parents:
                # Parents first, so the file order is a valid creation order and cycles can't exist.
                if parent not in seen:
                    raise ValueError(f"node {node.slug!r}: parent {parent!r} must be listed first")
            for tag in node.tags:
                if tag not in defs or defs[tag].value_type != "bool":
                    raise ValueError(f"node {node.slug!r}: tag {tag!r} is not a bool definition")
            _layer_ok(node.slug, node.layer, [seen[p].layer for p in node.parents])
            seen[node.slug] = node

        for recipe in self.recipes:
            if recipe.node not in seen:
                raise ValueError(f"recipe {recipe.stat!r}: no node {recipe.node!r}")
            if recipe.stat not in defs:
                raise ValueError(f"recipe on {recipe.node!r}: no definition {recipe.stat!r}")
            referenced = [recipe.source] if recipe.source else recipe.terms
            for name in referenced:
                if name not in defs:
                    raise ValueError(f"recipe {recipe.stat!r}: no definition {name!r}")
            if recipe.kind == "contents" and (recipe.source is None or recipe.terms):
                raise ValueError(f"recipe {recipe.stat!r}: contents takes a source, no terms")
            if recipe.kind == "sum" and (recipe.source is not None or not recipe.terms):
                raise ValueError(f"recipe {recipe.stat!r}: sum takes terms, no source")
        return self

    def node(self, slug: str) -> NodeSpec:
        return next(n for n in self.nodes if n.slug == slug)


def _unique(names: list[str], what: str) -> set[str]:
    if len(set(names)) != len(names):
        raise ValueError(f"a {what} name is listed twice")
    return set(names)


def _layer_ok(slug: str, layer: str, parent_layers: list[str]) -> None:
    """A node's parents are in its own layer or in core, never in another system's layer."""
    for parent_layer in parent_layers:
        if parent_layer not in (layer, "core"):
            raise ValueError(f"node {slug!r} ({layer}) has a parent in layer {parent_layer!r}")
    # Slug prefix follows the layer, so an item slug never has the shape of a taxonomy slug.
    prefixed = slug.startswith("dnd5e-")
    if (layer == "dnd5e") != prefixed:
        raise ValueError(
            f"node {slug!r}: slugs start with 'dnd5e-' exactly when the layer is dnd5e"
        )


def load_builtin() -> SeedSpec:
    text = resources.files("lorenzo_cli.seed").joinpath("builtin.toml").read_text("utf-8")
    return SeedSpec.model_validate(tomllib.loads(text))
