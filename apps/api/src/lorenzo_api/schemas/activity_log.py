import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

__all__ = ["AuditLogEntryOut"]


class AuditLogEntryOut(BaseModel):
    """GET /tenants/{tenant_id}/activity-log - see ADR 0059. A plain ORM
    passthrough, same shape `NotificationOut` already uses for the same
    reason: every field is copied onto the row directly at creation time,
    nothing derived at read time.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    detail: str | None
    created_at: datetime
