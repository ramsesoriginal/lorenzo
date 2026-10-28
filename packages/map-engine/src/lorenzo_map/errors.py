"""What the validator says when a document is refused.

The message is one of this module's own sentences, chosen by the check that failed. It never
repeats any part of the input, so a refusal reveals nothing about what was sent (ADR 0337).
"""

from __future__ import annotations


class MapDocumentError(ValueError):
    """A system, a geometry, a role, a style or a placement is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
