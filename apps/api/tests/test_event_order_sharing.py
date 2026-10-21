"""Reader results must not depend on private constraints or hidden Events."""

import asyncio
import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from test_event_order import compare, event, relation

from lorenzo_api.models import EntityAudience, Membership, MembershipRole, TenantAdminCampaignOptOut


async def share(client, t, a, b, kind="order", *, shared=True, version=None):
    base = f"/tenants/{t}/events/{a}/relationships"
    if version is None:
        version = (await client.get(base)).headers["etag"]
    return await client.put(
        base + f"/{b}/sharing",
        json={"kind": kind, "is_shared": shared},
        headers={"If-Match": version},
    )


async def optout(t, user, enabled):
    async with admin_session_factory() as s:
        if enabled:
            campaign = await make_campaign(s, tenant_id=t)
            s.add(
                TenantAdminCampaignOptOut(
                    tenant_id=t, user_id=user, campaign_id=campaign.id, created_by=user
                )
            )
        else:
            await s.execute(
                delete(TenantAdminCampaignOptOut).where(
                    TenantAdminCampaignOptOut.tenant_id == t,
                    TenantAdminCampaignOptOut.user_id == user,
                )
            )
        await s.commit()


async def make_event(client, t, name, n, public=True):
    result = await client.post(
        f"/tenants/{t}/entities",
        json={"id": str(uuid.UUID(int=n)), "name": name, "kinds": ["event"]},
    )
    assert result.status_code == 201, result.text
    e = result.json()["id"]
    async with admin_session_factory() as s:
        (await s.get_one(EntityAudience, uuid.UUID(e))).is_public = public
        if not public:
            from lorenzo_api.models import Entity, User

            other = User(authgear_subject_id=str(uuid.uuid4()))
            s.add(other)
            await s.flush()
            (await s.get_one(Entity, uuid.UUID(e))).created_by = other.id
        await s.commit()
    return e


