"""What a reviewer is told of the writing shared with them (ADR 0508)."""

import uuid

from pydantic import BaseModel


class SharedForReviewOut(BaseModel):
    """An Edition shared with the caller for review: where to open it, and its name."""

    tenant_id: uuid.UUID
    edition_id: uuid.UUID
    name: str
