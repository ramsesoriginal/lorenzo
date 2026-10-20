"""Bounded, reviewed calendar imports through the real API (ADR 0311)."""

import asyncio
from copy import deepcopy

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from sqlalchemy import func, select

from lorenzo_api.models import (
    CalendarImport,
    CalendarObservance,
    CalendarPeriod,
    Entity,
    Fact,
    Information,
    StoryEvent,
)

DOCUMENT = {
    "format": "lorenzo.calendar-document/1",
    "source_key": "isles",
    "name": "Isles",
    "definition": {"segments": [{"key": "spring", "name": "Spring", "days": 27}]},
    "annotations": [
        {
            "key": "diary",
            "date": {"year": 3286, "segment": "spring", "day": 16},
            "text": "A quiet evening.",
            "original_text": "A quiet evening.",
        },
        {
            "key": "storm-a",
            "date": {"year": 3286, "segment": "spring", "day": 17},
            "text": "The storm begins.",
            "original_text": "The storm begins.",
            "classification": "event",
            "group": "storm",
            "title": "Storm",
        },
        {
            "key": "storm-b",
            "date": {"year": 3286, "segment": "spring", "day": 18},
            "text": "The storm ends.",
            "original_text": "The storm ends.",
            "classification": "event",
            "group": "storm",
            "title": "Storm",
        },
        {
            "key": "charter",
            "date": {"year": 3286, "segment": "spring", "day": 19},
            "text": "The charter exists.",
            "original_text": "The charter exists.",
            "classification": "fact",
        },
        {
            "key": "feast",
            "date": {"year": 3286, "segment": "spring", "day": 20},
            "text": "The annual feast.",
            "original_text": "The annual feast.",
            "classification": "observance",
            "recurrence": {"segment": "spring", "day": 20},
        },
    ],
}


async def plan(client, tenant, document=None, **choices):
    body = {"document": document or DOCUMENT, **choices}
    response = await client.post(f"/tenants/{tenant}/calendar-imports/plan", json=body)
    assert response.status_code == 200, response.text
    return body, response.json()


async def apply(client, tenant, body, planned):
    return await client.post(
        f"/tenants/{tenant}/calendar-imports", json={**body, "token": planned["token"]}
    )


async def count(model, tenant):
    async with admin_session_factory() as session:
        return await session.scalar(
            select(func.count()).select_from(model).where(model.tenant_id == tenant)
        )


async def test_plan_is_read_only_and_all_classifications_import_atomically_and_repeat(
    client, test_user_id
):
    tenant = await make_tenant(test_user_id)
    try:
        body, planned = await plan(client, tenant)
        assert planned["ready"]
        assert await count(Entity, tenant) == 0
        assert await count(CalendarImport, tenant) == 0
        results = await asyncio.gather(*(apply(client, tenant, body, planned) for _ in range(2)))
        assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
        assert results[0].json() == results[1].json()
        assert await count(CalendarImport, tenant) == 1
        assert await count(Information, tenant) == 5
        assert await count(StoryEvent, tenant) == 1
        assert await count(Fact, tenant) == 1
        assert await count(CalendarObservance, tenant) == 1
        assert await count(CalendarPeriod, tenant) == 6  # year, month, four explicitly dated days
        _, again = await plan(client, tenant)
        assert all(c["action"] == "unchanged" for c in again["changes"])
        repeated = await apply(client, tenant, body, again)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["created"] == []
        assert len(repeated.json()["unchanged"]) == 5
        assert await count(Information, tenant) == 5
        event = (await client.get(f"/tenants/{tenant}/entities", params={"kind": "event"})).json()[
            "items"
        ][0]
        assert (
            len((await client.get(f"/tenants/{tenant}/entities/{event['id']}/dates")).json()) == 2
        )
    finally:
        await delete_tenant(tenant)