async def test_hidden_graph_changes_cannot_influence_reader_order_or_metadata(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        a = await make_event(client, t, "Arrival", 300)
        b = await make_event(client, t, "Departure", 100)
        hidden = await make_event(client, t, "Secret meeting", 1, False)
        await optout(t, test_user_id, True)
        base = f"/tenants/{t}/events"

        async def snapshot():
            ordered = (
                await client.get(base, params={"sort": "order", "size": 1, "page": 1})
            ).json()
            second = (await client.get(base, params={"sort": "order", "size": 1, "page": 2})).json()
            compared = await compare(client, t, a, b)
            links = await client.get(base + f"/{a}/relationships")
            assert "etag" not in links.headers
            return ordered, second, compared, links.json()

        initial = await snapshot()
        assert initial[0]["items"][0]["entity_id"] == b
        assert initial[2]["basis"] == "linearized"
        await optout(t, test_user_id, False)
        # Even shared incident edges cannot disclose an intermediary the reader cannot see.
        await relation(client, t, a, hidden, "causes")
        await relation(client, t, hidden, b, "causes")
        await share(client, t, a, hidden, "causes")
        await share(client, t, hidden, b, "causes")
        assert (await compare(client, t, a, b))["basis"] == "causal"
        await optout(t, test_user_id, True)
        assert await snapshot() == initial
        assert (await client.get(base, params={"causal_event_id": a})).json()["total"] == 1
        assert (await client.get(base + f"/{hidden}/relationships")).status_code == 404
        missing = str(uuid.uuid4())
        assert (await client.get(base + f"/{missing}/relationships")).status_code == 404
        denied = await client.post(
            base + "/compare", json={"pairs": [{"left": a, "right": hidden}]}
        )
        assert denied.status_code == 404 and "Secret meeting" not in denied.text
        await optout(t, test_user_id, False)
        await relation(client, t, a, b, "order")
        await optout(t, test_user_id, True)
        assert await snapshot() == initial  # private direct edge also cannot change tie order
        await optout(t, test_user_id, False)
        assert (await share(client, t, a, b)).status_code == 200
        await optout(t, test_user_id, True)
        shown = await snapshot()
        assert shown[0]["items"][0]["entity_id"] == a
        assert shown[2]["basis"] == "ruled" and len(shown[2]["path"]) == 1
        assert all(row["is_shared"] for row in shown[3])
        log = (await client.get(f"/tenants/{t}/activity-log")).json()
        assert not any(row["action"].startswith("event.relationship") for row in log["items"])
    finally:
        await delete_tenant(t)


async def test_sharing_is_versioned_independent_per_kind_and_does_not_open_endpoints(
    client, test_user_id
):
    t = await make_tenant(test_user_id)
    try:
        a, b = await event(client, t, "A"), await event(client, t, "B")
        await relation(client, t, a, b, "order")
        await relation(client, t, a, b, "causes")
        base = f"/tenants/{t}/events/{a}/relationships"
        current = await client.get(base)
        assert all(not r["is_shared"] for r in current.json())
        assert (
            await client.put(base + f"/{b}/sharing", json={"kind": "order", "is_shared": True})
        ).status_code == 428
        saved = current.headers["etag"]
        shared = await share(client, t, a, b, version=saved)
        assert shared.status_code == 200, shared.text
        assert {r["kind"] for r in shared.json() if r["is_shared"]} == {"order"}
        assert (await share(client, t, a, b, "causes", version=saved)).status_code == 412
        async with admin_session_factory() as s:
            with pytest.raises(IntegrityError, match="Remove and add"):
                await s.execute(
                    text(
                        "UPDATE event_relationship SET kind='order' "
                        "WHERE tenant_id=:t AND from_event_id=:a "
                        "AND to_event_id=:b AND kind='causes'"
                    ),
                    {"t": t, "a": a, "b": b},
                )
            await s.rollback()
        # Legacy duplicate assertion writes preserve its explicit sharing choice.
        assert (await relation(client, t, a, b, "order")).status_code == 200
        rows = (await client.get(base)).json()
        assert next(row for row in rows if row["kind"] == "order")["is_shared"]
        async with admin_session_factory() as s:
            assert not (await s.get_one(EntityAudience, uuid.UUID(a))).is_public
            assert not (await s.get_one(EntityAudience, uuid.UUID(b))).is_public
        version = (await client.get(base)).headers["etag"]
        results = await asyncio.gather(
            share(client, t, a, b, shared=False, version=version),
            share(client, t, a, b, "causes", version=version),
        )
        assert sorted(r.status_code for r in results) == [200, 412]
        async with admin_session_factory() as s:
            (await s.get_one(Membership, (t, test_user_id))).role = MembershipRole.AUTHOR
            await s.commit()
        # ADR 0316 admits this Author; the independent player denial remains below.
        assert (await client.get(base)).status_code == 200
        assert (
            await client.put(base + f"/{b}/sharing", json={"kind": "order", "is_shared": True})
        ).status_code == 428
        assert (await client.get(f"/tenants/{t}/events/{a}/participants")).status_code == 200
        assert (await client.get(f"/tenants/{t}/event-learning")).status_code == 200
    finally:
        await delete_tenant(t)


async def test_shared_assertions_copy_and_old_release_defaults_are_private(client, test_user_id):
    from datetime import UTC, datetime

    from lorenzo_api.models import EventRelationship, RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content
    from lorenzo_api.repository_copying import apply_plan, forget_copy, plan_copy

    async with admin_session_factory() as s:
        repo = Tenant(name="Shared Event repository", kind=TenantKind.REPOSITORY)
        s.add(repo)
        await s.flush()
        s.add(Membership(tenant_id=repo.id, user_id=test_user_id, role=MembershipRole.OWNER))
        await s.commit()
        source = repo.id
    target = await make_tenant(test_user_id)
    try:
        a, b, c = [await event(client, source, name) for name in ["A", "B", "C"]]
        await relation(client, source, a, b, "causes")
        await relation(client, source, b, c, "order")
        from test_event_learning import information

        from lorenzo_api.models import EntityAudience, Information

        note = await information(client, source, a, False)
        async with admin_session_factory() as s:
            (await s.get_one(EntityAudience, uuid.UUID(a))).shared_with_participants = True
            (await s.get_one(Information, uuid.UUID(note))).shared_with_participants = True
            await s.commit()
        await share(client, source, a, b, "causes")
        async with admin_session_factory() as s:
            (await s.get_one(Tenant, source)).published_at = datetime.now(UTC)
            await s.flush()
            s.add(RepositorySubscription(repository_tenant_id=source, subscriber_tenant_id=target))
            await s.commit()
            content = await load_content(s, source)
            doc, files = encode(content)
            assert decode(doc, files).shared_event_relationships == [
                (uuid.UUID(a), uuid.UUID(b), "causes")
            ]
            old = {k: v for k, v in doc.items() if k != "shared_event_relationships"}
            assert decode(old, files, format=8).shared_event_relationships == []
            await s.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(target)}
            )
            plan = await plan_copy(
                s, tenant_id=target, repository_id=source, user_id=test_user_id, resolutions=[]
            )
            assert sorted(row["is_shared"] for row in plan.rows["event_relationship"]) == [
                False,
                True,
            ]
            assert sum(row["shared_with_participants"] for row in plan.rows["entity_audience"]) == 1
            assert sum(row["shared_with_participants"] for row in plan.rows["information"]) == 1
            await apply_plan(s, plan, user_id=test_user_id)
            await s.commit()
            assert (
                len(
                    (
                        await s.scalars(
                            select(EntityAudience).where(
                                EntityAudience.tenant_id == target,
                                EntityAudience.shared_with_participants.is_(True),
                            )
                        )
                    ).all()
                )
                == 1
            )
            assert (
                len(
                    (
                        await s.scalars(
                            select(Information).where(
                                Information.tenant_id == target,
                                Information.shared_with_participants.is_(True),
                            )
                        )
                    ).all()
                )
                == 1
            )
            rows = (
                await s.scalars(
                    select(EventRelationship).where(EventRelationship.tenant_id == target)
                )
            ).all()
            assert sorted(row.is_shared for row in rows) == [False, True]
            await forget_copy(
                s, tenant_id=target, repository_id=source, user_id=test_user_id, purge=True
            )
            await s.commit()
    finally:
        await delete_tenant(target)
        await delete_tenant(source)


