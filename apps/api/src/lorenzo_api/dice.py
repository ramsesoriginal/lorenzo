"""A dice expression as parts, and the notation it is written and read in (RFC 0056, ADR 0462).

`2d6`, `W20`, `4d6dl1`: a count, a number of sides and an optional drop of the lowest or the highest
results. Lorenzo states dice and never rolls them, so this is a value type and its text, nothing
random. The value is held as parts; the text is produced from them (`notation`), and parsed only
when it arrives (`parse`).
"""

import re
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import comb
from typing import Literal, Protocol

__all__ = [
    "columns",
    "of_row",
    "MAX_COUNT",
    "MAX_SIDES",
    "MIN_SIDES",
    "Dice",
    "InvalidDice",
    "from_parts",
    "parse",
]

MAX_COUNT = 100
MIN_SIDES = 2
MAX_SIDES = 1000

DropMode = Literal["lowest", "highest"]

# `[count] (d|w) sides [d [l|h] number]`, case-insensitive, nothing else. The drop marker is `D`
# alone (only the die marker takes `W`), and a bare `d` before the number drops the lowest.
_NOTATION = re.compile(r"(?P<count>\d+)?[dw](?P<sides>\d+)(?:d(?P<mode>[lh])?(?P<drop>\d+))?")


class InvalidDice(ValueError):
    """A dice value that is not one: `part` names what failed (`notation`, `count`, `sides` or
    `drop`)."""

    def __init__(self, part: str, message: str) -> None:
        super().__init__(message)
        self.part = part


@dataclass(frozen=True)
class Dice:
    """`count` dice of `sides` sides, the `drop_count` lowest or highest results dropped."""

    count: int
    sides: int
    drop_mode: DropMode | None = None
    drop_count: int | None = None

    @property
    def notation(self) -> str:
        """The canonical form: lowercase `d`, the count left out when it is 1, and an explicit `dl`
        or `dh` for a drop."""
        text = f"{'' if self.count == 1 else self.count}d{self.sides}"
        if self.drop_mode is not None:
            text += f"d{self.drop_mode[0]}{self.drop_count}"
        return text

    @property
    def kept(self) -> int:
        """How many dice count: all but the dropped."""
        return self.count - (self.drop_count or 0)

    @property
    def minimum(self) -> int:
        """The least a roll can be: every kept die shows 1."""
        return self.kept

    @property
    def maximum(self) -> int:
        """The most a roll can be: every kept die shows its highest face."""
        return self.kept * self.sides

    @property
    def average(self) -> Fraction:
        """The exact expectation of the kept dice, from the order statistics of the dice (RFC 0056
        section 4), memoised by value."""
        return _average(self.count, self.sides, self.drop_mode, self.drop_count)

    def parts(self) -> dict[str, object]:
        """The parts as the API shows them."""
        drop = (
            None if self.drop_mode is None else {"mode": self.drop_mode, "count": self.drop_count}
        )
        return {"count": self.count, "sides": self.sides, "drop": drop}


def from_parts(
    count: object, sides: object, drop_mode: object = None, drop_count: object = None
) -> Dice:
    """A `Dice` from its parts, checked against the limits: count 1 to 100, sides 2 to 1000, a drop
    of 1 up to the count minus 1 (at least one die is kept). Raises `InvalidDice` naming the part.
    """
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_COUNT:
        raise InvalidDice("count", f"The number of dice is a whole number from 1 to {MAX_COUNT}")
    if not isinstance(sides, int) or isinstance(sides, bool) or not MIN_SIDES <= sides <= MAX_SIDES:
        raise InvalidDice(
            "sides", f"The number of sides is a whole number from {MIN_SIDES} to {MAX_SIDES}"
        )
    if drop_mode is None and drop_count is None:
        return Dice(count, sides)
    if drop_mode == "lowest":
        mode: DropMode = "lowest"
    elif drop_mode == "highest":
        mode = "highest"
    else:
        raise InvalidDice("drop", "A drop is of the lowest or the highest dice")
    if (
        not isinstance(drop_count, int)
        or isinstance(drop_count, bool)
        or not 1 <= drop_count <= count - 1
    ):
        raise InvalidDice(
            "drop",
            f"A drop is a whole number from 1 to {count - 1}: at least one of {count} dice is kept",
        )
    return Dice(count, sides, mode, drop_count)


