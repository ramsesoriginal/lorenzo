import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_opted_out_admin, make_tenant
from httpx import AsyncClient
from sqlalchemy import update

from lorenzo_api.models import Entity, Information


async def picture(client: AsyncClient, tenant_id: uuid.UUID) -> tuple[str, str, uuid.UUID]:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Portrait")
        session.add(entity)
        await session.commit()
        entity_id = entity.id
    url = f"/tenants/{tenant_id}/entities/{entity_id}/picture"
    response = await client.put(
        url,
        files={"file": ("portrait.png", b"first picture", "image/png")},
        data={"is_public": "true"},
    )
    assert response.status_code == 201, response.text
    info = response.json()
    return (
        url,
        f"/tenants/{tenant_id}/payloads/{info['payloads'][0]['id']}/content",
        uuid.UUID(info["id"]),
    )


@pytest.mark.parametrize("condition", ["strong", "weak", "list", "wildcard"])
async def test_picture_revalidation(
    client: AsyncClient, test_user_id: uuid.UUID, condition: str
) -> None:
    tenant_id = await make_tenant(test_user_id)
    try:
        _, content_url, _ = await picture(client, tenant_id)
        first = await client.get(content_url)
        assert first.status_code == 200
        assert first.content == b"first picture"
        assert first.headers["cache-control"] == "private, no-cache"
        tag = first.headers["etag"]
        header = {
            "strong": tag,
            "weak": f"W/{tag}",
            "list": f'"different", W/{tag}',
            "wildcard": "*",
        }[condition]
        cached = await client.get(content_url, headers={"If-None-Match": header})
        assert cached.status_code == 304
        assert cached.content == b""
        assert cached.headers["etag"] == tag
        assert cached.headers["cache-control"] == "private, no-cache"
    finally:
        await delete_tenant(tenant_id)


async def test_picture_replacements_invalidate_only_changed_bytes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    try:
        upload_url, content_url, _ = await picture(client, tenant_id)
        tag = (await client.get(content_url)).headers["etag"]
        for data, expected in [(b"first picture", 304), (b"new picture", 200)]:
            uploaded = await client.put(
                upload_url, files={"file": ("portrait.png", data, "image/png")}
            )
            assert uploaded.status_code == 200, uploaded.text
            response = await client.get(content_url, headers={"If-None-Match": tag})
            assert response.status_code == expected
            if expected == 200:
                assert response.content == data
                assert response.headers["etag"] != tag
    finally:
        await delete_tenant(tenant_id)


async def test_cached_picture_still_checks_visibility_and_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other_tenant = await make_tenant(test_user_id)
    try:
        _, content_url, info_id = await picture(client, tenant_id)
        tag = (await client.get(content_url)).headers["etag"]
        async with admin_session_factory() as session:
            await session.execute(
                update(Information).where(Information.id == info_id).values(is_public=False)
            )
            await session.commit()
        await make_opted_out_admin(tenant_id, test_user_id)
        denied = await client.get(content_url, headers={"If-None-Match": tag})
        assert denied.status_code == 404
        wrong_tenant = await client.get(
            content_url.replace(str(tenant_id), str(other_tenant)), headers={"If-None-Match": tag}
        )
        assert wrong_tenant.status_code == 404
    finally:
        await delete_tenant(tenant_id)
        await delete_tenant(other_tenant)
