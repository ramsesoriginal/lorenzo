import uuid

from pydantic import BaseModel

from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import EntityStatValueOut

__all__ = [
    "FeatureActiveIn",
    "FeatureAwardIn",
    "FeatureColumnsOut",
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


class HeldFeaturesOut(BaseModel):
    """GET .../entities/{holder}/features - the holder and what it has, by name then id."""

    holder: EntitySummary
    features: list[HeldFeatureOut]
