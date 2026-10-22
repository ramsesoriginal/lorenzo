"""Bulk period reads and the batch write (ADR 0324)."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import delete, func, select, update
from test_calendars import make_calendar

from lorenzo_api.models import CalendarPeriod, Entity, Membership, Player, User
from lorenzo_api.routers.calendar_period_reads import SUMMARY_TEXT_LIMIT, cut


async def period(client, tenant, calendar, **date):
    response = await client.post(f"/tenants/{tenant}/calendars/{calendar}/periods", json=date)
    assert response.status_code == 200, response.text
    return response.json()


async def entity_count(tenant) -> int:
    async with admin_session_factory() as session:
        return await session.scalar(select(func.count()).where(Entity.tenant_id == tenant))


async def become_player(tenant, user_id):
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant)
        session.add(Player(tenant_id=tenant, campaign_id=campaign.id, user_id=user_id))
        await session.execute(delete(Membership).where(Membership.tenant_id == tenant))
        await session.commit()


def test_a_long_note_is_cut_at_a_word_and_a_short_one_is_left_alone():
    assert cut("A quiet evening.") == ("A quiet evening.", False)
    text, truncated = cut("word " * 400)
    assert truncated
    assert len(text) <= SUMMARY_TEXT_LIMIT
    assert text.endswith("word")
    assert cut("x" * (SUMMARY_TEXT_LIMIT + 50))[0] == "x" * SUMMARY_TEXT_LIMIT


async def test_periods_are_listed_with_their_calendar_and_by_id(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        first = (await make_calendar(client, tenant, name="Alpha reckoning")).json()["entity_id"]
        second = (await make_calendar(client, tenant, name="Beta reckoning")).json()["entity_id"]
        day = await period(client, tenant, first, year=3286, segment="first", day=16)
        await period(client, tenant, second, year=1, segment="first", day=2)
        base = f"/tenants/{tenant}/calendar-periods"
        listed = (await client.get(base)).json()
        assert listed["total"] == 6
        assert [i["calendar_name"] for i in listed["items"]][:3] == ["Alpha reckoning"] * 3
        assert {i["granularity"] for i in listed["items"]} == {"year", "month", "day"}
        only = (await client.get(base, params={"calendar_id": second, "year": 1})).json()
        assert only["total"] == 3
        assert {i["calendar_entity_id"] for i in only["items"]} == {second}
        month = (await client.get(base, params={"calendar_id": first, "segment": "first"})).json()
        assert month["total"] == 2
        by_id = (await client.get(base, params={"id": [day["entity_id"]]})).json()
        assert [i["entity_id"] for i in by_id["items"]] == [day["entity_id"]]
        assert by_id["items"][0]["day"] == 16
        assert by_id["items"][0]["calendar_name"] == "Alpha reckoning"
        too_many = await client.get(base, params={"id": [str(uuid.uuid4()) for _ in range(101)]})
        assert too_many.status_code == 422
    finally:
        await delete_tenant(tenant)


async def test_summaries_carry_notes_and_dated_entries_and_write_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        day = await period(client, tenant, calendar, year=3286, segment="first", day=16)
        await period(client, tenant, calendar, year=3286, segment="festival", day=1)
        note = await client.post(
            f"/tenants/{tenant}/entities/{day['entity_id']}/information",
            json={"type": "note", "title": "Diary", "content": "A quiet evening."},
        )
        assert note.status_code == 201, note.text
        event = await client.post(
            f"/tenants/{tenant}/entities", json={"name": "Storm", "kinds": ["event"]}
        )
        assert event.status_code == 201, event.text
        dated = await client.put(
            f"/tenants/{tenant}/entities/{event.json()['id']}/dates",
            json={"period_ids": [day["entity_id"]]},
            headers={"If-Match": event.headers["etag"]},
        )
        assert dated.status_code == 200, dated.text
        before = await entity_count(tenant)
        base = f"/tenants/{tenant}/calendars/{calendar}/years/3286/period-summaries"
        month = await client.get(base, params={"segment": "first"})
        assert month.status_code == 200, month.text
        rows = {(r["segment"], r["day"]): r for r in month.json()["items"]}
        assert set(rows) == {("first", None), ("first", 16)}
        saved = rows[("first", 16)]
        assert saved["entity_id"] == day["entity_id"]
        assert [(n["title"], n["text"], n["truncated"]) for n in saved["notes"]] == [
            ("Diary", "A quiet evening.", False)
        ]
        assert [e["name"] for e in saved["entries"]] == ["Storm"]
        assert saved["entry_total"] == 1
        assert rows[("first", None)]["notes"] == [] and rows[("first", None)]["entry_total"] == 0
        whole = await client.get(base)
        assert whole.json()["total"] == 5
        assert (await client.get(base.replace("3286", "3287"))).json()["total"] == 0
        assert await entity_count(tenant) == before
    finally:
        await delete_tenant(tenant)


async def test_a_reader_gets_no_hidden_note_entry_or_period_in_a_summary_or_a_count(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    author_id = None
    try:
        calendar = (await make_calendar(client, tenant, is_public=True)).json()["entity_id"]
        visible = await period(
            client, tenant, calendar, year=1, segment="first", day=2, is_public=True
        )
        hidden = await period(client, tenant, calendar, year=1, segment="first", day=3)
        for target in (visible, hidden):
            note = await client.post(
                f"/tenants/{tenant}/entities/{target['entity_id']}/information",
                json={"type": "note", "title": "Private", "content": "Not for readers."},
            )
            assert note.status_code == 201, note.text
        event = await client.post(
            f"/tenants/{tenant}/entities", json={"name": "Secret rite", "kinds": ["event"]}
        )
        assert event.status_code == 201, event.text
        dated = await client.put(
            f"/tenants/{tenant}/entities/{event.json()['id']}/dates",
            json={"period_ids": [visible["entity_id"]]},
            headers={"If-Match": event.headers["etag"]},
        )
        assert dated.status_code == 200, dated.text
        # The creator of an entry keeps sight of it (ADR 0316), so someone else made this one.
        async with admin_session_factory() as session:
            author = User(authgear_subject_id=f"period-reads-{uuid.uuid4()}")
            session.add(author)
            await session.flush()
            await session.execute(
                update(Entity).where(Entity.id == event.json()["id"]).values(created_by=author.id)
            )
            await session.commit()
            author_id = author.id
        await become_player(tenant, test_user_id)
        summaries = await client.get(
            f"/tenants/{tenant}/calendars/{calendar}/years/1/period-summaries"
        )
        assert summaries.status_code == 200, summaries.text
        days = [r for r in summaries.json()["items"] if r["day"] is not None]
        assert [d["day"] for d in days] == [2]
        assert days[0]["notes"] == []
        assert days[0]["entries"] == [] and days[0]["entry_total"] == 0
        listed = (await client.get(f"/tenants/{tenant}/calendar-periods")).json()
        assert hidden["entity_id"] not in {i["entity_id"] for i in listed["items"]}
        assert (
            await client.get(
                f"/tenants/{tenant}/calendar-periods", params={"id": [hidden["entity_id"]]}
            )
        ).json()["total"] == 0
    finally:
        await delete_tenant(tenant)
        if author_id is not None:
            async with admin_session_factory() as session:
                await session.execute(delete(User).where(User.id == author_id))
                await session.commit()


async def test_batch_creates_periods_with_parents_in_order_and_is_idempotent(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        url = f"/tenants/{tenant}/calendars/{calendar}/periods/batch"
        body = {
            "periods": [
                {"year": 3286, "segment": "first", "day": 18},
                {"year": 3286, "segment": "first", "day": 16},
                {"year": 3286, "segment": "first"},
                {"year": 3286, "segment": "first", "day": 16},
            ]
        }
        made = await client.post(url, json=body)
        assert made.status_code == 200, made.text
        rows = made.json()
        assert [(r["granularity"], r["day"]) for r in rows] == [
            ("day", 18),
            ("day", 16),
            ("month", None),
            ("day", 16),
        ]
        assert rows[1]["entity_id"] == rows[3]["entity_id"]
        assert rows[0]["parent_entity_id"] == rows[2]["entity_id"]
        assert rows[2]["name"] == "First 3286"
        assert rows[0]["name"] == "18 First 3286"
        listed = (await client.get(f"/tenants/{tenant}/calendars/{calendar}/periods")).json()
        assert listed["total"] == 4  # the year, the month and two days
        again = await client.post(url, json=body)
        assert [r["entity_id"] for r in again.json()] == [r["entity_id"] for r in rows]
        assert (await client.get(f"/tenants/{tenant}/calendars/{calendar}/periods")).json()[
            "total"
        ] == 4
        single = await period(client, tenant, calendar, year=3286, segment="first", day=18)
        assert single["entity_id"] == rows[0]["entity_id"]
    finally:
        await delete_tenant(tenant)


async def test_one_invalid_date_fails_the_whole_batch_and_creates_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]
        before = await entity_count(tenant)
        refused = await client.post(
            f"/tenants/{tenant}/calendars/{calendar}/periods/batch",
            json={
                "periods": [
                    {"year": 1, "segment": "first", "day": 1},
                    {"year": 1, "segment": "first", "day": 28},
                ]
            },
        )
        assert refused.status_code == 422, refused.text
        assert await entity_count(tenant) == before
        async with admin_session_factory() as session:
            assert (
                await session.scalar(select(func.count()).where(CalendarPeriod.tenant_id == tenant))
                == 0
            )
        too_many = await client.post(
            f"/tenants/{tenant}/calendars/{calendar}/periods/batch",
            json={"periods": [{"year": 1}] * 1001},
        )
        assert too_many.status_code == 422
    finally:
        await delete_tenant(tenant)


async def test_a_reader_cannot_use_the_batch_write(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant, is_public=True)).json()["entity_id"]
        await become_player(tenant, test_user_id)
        before = await entity_count(tenant)
        refused = await client.post(
            f"/tenants/{tenant}/calendars/{calendar}/periods/batch",
            json={"periods": [{"year": 1, "segment": "first", "day": 1}]},
        )
        assert refused.status_code in (403, 404), refused.text
        assert await entity_count(tenant) == before
    finally:
        await delete_tenant(tenant)
