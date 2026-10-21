"""Evidence, fallback, isolation and database invariants of ADR 0312."""

import asyncio
import random
import time
import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from lorenzo_api.event_ordering import Edge, EventOrder
from lorenzo_api.models import Membership, MembershipRole, TenantAdminCampaignOptOut


def test_evidence_and_rebuildable_linearization():
    a, b, c, d = [uuid.UUID(int=i) for i in range(1, 5)]
    edges = [Edge(a, b, "causes"), Edge(b, c, "order")]
    graph = EventOrder({a, b, c, d}, edges)
    assert graph.compare(a, b) == ("before", "causal", [edges[0]])
    assert graph.compare(c, a) == ("after", "ruled", edges)
    assert graph.compare(d, a) == ("after", "linearized", [])
    assert graph.compare(b, b) == ("same", "identity", [])
    assert EventOrder({a, b, c, d}, list(reversed(edges))).positions == graph.positions
    # A pure causal path wins over a shorter ordering-only path.
    more = edges + [Edge(b, c, "causes"), Edge(a, c, "order")]
    assert EventOrder({a, b, c, d}, more).compare(a, c)[1:] == ("causal", [edges[0], more[2]])
    with pytest.raises(ValueError):
        EventOrder({a, b, c}, edges + [Edge(c, a, "causes")])


def test_two_hundred_session_campaign():
    # 20 Events/session, with explicit causal chains and independent threads.
    nodes = {uuid.UUID(int=i + 1) for i in range(4000)}
    edges = [
        Edge(uuid.UUID(int=i), uuid.UUID(int=i + 1), "causes") for i in range(1, 4000) if i % 20
    ]
    shuffled = edges.copy()
    random.Random(312).shuffle(shuffled)
    start = time.perf_counter()
    graph = EventOrder(nodes, shuffled)
    assert graph.positions == EventOrder(nodes, edges).positions
    assert graph.compare(uuid.UUID(int=1), uuid.UUID(int=20))[1] == "causal"
    assert graph.compare(uuid.UUID(int=1), uuid.UUID(int=4000))[1] == "linearized"
    assert time.perf_counter() - start < 2


async def event(client, tenant, name="Event"):
    response = await client.post(
        f"/tenants/{tenant}/entities", json={"name": name, "kinds": ["event"]}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def relation(client, tenant, a, b, kind="order", etag=None):
    url = f"/tenants/{tenant}/events/{a}/relationships"
    if etag is None:
        etag = (await client.get(url)).headers["etag"]
    return await client.put(url + f"/{b}", json={"kind": kind}, headers={"If-Match": etag})


async def compare(client, tenant, a, b):
    response = await client.post(
        f"/tenants/{tenant}/events/compare", json={"pairs": [{"left": a, "right": b}]}
    )
    assert response.status_code == 200, response.text
    return response.json()[0]


async def test_api_evidence_cycles_etags_and_deletion(client, test_user_id):
    tenant = await make_tenant(test_user_id)
    try:
        a, b, c, d = [
            await event(client, tenant, n) for n in ["Storm", "Flood", "Flight", "Elsewhere"]
        ]
        assert (await compare(client, tenant, a, d))["basis"] == "linearized"
        original = (await client.get(f"/tenants/{tenant}/events/{a}/relationships")).headers["etag"]
        assert (await relation(client, tenant, a, b, "causes")).status_code == 200
        assert (await relation(client, tenant, a, c, etag=original)).status_code == 412
        assert (await relation(client, tenant, b, c)).status_code == 200
        proof = await compare(client, tenant, a, c)
        assert proof["basis"] == "ruled"
        assert [p["kind"] for p in proof["path"]] == ["causes", "order"]
        assert (await compare(client, tenant, a, b))["basis"] == "causal"
        assert (await relation(client, tenant, c, a, "causes")).status_code == 409
        assert (await relation(client, tenant, a, a)).status_code == 409
        assert (await relation(client, tenant, a, b, "causes")).status_code == 200
        assert (await client.delete(f"/tenants/{tenant}/entities/{a}")).status_code == 409
        missing = await client.put(
            f"/tenants/{tenant}/events/{a}/relationships/{d}", json={"kind": "order"}
        )
        assert missing.status_code == 428
        url = f"/tenants/{tenant}/events/{a}/relationships"
        current = await client.get(url)
        removed = await client.delete(
            url + f"/{b}", params={"kind": "causes"}, headers={"If-Match": current.headers["etag"]}
        )
        assert removed.status_code == 200, removed.text
        assert removed.json() == []
        assert (await compare(client, tenant, a, b))["basis"] == "linearized"
        assert (await client.delete(f"/tenants/{tenant}/entities/{a}")).status_code == 204
    finally:
        # Whole-tenant purge must work even with remaining relationship FKs.
        await delete_tenant(tenant)


async def test_authors_opt_out_and_other_tenant_disclose_no_graph(client, test_user_id):
    tenant = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    try:
        a = await event(client, tenant, "Hidden Event")
        b = await event(client, other, "Foreign Event")
        assert (await relation(client, tenant, a, b)).status_code == 404
        own_other = await event(client, tenant, "Another Event")
        assert (await relation(client, tenant, a, own_other)).status_code == 200
        log_url = f"/tenants/{tenant}/activity-log"
        assert any(
            row["action"] == "event.relationship_added"
            for row in (await client.get(log_url)).json()["items"]
        )
        async with admin_session_factory() as session:
            member = await session.get_one(Membership, (tenant, test_user_id))
            member.role = MembershipRole.AUTHOR
            await session.commit()
        rows = await client.get(f"/tenants/{tenant}/events/{a}/relationships")
        assert rows.status_code == 200 and len(rows.json()) == 1
        assert "etag" in rows.headers
        assert (await compare(client, tenant, a, own_other))["basis"] == "ruled"
        response = await client.put(
            f"/tenants/{tenant}/events/{a}/relationships/{b}", json={"kind": "order"}
        )
        assert response.status_code == 404
        async with admin_session_factory() as session:
            member = await session.get_one(Membership, (tenant, test_user_id))
            member.role = MembershipRole.OWNER
            await session.commit()
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(
                TenantAdminCampaignOptOut(
                    tenant_id=tenant,
                    user_id=test_user_id,
                    campaign_id=campaign.id,
                    created_by=test_user_id,
                )
            )
            await session.commit()
        # Opting out removes staff graph access, but the creator still sees their entry.
        scoped = await client.get(f"/tenants/{tenant}/events/{a}/relationships")
        assert scoped.status_code == 200 and scoped.json() == []
        assert "etag" not in scoped.headers
        log = await client.get(log_url)
        assert log.status_code == 200, log.text
        assert all(
            not row["action"].startswith("event.relationship_") for row in log.json()["items"]
        )
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)


