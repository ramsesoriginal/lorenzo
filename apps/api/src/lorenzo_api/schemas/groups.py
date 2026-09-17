import uuid
from typing import Literal

from pydantic import BaseModel

from lorenzo_api.schemas.common import ProblemOut

__all__ = [
    "GroupCreate",
    "GroupUpdate",
    "DuplicateGroupRequest",
    "GroupMemberResultItem",
]


class GroupCreate(BaseModel):
    """POST /groups - see ADR 0064. Creates a fresh bare Entity to serve as
    the group, plus one GroupMember row per id in member_character_ids
    (each individually validated and authorized, same as the single-member
    PUT route below).
    """

    name: str
    member_character_ids: list[uuid.UUID] = []


class GroupUpdate(BaseModel):
    """PATCH /groups/{id} - only Entity.name is mutable, a group has
    nothing else of its own.
    """

    name: str | None = None


class DuplicateGroupRequest(BaseModel):
    """POST /groups/{id}/duplicate - name defaults to the source group's
    own name when omitted.
    """

    name: str | None = None


class GroupMemberResultItem(BaseModel):
    """POST /groups/{id}/members/bulk - one output entry, always present
    for every input entry regardless of outcome (never all-or-nothing,
    matching BulkAssignResultItem/BulkMembershipResultItem's identical
    shape). Exactly one of problem/status="ok" applies.
    """

    character_entity_id: uuid.UUID
    status: Literal["ok", "error"]
    problem: ProblemOut | None = None
