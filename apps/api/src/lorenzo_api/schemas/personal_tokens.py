import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field

__all__ = [
    "DeviceCodeCreate",
    "DeviceCodeOut",
    "DeviceCodePreviewOut",
    "DeviceTokenRequest",
    "DeviceApproval",
    "PersonalTokenIssuedOut",
    "PersonalTokenOut",
]


class DeviceCodeCreate(BaseModel):
    """POST /device-codes - `client_name` is what the device calls itself ("lorenzo CLI on
    laptop"); the approval page shows it and offers it as the token's name.
    """

    client_name: str | None = Field(default=None, min_length=1, max_length=80)


class DeviceCodeOut(BaseModel):
    """RFC 8628 section 3.2, minus the redundant bits."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    interval: int
    expires_in: int


class DeviceTokenRequest(BaseModel):
    device_code: str = Field(min_length=1, max_length=200)


class DeviceCodePreviewOut(BaseModel):
    """GET /me/device-codes/{user_code} - what a signed-in user is shown before approving."""

    user_code: str
    client_name: str | None
    expires_at: datetime


class DeviceApproval(BaseModel):
    """POST /me/device-codes/{user_code}/approve. No expiry unless the user sets one."""

    name: str = Field(min_length=1, max_length=80)
    expires_at: AwareDatetime | None = None


class PersonalTokenOut(BaseModel):
    """A token as listed - never its secret; `hint` is its last four characters."""

    id: uuid.UUID
    name: str
    hint: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    is_expired: bool


class PersonalTokenIssuedOut(BaseModel):
    """The one answer that carries the secret (POST /device-codes/token on success)."""

    access_token: str
    token_type: str = "Bearer"
    id: uuid.UUID
    name: str
    expires_at: datetime | None
