import uuid

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select

from lorenzo_api.dependencies import SessionDep, set_tenant_rls_context
from lorenzo_api.exceptions import ProfilePictureNotFoundError
from lorenzo_api.models import (
    CampaignProfilePicture,
    ProfilePicture,
    TenantProfilePicture,
    User,
    UserProfilePicture,
)
from lorenzo_api.profile_pictures import gravatar_url

# Deliberately its own router, with no router-level auth dependency and no
# CurrentUser on any route below - see ADR 0052. `routers/campaigns.py`'s
# own router applies `Depends(get_tenant_or_404)` at the router level, which
# itself requires `CurrentUser` - nesting a public route there would force
# authentication regardless of that route's own signature, so these three
# live here instead, deliberately public: a plain `<img src="...">` can't
# send a Bearer token.
router = APIRouter(tags=["pictures"])


@router.get("/users/{user_id}/picture")
async def get_user_picture(user_id: uuid.UUID, session: SessionDep) -> Response:
    """No auth - see module docstring. Falls back to a computed Gravatar
    URL (302, not 301 - so a later custom upload isn't cached past) when
    the user has no upload but does have a verified email; 404 only when
    neither exists. `user_profile_picture` carries no RLS (ADR 0052), so no
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


@router.get("/tenants/{tenant_id}/picture")
async def get_tenant_picture(tenant_id: uuid.UUID, session: SessionDep) -> Response:
    """No auth, no fallback - see module docstring and ADR 0052. A tenant
    with no uploaded picture 404s the same way an unknown tenant_id does;
    the only signal disclosed either way is whether a *picture* exists for
    this id, not bare tenant existence beyond that.
    """
    await set_tenant_rls_context(session, tenant_id)
    link = await session.get(TenantProfilePicture, tenant_id)
    if link is None:
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
