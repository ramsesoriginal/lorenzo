import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.grant_rules import RuleOptionOut

__all__ = [
    "ApplyIn",
    "ApplyOut",
    "DueGrantOut",
    "GrantSourceOut",
    "GrantsOut",
    "HeldGrantOut",
    "OpenChoiceOut",
    "OrphanOut",
    "PickIn",
    "RevokedOut",
]


class PickIn(BaseModel):
    """A holder's pick for one open choice of `apply` (ADR 0456): the rule, the source it is
    open through (`source_id`, an ancestor entry or an instance the holder holds), and the
    features chosen."""

    rule_id: uuid.UUID
    source_id: uuid.UUID
    options: list[uuid.UUID]


class ApplyIn(BaseModel):
    """POST .../grants/apply. `picks` fill open choices; `dry_run` reports what would happen and
    writes nothing; `override` (a GM's) lets a pick go below the minimum, above the maximum or past
    a prerequisite."""

    picks: list[PickIn] = []
    dry_run: bool = False
    override: bool = False


class GrantSourceOut(BaseModel):
    """The source a rule applies through: an entry on the holder's prototype walk
    (`ancestor`), or an active instance the holder holds (`instance`)."""

    id: uuid.UUID | None
    name: str
    kind: Literal["ancestor", "instance"]
    hidden: bool = False


class HeldGrantOut(BaseModel):
    """A feature the holder has through a rule (or, with no rule, by an award)."""

    record_id: uuid.UUID
    instance_id: uuid.UUID
    feature: EntitySummary
    rule_id: uuid.UUID | None
    label: str | None
    source: GrantSourceOut | None
    created_at: datetime


class DueGrantOut(BaseModel):
    """An automatic grant whose conditions hold and that has no record yet: what `apply` makes."""

    rule_id: uuid.UUID
    label: str | None
    source: GrantSourceOut
    feature: RuleOptionOut


class OpenChoiceOut(BaseModel):
    """A choose rule that holds and still has room (ADR 0456): how many the holder must and may
    pick, what it has picked, and the options that pass their prerequisites. An option that does
    not pass is left out; one the library hides is `a hidden entry`."""

    rule_id: uuid.UUID
    label: str | None
    source: GrantSourceOut
    minimum: int
    maximum: int
    picked: list[RuleOptionOut]
    options: list[RuleOptionOut]
    changeable: bool


class OrphanOut(BaseModel):
    """An active record whose source is gone or inactive, or whose conditions no longer hold:
    what the next request that checks, or an `apply`, revokes."""

    record_id: uuid.UUID
    rule_id: uuid.UUID | None
    label: str | None
    feature: RuleOptionOut
    instance_id: uuid.UUID | None
    reason: Literal["source", "conditions", "removed"]


class RevokedOut(OrphanOut):
    """A record `apply` revoked: its instance is deleted."""


class GrantsOut(BaseModel):
    """GET .../entities/{holder}/grants - what is held through rules and awards, what is due,
    the choices still open and what is orphaned (ADR 0456). A read never writes."""

    holder: EntitySummary
    held: list[HeldGrantOut]
    due: list[DueGrantOut]
    open_choices: list[OpenChoiceOut]
    orphaned: list[OrphanOut]


class ApplyOut(BaseModel):
    """What `apply` did (or, with `dry_run`, would do): the grants it made, the records it
    revoked, the choices still open, and whether the chain of grants was cut at the depth cap."""

    created: list[HeldGrantOut]
    revoked: list[RevokedOut]
    open_choices: list[OpenChoiceOut]
    dry_run: bool
    truncated: bool
