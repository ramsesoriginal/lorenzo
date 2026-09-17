import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

__all__ = ["AdminNotificationCreate", "NotificationCreate", "NotificationOut"]


class NotificationOut(BaseModel):
    """GET /me/notifications, GET /me/notifications/sent, POST /me/
    notifications/{id}/read - see ADR 0058/0061. A plain ORM passthrough -
    every field is copied onto the row directly at creation time, nothing
    derived at read time. `user_id` (the recipient) and `batch_id` are
    harmless to echo back on a recipient's own inbox read (it's already
    their own id) and exactly what a sender needs reading the same shape
    from the other side via `/sent`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    user_id: uuid.UUID
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
    scope routes - see ADR 0058. An omitted `recipient_user_id` broadcasts
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
    yet (ADR 0058, a deliberately smaller, safer slice than a mass-mailing
    feature).
    """

    recipient_user_id: uuid.UUID
