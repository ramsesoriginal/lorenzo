"""Account-scoped manuscript length targets (ADR 0383)."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.exceptions import (
    EventOrderPreconditionRequiredError,
    InformationManagementForbiddenError,
    InvalidKindRequestError,
    PreconditionFailedError,
)
from lorenzo_api.manuscript_redirects import require_unjoined
from lorenzo_api.models import ManuscriptGoal
from lorenzo_api.routers.writing import author, entry, writing_kind

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)
GoalScope = Literal["direct", "assembled"]


class LengthTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_words: int | None = Field(ge=1, le=100000000, strict=True)


class LengthGoalOut(LengthTarget):
    version: int


async def accessible_goal(
    session: SessionDep,
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    user: CurrentUser,
    scope: GoalScope,
    *,
    write: bool = False,
) -> ManuscriptGoal | None:
    if write:
        await author(session, tenant_id, user)
    else:
        await require_tenant_participant(session, tenant_id=tenant_id, user=user)
        if not await is_tenant_author(session, tenant_id=tenant_id, user_id=user.id):
            raise InformationManagementForbiddenError(
                detail="Only library Authors can keep writing goals."
            )
    await entry(session, tenant_id, id, user)
    await require_unjoined(session, id)
    if await writing_kind(session, id) == "book":
        raise InvalidKindRequestError(detail="Choose an Edition for this Book's length goal.")
    return await session.get(ManuscriptGoal, (id, user.id, scope))


def view(row: ManuscriptGoal | None, response: Response) -> LengthGoalOut:
    goal = LengthGoalOut(
        target_words=row.target_words if row else None, version=row.version if row else 0
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["ETag"] = f'"{goal.version}"'
    return goal


@router.get("/entries/{id}/length-goals/{scope}")
async def get_goal(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    scope: GoalScope,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> LengthGoalOut:
    return view(await accessible_goal(session, tenant_id, id, user, scope), response)


@router.put("/entries/{id}/length-goals/{scope}")
async def put_goal(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    scope: GoalScope,
    body: LengthTarget,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> LengthGoalOut:
    row = await accessible_goal(session, tenant_id, id, user, scope, write=True)
    current = view(row, response)
    if not if_match:
        raise EventOrderPreconditionRequiredError(
            detail="Read your length goal before changing it."
        )
    if current.target_words == body.target_words:
        return current
    if if_match != response.headers["ETag"]:
        raise PreconditionFailedError(
            detail="Your length goal changed. Read it again before saving."
        )
    if row is None:
        row = ManuscriptGoal(
            tenant_id=tenant_id,
            entry_id=id,
            author_id=user.id,
            scope=scope,
            version=1,
            target_words=body.target_words,
        )
        session.add(row)
    else:
        row.version += 1
        row.target_words = body.target_words
    out = view(row, response)
    await session.commit()
    return out