async def test_raw_database_serializes_competing_cycles(client, test_user_id):
    tenant = await make_tenant(test_user_id)
    try:
        a, b = await event(client, tenant), await event(client, tenant)
        insert = text(
            "INSERT INTO event_relationship(tenant_id,from_event_id,to_event_id,kind) "
            "VALUES(:t,:a,:b,'causes')"
        )
        async with admin_session_factory() as first, admin_session_factory() as second:
            await first.execute(insert, {"t": tenant, "a": a, "b": b})
            task = asyncio.create_task(second.execute(insert, {"t": tenant, "a": b, "b": a}))
            await asyncio.sleep(0.1)
            assert not task.done()  # The DB trigger itself waits, without an API lock.
            await first.commit()
            with pytest.raises(IntegrityError, match="acyclic"):
                await task
            await second.rollback()
        async with admin_session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(insert, {"t": tenant, "a": a, "b": a})
            await session.rollback()
            bare = await client.post(f"/tenants/{tenant}/entities", json={"name": "Not an Event"})
            with pytest.raises(IntegrityError):
                await session.execute(insert, {"t": tenant, "a": a, "b": bare.json()["id"]})
                await session.commit()  # The StoryEvent FKs are deliberately deferred.
            await session.rollback()
    finally:
        await delete_tenant(tenant)


async def test_copy_release_remaps_event_assertions_and_purge_removes_them(client, test_user_id):
    from datetime import UTC, datetime

    from sqlalchemy import select

    from lorenzo_api.models import EventRelationship, RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content
    from lorenzo_api.repository_copying import apply_plan, forget_copy, plan_copy

    async with admin_session_factory() as session:
        repo = Tenant(name="Event repository", kind=TenantKind.REPOSITORY)
        session.add(repo)
        await session.flush()
        session.add(Membership(tenant_id=repo.id, user_id=test_user_id, role=MembershipRole.OWNER))
        await session.commit()
        repository = repo.id
    library = await make_tenant(test_user_id)
    try:
        a, b = (
            await event(client, repository, "First Event"),
            await event(client, repository, "Second Event"),
        )
        assert (await relation(client, repository, a, b, "causes")).status_code == 200
        async with admin_session_factory() as session:
            tenant = await session.get_one(Tenant, repository)
            tenant.published_at = datetime.now(UTC)
            await session.flush()
            session.add(
                RepositorySubscription(
                    repository_tenant_id=repository, subscriber_tenant_id=library
                )
            )
            await session.commit()
            content = await load_content(session, repository)
            document, files = encode(content)
            assert decode(document, files).event_relationships == [
                (uuid.UUID(a), uuid.UUID(b), "causes")
            ]
            await session.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(library)}
            )
            plan = await plan_copy(
                session,
                tenant_id=library,
                repository_id=repository,
                user_id=test_user_id,
                resolutions=[],
            )
            assert len(plan.rows["event_relationship"]) == 1
            row = plan.rows["event_relationship"][0]
            assert row["from_event_id"] != uuid.UUID(a) and row["to_event_id"] != uuid.UUID(b)
            await apply_plan(session, plan, user_id=test_user_id)
            await session.commit()
            local = (
                await session.scalars(
                    select(EventRelationship).where(EventRelationship.tenant_id == library)
                )
            ).one()
            assert local.kind == "causes"
            assert (
                await compare(client, library, str(local.from_event_id), str(local.to_event_id))
            )["basis"] == "causal"
            await forget_copy(
                session,
                tenant_id=library,
                repository_id=repository,
                user_id=test_user_id,
                purge=True,
            )
            await session.commit()
            assert not (
                await session.scalars(
                    select(EventRelationship).where(EventRelationship.tenant_id == library)
                )
            ).all()
    finally:
        await delete_tenant(library)
        await delete_tenant(repository)


