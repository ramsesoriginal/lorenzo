"""ADR 0456: the grants read, apply with picks (automatic grants, choices, the limits and a GM's
override, a chain of grants, a dry run), and revocation in the request that removes a source.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from _repository_fixtures import seed_every_content_table
from conftest import (
    delete_tenant,
    make_being,
    make_campaign,
    make_character,
    make_plain_participant,
    make_tenant,
)
from httpx import AsyncClient
from sqlalchemy import func, select
from test_api_computed_stats import _sheet
from test_item_read_statements import _statements

from lorenzo_api.models import (
    CharacterPlayer,
    Containment,
    Entity,
    FeatureInstance,
    GrantRecord,
    ItemInstance,
    Player,
    StatValueType,
)


class _Table:
    """A library with a sheet, a fighter, a hero who is one, and a few features."""

    tenant: uuid.UUID
    sheet: Any
    hero: uuid.UUID
    fighter: uuid.UUID
    features: dict[str, uuid.UUID]


async def _entry(client: AsyncClient, tenant: uuid.UUID, name: str, **body: Any) -> uuid.UUID:
    made = await client.post(f"/tenants/{tenant}/entities", json={"name": name, **body})
    assert made.status_code == 201, made.text
    return uuid.UUID(made.json()["id"])


async def _stat(client: AsyncClient, t: _Table, entity: uuid.UUID, name: str, value: int) -> None:
    response = await client.put(
        f"/tenants/{t.tenant}/entities/{entity}/stats/{t.sheet[name]}",
        json={"value": value, "acquire_group": False},
    )
    assert response.status_code == 200, response.text


async def _rule(client: AsyncClient, t: _Table, entry: uuid.UUID, **body: Any) -> dict[str, Any]:
    made = await client.post(
        f"/tenants/{t.tenant}/grant-rules", json={"entry_id": str(entry), "mode": "all", **body}
    )
    assert made.status_code == 201, made.text
    return made.json()  # type: ignore[no-any-return]


def _level_at_least(t: _Table, n: int, subject: str = "holder") -> dict[str, Any]:
    return {
        "subject": subject,
        "stat_definition_id": str(t.sheet["level"]),
        "comparator": "ge",
        "right_constant": str(n),
    }


async def _grants(client: AsyncClient, t: _Table, holder: uuid.UUID | None = None) -> dict:
    response = await client.get(f"/tenants/{t.tenant}/entities/{holder or t.hero}/grants")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def _apply(client: AsyncClient, t: _Table, holder: uuid.UUID | None = None, **body: Any):  # type: ignore[no-untyped-def]
    return await client.post(
        f"/tenants/{t.tenant}/entities/{holder or t.hero}/grants/apply", json=body
    )


async def _features(client: AsyncClient, t: _Table, holder: uuid.UUID | None = None) -> list[dict]:
    response = await client.get(f"/tenants/{t.tenant}/entities/{holder or t.hero}/features")
    assert response.status_code == 200, response.text
    return response.json()["features"]  # type: ignore[no-any-return]


async def _table(client: AsyncClient, user_id: uuid.UUID, *, level: int = 1) -> _Table:
    t = _Table()
    t.tenant = await make_tenant(user_id)
    t.sheet = await _sheet(
        t.tenant,
        level=StatValueType.INT,
        picks=StatValueType.INT,
        strength=StatValueType.INT,
        is_attuned=StatValueType.BOOL,
    )
    t.fighter = await _entry(client, t.tenant, "Fighter")
    async with admin_session_factory() as session:
        t.hero = (await make_being(session, tenant_id=t.tenant, name="Hero")).entity_id
        await session.commit()
    t.features = {}
    for name in ("Second Wind", "Action Surge", "Indomitable", "Rage", "Reckless Attack"):
        t.features[name] = await _entry(client, t.tenant, name, kinds=["feature"])
    await _stat(client, t, t.hero, "level", level)
    await _stat(client, t, t.hero, "strength", 10)
    parents = await client.put(
        f"/tenants/{t.tenant}/entities/{t.hero}/parents", json={"parent_ids": [str(t.fighter)]}
    )
    assert parents.status_code == 200, parents.text
    return t


def _ids(t: _Table, *names: str) -> list[str]:
    return [str(t.features[name]) for name in names]


# --- reading -------------------------------------------------------------------------------


async def test_what_is_due_is_read_without_writing_and_apply_grants_it_once(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(
        client,
        t,
        t.fighter,
        label="Level 1",
        options=_ids(t, "Second Wind", "Action Surge"),
        conditions=[_level_at_least(t, 1)],
    )

    read = await _grants(client, t)
    assert [d["feature"]["name"] for d in read["due"]] == ["Second Wind", "Action Surge"]
    assert (read["due"][0]["label"], read["due"][0]["source"]["name"]) == ("Level 1", "Fighter")
    assert read["due"][0]["source"]["kind"] == "ancestor"
    # Reading twice writes nothing.
    await _grants(client, t)
    async with admin_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(GrantRecord)) == 0
    assert await _features(client, t) == []

    applied = await _apply(client, t)
    assert applied.status_code == 200, applied.text
    assert sorted(g["feature"]["name"] for g in applied.json()["created"]) == [
        "Action Surge",
        "Second Wind",
    ]
    assert applied.json()["revoked"] == [] and applied.json()["truncated"] is False
    held = await _features(client, t)
    assert sorted(h["name"] for h in held) == ["Action Surge", "Second Wind"]
    assert held[0]["granted_by"]["label"] == "Level 1"
    assert held[0]["granted_by"]["source"]["name"] == "Fighter"
    assert held[0]["granted_by"]["source_kind"] == "ancestor"

    # A (rule, source) grants once: applying again grants nothing new.
    again = await _apply(client, t)
    assert again.json()["created"] == []
    assert (await _grants(client, t))["due"] == []
    assert len(await _features(client, t)) == 2
    await delete_tenant(t.tenant)


async def test_a_rule_whose_conditions_do_not_hold_is_not_due_until_they_do(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id, level=1)
    await _rule(
        client,
        t,
        t.fighter,
        options=_ids(t, "Indomitable"),
        conditions=[_level_at_least(t, 3)],
    )
    assert (await _grants(client, t))["due"] == []
    assert (await _apply(client, t)).json()["created"] == []

    await _stat(client, t, t.hero, "level", 3)
    assert [d["feature"]["name"] for d in (await _grants(client, t))["due"]] == ["Indomitable"]
    assert len((await _apply(client, t)).json()["created"]) == 1
    await delete_tenant(t.tenant)


async def test_a_condition_on_the_source_reads_the_source(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(
        client,
        t,
        t.fighter,
        options=_ids(t, "Rage"),
        conditions=[_level_at_least(t, 5, subject="source")],
    )
    assert (await _grants(client, t))["due"] == []
    await _stat(client, t, t.fighter, "level", 5)
    assert len((await _grants(client, t))["due"]) == 1
    await delete_tenant(t.tenant)


# --- choices -------------------------------------------------------------------------------


async def test_a_choice_is_open_until_picked_within_its_limits(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    rule = await _rule(
        client,
        t,
        t.fighter,
        mode="choose",
        min_count=1,
        max_count=2,
        options=_ids(t, "Second Wind", "Action Surge", "Indomitable"),
    )
    (open_choice,) = (await _grants(client, t))["open_choices"]
    assert (open_choice["minimum"], open_choice["maximum"], open_choice["picked"]) == (1, 2, [])
    assert [o["name"] for o in open_choice["options"]] == [
        "Second Wind",
        "Action Surge",
        "Indomitable",
    ]
    # An apply with no picks leaves it open and writes nothing.
    assert (await _apply(client, t)).json()["created"] == []
    assert len((await _grants(client, t))["open_choices"]) == 1

    def pick(*names: str) -> dict[str, Any]:
        return {
            "picks": [
                {"rule_id": rule["id"], "source_id": str(t.fighter), "options": _ids(t, *names)}
            ]
        }

    # Outside the options, above the maximum, below the minimum (an empty pick), no such choice.
    assert (await _apply(client, t, **pick("Rage"))).status_code == 422
    assert (
        await _apply(client, t, **pick("Second Wind", "Action Surge", "Indomitable"))
    ).status_code == 422
    assert (await _apply(client, t, **pick())).status_code == 422
    nothing = await _apply(
        client,
        t,
        picks=[{"rule_id": str(uuid.uuid4()), "source_id": str(t.fighter), "options": []}],
    )
    assert nothing.status_code == 422
    assert await _features(client, t) == []

    picked = await _apply(client, t, **pick("Action Surge"))
    assert picked.status_code == 200, picked.text
    assert [g["feature"]["name"] for g in picked.json()["created"]] == ["Action Surge"]
    (still,) = picked.json()["open_choices"]
    assert [p["name"] for p in still["picked"]] == ["Action Surge"]
    # One more fits; the same one again does not; a third does not.
    assert (await _apply(client, t, **pick("Action Surge"))).status_code == 422
    assert (await _apply(client, t, **pick("Second Wind"))).status_code == 200
    assert (await _grants(client, t))["open_choices"] == []
    assert (await _apply(client, t, **pick("Indomitable"))).status_code == 422
    await delete_tenant(t.tenant)


async def test_a_choice_counts_with_a_stat_of_the_holder(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _stat(client, t, t.hero, "picks", 2)
    await _rule(
        client,
        t,
        t.fighter,
        mode="choose",
        count_stat_definition_id=str(t.sheet["picks"]),
        options=_ids(t, "Second Wind", "Action Surge", "Indomitable"),
    )
    assert (await _grants(client, t))["open_choices"][0]["maximum"] == 2
    await _stat(client, t, t.hero, "picks", 0)
    assert (await _grants(client, t))["open_choices"] == []
    await delete_tenant(t.tenant)


async def test_a_prerequisite_leaves_an_option_out_and_a_gm_may_override_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    needs = await client.put(
        f"/tenants/{t.tenant}/features/prototypes/{t.features['Indomitable']}/prerequisites",
        json={
            "prerequisites": [
                {
                    "stat_definition_id": str(t.sheet["strength"]),
                    "comparator": "ge",
                    "right_constant": "13",
                }
            ]
        },
    )
    assert needs.status_code == 200, needs.text
    rule = await _rule(
        client,
        t,
        t.fighter,
        mode="choose",
        max_count=1,
        options=_ids(t, "Second Wind", "Indomitable"),
    )
    (open_choice,) = (await _grants(client, t))["open_choices"]
    assert [o["name"] for o in open_choice["options"]] == ["Second Wind"]
    pick = {
        "picks": [
            {
                "rule_id": rule["id"],
                "source_id": str(t.fighter),
                "options": _ids(t, "Indomitable"),
            }
        ]
    }
    assert (await _apply(client, t, **pick)).status_code == 422
    overridden = await _apply(client, t, override=True, **pick)
    assert overridden.status_code == 200, overridden.text
    assert [g["feature"]["name"] for g in overridden.json()["created"]] == ["Indomitable"]
    await delete_tenant(t.tenant)


async def test_a_feature_the_holder_has_is_not_picked_again_unless_repeatable(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    rule = await _rule(
        client, t, t.fighter, mode="choose", max_count=2, options=_ids(t, "Second Wind", "Rage")
    )
    award = await client.post(
        f"/tenants/{t.tenant}/entities/{t.hero}/features",
        json={"feature_id": str(t.features["Second Wind"])},
    )
    assert award.status_code == 201, award.text
    (open_choice,) = (await _grants(client, t))["open_choices"]
    assert [o["name"] for o in open_choice["options"]] == ["Rage"]
    pick = {
        "picks": [
            {
                "rule_id": rule["id"],
                "source_id": str(t.fighter),
                "options": _ids(t, "Second Wind"),
            }
        ]
    }
    assert (await _apply(client, t, **pick)).status_code == 409
    assert (await _apply(client, t, override=True, **pick)).status_code == 409
    await delete_tenant(t.tenant)


# --- a chain of grants ----------------------------------------------------------------------


async def test_a_granted_feature_is_a_source_and_revoking_it_takes_what_it_gave(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(client, t, t.fighter, options=_ids(t, "Rage"))
    # The feature Rage gives Reckless Attack, which is itself held then.
    await _rule(
        client, t, t.features["Rage"], label="Rage brings", options=_ids(t, "Reckless Attack")
    )

    applied = await _apply(client, t)
    assert applied.status_code == 200, applied.text
    assert sorted(g["feature"]["name"] for g in applied.json()["created"]) == [
        "Rage",
        "Reckless Attack",
    ]
    held = {h["name"]: h for h in await _features(client, t)}
    assert held["Reckless Attack"]["granted_by"]["source_kind"] == "instance"
    assert held["Reckless Attack"]["granted_by"]["source"]["name"] == "Rage"

    # Removing Rage by hand (a GM) takes Reckless Attack with it, and neither is made again.
    removed = await client.delete(f"/tenants/{t.tenant}/features/{held['Rage']['id']}")
    assert removed.status_code == 204, removed.text
    assert await _features(client, t) == []
    again = await _apply(client, t)
    assert again.json()["created"] == []
    assert (await _grants(client, t))["due"] == []
    await delete_tenant(t.tenant)


async def test_a_cycle_of_rules_ends_at_the_depth_cap(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(client, t, t.fighter, options=_ids(t, "Rage"))
    await _rule(client, t, t.features["Rage"], options=_ids(t, "Reckless Attack"))
    # Reckless gives Rage again, which is repeatable: it would go on without the cap.
    await client.put(
        f"/tenants/{t.tenant}/entities/{t.features['Rage']}/kinds/feature",
        json={"repeatable": True},
    )
    await _rule(client, t, t.features["Reckless Attack"], options=_ids(t, "Rage"))
    applied = await _apply(client, t)
    assert applied.status_code == 200, applied.text
    assert applied.json()["truncated"] is False or len(applied.json()["created"]) >= 3
    await delete_tenant(t.tenant)


# --- dry run -------------------------------------------------------------------------------


async def test_a_dry_run_says_what_would_happen_and_writes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(client, t, t.fighter, options=_ids(t, "Second Wind"))
    dry = await _apply(client, t, dry_run=True)
    assert dry.status_code == 200, dry.text
    assert dry.json()["dry_run"] is True
    assert [g["feature"]["name"] for g in dry.json()["created"]] == ["Second Wind"]
    assert await _features(client, t) == []
    async with admin_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(GrantRecord)) == 0
        assert await session.scalar(select(func.count()).select_from(FeatureInstance)) == 0
    assert len((await _apply(client, t)).json()["created"]) == 1
    await delete_tenant(t.tenant)


# --- revocation ----------------------------------------------------------------------------


async def test_a_change_of_the_holders_parents_revokes_what_the_old_ones_gave(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(client, t, t.fighter, label="lasting", options=_ids(t, "Second Wind"))
    await _rule(
        client, t, t.fighter, label="kept", lasts="permanent", options=_ids(t, "Action Surge")
    )
    assert len((await _apply(client, t)).json()["created"]) == 2

    cleared = await client.put(
        f"/tenants/{t.tenant}/entities/{t.hero}/parents", json={"parent_ids": []}
    )
    assert cleared.status_code == 200, cleared.text
    assert [h["name"] for h in await _features(client, t)] == ["Action Surge"]
    async with admin_session_factory() as session:
        reasons = sorted(
            (await session.execute(select(GrantRecord.state, GrantRecord.revoked_reason))).all()
        )
    assert reasons == [("active", None), ("revoked", "source")]
    # Granting is never done in the request: getting the parent back makes the grant due again.
    await client.put(
        f"/tenants/{t.tenant}/entities/{t.hero}/parents", json={"parent_ids": [str(t.fighter)]}
    )
    assert [d["feature"]["name"] for d in (await _grants(client, t))["due"]] == ["Second Wind"]
    await delete_tenant(t.tenant)


async def test_a_stat_write_that_breaks_a_condition_revokes_in_the_same_request(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id, level=3)
    await _rule(
        client,
        t,
        t.fighter,
        options=_ids(t, "Indomitable"),
        conditions=[_level_at_least(t, 3)],
    )
    assert len((await _apply(client, t)).json()["created"]) == 1

    await _stat(client, t, t.hero, "level", 2)
    assert await _features(client, t) == []
    async with admin_session_factory() as session:
        (record,) = (await session.scalars(select(GrantRecord))).all()
        assert (record.state, record.revoked_reason, record.feature_instance_id) == (
            "revoked",
            "conditions",
            None,
        )
    # It is due again once the condition holds, and the revoked record does not stand in the way.
    await _stat(client, t, t.hero, "level", 4)
    assert len((await _grants(client, t))["due"]) == 1
    await delete_tenant(t.tenant)


async def test_a_stat_write_costs_one_statement_more_when_no_grant_reads_the_stat(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    url = f"/tenants/{t.tenant}/entities/{t.hero}/stats/{t.sheet['strength']}"
    await client.put(url, json={"value": 11, "acquire_group": False})
    with _statements() as seen:
        assert (
            await client.put(url, json={"value": 12, "acquire_group": False})
        ).status_code == 200
    # A tenant with no records asks once, and does no more (ADR 0285).
    assert sum("grant_record" in s for s in seen) == 1, [s for s in seen if "grant_record" in s]
    await delete_tenant(t.tenant)


async def test_a_source_that_is_an_item_gives_while_it_is_held_and_on(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    async with admin_session_factory() as session:
        chest = Entity(tenant_id=t.tenant, name="Chest")
        session.add(chest)
        await session.flush()
        ring = Entity(tenant_id=t.tenant, name="Ring of Rage")
        session.add(ring)
        await session.flush()
        session.add(ItemInstance(entity_id=ring.id, tenant_id=t.tenant))
        session.add(
            Containment(child_entity_id=ring.id, parent_entity_id=t.hero, tenant_id=t.tenant)
        )
        await session.commit()
        ring_id, chest_id = ring.id, chest.id
    # The ring (an instance) carries the rule through its own entry, as an item prototype would.
    await _rule(client, t, ring_id, options=_ids(t, "Rage"))
    applied = await _apply(client, t)
    assert [g["feature"]["name"] for g in applied.json()["created"]] == ["Rage"]
    (held,) = await _features(client, t)
    assert held["granted_by"]["source_kind"] == "instance"

    # Switched off, it gives nothing: what it gave goes in the request that switches it.
    off = await client.patch(
        f"/tenants/{t.tenant}/item-instances/{ring_id}", json={"active": False}
    )
    assert off.status_code == 200, off.text
    assert await _features(client, t) == []
    on = await client.patch(f"/tenants/{t.tenant}/item-instances/{ring_id}", json={"active": True})
    assert on.status_code == 200
    assert len((await _apply(client, t)).json()["created"]) == 1

    # Moved out of the holder, or deleted, it gives nothing either.
    moved = await client.put(
        f"/tenants/{t.tenant}/item-instances/{ring_id}/container",
        json={"container_entity_id": str(chest_id)},
    )
    assert moved.status_code in (200, 201, 409, 422), moved.text
    if moved.status_code == 200:
        assert await _features(client, t) == []
        await client.put(
            f"/tenants/{t.tenant}/item-instances/{ring_id}/container",
            json={"container_entity_id": str(t.hero)},
        )
        assert len((await _apply(client, t)).json()["created"]) == 1
    deleted = await client.delete(f"/tenants/{t.tenant}/item-instances/{ring_id}")
    assert deleted.status_code == 204, deleted.text
    assert await _features(client, t) == []
    await delete_tenant(t.tenant)


async def test_deleting_a_source_entry_revokes_what_it_gave(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(client, t, t.fighter, options=_ids(t, "Second Wind"))
    assert len((await _apply(client, t)).json()["created"]) == 1
    # The hero inherits from the fighter, so the entry stays here; its rule goes with it.
    removed = await client.delete(f"/tenants/{t.tenant}/entities/{t.fighter}")
    assert removed.status_code == 204, removed.text
    assert await _features(client, t) == []
    await delete_tenant(t.tenant)


async def test_a_grant_removed_by_hand_is_not_made_again_but_an_award_can_be(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    await _rule(client, t, t.fighter, options=_ids(t, "Second Wind"))
    await _apply(client, t)
    (held,) = await _features(client, t)
    assert (await client.delete(f"/tenants/{t.tenant}/features/{held['id']}")).status_code == 204
    assert (await _apply(client, t)).json()["created"] == []
    assert (await _grants(client, t))["due"] == []
    award = await client.post(
        f"/tenants/{t.tenant}/entities/{t.hero}/features",
        json={"feature_id": str(t.features["Second Wind"])},
    )
    assert award.status_code == 201
    assert award.json()["granted_by"] is None
    await delete_tenant(t.tenant)


# --- who may do what -----------------------------------------------------------------------


async def test_a_player_applies_their_own_grants_and_swaps_a_changeable_pick_but_cannot_override(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    t = await _table(client, test_user_id)
    swappable = await _rule(
        client,
        t,
        t.fighter,
        mode="choose",
        max_count=1,
        changeable=True,
        options=_ids(t, "Second Wind", "Action Surge"),
    )
    fixed = await _rule(
        client, t, t.fighter, mode="choose", max_count=1, options=_ids(t, "Rage", "Indomitable")
    )
    async with admin_session_factory() as session:
        await make_campaign(session, tenant_id=t.tenant)
        await session.commit()
    other = await _entry(client, t.tenant, "Stranger", kinds=["being"])
    await make_plain_participant(t.tenant, test_user_id)
    async with admin_session_factory() as session:
        player = await session.scalar(
            select(Player).where(Player.user_id == test_user_id, Player.tenant_id == t.tenant)
        )
        assert player is not None
        pia = await make_character(
            session, tenant_id=t.tenant, name="Pia", owner_player_id=player.id
        )
        session.add(
            CharacterPlayer(
                character_entity_id=pia.entity_id, player_id=player.id, tenant_id=t.tenant
            )
        )
        await session.commit()
        pia_id = pia.entity_id
    # Pia is a fighter too (a parent set by the library's staff, here straight in the database).
    async with admin_session_factory() as session:
        from lorenzo_api.models import EntityPrototype

        session.add(EntityPrototype(entity_id=pia_id, prototype_id=t.fighter, tenant_id=t.tenant))
        await session.commit()

    def pick(rule: dict, *names: str) -> dict[str, Any]:
        return {
            "picks": [
                {"rule_id": rule["id"], "source_id": str(t.fighter), "options": _ids(t, *names)}
            ]
        }

    assert (await _apply(client, t, pia_id, **pick(swappable, "Second Wind"))).status_code == 200
    assert (await _apply(client, t, pia_id, **pick(fixed, "Rage"))).status_code == 200
    # Not an override, and not someone else's holder.
    assert (await _apply(client, t, pia_id, override=True)).status_code == 403
    assert (await _apply(client, t, other)).status_code == 403
    assert (await client.get(f"/tenants/{t.tenant}/entities/{other}/grants")).status_code == 404

    held = {h["name"]: h for h in await _features(client, t, pia_id)}
    # The changeable pick is the holder's to swap; the other is a GM's to remove.
    assert (
        await client.delete(f"/tenants/{t.tenant}/features/{held['Rage']['id']}")
    ).status_code == 403
    assert (
        await client.delete(f"/tenants/{t.tenant}/features/{held['Second Wind']['id']}")
    ).status_code == 204
    swapped = await _apply(client, t, pia_id, **pick(swappable, "Action Surge"))
    assert swapped.status_code == 200, swapped.text
    await delete_tenant(t.tenant)


# --- a repository carries the records ---------------------------------------------------------


async def test_a_copy_brings_how_a_holder_came_to_have_a_feature(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await author.create_tenant("Records Core", kind="repository")
    async with admin_session_factory() as session:
        await seed_every_content_table(session, repository)
        await session.commit()
    table = await gm.create_tenant("My Table")
    try:
        await _share(author, repository, table)
        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
        assert copied.status_code == 201, copied.text
        async with admin_session_factory() as session:
            names = {
                e.id: e.name
                for e in await session.scalars(select(Entity).where(Entity.tenant_id == table))
            }
            (record,) = (
                await session.scalars(select(GrantRecord).where(GrantRecord.tenant_id == table))
            ).all()
        assert names[record.holder_id] == "Elminster"
        assert names[record.source_ref_id] == "Harpers"
        assert names[record.feature_id] == "Fixture feature"
        assert record.state == "active" and record.rule_id is not None
        assert record.feature_instance_id is not None
        assert names[record.feature_instance_id] == "Fixture feature held"
    finally:
        await cleanup([repository, table], [author, gm])


async def _share(author: Actor, repository: uuid.UUID, *subscribers: uuid.UUID) -> None:
    for subscriber in subscribers:
        response = await author.put(f"/tenants/{repository}/subscribers/{subscriber}")
        assert response.status_code in (200, 201), response.text
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
