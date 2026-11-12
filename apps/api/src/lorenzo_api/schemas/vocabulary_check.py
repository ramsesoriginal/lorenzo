import uuid
from typing import Any, Literal

from pydantic import BaseModel

__all__ = ["CheckCode", "FindingOut"]

CheckCode = Literal[
    "computed-outside-scale",
    "above-hint",
    "formula-chain-depth",
    "unset-input",
    "own-value-shadows-formula",
    "tie",
]


class FindingOut(BaseModel):
    """One thing a library's stats got wrong without saying so (ADR 0458, RFC 0055). It names the
    stat, and the entry unless the finding is about the library's formulas; `message` is a
    sentence, `details` the numbers and ids behind it. `warning` is what an author most likely did
    not mean, `info` what the rules produce on purpose."""

    code: CheckCode
    severity: Literal["warning", "info"]
    entry_id: uuid.UUID | None
    stat_definition_id: uuid.UUID
    message: str
    details: dict[str, Any]
