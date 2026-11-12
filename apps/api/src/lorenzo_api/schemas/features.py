import uuid
from typing import Literal

from pydantic import BaseModel

from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import EntityStatValueOut
from lorenzo_api.schemas.grant_rules import RuleOptionOut

__all__ = [
    "FeatureActiveIn",
    "FeatureAwardIn",
    "FeatureColumnsOut",
    "GrantedByOut",
    "HeldFeatureOut",
    "HeldFeaturesOut",
]


class FeatureAwardIn(BaseModel):
    """POST .../entities/{holder}/features - an award (ADR 0454): the feature, and optionally the
    switch the instance starts with (left out, it starts as its feature says)."""

    feature_id: uuid.UUID
    active: bool | None = None


class FeatureActiveIn(BaseModel):
    """PUT .../features/{instance}/active - the switch (ADR 0447's `active`, on a feature)."""

    active: bool


class FeatureColumnsOut(BaseModel):
    """GET .../features/prototypes/{feature_id} - the two columns of a feature (ADR 0454)."""

    id: uuid.UUID
    name: str
    repeatable: bool
    starts_inactive: bool


class GrantedByOut(BaseModel):
    """What gave a feature to its holder (ADR 0456): the record, the rule (and its label), and the
    source it was given from, an ancestor entry of the holder or an instance it holds."""

    record_id: uuid.UUID
    rule_id: uuid.UUID | None
    label: str | None
    source: RuleOptionOut | None
    source_kind: Literal["ancestor", "instance"] | None


class HeldFeatureOut(BaseModel):
    """One feature a holder has (ADR 0454): the instance, the feature it is of, the feature's
    types (the category entries among its parents, as many as the caller may see), its switch and
    its effective stats, the instance's own over the feature's, as an entry's read gives them."""

    id: uuid.UUID
    name: str
    feature: EntitySummary
    types: list[EntitySummary]
    active: bool
    stats: list[EntityStatValueOut]
    # The rule and the source that gave it (ADR 0456); none for an award.
    granted_by: GrantedByOut | None = None


class HeldFeaturesOut(BaseModel):
    """GET .../entities/{holder}/features - the holder and what it has, by name then id."""

    holder: EntitySummary
    features: list[HeldFeatureOut]
