"""Making a repository public and private - ADR 0290, RFC 0038 section 7, RFC 0037 section 6.

The routes over the rules of `repository_flips.py` (ADR 0289), all the Owner's, under
`/tenants/{tenant_id}`: `GET /flip-check` says what a flip would run into, `PUT /public` makes the
repository public with its first release, `DELETE /public` makes it private. While the deployment
does not accept public repositories (`public_repositories_enabled`) `PUT` is refused with
`public-repositories-not-available`; the other two still answer, which is the safe direction.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func, select

from lorenzo_api.config import get_settings
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    PublicRepositoriesNotAvailableError,
    PublicRepositorySummaryRequiredError,
)
from lorenzo_api.models import RepositorySubscription, Tenant
from lorenzo_api.release_fanout import drain_after_response
from lorenzo_api.repository_built_on import (
    built_on_behind,
    built_on_not_public,
    public_dependents,
)
from lorenzo_api.repository_delisting import delisted_out, refuse_if_delisted
from lorenzo_api.repository_flips import count_public_grants, make_private, make_public
from lorenzo_api.repository_profiles import profile_of
from lorenzo_api.routers.repositories import _authored, _require_owner, _require_repository
from lorenzo_api.schemas.repositories import BuiltOnBehindOut, PublishedOut, PublishRequest
from lorenzo_api.schemas.repository_flips import (
    BuiltOnPublicOut,
    FlipCheckOut,
    MadePrivateOut,
    MakePublicRequest,
    PublicDependentOut,
)
from lorenzo_api.schemas.tenants import TenantOut

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["repositories"])


@router.get("/flip-check")
async def check_flip(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
) -> FlipCheckOut:
    """What making the repository public, or private, would run into, before it is asked: the
    repositories it is built on that are not public (with whether the caller owns each) or are
    behind, the public repositories built on it, the summary, and how many libraries hold a
    grant they gave themselves by copying it and how many it invited. Owner only; writes
    nothing."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    repository = await _require_repository(session, tenant_id)
    profile = await profile_of(session, tenant_id)
    invited = await session.scalar(
        select(func.count())
        .select_from(RepositorySubscription)
        .where(
            RepositorySubscription.repository_tenant_id == tenant_id,
            RepositorySubscription.source == "invited",
        )
    )
    behind = await built_on_behind(session, tenant_id)
    return FlipCheckOut(
        available=get_settings().public_repositories_enabled,
        visibility="public" if profile.visibility == "public" else "private",
        has_summary=bool(profile.summary.strip()),
        built_on_not_public=[
            BuiltOnPublicOut(**r) for r in await built_on_not_public(session, tenant_id, user.id)
        ],
        built_on_behind=[BuiltOnBehindOut.model_validate(b.as_json()) for b in behind],
        public_dependents=[
            PublicDependentOut(**d) for d in await public_dependents(session, tenant_id, user.id)
        ],
        public_libraries=await count_public_grants(session, tenant_id),
        invited_libraries=invited or 0,
        delisted=delisted_out(repository),
    )


@router.put("/public")
async def make_repository_public(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    body: MakePublicRequest | None = None,
) -> PublishedOut:
    """Makes the repository public and makes its first public release, together or not at all
    (ADR 0289): the release, its document and its notice are those of `PUT .../published`.
    Needs a summary, given here or already on the profile (`422
    public-repository-summary-required`), every repository it is built on public (`409
    built-on-not-public`) and up to date (`409 built-on-behind`), and says what a visitor may
    look at before copying (`preview`, the default `showcase`). Owner only; `422
    public-repositories-not-available` while the deployment does not accept public
    repositories."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    if not get_settings().public_repositories_enabled:
        raise PublicRepositoriesNotAvailableError(
            detail="Public repositories are not available yet. This repository stays private."
        )
    refuse_if_delisted(tenant)
    body = body or MakePublicRequest()
    profile = await profile_of(session, tenant_id)
    if body.summary is not None:
        profile.summary = body.summary
    profile.preview = body.preview
    if not profile.summary.strip():
        raise PublicRepositorySummaryRequiredError(
            detail="Say in a line or two what this repository is, so that a visitor can tell "
            "whether it is for them."
        )
    published = await make_public(
        session,
        repository=tenant,
        user_id=user.id,
        body=PublishRequest(
            label=body.label,
            notes=body.notes,
            breaking=body.breaking,
            acknowledge_breaking=body.acknowledge_breaking,
        ),
    )
    release_out = _authored(published.release, current=True, kept=True)
    await session.commit()
    drain_after_response(background_tasks, session)
    await set_tenant_rls_context(session, tenant_id)
    return PublishedOut(
        **TenantOut.model_validate(await session.get_one(Tenant, tenant_id)).model_dump(),
        release=release_out,
    )


@router.delete("/public")
async def make_repository_private(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    acknowledge_revokes: bool = False,
) -> MadePrivateOut:
    """Makes the repository private. `409 public-repositories-built-on-it` while a public
    repository is built on it, and `409 public-copies-would-be-cut-off` with the number of
    libraries until `acknowledge_revokes` says the Owner has been told: they keep what they
    copied and lose its updates. Invited libraries keep their grant. Owner only."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    made = await make_private(
        session, repository=tenant, user_id=user.id, acknowledge_revokes=acknowledge_revokes
    )
    await session.commit()
    drain_after_response(background_tasks, session)
    return MadePrivateOut(revoked=made.revoked)
