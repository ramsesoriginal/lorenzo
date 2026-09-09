import uuid
from typing import Self

from pydantic import BaseModel

from lorenzo_api.models import Membership, User


class MembershipOut(BaseModel):
    """A tenant-wide administrative access grant - see ADR 0022/0023."""

    tenant_id: uuid.UUID
    role: str

    @classmethod
    def from_membership(cls, membership: Membership) -> Self:
        return cls(tenant_id=membership.tenant_id, role=membership.role.value)


class MeOut(BaseModel):
    """The caller's own identity and tenant-wide memberships - see ADR 0023.
    Exists purely to prove the token-verification pipeline end to end over
    real HTTP, not the start of a fuller /users API.
    """

    id: uuid.UUID
    authgear_subject_id: str
    memberships: list[MembershipOut]

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(
            id=user.id,
            authgear_subject_id=user.authgear_subject_id,
            memberships=[MembershipOut.from_membership(m) for m in user.memberships],
        )