async def test_visible_transitive_proofs_survive_name_filter_and_pagination(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        a, x, b = [await event(client, t, name) for name in ["Session A", "Interlude", "Session B"]]
        for e in [a, x, b]:
            async with admin_session_factory() as s:
                (await s.get_one(EntityAudience, uuid.UUID(e))).is_public = True
                await s.commit()
        for left, right in [(a, x), (x, b)]:
            await relation(client, t, left, right, "causes")
            await share(client, t, left, right, "causes")
        await optout(t, test_user_id, True)
        proof = await compare(client, t, a, b)
        assert proof["basis"] == "causal" and len(proof["path"]) == 2
        rows = await client.get(
            f"/tenants/{t}/events", params={"sort": "order", "q": "Session", "size": 1, "page": 2}
        )
        assert rows.status_code == 200, rows.text
        assert rows.json()["total"] == 2
        assert rows.json()["items"][0]["entity_id"] == b
        assert rows.json()["items"][0]["order_basis"] == "causal"
        assert (await client.get(f"/tenants/{t}/events", params={"causal_event_id": x})).json()[
            "total"
        ] == 3
    finally:
        await delete_tenant(t)


async def test_authors_gms_and_players_get_reader_graph_but_no_ordering_write(
    raw_client, fake_jwks_server
):
    from _author_world import make_world

    from lorenzo_api.models import CampaignGm, Player

    world = await make_world(raw_client, fake_jwks_server)
    t = world.tenant_id
    try:
        a, b = await event(world.owner, t, "Arrival"), await event(world.owner, t, "Departure")
        base = f"/tenants/{t}/events/{a}/relationships"
        current = await world.owner.get(base)
        created = await world.owner.client.put(
            base + f"/{b}",
            headers={**world.owner.headers, "If-Match": current.headers["etag"]},
            json={"kind": "causes"},
        )
        assert created.status_code == 200, created.text
        published = await world.owner.client.put(
            base + f"/{b}/sharing",
            headers={**world.owner.headers, "If-Match": created.headers["etag"]},
            json={"kind": "causes", "is_shared": True},
        )
        assert published.status_code == 200, published.text
        async with admin_session_factory() as s:
            campaign = await make_campaign(s, tenant_id=t)
            s.add(CampaignGm(tenant_id=t, campaign_id=campaign.id, user_id=world.outsider.user_id))
            for e in [a, b]:
                (await s.get_one(EntityAudience, uuid.UUID(e))).is_public = True
            await s.commit()
            campaign_id = campaign.id
        base = f"/tenants/{t}/events/{a}/relationships"
        for reader in [world.author, world.outsider]:
            rows = await reader.get(base)
            assert rows.status_code == 200 and len(rows.json()) == 1, rows.text
            assert (await compare(reader, t, a, b))["basis"] == "causal"
            denied = await reader.put(
                base + f"/{b}/sharing", json={"kind": "causes", "is_shared": False}
            )
            assert denied.status_code == 428
        async with admin_session_factory() as s:
            await s.execute(
                delete(CampaignGm).where(
                    CampaignGm.tenant_id == t, CampaignGm.user_id == world.outsider.user_id
                )
            )
            s.add(Player(tenant_id=t, campaign_id=campaign_id, user_id=world.outsider.user_id))
            await s.commit()
        rows = await world.outsider.get(base)
        assert rows.status_code == 200 and len(rows.json()) == 1, rows.text
        assert (await compare(world.outsider, t, a, b))["basis"] == "causal"
        assert (await world.outsider.get(f"/tenants/{t}/events/{a}/participants")).status_code in [
            403,
            404,
        ]
        denied = await world.outsider.delete(base + f"/{b}", params={"kind": "causes"})
        assert denied.status_code in [403, 404]
    finally:
        await world.clean_up()


def test_participant_audiences_release_v9_defaults_private():
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import Content

    c = Content(tenant_id=uuid.uuid4())
    c.participant_entry_audiences = [uuid.uuid4()]
    c.participant_information_audiences = [uuid.uuid4()]
    document, files = encode(c)
    back = decode(document, files)
    assert back.participant_entry_audiences == c.participant_entry_audiences
    assert back.participant_information_audiences == c.participant_information_audiences
    old = {
        k: v
        for k, v in document.items()
        if k not in {"participant_entry_audiences", "participant_information_audiences"}
    }
    back = decode(old, files, format=9)
    assert back.participant_entry_audiences == []
    assert back.participant_information_audiences == []
