"""What a campaign calls its game master (ADR 0294, RFC 0040 section 4)."""

import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign
from httpx import AsyncClient

from lorenzo_api.models import CampaignGm, Tenant


async def _campaign_of_mine(test_user_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id))
        await session.commit()
    return tenant_id, campaign_id


async def test_a_campaign_says_gm_and_gms_until_it_chooses_otherwise(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id = await _campaign_of_mine(test_user_id)

    page = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    listing = await client.get(f"/tenants/{tenant_id}/campaigns")

    assert (page.json()["gm_title"], page.json()["gm_title_plural"]) == ("GM", "GMs")
    row = listing.json()["items"][0]
    assert (row["gm_title"], row["gm_title_plural"]) == ("GM", "GMs")
    await delete_tenant(tenant_id)


async def test_a_title_and_its_plural_are_kept_and_read_everywhere(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id = await _campaign_of_mine(test_user_id)
    url = f"/tenants/{tenant_id}/campaigns/{campaign_id}"

    set_ = await client.patch(
        url, json={"gm_title": " Storyteller ", "gm_title_plural": "Storytellers"}
    )
    assert set_.status_code == 200, set_.text
    assert (set_.json()["gm_title"], set_.json()["gm_title_plural"]) == (
        "Storyteller",
        "Storytellers",
    )

    listing = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert listing.json()["items"][0]["gm_title"] == "Storyteller"
    managed = await client.get("/me/managed")
    campaign = managed.json()["tenants"][0]["campaigns"][0]
    assert (campaign["gm_title"], campaign["gm_title_plural"]) == ("Storyteller", "Storytellers")
    me = await client.get("/me")
    grants = me.json()["campaign_gm_grants"]
    assert [g["gm_title_plural"] for g in grants] == ["Storytellers"]
    await delete_tenant(tenant_id)


async def test_an_empty_title_puts_both_back_to_the_default(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id = await _campaign_of_mine(test_user_id)
    url = f"/tenants/{tenant_id}/campaigns/{campaign_id}"
    await client.patch(url, json={"gm_title": "DM", "gm_title_plural": "DMs"})

    cleared = await client.patch(url, json={"gm_title": "  ", "gm_title_plural": ""})

    assert cleared.status_code == 200, cleared.text
    assert (cleared.json()["gm_title"], cleared.json()["gm_title_plural"]) == ("GM", "GMs")
    await delete_tenant(tenant_id)


async def test_a_patch_that_leaves_the_title_out_keeps_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id = await _campaign_of_mine(test_user_id)
    url = f"/tenants/{tenant_id}/campaigns/{campaign_id}"
    await client.patch(url, json={"gm_title": "Master", "gm_title_plural": "Masters"})

    renamed = await client.patch(url, json={"name": "Another name"})

    assert renamed.json()["gm_title"] == "Master"
    await delete_tenant(tenant_id)


@pytest.mark.parametrize(
    "body",
    [
        {"gm_title": "Storyteller"},
        {"gm_title_plural": "Storytellers"},
        {"gm_title": "Storyteller", "gm_title_plural": ""},
        {"gm_title": "", "gm_title_plural": "Storytellers"},
        {"gm_title": "Story\nteller", "gm_title_plural": "Storytellers"},
        {"gm_title": "Story\tteller", "gm_title_plural": "Storytellers"},
        {"gm_title": "<b>DM</b>", "gm_title_plural": "DMs"},
        {"gm_title": "DM", "gm_title_plural": "*DMs*"},
        {"gm_title": "DM_", "gm_title_plural": "DMs"},
        {"gm_title": "[DM]", "gm_title_plural": "DMs"},
        {"gm_title": "x" * 31, "gm_title_plural": "DMs"},
    ],
)
async def test_a_title_that_is_not_plain_text_or_not_in_a_pair_is_refused_and_nothing_is_kept(
    client: AsyncClient, test_user_id: uuid.UUID, body: dict[str, str]
) -> None:
    tenant_id, campaign_id = await _campaign_of_mine(test_user_id)
    url = f"/tenants/{tenant_id}/campaigns/{campaign_id}"

    response = await client.patch(url, json=body)

    assert response.status_code == 422, response.text
    assert response.json()["type"].endswith("campaign-gm-title-invalid")
    after = await client.get(url)
    assert (after.json()["gm_title"], after.json()["gm_title_plural"]) == ("GM", "GMs")
    await delete_tenant(tenant_id)


async def test_a_name_with_an_apostrophe_a_space_and_other_scripts_is_kept_as_written(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id = await _campaign_of_mine(test_user_id)
    url = f"/tenants/{tenant_id}/campaigns/{campaign_id}"

    ok = await client.patch(
        url,
        json={
            "gm_title": "Mistress of Ceremonies",
            "gm_title_plural": "Mistresses o’ Ceremonies",
        },
    )
    other = await client.patch(
        url, json={"gm_title": "Spielleiter", "gm_title_plural": "Spielleiter"}
    )

    assert ok.status_code == 200, ok.text
    assert ok.json()["gm_title_plural"] == "Mistresses o’ Ceremonies"
    assert other.status_code == 200, other.text
    await delete_tenant(tenant_id)


async def test_someone_who_is_not_a_manager_cannot_set_the_title(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        await session.commit()

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}",
        json={"gm_title": "DM", "gm_title_plural": "DMs"},
    )

    assert response.status_code in (403, 404), response.text
    await delete_tenant(tenant_id)
