import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel

from lorenzo_api.models import User

__all__ = ["AdminUserOut", "SuspendUserRequest"]


class AdminUserOut(BaseModel):
    """GET /admin/users, PUT/DELETE /admin/users/{id}/suspend - see ADR
    0053. Deliberately more than `UserRefOut` exposes (email, suspension
    state, the full ADR 0056 profile) - admin-only, unlike that public
    exact-match lookup.
    """

    id: uuid.UUID
    email: str | None
    nickname: str | None
    display_name: str | None
    pronouns: str | None
    bio: str | None
    locales: list[str]
    user_color: str | None
    suspended_at: datetime | None
    suspension_reason: str | None
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(
            id=user.id,
            email=user.email,
            nickname=user.nickname,
            display_name=user.display_name,
            pronouns=user.pronouns,
            bio=user.bio,
            locales=user.locales,
            user_color=user.user_color,
            suspended_at=user.suspended_at,
            suspension_reason=user.suspension_reason,
            created_at=user.created_at,
        )


class SuspendUserRequest(BaseModel):
    """PUT /admin/users/{id}/suspend body - see ADR 0053."""

    reason: str | None = None