async def test_source_and_local_conflicts_require_review_and_stale_plan_cannot_overwrite(
    client, test_user_id
):
    tenant = await make_tenant(test_user_id)
    try:
        body, planned = await plan(client, tenant)
        made = await apply(client, tenant, body, planned)
        assert made.status_code == 200, made.text
        changed = deepcopy(DOCUMENT)
        changed["annotations"][0]["text"] = "A loud evening."
        changed_body, changed_plan = await plan(client, tenant, changed)
        assert not changed_plan["ready"]
        assert (
            next(c for c in changed_plan["changes"] if c["key"] == "note:diary")["action"]
            == "conflict"
        )
        assert (await apply(client, tenant, changed_body, changed_plan)).status_code == 409
        resolved_body, resolved = await plan(
            client, tenant, changed, resolutions={"note:diary": "take_source"}
        )
        calendar = made.json()["calendar_entity_id"]
        renamed = await client.patch(
            f"/tenants/{tenant}/entities/{calendar}", json={"name": "Local name"}
        )
        assert renamed.status_code == 200, renamed.text
        stale = await apply(client, tenant, resolved_body, resolved)
        assert stale.status_code == 412, stale.text
        final_body, final_plan = await plan(
            client,
            tenant,
            changed,
            resolutions={"note:diary": "take_source", "$calendar": "keep_local"},
        )
        assert final_plan["ready"]
        done = await apply(client, tenant, final_body, final_plan)
        assert done.status_code == 200, done.text
        assert done.json()["changed"] == ["note:diary"]
        assert done.json()["kept_local"] == ["$calendar"]
        assert (await client.get(f"/tenants/{tenant}/calendars/{calendar}")).json()[
            "name"
        ] == "Local name"
    finally:
        await delete_tenant(tenant)


async def test_unreviewed_warnings_and_cross_tenant_token_are_refused(client, test_user_id):
    tenant, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        document = deepcopy(DOCUMENT)
        document["warnings"] = [
            {"key": "anchor-review", "message": "Choose the anchor deliberately."}
        ]
        body, planned = await plan(client, tenant, document)
        assert not planned["ready"]
        assert planned["unaccepted_warnings"] == ["anchor-review"]
        assert (await apply(client, tenant, body, planned)).status_code == 409
        assert await count(Entity, tenant) == 0
        body, planned = await plan(client, tenant, document, accepted_warnings=["anchor-review"])
        assert (await apply(client, other, body, planned)).status_code == 412
        assert await count(Entity, other) == 0
        assert (await apply(client, tenant, body, planned)).status_code == 200
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)


async def test_failed_apply_rolls_back_entries_periods_information_and_receipt(
    client, test_user_id, monkeypatch
):
    from lorenzo_api import calendar_imports
    from lorenzo_api.exceptions import CalendarImportReviewRequiredError

    original = calendar_imports.write_information
    calls = 0

    async def fail_after_a_write(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise CalendarImportReviewRequiredError(detail="A later annotation was refused")
        return await original(*args, **kwargs)

    monkeypatch.setattr(calendar_imports, "write_information", fail_after_a_write)
    tenant = await make_tenant(test_user_id)
    try:
        body, planned = await plan(client, tenant)
        refused = await apply(client, tenant, body, planned)
        assert refused.status_code == 409, refused.text
        assert await count(Entity, tenant) == 0
        assert await count(Information, tenant) == 0
        assert await count(CalendarPeriod, tenant) == 0
        assert await count(CalendarImport, tenant) == 0
    finally:
        await delete_tenant(tenant)


async def test_native_source_export_round_trip_and_provenance_stays_local(client, test_user_id):
    tenant, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        body, planned = await plan(client, tenant)
        assert (await apply(client, tenant, body, planned)).status_code == 200
        exported = await client.get(f"/tenants/{tenant}/calendar-imports/isles/document")
        assert exported.status_code == 200, exported.text
        assert exported.json()["format"] == "lorenzo.calendar-document/1"
        assert len(exported.json()["annotations"]) == 5
        again_body, again_plan = await plan(client, tenant, exported.json())
        assert all(c["action"] == "unchanged" for c in again_plan["changes"]), again_plan
        assert (await apply(client, tenant, again_body, again_plan)).status_code == 200
        assert (
            await client.get(f"/tenants/{other}/calendar-imports/isles/document")
        ).status_code == 404
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)
