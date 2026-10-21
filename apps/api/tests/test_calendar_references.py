from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from sqlalchemy import delete, func, select
from test_calendars import make_calendar

from lorenzo_api.models import Entity, Membership, Player


async def test_date_references_are_read_only_and_apply_calendar_audiences(client, test_user_id):
    tenant, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        made = await make_calendar(client, tenant, slug="reckoning")
        expressions = [
            "reckoning 3286",
            "reckoning 3286/First",
            "reckoning 3286/1/16",
            "reckoning 3286/festival/2",
            "reckoning 3286/2/3",
            "missing 0",
            "reckoning 3286/unknown",
        ]
        async with admin_session_factory() as s:
            before = await s.scalar(select(func.count()).where(Entity.tenant_id == tenant))
        url = f"/tenants/{tenant}/calendar-references/resolve"
        response = await client.post(url, json={"expressions": expressions})
        assert response.status_code == 200, response.text
        rows = response.json()
        assert len(rows) == 4
        assert rows[2]["segment"] == "first" and rows[2]["day"] == 16
        assert rows[2]["calendar_entity_id"] == made.json()["entity_id"]
        assert (
            await client.post(
                f"/tenants/{other}/calendar-references/resolve", json={"expressions": expressions}
            )
        ).json() == []
        assert (await client.post(url, json={"expressions": ["invalid"]})).json() == []
        async with admin_session_factory() as s:
            assert await s.scalar(select(func.count()).where(Entity.tenant_id == tenant)) == before
            campaign = await make_campaign(s, tenant_id=tenant)
            s.add(Player(tenant_id=tenant, campaign_id=campaign.id, user_id=test_user_id))
            await s.execute(delete(Membership).where(Membership.tenant_id == tenant))
            await s.commit()
        assert (await client.post(url, json={"expressions": expressions})).json() == []
        assert (await client.get(f"/tenants/{tenant}/calendars")).json()["total"] == 0
    finally:
        await delete_tenant(tenant)
        await delete_tenant(other)
