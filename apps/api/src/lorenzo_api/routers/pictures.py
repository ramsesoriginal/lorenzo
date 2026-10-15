import uuid

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.dependencies import OptionalUser, SessionDep, set_tenant_rls_context
from lorenzo_api.exceptions import ProfilePictureNotFoundError
from lorenzo_api.models import (
    CampaignProfilePicture,
    ProfilePicture,
    RepositoryProfile,
    Tenant,
    TenantKind,
    TenantProfilePicture,
    User,
    UserProfilePicture,
)
from lorenzo_api.profile_pictures import gravatar_url

# Deliberately its own router, with no router-level auth dependency and no
# CurrentUser on any route below - see ADR 0056. `routers/campaigns.py`'s
# own router applies `Depends(get_tenant_or_404)` at the router level, which
# itself requires `CurrentUser` - nesting a public route there would force
# authentication regardless of that route's own signature, so these three
# live here instead, deliberately public: a plain `<img src="...">` can't
# send a Bearer token. One exception since ADR 0300: a private repository's
# picture (`get_tenant_picture`) is for a signed-in user, so an app fetches it
# with the token and shows it from the response.
router = APIRouter(tags=["pictures"])


@router.get("/users/{user_id}/picture")
async def get_user_picture(user_id: uuid.UUID, session: SessionDep) -> Response:
    """No auth - see module docstring. Falls back to a computed Gravatar
    URL (302, not 301 - so a later custom upload isn't cached past) when
    the user has no upload but does have a verified email; 404 only when
    neither exists. `user_profile_picture` carries no RLS (ADR 0056), so no
    `set_tenant_rls_context` call is needed here, unlike the tenant/
    campaign routes below.
    """
    link = await session.get(UserProfilePicture, user_id)
    if link is not None:
        picture = await session.get_one(ProfilePicture, link.profile_picture_id)
        return Response(content=picture.data, media_type=picture.file_type)

    user = await session.get(User, user_id)
    if user is not None and user.email is not None:
        return RedirectResponse(gravatar_url(user.email), status_code=302)
    raise ProfilePictureNotFoundError(detail=f"No profile picture for user {user_id}")


async def _is_private_repository(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """A repository tenant whose profile does not say `public` (the tenant context is set, so both
    rows are readable). A play tenant is never private in this sense; a repository with no profile
    row has said nothing, so it is private."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None or tenant.kind is not TenantKind.REPOSITORY:
        return False
    profile = await session.get(RepositoryProfile, tenant_id)
    return profile is None or profile.visibility != "public"


@router.get("/tenants/{tenant_id}/picture")
async def get_tenant_picture(
    tenant_id: uuid.UUID, session: SessionDep, user: OptionalUser
) -> Response:
    """Open, with no fallback - see module docstring and ADR 0056 - except for a private
    repository's picture, which is for a signed-in user: any, a member or not (ADR 0300). A
    request with no token for one gets the answer of a tenant with no picture, a `404`, so that
    nothing tells a private repository from an unknown id or a play tenant without a picture; a
    token that is sent is checked, and a bad one is a `401` for every tenant alike. A play
    tenant's picture and a public repository's are served as ever.

    A tenant with no uploaded picture 404s the same way an unknown tenant_id does;
    the only signal disclosed either way is whether a *picture* exists for
    this id, not bare tenant existence beyond that.
    """
    await set_tenant_rls_context(session, tenant_id)
    link = await session.get(TenantProfilePicture, tenant_id)
    if link is None or (user is None and await _is_private_repository(session, tenant_id)):
        raise ProfilePictureNotFoundError(detail=f"No profile picture for tenant {tenant_id}")
    picture = await session.get_one(ProfilePicture, link.profile_picture_id)
    return Response(content=picture.data, media_type=picture.file_type)


@router.get("/tenants/{tenant_id}/campaigns/{campaign_id}/picture")
async def get_campaign_picture(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, session: SessionDep
) -> Response:
    """No auth, no fallback - see get_tenant_picture above, same reasoning.

    Explicitly filtered by both `campaign_id` and `tenant_id`, not just
    looked up by its `campaign_id` primary key - RLS (via
    `set_tenant_rls_context` above) would already reject a `campaign_id`
    belonging to a different tenant than the one in the URL, but every
    route in this codebase still filters its own queries by tenant_id
    explicitly regardless; RLS is defense in depth for a missed filter, not
    a replacement for filtering deliberately (ADR 0002).
    """
    await set_tenant_rls_context(session, tenant_id)
    link = (
        await session.execute(
            select(CampaignProfilePicture).where(
                CampaignProfilePicture.campaign_id == campaign_id,
                CampaignProfilePicture.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise ProfilePictureNotFoundError(detail=f"No profile picture for campaign {campaign_id}")
    picture = await session.get_one(ProfilePicture, link.profile_picture_id)
    return Response(content=picture.data, media_type=picture.file_type)
