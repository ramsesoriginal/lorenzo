"""The `pattern` the OpenAPI contract gives the string form of every Decimal.

Up to 2.13, pydantic always put a regex `pattern` on a Decimal's string form in JSON Schema. From
2.14 it puts none unless the schema generator asks for one (`get_decimal_pattern`, pydantic#13672),
and the pattern it builds when asked matches what pydantic really accepts and writes, exponent
notation (`1E+3`) included. Without the opt-in, every Decimal field in the contract would lose its
pattern, which oasdiff reports as a breaking change for each response field
(`response-property-pattern-removed`); with it, the patterns only change, which it reports as a
warning. FastAPI builds its schemas with its own `GenerateJsonSchema` subclass and has no setting
for it, so the opt-in goes on that class.
"""

from __future__ import annotations

from typing import Any

from fastapi._compat import v2 as fastapi_v2
from pydantic_core import core_schema


def _decimal_pattern(self: Any, schema: core_schema.DecimalSchema) -> str | None:
    pattern: str = self.build_decimal_pattern(schema)
    return pattern


def install() -> None:
    """Gives every Decimal in the OpenAPI contract the pattern pydantic builds for it."""
    fastapi_v2.GenerateJsonSchema.get_decimal_pattern = _decimal_pattern  # type: ignore[method-assign]
