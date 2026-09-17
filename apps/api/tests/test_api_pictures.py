"""Profile pictures for User/Tenant/Campaign - see ADR 0052."""

import hashlib
import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient

from lorenzo_api.config import get_settings
from lorenzo_api.models import (
    CampaignProfilePicture,
    Player,
    ProfilePicture,
    Tenant,
    TenantProfilePicture,
    User,
    UserProfilePicture,
)

# Not a real, decodable PNG - the API trusts the client-declared content_type
# the same way payload_picture/payload_document's own file_type already is
# trusted (ADR 0017), so a real image isn't needed to exercise any of this.
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-content"


# --- User picture (ADR 0050/0052) -----------------------------------------


async def test_upload_and_serve_my_picture(
    client: AsyncClient, raw_client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    upload = await client.put(
        "/me/picture", files={"file": ("avatar.png", _PNG_BYTES, "image/png")}
    )
    assert upload.status_code == 204

    served = await raw_client.get(f"/users/{test_user_id}/picture")
    assert served.status_code == 200
    assert served.content == _PNG_BYTES
    assert served.headers["content-type"] == "image/png"

    await client.delete("/me/picture")


async def test_replacing_my_picture_updates_the_same_row_in_place(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    await client.put("/me/picture", files={"file": ("a.png", _PNG_BYTES, "image/png")})
    async with admin_session_factory() as session:
        picture_id_before = (
            await session.get_one(UserProfilePicture, test_user_id)
        ).profile_picture_id

    new_bytes = _PNG_BYTES + b"-v2"
    await client.put("/me/picture", files={"file": ("b.png", new_bytes, "image/png")})
    async with admin_session_factory() as session:
        link = await session.get_one(UserProfilePicture, test_user_id)
        assert link.profile_picture_id == picture_id_before
        assert (await session.get_one(ProfilePicture, link.profile_picture_id)).data == new_bytes

    await client.delete("/me/picture")


async def test_delete_my_picture(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    await client.put("/me/picture", files={"file": ("a.png", _PNG_BYTES, "image/png")})

    response = await client.delete("/me/picture")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(UserProfilePicture, test_user_id) is None


async def test_delete_my_picture_is_a_noop_without_one(client: AsyncClient) -> None:
    response = await client.delete("/me/picture")
    assert response.status_code == 204


async def test_upload_my_picture_rejects_unsupported_content_type(client: AsyncClient) -> None:
    response = await client.put(
        "/me/picture", files={"file": ("a.txt", b"not an image", "text/plain")}
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_upload_my_picture_rejects_oversized_file(client: AsyncClient) -> None:
    oversized = b"0" * (get_settings().profile_picture_max_bytes + 1)
    response = await client.put("/me/picture", files={"file": ("a.png", oversized, "image/png")})
    assert response.status_code == 422


async def test_user_picture_redirects_to_gravatar_when_no_upload_but_has_email(
    raw_client: AsyncClient,
) -> None:
    email = f"gravatar-{uuid.uuid4()}@example.com"
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|gravatar-{uuid.uuid4()}", email=email)
        session.add(user)
        await session.commit()
        user_id = user.id

    response = await raw_client.get(f"/users/{user_id}/picture", follow_redirects=False)

    assert response.status_code == 302
    expected_hash = hashlib.md5(email.strip().lower().encode()).hexdigest()
    assert (
        response.headers["location"]
        == f"https://www.gravatar.com/avatar/{expected_hash}?d=mp&s=200"
    )

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_user_picture_404s_without_upload_or_email(raw_client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|no-email-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        user_id = user.id

    response = await raw_client.get(f"/users/{user_id}/picture")
    assert response.status_code == 404

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_user_picture_404s_for_unknown_user(raw_client: AsyncClient) -> None:
    response = await raw_client.get(f"/users/{uuid.uuid4()}/picture")
    assert response.status_code == 404


async def test_picture_routes_require_no_authorization_header(raw_client: AsyncClient) -> None:
    """The actual proof of "public" - raw_client has no get_current_user
    override at all, and this request carries no Authorization header
    whatsoever, unlike every other route in this API.
    """
    response = await raw_client.get(f"/users/{uuid.uuid4()}/picture")
    assert response.status_code != 401


async def test_delete_me_cleans_up_the_orphaned_picture_row(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """No cascade points from profile_picture back to its link - delete_me
    must clean it up explicitly, or it leaks forever (ADR 0052)."""
    await client.put("/me/picture", files={"file": ("a.png", _PNG_BYTES, "image/png")})
    async with admin_session_factory() as session:
        picture_id = (await session.get_one(UserProfilePicture, test_user_id)).profile_picture_id

    response = await client.delete("/me")
    assert response.status_code == 204

    async with admin_session_factory() as session:
        assert await session.get(ProfilePicture, picture_id) is None
        session.add(User(id=test_user_id, authgear_subject_id="conftest-fixture-user"))
        await session.commit()


# --- Tenant picture (ADR 0052) ---------------------------------------------


async def test_upload_and_serve_tenant_picture(
    client: AsyncClient, raw_client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    upload = await client.put(
        f"/tenants/{tenant_id}/picture", files={"file": ("t.png", _PNG_BYTES, "image/png")}
    )
    assert upload.status_code == 204

    served = await raw_client.get(f"/tenants/{tenant_id}/picture")
    assert served.status_code == 200
    assert served.content == _PNG_BYTES

    await delete_tenant(tenant_id)


async def test_tenant_picture_404_without_upload(
    raw_client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await raw_client.get(f"/tenants/{tenant_id}/picture")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_tenant_picture_404_for_unknown_tenant(raw_client: AsyncClient) -> None:
    response = await raw_client.get(f"/tenants/{uuid.uuid4()}/picture")
    assert response.status_code == 404


async def test_upload_tenant_picture_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.put(
        f"/tenants/{tenant_id}/picture", files={"file": ("t.png", _PNG_BYTES, "image/png")}
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_delete_tenant_picture(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    await client.put(
        f"/tenants/{tenant_id}/picture", files={"file": ("t.png", _PNG_BYTES, "image/png")}
    )

    response = await client.delete(f"/tenants/{tenant_id}/picture")

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(TenantProfilePicture, tenant_id) is None

    await delete_tenant(tenant_id)


# --- Campaign picture (ADR 0052) -------------------------------------------


async def test_upload_and_serve_campaign_picture(
    client: AsyncClient, raw_client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    upload = await client.put(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/picture",
        files={"file": ("c.png", _PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 204

    served = await raw_client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}/picture")
    assert served.status_code == 200
    assert served.content == _PNG_BYTES

    await delete_tenant(tenant_id)


async def test_campaign_picture_404_without_upload(
    raw_client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id

    response = await raw_client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}/picture")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_campaign_picture_404_when_tenant_id_in_url_does_not_match(
    client: AsyncClient, raw_client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A real campaign_id, wrong tenant_id in the URL - must 404, not leak
    the other tenant's picture (the explicit tenant_id filter, backed by
    RLS as defense in depth - see routers/pictures.py).
    """
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_a)
        await session.commit()
        campaign_id = campaign.id
    await client.put(
        f"/tenants/{tenant_a}/campaigns/{campaign_id}/picture",
        files={"file": ("c.png", _PNG_BYTES, "image/png")},
    )

    response = await raw_client.get(f"/tenants/{tenant_b}/campaigns/{campaign_id}/picture")
    assert response.status_code == 404

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_upload_campaign_picture_403_for_a_plain_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Same two-tier 404-then-403 shape update_campaign's own identical
    test already establishes (ADR 0032/0034)."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()

    response = await client.put(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/picture",
        files={"file": ("c.png", _PNG_BYTES, "image/png")},
    )
    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_delete_campaign_cleans_up_the_orphaned_picture_row(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_id = campaign.id
    await client.put(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/picture",
        files={"file": ("c.png", _PNG_BYTES, "image/png")},
    )
    async with admin_session_factory() as session:
        picture_id = (await session.get_one(CampaignProfilePicture, campaign_id)).profile_picture_id

    response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 204

    async with admin_session_factory() as session:
        assert await session.get(ProfilePicture, picture_id) is None

    await delete_tenant(tenant_id)