def parse(text: str) -> Dice:
    """The `Dice` a notation says, in any accepted form (`d20`, `W20`, `2W6`, `4d6d1`, `4D6DL1`);
    spaces around the whole value are ignored. Raises `InvalidDice`."""
    found = _NOTATION.fullmatch(text.strip().lower())
    if found is None:
        raise InvalidDice(
            "notation", f"{text!r} is not dice: write it like 2d6, W20 or 4d6dl1 (a drop: dl or dh)"
        )
    mode: DropMode | None = None
    drop: int | None = None
    if found["drop"] is not None:
        mode = "highest" if found["mode"] == "h" else "lowest"
        drop = int(found["drop"])
    return from_parts(
        1 if found["count"] is None else int(found["count"]), int(found["sides"]), mode, drop
    )


class _HoldsDice(Protocol):
    dice_count: int | None
    dice_sides: int | None
    dice_drop_mode: str | None
    dice_drop_count: int | None


def of_row(row: _HoldsDice) -> Dice | None:
    """The `Dice` an `entity_stat` row (or a row of `v_effective_stat`) holds in its `dice_*`
    columns, or None when it holds none."""
    if row.dice_count is None:
        return None
    return from_parts(row.dice_count, row.dice_sides, row.dice_drop_mode, row.dice_drop_count)


def columns(value: Dice | None) -> dict[str, int | str | None]:
    """The four `dice_*` columns for a value, all null for none."""
    if value is None:
        return {
            "dice_count": None,
            "dice_sides": None,
            "dice_drop_mode": None,
            "dice_drop_count": None,
        }
    return {
        "dice_count": value.count,
        "dice_sides": value.sides,
        "dice_drop_mode": value.drop_mode,
        "dice_drop_count": value.drop_count,
    }


@lru_cache(maxsize=4096)
def _average(count: int, sides: int, drop_mode: str | None, drop_count: int | None) -> Fraction:
    """The expected sum of the kept dice, exactly.

    With the dice in order, the k-th lowest is at least `v` when at least `count - k + 1` dice show
    `v` or more, so its expectation is the sum over `v` of that tail of a binomial: `a` faces of
    `sides` qualify (`a = sides - v + 1`) and `b = v - 1` do not. The sum of the tails of the ranks
    that are kept is taken over a common denominator, `sides ** count`, in whole numbers, and made
    one fraction at the end.
    """
    drop = drop_count or 0
    if drop == 0:
        return Fraction(count * (sides + 1), 2)
    # `m = count - k + 1` for a kept rank `k`: dropping the lowest keeps ranks drop+1..count, so
    # m runs 1..count-drop; dropping the highest keeps ranks 1..count-drop, so m runs drop+1..count.
    first, last = (1, count - drop) if drop_mode == "lowest" else (drop + 1, count)
    total = 0
    for v in range(1, sides + 1):
        a, b = sides - v + 1, v - 1
        powers_a = [1] * (count + 1)
        powers_b = [1] * (count + 1)
        for j in range(1, count + 1):
            powers_a[j] = powers_a[j - 1] * a
            powers_b[j] = powers_b[j - 1] * b
        terms = [comb(count, j) * powers_a[j] * powers_b[count - j] for j in range(count + 1)]
        # tails[m] is the sum of terms[m..count]
        tail = 0
        tails = [0] * (count + 2)
        for j in range(count, -1, -1):
            tail += terms[j]
            tails[j] = tail
        total += sum(tails[first : last + 1])
    return Fraction(total, sides**count)
