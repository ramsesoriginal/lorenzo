import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

__all__ = ["AdminNotificationCreate", "NotificationCreate", "NotificationOut"]


class NotificationOut(BaseModel):
    """GET /me/notifications, POST /me/notifications/{id}/read - see ADR
    0054. A plain ORM passthrough - every field is copied onto the row
    directly at creation time, nothing derived at read time.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: str
    type: str
    tenant_id: uuid.UUID | None
    source_id: uuid.UUID | None
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


class NotificationCreate(BaseModel):
    """POST .../notifications body, shared by the tenant/campaign/character
    scope routes - see ADR 0054. An omitted `recipient_user_id` broadcasts
    to that scope's own roster (each route's own docstring says exactly
    who that includes) - not accepted at platform scope, which requires an
    explicit recipient (`AdminNotificationCreate` below).
    """

    recipient_user_id: uuid.UUID | None = None
    type: str
    title: str
    body: str


class AdminNotificationCreate(NotificationCreate):
    """POST /admin/notifications - platform scope requires an explicit
    recipient; no broadcast-to-every-user-on-the-platform mechanism exists
    yet (ADR 0054, a deliberately smaller, safer slice than a mass-mailing
    feature).
    """

    recipient_user_id: uuid.UUID