async def test_dates_remain_annotations_and_comparison_scales(client, test_user_id):
    from sqlalchemy import insert
    from test_calendar_periods import period
    from test_calendars import make_calendar

    from lorenzo_api.models import Entity, EventRelationship, StoryEvent

    tenant = await make_tenant(test_user_id)
    try:
        ids = [uuid.uuid4() for _ in range(4000)]
        async with admin_session_factory() as session:
            await session.execute(
                insert(Entity),
                [
                    {"id": i, "tenant_id": tenant, "name": f"Session {n // 20} Event {n % 20}"}
                    for n, i in enumerate(ids)
                ],
            )
            await session.execute(
                insert(StoryEvent), [{"entity_id": i, "tenant_id": tenant} for i in ids]
            )
            await session.execute(
                insert(EventRelationship),
                [
                    {
                        "tenant_id": tenant,
                        "from_event_id": ids[n],
                        "to_event_id": ids[n + 1],
                        "kind": "causes",
                    }
                    for n in range(3999)
                    if (n + 1) % 20
                ],
            )
            await session.commit()
        start = time.perf_counter()
        initial = await compare(client, tenant, str(ids[0]), str(ids[19]))
        elapsed = time.perf_counter() - start
        assert initial["basis"] == "causal" and len(initial["path"]) == 19
        assert elapsed < 5, f"4,000-Event graph read and comparison took {elapsed:.2f}s"
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        late = await period(client, tenant, calendar, year=100, segment="first", day=20)
        early = await period(client, tenant, calendar, year=1, segment="first", day=1)
        for entry_id, date in [(ids[0], late), (ids[19], early)]:
            base = f"/tenants/{tenant}/entities/{entry_id}"
            saved = await client.get(base)
            dated = await client.put(
                base + "/dates",
                json={"period_ids": [date["entity_id"]]},
                headers={"If-Match": saved.headers["etag"]},
            )
            assert dated.status_code == 200, dated.text
        assert await compare(client, tenant, str(ids[0]), str(ids[19])) == initial
        # The same 200-session fixture also exercises the reader projection and role resolver.
        from sqlalchemy import update

        async with admin_session_factory() as session:
            await session.execute(
                update(EventRelationship)
                .where(EventRelationship.tenant_id == tenant)
                .values(is_shared=True)
            )
            (await session.get_one(Membership, (tenant, test_user_id))).role = MembershipRole.AUTHOR
            await session.commit()
        start = time.perf_counter()
        permitted = await compare(client, tenant, str(ids[0]), str(ids[19]))
        elapsed = time.perf_counter() - start
        assert permitted["basis"] == "causal" and len(permitted["path"]) == 19
        assert elapsed < 5, f"4,000-Event reader comparison took {elapsed:.2f}s"
    finally:
        await delete_tenant(tenant)


async def test_copy_plan_reports_do_not_disclose_event_constraints(
    client, test_user_id, monkeypatch
):
    from lorenzo_api.repository_copying import Dropped, Plan, Step
    from lorenzo_api.routers import repositories

    tenant = await make_tenant(test_user_id)
    repository = uuid.uuid4()
    hidden = uuid.uuid4()

    async def planned(*args, **kwargs):
        step = Step(
            repository_id=repository,
            name="Repository",
            granted=True,
            published=True,
            already_copied=False,
        )
        step.dropped = [Dropped("event_relationship", hidden, "its target Event was not copied")]
        return Plan(tenant_id=tenant, steps=[step])

    monkeypatch.setattr(repositories, "plan_copy", planned)
    try:
        url = f"/tenants/{tenant}/repositories/{repository}/copy-plan"
        full = await client.get(url)
        assert full.status_code == 200, full.text
        assert full.json()["steps"][0]["dropped"][0]["kind"] == "event_relationship"
        async with admin_session_factory() as session:
            member = await session.get_one(Membership, (tenant, test_user_id))
            member.role = MembershipRole.AUTHOR
            await session.commit()
        restricted = await client.get(url)
        assert restricted.status_code == 200, restricted.text
        assert restricted.json()["steps"][0]["dropped"] == []
        assert str(hidden) not in restricted.text
    finally:
        await delete_tenant(tenant)
