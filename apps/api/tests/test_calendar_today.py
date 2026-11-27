"""A calendar's own current date, and where Events are dated in a year (ADR 0530)."""

import uuid

from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_calendar_periods import period
from test_calendars import DEFINITION, make_calendar


async def test_a_calendar_keeps_a_current_date_that_is_checked_and_conditional(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        made = await make_calendar(client, tenant)
        base = f"/tenants/{tenant}/calendars/{made.json()['entity_id']}"
        assert made.json()["today"] is None
        read = await client.get(base)
        assert read.json()["today"] is None
        tag = read.headers["etag"]
        today = {"today": {"year": 3286, "segment": "first", "day": 12}}
        # A write needs the version it read, and the date must exist in this calendar.
        assert (await client.put(base + "/today", json=today)).status_code == 428
        assert (
            await client.put(base + "/today", json=today, headers={"If-Match": '"stale"'})
        ).status_code == 412
        bad = await client.put(
            base + "/today",
            json={"today": {"year": 3286, "segment": "nowhere", "day": 1}},
            headers={"If-Match": tag},
        )
        assert bad.status_code == 422, bad.text
        set_ = await client.put(base + "/today", json=today, headers={"If-Match": tag})
        assert set_.status_code == 200, set_.text
        assert set_.json()["today"] == today["today"]
        assert (await client.get(base)).json()["today"] == today["today"]
        # Changing the definition so that the day is gone clears it; a day still there stays.
        again = await client.get(base)
        kept = await client.put(
            base + "/definition", json=DEFINITION, headers={"If-Match": again.headers["etag"]}
        )
        assert kept.status_code == 200, kept.text
        assert kept.json()["today"] == today["today"]
        smaller = {
            **DEFINITION,
            "segments": [
                {**s, "days": 5} if s["key"] == "first" else s for s in DEFINITION["segments"]
            ],
        }
        shorter = await client.put(
            base + "/definition", json=smaller, headers={"If-Match": kept.headers["etag"]}
        )
        assert shorter.status_code == 200, shorter.text
        assert shorter.json()["today"] is None
        # Null clears it.
        again = await client.get(base)
        put = await client.put(
            base + "/today",
            json={"today": {"year": 3286, "segment": "first", "day": 3}},
            headers={"If-Match": again.headers["etag"]},
        )
        assert put.status_code == 200, put.text
        cleared = await client.put(
            base + "/today", json={"today": None}, headers={"If-Match": put.headers["etag"]}
        )
        assert cleared.status_code == 200 and cleared.json()["today"] is None
    finally:
        await delete_tenant(tenant)


async def test_dated_days_say_where_a_year_has_events(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    try:
        calendar = (await make_calendar(client, tenant)).json()["entity_id"]

        async def dated(name, **date):
            event = await client.post(
                f"/tenants/{tenant}/entities", json={"name": name, "kinds": ["event"]}
            )
            assert event.status_code == 201, event.text
            p = await period(client, tenant, calendar, **date)
            put = await client.put(
                f"/tenants/{tenant}/entities/{event.json()['id']}/dates",
                json={"period_ids": [p["entity_id"]]},
                headers={"If-Match": event.headers["etag"]},
            )
            assert put.status_code == 200, put.text

        await dated("One", year=3286, segment="first", day=3)
        await dated("Two", year=3286, segment="first", day=3)
        await dated("Feast", year=3286, segment="festival", day=1)
        await dated("Month", year=3286, segment="first")
        await dated("Whole", year=3286)
        await dated("Elsewhere", year=3287, segment="first", day=3)
        url = f"/tenants/{tenant}/events/dated-days"
        got = await client.get(url, params={"calendar_id": calendar, "year": 3286})
        assert got.status_code == 200, got.text
        assert got.json() == [
            {"segment": None, "day": None, "count": 1},
            {"segment": "first", "day": None, "count": 1},
            {"segment": "first", "day": 3, "count": 2},
            {"segment": "festival", "day": 1, "count": 1},
        ]
        other = await client.get(url, params={"calendar_id": calendar, "year": 3287})
        assert other.json() == [{"segment": "first", "day": 3, "count": 1}]
        empty = await client.get(url, params={"calendar_id": calendar, "year": 1})
        assert empty.json() == []
        missing = await client.get(url, params={"calendar_id": str(uuid.uuid4()), "year": 1})
        assert missing.status_code == 404
    finally:
        await delete_tenant(tenant)
