"""A dice value in a request and in a response (RFC 0056, ADR 0462)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from lorenzo_api import dice
from lorenzo_api.models import StatValueType

__all__ = ["DiceDropIn", "DiceDropOut", "DiceIn", "DiceOut", "dice_out"]


class DiceDropIn(BaseModel):
    """The dice a value drops: the `count` lowest or highest results. Checked with the notation's
    limits by the route (422 `invalid-dice` naming the part), not by the schema."""

    model_config = ConfigDict(extra="forbid")
    mode: str
    count: int


class DiceIn(BaseModel):
    """A dice value given as its parts instead of its notation: `{"count": 4, "sides": 6,
    "drop": {"mode": "lowest", "count": 1}}` is `4d6dl1`."""

    model_config = ConfigDict(extra="forbid")
    count: int
    sides: int
    drop: DiceDropIn | None = None


class DiceDropOut(BaseModel):
    mode: Literal["lowest", "highest"]
    count: int


class DiceOut(BaseModel):
    """A dice value as its parts. The stat's `value` is its notation in the canonical form."""

    count: int
    sides: int
    drop: DiceDropOut | None = None


def dice_out(value_type: StatValueType, value: object) -> DiceOut | None:
    """The parts of a dice stat's value (its notation, as every read carries it), or None for a stat
    of any other type: such a row has no `dice` at all."""
    if value_type is not StatValueType.DICE or not isinstance(value, str):
        return None
    return DiceOut.model_validate(dice.parse(value).parts())
