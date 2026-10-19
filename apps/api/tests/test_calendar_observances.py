"""Recurrence authoring never records an occurrence (ADR 0310)."""

import asyncio
import uuid
from copy import deepcopy

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from sqlalchemy import delete, select
from test_calendars import DEFINITION, make_calendar

from lorenzo_api.models import EntityAudience, Membership, Player


async def test_observance_calculation_is_conditional_and_does_not_materialize(client, test_user_id):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        url = f"/tenants/{tenant}/calendars/{calendar}"
        made = await client.post(
            url + "/observances",
            json={
                "name": "First Feast",
                "rule": {"segment": "first", "day": 2, "when": {"every": 2, "offset": 1}},
            },
        )
        assert made.status_code == 201, made.text
        assert (await client.get(f"/tenants/{tenant}/entities/{made.json()['entity_id']}")).json()[
            "kinds"
        ] == ["observance"]
        for year in [-1, 1, 3287]:
            occurrences = await client.get(url + f"/years/{year}/observances")
            assert occurrences.status_code == 200, occurrences.text
            assert occurrences.json()["total"] == 1
            assert occurrences.json()["items"][0]["date"] == {
                "year": year,
                "segment": "first",
                "day": 2,
            }
        assert (await client.get(url + "/years/0/observances")).json()["total"] == 0
        assert (await client.get(url + "/periods")).json()["total"] == 0
        assert (await client.get(url + "/observances")).json()["total"] == 1
        rule_url = f"/tenants/{tenant}/observances/{made.json()['entity_id']}/rule"
        assert (await client.put(rule_url, json={"segment": "first", "day": 3})).status_code == 428
        edits = await asyncio.gather(
            *(
                client.put(
                    rule_url,
                    json={"segment": "first", "day": d},
                    headers={"If-Match": made.headers["etag"]},
                )
                for d in [3, 4]
            )
        )
        assert sorted(e.status_code for e in edits) == [200, 412]
        current = await client.get(url)
        changed = deepcopy(DEFINITION)
        changed["segments"][0]["days"] = 1
        refused = await client.put(
            url + "/definition", json=changed, headers={"If-Match": current.headers["etag"]}
        )
        assert refused.status_code == 409, refused.text
        assert (await client.delete(f"/tenants/{tenant}/entities/{calendar}")).status_code == 409
    finally:
        await delete_tenant(tenant)


async def test_observance_hidden_calendar_and_hidden_rule_do_not_disclose_counts(
    client, test_user_id
):
    tenant = await make_tenant(test_user_id)
    try:
        made = await make_calendar(client, tenant, is_public=True)
        calendar = made.json()["entity_id"]
        base = f"/tenants/{tenant}/calendars/{calendar}"
        hidden = await client.post(
            base + "/observances", json={"name": "Hidden", "rule": {"segment": "first", "day": 1}}
        )
        public = await client.post(
            base + "/observances",
            json={"name": "Public", "rule": {"segment": "first", "day": 1}, "is_public": True},
        )
        assert hidden.status_code == public.status_code == 201
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(Player(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id))
            await session.execute(delete(Membership).where(Membership.tenant_id == tenant))
            await session.commit()
        rows = (await client.get(base + "/years/1/observances")).json()
        assert rows["total"] == 1
        assert rows["items"][0]["name"] == "Public"
        assert (
            await client.get(f"/tenants/{tenant}/observances/{hidden.json()['entity_id']}")
        ).status_code == 404
        async with admin_session_factory() as session:
            audience = await session.get(EntityAudience, calendar)
            audience.is_public = False
            await session.commit()
        assert (
            await client.get(f"/tenants/{tenant}/observances/{public.json()['entity_id']}")
        ).status_code == 404
        assert (await client.get(base + "/years/1/observances")).status_code == 404
    finally:
        await delete_tenant(tenant)


async def test_observance_copy_release_and_reviewed_rule_updates(raw_client, fake_jwks_server):
    from _repository_actors import cleanup, make_actor

    from lorenzo_api.models import CalendarObservance
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content, public_entry

    author = await make_actor(raw_client, fake_jwks_server, "observance-author")
    keeper = await make_actor(raw_client, fake_jwks_server, "observance-keeper")
    repository = await author.create_tenant("Observance repository", kind="repository")
    library = await keeper.create_tenant("Observance library")
    try:
        calendar = await author.post(
            f"/tenants/{repository}/calendars", json={"name": "Calendar", "definition": DEFINITION}
        )
        assert calendar.status_code == 201, calendar.text
        source_calendar = calendar.json()["entity_id"]
        made = await author.post(
            f"/tenants/{repository}/calendars/{source_calendar}/observances",
            json={"name": "Feast", "rule": {"segment": "first", "day": 1}, "is_public": True},
        )
        assert made.status_code == 201, made.text
        source = made.json()["entity_id"]
        await author.put(f"/tenants/{repository}/subscribers/{library}")
        published = await author.put(f"/tenants/{repository}/published", json={})
        assert published.status_code == 200, published.text
        copied = await keeper.post(f"/tenants/{library}/repositories/{repository}/copy", json={})
        assert copied.status_code == 201, copied.text
        async with admin_session_factory() as session:
            local = await session.scalar(
                select(CalendarObservance).where(CalendarObservance.tenant_id == library)
            )
            local_id, local_calendar = local.entity_id, local.calendar_entity_id
            assert str(local_calendar) != source_calendar
            content = await load_content(session, repository)
            document, files = encode(content)
            back = decode(document, files)
            assert back.observances == content.observances
            assert not public_entry(back, uuid.UUID(source))
        edited = await raw_client.put(
            f"/tenants/{repository}/observances/{source}/rule",
            json={"segment": "first", "day": 2},
            headers={**author.headers, "If-Match": made.headers["etag"]},
        )
        assert edited.status_code == 200, edited.text
        updates_url = f"/tenants/{library}/repositories/{repository}/updates"
        updates = await keeper.get(updates_url)
        assert updates.status_code == 200, updates.text
        row = next(r for r in updates.json()["changed"] if r["source_id"] == source)
        assert next(f for f in row["fields"] if f["field"] == "observance_rule")["state"] == "clean"
        assert (await keeper.get(f"/tenants/{library}/observances/{local_id}")).json()["rule"][
            "day"
        ] == 1
        applied = await keeper.post(
            updates_url,
            json={"actions": [{"kind": "entity", "source_id": source, "action": "apply"}]},
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["not_applied"] == []
        assert (await keeper.get(f"/tenants/{library}/observances/{local_id}")).json()["rule"][
            "day"
        ] == 2
    finally:
        await cleanup([library, repository], [author, keeper])
