"""Learning provenance is optional and does not grant access."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_event_order import event
from test_event_participation import being, participate

from lorenzo_api.models import (
    EventLearning,
    Knowledge,
    Membership,
    MembershipRole,
    TenantAdminCampaignOptOut,
)


async def information(client, t, e, public=True):
    response = await client.post(
        f"/tenants/{t}/entities/{e}/information",
        json={
            "title": "Hidden entrance",
            "is_public": public,
            "type": "note",
            "content": "Behind the waterfall.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def learn(client, t, e, b, i, *, version=None, removing=False):
    if version is None:
        version = (await client.get(f"/tenants/{t}/events/{e}/learning-version")).headers["etag"]
    method = client.delete if removing else client.put
    return await method(f"/tenants/{t}/events/{e}/learning/{b}/{i}", headers={"If-Match": version})


async def setup(client, t):
    e = await event(client, t, "Interrogation")
    b = await being(client, t, "Mara")
    source = await event(client, t, "Entrance")
    i = await information(client, t, source)
    return e, b, source, i


async def test_learning_requires_participation_and_keeps_audiences_and_order(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        e, b, source, i = await setup(client, t)
        assert (await learn(client, t, e, b, i)).status_code == 404
        assert (await participate(client, t, e, b)).status_code == 200
        audience_url = f"/tenants/{t}/information/{i}/audience"
        audience = (await client.get(audience_url)).json()
        assert (await learn(client, t, e, b, i)).status_code == 200
        assert (await learn(client, t, e, b, i)).status_code == 200  # retry, no duplicate
        assert (await client.get(audience_url)).json() == audience
        async with admin_session_factory() as s:
            assert not (await s.scalars(select(Knowledge).where(Knowledge.tenant_id == t))).all()
        assert (await client.get(f"/tenants/{t}/events/{e}/relationships")).json() == []
        listing = f"/tenants/{t}/event-learning"
        for query in [{"event_id": e}, {"being_id": b}, {"information_id": i}]:
            rows = (await client.get(listing, params=query)).json()
            assert rows["total"] == 1
            assert rows["items"][0]["information_entity_id"] == source
        another = await event(client, t, "Reminder")
        await participate(client, t, another, b)
        await learn(client, t, another, b, i)
        assert (await client.get(listing, params={"being_id": b, "size": 1, "page": 2})).json()[
            "total"
        ] == 2
        # Corrections remove provenance only, never participation or current access.
        assert (await learn(client, t, e, b, i, removing=True)).status_code == 200
        assert (await client.get(audience_url)).json() == audience
        assert len((await client.get(f"/tenants/{t}/events/{e}/participants")).json()) == 1
    finally:
        await delete_tenant(t)


async def test_learning_versions_concurrency_and_deletion_guards(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        e, b, source, i = await setup(client, t)
        await participate(client, t, e, b)
        url = f"/tenants/{t}/events/{e}/learning/{b}/{i}"
        assert (await client.put(url)).status_code == 428
        old = (await client.get(f"/tenants/{t}/events/{e}/learning-version")).headers["etag"]
        assert (await learn(client, t, e, b, i)).status_code == 200
        assert (await learn(client, t, e, b, i, version=old)).status_code == 412
        current = (await client.get(f"/tenants/{t}/events/{e}/participants")).headers["etag"]
        assert (
            await client.delete(
                f"/tenants/{t}/events/{e}/participants/{b}", headers={"If-Match": current}
            )
        ).status_code == 409
        assert (await client.delete(f"/tenants/{t}/information/{i}")).status_code == 409
        assert (await client.delete(f"/tenants/{t}/entities/{source}")).status_code == 409
        second = await information(client, t, source, False)
        results = await asyncio.gather(
            learn(client, t, e, b, second, version=current),
            learn(client, t, e, b, i, version=current, removing=True),
        )
        assert sorted(r.status_code for r in results) == [200, 412]
    finally:
        await delete_tenant(t)


async def test_learning_roles_optout_and_cross_tenant(client, test_user_id):
    t, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        e, b, source, i = await setup(client, t)
        await participate(client, t, e, b)
        foreign = await information(client, other, await event(client, other))
        assert (await learn(client, t, e, b, i)).status_code == 200
        assert (await learn(client, t, e, b, foreign)).status_code == 404
        # ADR 0316 explicitly admits Authors. Player denials are covered in
        # test_event_collaboration.test_player_creator_and_reader_notes_do_not_grant_other_editing.
        async with admin_session_factory() as s:
            (await s.get_one(Membership, (t, test_user_id))).role = MembershipRole.AUTHOR
            await s.commit()
        assert (await client.get(f"/tenants/{t}/event-learning")).status_code == 200
        assert (await client.get(f"/tenants/{t}/events/{e}/learning-version")).status_code == 200
        assert (await client.put(f"/tenants/{t}/events/{e}/learning/{b}/{i}")).status_code == 428
        async with admin_session_factory() as s:
            (await s.get_one(Membership, (t, test_user_id))).role = MembershipRole.OWNER
            campaign = await make_campaign(s, tenant_id=t)
            s.add(
                TenantAdminCampaignOptOut(
                    tenant_id=t,
                    user_id=test_user_id,
                    campaign_id=campaign.id,
                    created_by=test_user_id,
                )
            )
            await s.commit()
        assert (await client.get(f"/tenants/{t}/event-learning")).status_code == 403
        log = (await client.get(f"/tenants/{t}/activity-log")).json()
        assert not any(row["action"].startswith("event.learning") for row in log["items"])
    finally:
        await delete_tenant(t)
        await delete_tenant(other)


async def test_learning_database_requires_same_tenant_participation_and_information(
    client, test_user_id
):
    t, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        e, b, source, i = await setup(client, t)
        foreign = await information(client, other, await event(client, other))
        async with admin_session_factory() as s:
            for info in [i, foreign]:
                with pytest.raises(IntegrityError):
                    s.add(
                        EventLearning(
                            tenant_id=t,
                            event_entity_id=uuid.UUID(e),
                            being_entity_id=uuid.UUID(b),
                            information_id=uuid.UUID(info),
                        )
                    )
                    await s.commit()
                await s.rollback()
        await participate(client, t, e, b)
        async with admin_session_factory() as s:
            with pytest.raises(IntegrityError):
                s.add(
                    EventLearning(
                        tenant_id=t,
                        event_entity_id=uuid.UUID(e),
                        being_entity_id=uuid.UUID(b),
                        information_id=uuid.UUID(foreign),
                    )
                )
                await s.commit()
            await s.rollback()
    finally:
        await delete_tenant(t)
        await delete_tenant(other)


async def test_learning_copy_release_old_documents_and_purge(client, test_user_id):
    from datetime import UTC, datetime

    from lorenzo_api.models import RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content
    from lorenzo_api.repository_copying import apply_plan, forget_copy, plan_copy

    async with admin_session_factory() as s:
        repo = Tenant(name="Learning repository", kind=TenantKind.REPOSITORY)
        s.add(repo)
        await s.flush()
        s.add(Membership(tenant_id=repo.id, user_id=test_user_id, role=MembershipRole.OWNER))
        await s.commit()
        source = repo.id
    target = await make_tenant(test_user_id)
    try:
        e, b, anchor, i = await setup(client, source)
        await participate(client, source, e, b)
        assert (await learn(client, source, e, b, i)).status_code == 200
        async with admin_session_factory() as s:
            (await s.get_one(Tenant, source)).published_at = datetime.now(UTC)
            await s.flush()
            s.add(RepositorySubscription(repository_tenant_id=source, subscriber_tenant_id=target))
            await s.commit()
            content = await load_content(s, source)
            document, files = encode(content)
            assert decode(document, files).event_learning == [
                (uuid.UUID(e), uuid.UUID(b), uuid.UUID(i))
            ]
            old = {k: v for k, v in document.items() if k != "event_learning"}
            assert decode(old, files, format=7).event_learning == []
            await s.execute(text("SELECT set_config('app.tenant_id',:t,true)"), {"t": str(target)})
            plan = await plan_copy(
                s, tenant_id=target, repository_id=source, user_id=test_user_id, resolutions=[]
            )
            row = plan.rows["event_learning"][0]
            assert row["event_entity_id"] != uuid.UUID(e)
            assert row["being_entity_id"] != uuid.UUID(b)
            assert row["information_id"] != uuid.UUID(i)
            await apply_plan(s, plan, user_id=test_user_id)
            await s.commit()
            assert (
                len(
                    (
                        await s.scalars(
                            select(EventLearning).where(EventLearning.tenant_id == target)
                        )
                    ).all()
                )
                == 1
            )
            await forget_copy(
                s, tenant_id=target, repository_id=source, user_id=test_user_id, purge=True
            )
            await s.commit()
            assert not (
                await s.scalars(select(EventLearning).where(EventLearning.tenant_id == target))
            ).all()
    finally:
        await delete_tenant(target)
        await delete_tenant(source)


@pytest.mark.parametrize("instance", [False, True])
async def test_item_information_deletion_cannot_bypass_learning_guard(
    client, test_user_id, instance
):
    t = await make_tenant(test_user_id)
    try:
        e = await event(client, t)
        b = await being(client, t)
        await participate(client, t, e, b)
        item = (
            await client.post(f"/tenants/{t}/entities", json={"name": "Map", "kinds": ["item"]})
        ).json()["id"]
        route = "items"
        if instance:
            item = (
                await client.post(f"/tenants/{t}/item-instances", json={"prototype_id": item})
            ).json()["entity_id"]
            route = "item-instances"
        i = await information(client, t, item)
        assert (await learn(client, t, e, b, i)).status_code == 200
        result = await client.delete(f"/tenants/{t}/{route}/{item}")
        assert result.status_code == 409, result.text
        assert (await learn(client, t, e, b, i, removing=True)).status_code == 200
        assert (await client.delete(f"/tenants/{t}/{route}/{item}")).status_code == 204
    finally:
        await delete_tenant(t)


async def test_main_picture_learning_guard_covers_payload_and_entry_routes(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        e, b, source, unused = await setup(client, t)
        await participate(client, t, e, b)
        picture = await client.put(
            f"/tenants/{t}/entities/{source}/picture",
            files={"file": ("map.png", b"\x89PNG\r\n\x1a\nfake-png-content", "image/png")},
        )
        assert picture.status_code == 201, picture.text
        info = picture.json()
        assert (await learn(client, t, e, b, info["id"])).status_code == 200
        assert (await client.delete(f"/tenants/{t}/entities/{source}/picture")).status_code == 409
        payload = info["payloads"][0]["id"]
        assert (await client.delete(f"/tenants/{t}/payloads/{payload}")).status_code == 409
        assert (await learn(client, t, e, b, info["id"], removing=True)).status_code == 200
        assert (await client.delete(f"/tenants/{t}/payloads/{payload}")).status_code == 204
    finally:
        await delete_tenant(t)
