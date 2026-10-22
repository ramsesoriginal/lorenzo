"""Exact, bounded clock coordinates. Calendar ordinals are not clock readings."""

import re
from fractions import Fraction
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def rational(value: str) -> str:
    if not re.fullmatch(r"-?[0-9]{1,38}(?:/[1-9][0-9]{0,37}|\.[0-9]{1,38})?", value):
        raise ValueError("A clock number is too large")
    try:
        number = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("Use a finite number or a fraction such as 1/3") from error
    if len(str(abs(number.numerator))) > 38 or len(str(number.denominator)) > 38:
        raise ValueError("A clock number is too large")
    return str(number)


Rational = Annotated[str, Field(max_length=80), AfterValidator(rational)]


class ReadingRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lo: Rational
    hi: Rational
    lo_inclusive: bool = True
    hi_inclusive: bool = True

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if Fraction(self.lo) > Fraction(self.hi) or (
            self.lo == self.hi and not (self.lo_inclusive and self.hi_inclusive)
        ):
            raise ValueError("A reading must be a point or a nonempty range")
        return self

    def shift(self, offset: Fraction) -> ReadingRange:
        return self.model_copy(
            update={
                "lo": rational(str(Fraction(self.lo) + offset)),
                "hi": rational(str(Fraction(self.hi) + offset)),
            }
        )
