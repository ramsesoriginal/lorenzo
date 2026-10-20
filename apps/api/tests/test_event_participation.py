"""Participation is an explicit association, never evidence of learning or lived order."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_event_order import event, relation

from lorenzo_api.models import Membership, MembershipRole, TenantAdminCampaignOptOut


async def being(client, tenant, name="Traveller"):
    result = await client.post(
        f"/tenants/{tenant}/entities", json={"name": name, "kinds": ["being"]}
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


async def participate(client, tenant, e, b, etag=None):
    url = f"/tenants/{tenant}/events/{e}/participants"
    if etag is None:
        etag = (await client.get(url)).headers["etag"]
    return await client.put(url + f"/{b}", headers={"If-Match": etag})


async def test_participants_are_versioned_and_do_not_create_order_or_knowledge(
    client, test_user_id
):
    t = await make_tenant(test_user_id)
    try:
        e = await event(client, t)
        b = await being(client, t)
        url = f"/tenants/{t}/events/{e}/participants"
        old = await client.get(url)
        added = await participate(client, t, e, b)
        assert added.status_code == 200, added.text
        assert added.json()[0]["being_entity_id"] == b
        assert (await participate(client, t, e, b, old.headers["etag"])).status_code == 412
        assert (await participate(client, t, e, b)).status_code == 200
        assert (await client.get(f"/tenants/{t}/events/{e}/relationships")).json() == []
        assert (await client.get(f"/tenants/{t}/entities/{e}/dates")).json() == []
        assert (await client.delete(f"/tenants/{t}/entities/{b}")).status_code == 409
        assert (await client.delete(f"/tenants/{t}/entities/{e}")).status_code == 409
        assert (await client.delete(f"/tenants/{t}/entities/{b}/kinds/being")).status_code == 409
        missing = await client.put(url + f"/{b}")
        assert missing.status_code == 428
        # Independent additions to the same Event serialize and reject a stale second writer.
        another = await being(client, t, "Other being")
        saved = await client.get(url)
        replies = await asyncio.gather(
            participate(client, t, e, another, saved.headers["etag"]),
            participate(client, t, e, b, saved.headers["etag"]),
        )
        assert sorted(r.status_code for r in replies) in ([200, 200], [200, 412])
        assert (await client.get(f"/tenants/{t}/events", params={"being_id": b})).json()[
            "total"
        ] == 1
        current = await client.get(url)
        removed = await client.delete(url + f"/{b}", headers={"If-Match": current.headers["etag"]})
        assert removed.status_code == 200, removed.text
        assert all(p["being_entity_id"] != b for p in removed.json())
        assert (await client.delete(f"/tenants/{t}/entities/{b}")).status_code == 204
    finally:
        await delete_tenant(t)


async def test_causal_branches_and_participant_filter_keep_full_graph_order(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        a, x, b, c, d = [
            await event(client, t, n) for n in ["A", "Middle", "B", "Branch", "Order only"]
        ]
        person = await being(client, t)
        for left, right, kind in [
            (a, x, "causes"),
            (x, b, "causes"),
            (x, c, "causes"),
            (b, d, "order"),
        ]:
            assert (await relation(client, t, left, right, kind)).status_code == 200
        for e in [a, b, c]:
            assert (await participate(client, t, e, person)).status_code == 200
        base = f"/tenants/{t}/events"
        chain = await client.get(base, params={"causal_event_id": x, "sort": "order"})
        assert chain.status_code == 200, chain.text
        assert {e["entity_id"] for e in chain.json()["items"]} == {a, x, b, c}
        filtered = await client.get(base, params={"being_id": person, "sort": "order"})
        rows = filtered.json()["items"]
        assert rows[0]["entity_id"] == a
        assert rows[1]["order_basis"] == "causal"  # Middle is absent, its proof is not lost.
        assert rows[2]["order_basis"] == "linearized"  # Sibling branches are not a causal chain.
        assert (await client.get(base, params={"q": "branch"})).json()["total"] == 1
        page = await client.get(
            base, params={"being_id": person, "sort": "order", "page": 2, "size": 1}
        )
        assert page.json()["items"][0]["order_basis"] == "causal"
    finally:
        await delete_tenant(t)


async def test_participation_roles_opt_out_and_foreign_targets(client, test_user_id):
    t, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        e = await event(client, t)
        b = await being(client, other)
        assert (await participate(client, t, e, b)).status_code == 404
        async with admin_session_factory() as s:
            member = await s.get_one(Membership, (t, test_user_id))
            member.role = MembershipRole.AUTHOR
            await s.commit()
        assert (await client.get(f"/tenants/{t}/events")).status_code == 200
        for params in [{"sort": "order"}, {"being_id": b}, {"causal_event_id": e}]:
            assert (await client.get(f"/tenants/{t}/events", params=params)).status_code == 403
        assert (await client.get(f"/tenants/{t}/events/{e}/participants")).status_code == 403
        async with admin_session_factory() as s:
            member = await s.get_one(Membership, (t, test_user_id))
            member.role = MembershipRole.OWNER
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
        assert (await client.get(f"/tenants/{t}/events/access")).json() == {"can_order": False}
        assert (
            await client.get(f"/tenants/{t}/events", params={"sort": "order"})
        ).status_code == 403
    finally:
        await delete_tenant(t)
        await delete_tenant(other)


async def test_raw_associations_require_same_tenant_components(client, test_user_id):
    t, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        e = await event(client, t)
        b = await being(client, other)
        insert = text(
            "INSERT INTO event_participant(tenant_id,event_entity_id,being_entity_id) "
            "VALUES(:t,:e,:b)"
        )
        async with admin_session_factory() as s:
            with pytest.raises(IntegrityError):
                await s.execute(insert, {"t": t, "e": e, "b": b})
                await s.commit()
            await s.rollback()
            bare = (
                await client.post(f"/tenants/{t}/entities", json={"name": "Not a being"})
            ).json()["id"]
            with pytest.raises(IntegrityError):
                await s.execute(insert, {"t": t, "e": e, "b": bare})
                await s.commit()
            await s.rollback()
    finally:
        await delete_tenant(t)
        await delete_tenant(other)


async def test_participation_copy_round_trip_and_purge(client, test_user_id):
    from datetime import UTC, datetime

    from sqlalchemy import select

    from lorenzo_api.models import EventParticipant, RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content
    from lorenzo_api.repository_copying import apply_plan, forget_copy, plan_copy

    async with admin_session_factory() as s:
        repo = Tenant(name="Participation repository", kind=TenantKind.REPOSITORY)
        s.add(repo)
        await s.flush()
        s.add(Membership(tenant_id=repo.id, user_id=test_user_id, role=MembershipRole.OWNER))
        await s.commit()
        source = repo.id
    target = await make_tenant(test_user_id)
    try:
        e = await event(client, source)
        b = await being(client, source)
        assert (await participate(client, source, e, b)).status_code == 200
        async with admin_session_factory() as s:
            (await s.get_one(Tenant, source)).published_at = datetime.now(UTC)
            await s.flush()
            s.add(RepositorySubscription(repository_tenant_id=source, subscriber_tenant_id=target))
            await s.commit()
            content = await load_content(s, source)
            document, files = encode(content)
            assert decode(document, files).event_participants == [(uuid.UUID(e), uuid.UUID(b))]
            old = {k: v for k, v in document.items() if k != "event_participants"}
            assert decode(old, files, format=6).event_participants == []
            await s.execute(text("SELECT set_config('app.tenant_id',:t,true)"), {"t": str(target)})
            plan = await plan_copy(
                s, tenant_id=target, repository_id=source, user_id=test_user_id, resolutions=[]
            )
            row = plan.rows["event_participant"][0]
            assert row["event_entity_id"] != uuid.UUID(e) and row["being_entity_id"] != uuid.UUID(b)
            await apply_plan(s, plan, user_id=test_user_id)
            await s.commit()
            assert (
                await s.scalars(
                    select(EventParticipant).where(EventParticipant.tenant_id == target)
                )
            ).one()
            await forget_copy(
                s, tenant_id=target, repository_id=source, user_id=test_user_id, purge=True
            )
            await s.commit()
            assert not (
                await s.scalars(
                    select(EventParticipant).where(EventParticipant.tenant_id == target)
                )
            ).all()
    finally:
        await delete_tenant(target)
        await delete_tenant(source)
