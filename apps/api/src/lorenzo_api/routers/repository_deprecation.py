"""Retiring a repository and bringing it back - ADR 0383, RFC 0038 section 7.

The Owner's two routes under `/tenants/{tenant_id}`, over the rules of `repository_deprecation.py`:
`PUT /deprecation` retires the repository, with an optional message the libraries that hold it
read, and `DELETE /deprecation` brings it back. A retired repository keeps its updates for the
libraries that copied it and blocks new copies and leaves Discover. Each change tells the libraries
that hold it through the release fan-out, after the response.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends

from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_context
from lorenzo_api.release_fanout import drain_after_response
from lorenzo_api.repository_deprecation import (
    deprecate_repository,
    deprecated_out,
    undeprecate_repository,
)
from lorenzo_api.routers.repositories import _require_owner, _require_repository
from lorenzo_api.schemas.repository_deprecation import DeprecateRequest, UndeprecatedOut
from lorenzo_api.schemas.repository_profiles import DeprecatedOut

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["repositories"])


@router.put("/deprecation")
async def deprecate(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    body: DeprecateRequest | None = None,
) -> DeprecatedOut:
    """Retires the repository, public or not: libraries that already hold it keep their copy and
    its updates, and nobody can copy it any more; it leaves Discover. The optional `message` (1 to
    500 characters) is read by the libraries that hold it. Idempotent: retiring a retired
    repository replaces the message and keeps the time it was first retired, and tells nobody
    again. The first time, the Owners and Organizers of every library that holds it are told.
    Owner only."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    repository = await _require_repository(session, tenant_id)
    await deprecate_repository(
        session,
        repository=repository,
        user_id=user.id,
        message=(body or DeprecateRequest()).message,
    )
    out = deprecated_out(repository)
    assert out is not None
    await session.commit()
    drain_after_response(background_tasks, session)
    return out


@router.delete("/deprecation")
async def undeprecate(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> UndeprecatedOut:
    """Brings a retired repository back: it can be copied again, and is listed again if it is
    public. The libraries that hold it are told. A repository that is not retired is left as it
    is (`undeprecated: false`). Owner only."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    repository = await _require_repository(session, tenant_id)
    changed = await undeprecate_repository(session, repository=repository, user_id=user.id)
    await session.commit()
    drain_after_response(background_tasks, session)
    return UndeprecatedOut(undeprecated=changed)
