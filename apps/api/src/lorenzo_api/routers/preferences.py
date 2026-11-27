"""A person's preferences in their account, and their saved views of lists (ADR 0532)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    SavedViewTooLargeError,
    TooManySavedViewsError,
)
from lorenzo_api.models import SavedView, User

me_router = APIRouter(prefix="/me/preferences", tags=["preferences"])
saved_views_router = APIRouter(
    prefix="/tenants/{tenant_id}/saved-views",
    tags=["preferences"],
    dependencies=[Depends(get_tenant_or_404)],
)

MAX_VIEWS = 50
MAX_QUERY_BYTES = 4000


class Preferences(BaseModel):
    """How the web apps look for a person. Each part is optional: one that is absent is the
    device's own choice, which is also what applies before they sign in."""

    model_config = ConfigDict(extra="forbid")
    theme: Literal["system", "light", "dark"] | None = None
    density: Literal["comfortable", "compact", "dense"] | None = None
    motion: Literal["system", "reduced"] | None = None


@me_router.get("")
async def get_preferences(user: CurrentUser, session: SessionDep) -> Preferences:
    row = await session.get_one(User, user.id)
    return Preferences.model_validate(row.preferences or {})


@me_router.put("")
async def replace_preferences(
    body: Preferences, user: CurrentUser, session: SessionDep
) -> Preferences:
    """Replaces the person's preferences with what is sent; a part left out is cleared. There is
    no `If-Match`: they are one person's own and the last write is the one they meant."""
    row = await session.get_one(User, user.id)
    row.preferences = body.model_dump(exclude_none=True)
    await session.commit()
    return body


class SavedViewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9-]*$")
    list: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=80)
    query: dict[str, Any]


class SavedViewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    query: dict[str, Any] | None = None


class SavedViewOut(BaseModel):
    id: uuid.UUID
    app: str
    list: str
    name: str
    query: dict[str, Any]
    updated_at: datetime

    @classmethod
    def of(cls, row: SavedView) -> SavedViewOut:
        return cls(
            id=row.id,
            app=row.app,
            list=row.list,
            name=row.name,
            query=row.query,
            updated_at=row.updated_at,
        )


def _checked(query: dict[str, Any]) -> None:
    if len(json.dumps(query, separators=(",", ":")).encode()) > MAX_QUERY_BYTES:
        raise SavedViewTooLargeError(
            detail=f"A saved view may hold at most {MAX_QUERY_BYTES} bytes."
        )


async def _own(
    session: SessionDep, tenant_id: uuid.UUID, user: CurrentUser, view_id: uuid.UUID
) -> SavedView:
    row = await session.scalar(
        select(SavedView).where(
            SavedView.id == view_id,
            SavedView.tenant_id == tenant_id,
            SavedView.user_id == user.id,
        )
    )
    if row is None:
        raise EntityNotFoundError(detail="No such saved view")
    return row


@saved_views_router.get("")
async def list_saved_views(
    tenant_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    app: Annotated[str | None, Query(max_length=40)] = None,
    list_: Annotated[str | None, Query(alias="list", max_length=60)] = None,
) -> list[SavedViewOut]:
    """The caller's own saved views in this library, by name; never anyone else's."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    stmt = select(SavedView).where(SavedView.tenant_id == tenant_id, SavedView.user_id == user.id)
    if app is not None:
        stmt = stmt.where(SavedView.app == app)
    if list_ is not None:
        stmt = stmt.where(SavedView.list == list_)
    rows = await session.scalars(stmt.order_by(SavedView.app, SavedView.list, SavedView.name))
    return [SavedViewOut.of(r) for r in rows]


@saved_views_router.post("", status_code=201)
async def create_saved_view(
    tenant_id: uuid.UUID, body: SavedViewIn, user: CurrentUser, session: SessionDep
) -> SavedViewOut:
    """Keeps a view under a name; a name already taken for that list replaces its query."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    _checked(body.query)
    existing = await session.scalar(
        select(SavedView).where(
            SavedView.tenant_id == tenant_id,
            SavedView.user_id == user.id,
            SavedView.app == body.app,
            SavedView.list == body.list,
            SavedView.name == body.name,
        )
    )
    if existing is not None:
        existing.query = body.query
        existing.updated_at = datetime.now(UTC)
        row = existing
    else:
        held = await session.scalar(
            select(func.count()).where(
                SavedView.tenant_id == tenant_id, SavedView.user_id == user.id
            )
        )
        if (held or 0) >= MAX_VIEWS:
            raise TooManySavedViewsError(
                detail=f"A person may keep at most {MAX_VIEWS} saved views in a library."
            )
        row = SavedView(
            tenant_id=tenant_id,
            user_id=user.id,
            app=body.app,
            list=body.list,
            name=body.name,
            query=body.query,
        )
        session.add(row)
    await session.flush()
    out = SavedViewOut.of(row)
    await session.commit()
    return out


@saved_views_router.patch("/{view_id}")
async def update_saved_view(
    tenant_id: uuid.UUID,
    view_id: uuid.UUID,
    body: SavedViewUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> SavedViewOut:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    row = await _own(session, tenant_id, user, view_id)
    if body.query is not None:
        _checked(body.query)
        row.query = body.query
    if body.name is not None:
        row.name = body.name
    row.updated_at = datetime.now(UTC)
    await session.flush()
    out = SavedViewOut.of(row)
    await session.commit()
    return out


@saved_views_router.delete("/{view_id}", status_code=204)
async def delete_saved_view(
    tenant_id: uuid.UUID, view_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    row = await _own(session, tenant_id, user, view_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)
