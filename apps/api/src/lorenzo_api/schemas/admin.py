import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, StringConstraints

from lorenzo_api.models import User

__all__ = [
    "AdminUserOut",
    "DelistRepositoryRequest",
    "DelistedRepositoryOut",
    "RelistedRepositoryOut",
    "SuspendUserRequest",
]


class AdminUserOut(BaseModel):
    """GET /admin/users, PUT/DELETE /admin/users/{id}/suspend - see ADR
    0057. Deliberately more than `UserRefOut` exposes (email, suspension
    state, the full ADR 0060 profile) - admin-only, unlike that public
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
    """PUT /admin/users/{id}/suspend body - see ADR 0057."""

    reason: str | None = None


DELIST_REASON_MAX = 500


class DelistRepositoryRequest(BaseModel):
    """PUT /admin/repositories/{id}/delist body - ADR 0297: why, in 1 to 500 characters. The
    repository's Owners read it, in the notice and on their repository's page."""

    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DELIST_REASON_MAX)
    ]


class DelistedRepositoryOut(BaseModel):
    """A repository the platform's operators have off Discover: GET /admin/repositories/delisted
    and PUT /admin/repositories/{id}/delist - ADR 0297. `delisted_by` is the operator's account,
    which only operators read (`delisted_by_nickname` its nickname, where it has one); the
    repository's own members read the reason and the time and never who."""

    id: uuid.UUID
    name: str
    slug: str
    reason: str
    delisted_at: datetime
    delisted_by: uuid.UUID | None
    delisted_by_nickname: str | None


class RelistedRepositoryOut(BaseModel):
    """DELETE /admin/repositories/{id}/delist: `relisted` says whether it had been delisted
    (a repository that was not is left as it is) - ADR 0297."""

    id: uuid.UUID
    name: str
    relisted: bool
