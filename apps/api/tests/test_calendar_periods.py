"""Explicit period entries and minimal dated Events (ADR 0309)."""

import asyncio
import uuid
from copy import deepcopy

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import delete
from test_calendars import DEFINITION, make_calendar

from lorenzo_api.models import Membership, Player


async def period(client, tenant, calendar, **date):
    response = await client.post(f"/tenants/{tenant}/calendars/{calendar}/periods", json=date)
    assert response.status_code == 200, response.text
    return response.json()


async def test_materialization_reuses_identity_and_reading_never_writes(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        url = f"/tenants/{tenant}/calendars/{calendar}"
        assert (await client.get(url + "/periods")).json()["total"] == 0
        dates = await asyncio.gather(
            *(
                period(client, tenant, calendar, year=3286, segment="first", day=16)
                for _ in range(2)
            )
        )
        assert dates[0]["entity_id"] == dates[1]["entity_id"]
        assert dates[0]["granularity"] == "day"
        rows = (await client.get(url + "/periods")).json()
        assert rows["total"] == 3
        assert {r["granularity"] for r in rows["items"]} == {"year", "month", "day"}
        await client.get(url + "/years/3287")
        assert (await client.get(url + "/periods")).json()["total"] == 3
        invalid = await client.post(
            url + "/periods", json={"year": 3286, "segment": "first", "day": 28}
        )
        assert invalid.status_code == 422, invalid.text
        changed = deepcopy(DEFINITION)
        changed["segments"][0]["days"] = 15
        current = await client.get(url)
        refused = await client.put(
            url + "/definition", json=changed, headers={"If-Match": current.headers["etag"]}
        )
        assert refused.status_code == 409, refused.text
        assert (await client.get(url)).json()["definition"] == current.json()["definition"]
    finally:
        await delete_tenant(tenant)


async def test_event_date_associations_are_versioned_and_notes_stay_information(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        a = await period(client, tenant, calendar, year=3286, segment="first", day=16)
        b = await period(client, tenant, calendar, year=3286, segment="first", day=18)
        event = await client.post(
            f"/tenants/{tenant}/entities", json={"name": "Storm", "kinds": ["event"]}
        )
        assert event.status_code == 201, event.text
        assert event.json()["kinds"] == ["event"]
        base = f"/tenants/{tenant}/entities/{event.json()['id']}"
        dates = await client.put(
            base + "/dates",
            json={"period_ids": [a["entity_id"], b["entity_id"]]},
            headers={"If-Match": event.headers["etag"]},
        )
        assert dates.status_code == 200, dates.text
        assert {d["day"] for d in dates.json()} == {16, 18}
        assert (
            await client.put(
                base + "/dates",
                json={"period_ids": []},
                headers={"If-Match": event.headers["etag"]},
            )
        ).status_code == 412
        at_day = await client.get(f"/tenants/{tenant}/calendar-periods/{a['entity_id']}/entries")
        assert [e["name"] for e in at_day.json()["items"]] == ["Storm"]
        note = await client.post(
            f"/tenants/{tenant}/entities/{a['entity_id']}/information",
            json={"type": "note", "title": "Diary", "content": "A quiet evening."},
        )
        assert note.status_code == 201, note.text
        assert (
            await client.get(f"/tenants/{tenant}/calendar-periods/{a['entity_id']}/entries")
        ).json()["total"] == 1
        deleted = await client.delete(f"/tenants/{tenant}/entities/{a['entity_id']}")
        assert deleted.status_code == 409, deleted.text
    finally:
        await delete_tenant(tenant)


async def test_hidden_calendar_also_hides_public_period_and_date_link(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        date = await period(
            client, tenant, calendar, year=3286, segment="first", day=16, is_public=True
        )
        made = await client.post(
            f"/tenants/{tenant}/entities", json={"name": "Public event", "kinds": ["event"]}
        )
        assert made.status_code == 201, made.text
        event = made.json()["id"]
        base = f"/tenants/{tenant}/entities/{event}"
        dated = await client.put(
            base + "/dates",
            json={"period_ids": [date["entity_id"]]},
            headers={"If-Match": made.headers["etag"]},
        )
        assert dated.status_code == 200, dated.text
        gate = await client.get(base + "/audience")
        shared = await client.put(
            base + "/audience", json={"is_public": True}, headers={"If-Match": gate.headers["etag"]}
        )
        assert shared.status_code == 200, shared.text
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(Player(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id))
            await session.execute(delete(Membership).where(Membership.tenant_id == tenant))
            await session.commit()
        assert (await client.get(base)).status_code == 200
        assert (await client.get(base + "/dates")).json() == []
        assert (
            await client.get(f"/tenants/{tenant}/entities/{date['entity_id']}")
        ).status_code == 404
        assert (
            await client.get(f"/tenants/{tenant}/entities", params={"kind": "calendar_period"})
        ).json()["total"] == 0
        assert (
            await client.get(f"/tenants/{tenant}/calendar-periods/{date['entity_id']}/entries")
        ).status_code == 404
    finally:
        await delete_tenant(tenant)


async def test_month_only_date_and_other_tenant_target(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        month = await period(client, tenant, calendar, year=0, segment="first")
        assert month["granularity"] == "month"
        assert month["day"] is None
        event = await client.post(
            f"/tenants/{other}/entities", json={"name": "Other event", "kinds": ["event"]}
        )
        assert event.status_code == 201, event.text
        result = await client.put(
            f"/tenants/{other}/entities/{event.json()['id']}/dates",
            json={"period_ids": [month["entity_id"]]},
            headers={"If-Match": event.headers["etag"]},
        )
        assert result.status_code == 422, result.text
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)


async def test_period_event_copy_release_and_local_definition_protection(
    raw_client, fake_jwks_server
):
    from _repository_actors import cleanup, make_actor
    from sqlalchemy import select

    from lorenzo_api.models import Calendar, CalendarPeriod, EntryCalendarPeriod, StoryEvent
    from lorenzo_api.release_document import decode, encode
    from lorenzo_api.repository_content import load_content, public_entry

    author = await make_actor(raw_client, fake_jwks_server, "period-author")
    keeper = await make_actor(raw_client, fake_jwks_server, "period-keeper")
    repository = await author.create_tenant("Periods repository", kind="repository")
    library = await keeper.create_tenant("Periods library")
    try:
        made = await author.post(
            f"/tenants/{repository}/calendars", json={"name": "Calendar", "definition": DEFINITION}
        )
        assert made.status_code == 201, made.text
        source = made.json()["entity_id"]
        day = await author.post(
            f"/tenants/{repository}/calendars/{source}/periods",
            json={"year": 10, "segment": "first", "day": 16, "is_public": True},
        )
        assert day.status_code == 200, day.text
        event = await author.post(
            f"/tenants/{repository}/entities", json={"name": "Storm", "kinds": ["event"]}
        )
        assert event.status_code == 201, event.text
        dated = await raw_client.put(
            f"/tenants/{repository}/entities/{event.json()['id']}/dates",
            json={"period_ids": [day.json()["entity_id"]]},
            headers={**author.headers, "If-Match": event.headers["etag"]},
        )
        assert dated.status_code == 200, dated.text
        await author.put(f"/tenants/{repository}/subscribers/{library}")
        published = await author.put(f"/tenants/{repository}/published", json={})
        assert published.status_code == 200, published.text
        copied = await keeper.post(f"/tenants/{library}/repositories/{repository}/copy", json={})
        assert copied.status_code == 201, copied.text
        async with admin_session_factory() as session:
            content = await load_content(session, repository)
            document, files = encode(content)
            released = decode(document, files)
            assert released.calendar_periods == content.calendar_periods
            assert released.entry_dates == content.entry_dates
            # Public period coordinates must not disclose a restricted calendar in a release.
            assert not public_entry(released, uuid.UUID(day.json()["entity_id"]))
            local_calendar = await session.scalar(
                select(Calendar.entity_id).where(Calendar.tenant_id == library)
            )
            local_day = await session.scalar(
                select(CalendarPeriod).where(
                    CalendarPeriod.tenant_id == library, CalendarPeriod.day == 16
                )
            )
            assert local_day.calendar_entity_id == local_calendar
            assert str(local_day.entity_id) != day.json()["entity_id"]
            parent = await session.get(CalendarPeriod, local_day.parent_entity_id)
            assert parent.calendar_entity_id == local_calendar
            assert parent.day is None and parent.segment == "first"
            local_event = await session.scalar(
                select(StoryEvent.entity_id).where(StoryEvent.tenant_id == library)
            )
            assert (
                await session.scalar(
                    select(EntryCalendarPeriod.period_entity_id).where(
                        EntryCalendarPeriod.entity_id == local_event
                    )
                )
                == local_day.entity_id
            )
        # A local later-day entry may block an otherwise valid upstream shortening.
        added = await keeper.post(
            f"/tenants/{library}/calendars/{local_calendar}/periods",
            json={"year": 11, "segment": "first", "day": 27},
        )
        assert added.status_code == 200, added.text
        changed = deepcopy(DEFINITION)
        changed["segments"][0]["days"] = 20
        edited = await raw_client.put(
            f"/tenants/{repository}/calendars/{source}/definition",
            json=changed,
            headers={**author.headers, "If-Match": made.headers["etag"]},
        )
        assert edited.status_code == 200, edited.text
        updates = f"/tenants/{library}/repositories/{repository}/updates"
        applied = await keeper.post(
            updates, json={"actions": [{"kind": "entity", "source_id": source, "action": "apply"}]}
        )
        assert applied.status_code == 409, applied.text
        local = await keeper.get(f"/tenants/{library}/calendars/{local_calendar}")
        assert local.json()["definition"]["segments"][0]["days"] == 27
        purged = await keeper.post(
            f"/tenants/{library}/repositories/{repository}/copy", json={"again": "purge"}
        )
        assert purged.status_code == 409, purged.text
        assert (
            await keeper.get(f"/tenants/{library}/calendars/{local_calendar}")
        ).status_code == 200
    finally:
        await cleanup([library, repository], [author, keeper])


async def test_public_period_list_for_a_player_uses_calendar_visibility(client, test_user_id):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant, is_public=True)).json()["entity_id"]
        await period(client, tenant, calendar, year=1, segment="first", day=2, is_public=True)
        async with admin_session_factory() as session:
            campaign = await make_campaign(session, tenant_id=tenant)
            session.add(Player(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id))
            await session.execute(delete(Membership).where(Membership.tenant_id == tenant))
            await session.commit()
        listed = await client.get(f"/tenants/{tenant}/calendars/{calendar}/periods")
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 3
    finally:
        await delete_tenant(tenant)
