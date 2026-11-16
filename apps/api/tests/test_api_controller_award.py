"""ADR 0467: where a library allows it, the controller of a holder awards it a feature, as its
manager may; it is a setting of the library, off by default, and nothing else a controller may not
do changes.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import (
    delete_tenant,
    make_campaign,
    make_character,
    make_plain_participant,
    make_tenant,
)
from httpx import AsyncClient
from sqlalchemy import select, update
from test_api_features import _award, _being, _feature, _held

from lorenzo_api.models import CharacterPlayer, Player, Tenant


async def _set(tenant_id: uuid.UUID, allowed: bool) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant).where(Tenant.id == tenant_id).values(controllers_award_features=allowed)
        )
        await session.commit()


async def test_the_setting_is_off_until_an_administrator_turns_it_on(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    url = f"/tenants/{tenant_id}"
    assert (await client.get(url)).json()["controllers_award_features"] is False

    on = await client.patch(url, json={"controllers_award_features": True})
    assert on.status_code == 200, on.text
    assert on.json()["controllers_award_features"] is True
    assert (await client.get(url)).json()["controllers_award_features"] is True
    # Another change does not touch it.
    renamed = await client.patch(url, json={"description": "A table"})
    assert renamed.json()["controllers_award_features"] is True

    off = await client.patch(url, json={"controllers_award_features": False})
    assert off.status_code == 200, off.text
    assert off.json()["controllers_award_features"] is False
    await delete_tenant(tenant_id)


async def test_a_controller_awards_their_own_holder_a_feature_only_where_the_library_allows_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Rage", repeatable=True)
    single = await _feature(client, tenant_id, "Darkvision")
    async with admin_session_factory() as session:
        await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
    stranger = await _being(tenant_id, "Stranger")
    # The caller plays Pia, and is no longer an administrator.
    await make_plain_participant(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        player = await session.scalar(
            select(Player).where(Player.user_id == test_user_id, Player.tenant_id == tenant_id)
        )
        assert player is not None
        pia = await make_character(
            session, tenant_id=tenant_id, name="Pia", owner_player_id=player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=pia.entity_id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        pia_id = pia.entity_id

    # Off, as it was: a player is not the holder's manager.
    assert (await _award(client, tenant_id, pia_id, feature)).status_code == 403

    await _set(tenant_id, True)
    awarded = await _award(client, tenant_id, pia_id, feature)
    assert awarded.status_code == 201, awarded.text
    assert [h["name"] for h in await _held(client, tenant_id, pia_id)] == ["Rage"]
    # The same rules as for a manager: a feature that is repeatable can come again, one that is not
    # cannot, and what is no feature is no feature.
    assert (await _award(client, tenant_id, pia_id, feature)).status_code == 201
    assert (await _award(client, tenant_id, pia_id, single)).status_code == 201
    assert (await _award(client, tenant_id, pia_id, single)).status_code == 409
    assert (await _award(client, tenant_id, pia_id, pia_id)).status_code == 422

    # Only what they control: not another being, and not the removal of what they were awarded.
    assert (await _award(client, tenant_id, stranger, feature)).status_code == 403
    (first, *_) = await _held(client, tenant_id, pia_id)
    removed = await client.delete(f"/tenants/{tenant_id}/features/{first['id']}")
    assert removed.status_code == 403

    await _set(tenant_id, False)
    assert (await _award(client, tenant_id, pia_id, feature)).status_code == 403
    await delete_tenant(tenant_id)


async def test_an_administrator_awards_with_the_setting_on_or_off(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    feature = await _feature(client, tenant_id, "Rage", repeatable=True)
    hero = await _being(tenant_id)
    assert (await _award(client, tenant_id, hero, feature)).status_code == 201
    await _set(tenant_id, True)
    assert (await _award(client, tenant_id, hero, feature)).status_code == 201
    await delete_tenant(tenant_id)
