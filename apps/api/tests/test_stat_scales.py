"""ADR 0403: an optional minimum and maximum on an int or float stat."""

from typing import Any

from test_placement import entry
from test_story_sessions import world


async def group(actor: Any, t: Any) -> str:
    made = await actor.post(f"/tenants/{t}/stat-groups", json={"name": "Standings"})
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


async def definition(actor: Any, t: Any, g: str, name: str, **fields: Any) -> Any:
    return await actor.post(
        f"/tenants/{t}/stat-definitions",
        json={"stat_group_id": g, "name": name, "value_type": "int", **fields},
    )


async def put_value(actor: Any, t: Any, entity: str, stat: str, value: Any) -> Any:
    return await actor.put(f"/tenants/{t}/entities/{entity}/stats/{stat}", json={"value": value})


async def test_a_scale_is_set_read_and_checked_on_a_write(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        g = await group(gm, t)
        made = await definition(gm, t, g, "Honor", min_value=-10, max_value=10)
        assert made.status_code == 201, made.text
        honor = made.json()
        assert (honor["min_value"], honor["max_value"]) == (-10.0, 10.0)
        plain = (await definition(gm, t, g, "Faith")).json()
        assert (plain["min_value"], plain["max_value"]) == (None, None)
        thing = await entry(gm, t, "Oath")
        for fine in (-10, 0, 10):
            assert (await put_value(gm, t, thing, honor["id"], fine)).status_code == 200
        for outside in (11, -11, 1000):
            refused = await put_value(gm, t, thing, honor["id"], outside)
            assert refused.status_code == 422, refused.text
            assert "-10" in refused.json()["detail"] and "10" in refused.json()["detail"]
        # An unbounded stat reads and writes exactly as before.
        assert (await put_value(gm, t, thing, plain["id"], 123456)).status_code == 200
        # One bound alone limits one side.
        up = (await definition(gm, t, g, "Debt", max_value=5)).json()
        assert (await put_value(gm, t, thing, up["id"], -999)).status_code == 200
        assert (await put_value(gm, t, thing, up["id"], 6)).status_code == 422
    finally:
        await w.clean_up()


async def test_a_scale_is_for_numbers_and_in_order(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        g = await group(gm, t)
        for kind in ("text", "bool"):
            refused = await gm.post(
                f"/tenants/{t}/stat-definitions",
                json={"stat_group_id": g, "name": f"A {kind}", "value_type": kind, "max_value": 3},
            )
            assert refused.status_code == 422, refused.text
        assert (
            await definition(gm, t, g, "Upside down", min_value=5, max_value=1)
        ).status_code == 422
        floating = await gm.post(
            f"/tenants/{t}/stat-definitions",
            json={"stat_group_id": g, "name": "Ratio", "value_type": "float", "max_value": 1.5},
        )
        assert floating.status_code == 201 and floating.json()["max_value"] == 1.5
        # A change keeps the order and the type rules, and a bound can be cleared.
        base = f"/tenants/{t}/stat-definitions/{floating.json()['id']}"
        assert (await gm.patch(base, json={"min_value": 2})).status_code == 422
        assert (await gm.patch(base, json={"min_value": 0.5})).status_code == 200
        cleared = await gm.patch(base, json={"min_value": None, "max_value": None})
        assert cleared.status_code == 200
        assert (cleared.json()["min_value"], cleared.json()["max_value"]) == (None, None)
        text = (
            await gm.post(
                f"/tenants/{t}/stat-definitions",
                json={"stat_group_id": g, "name": "Motto", "value_type": "text"},
            )
        ).json()
        assert (
            await gm.patch(f"/tenants/{t}/stat-definitions/{text['id']}", json={"min_value": 1})
        ).status_code == 422
    finally:
        await w.clean_up()


async def test_a_bound_that_values_already_break_is_a_conflict(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        g = await group(gm, t)
        honor = (await definition(gm, t, g, "Honor")).json()
        base = f"/tenants/{t}/stat-definitions/{honor['id']}"
        for name, value in (("One", 3), ("Two", 50), ("Three", 70)):
            thing = await entry(gm, t, name)
            assert (await put_value(gm, t, thing, honor["id"], value)).status_code == 200
        broken = await gm.patch(base, json={"max_value": 10})
        assert broken.status_code == 409, broken.text
        assert "2 entries" in broken.json()["detail"]
        # Nothing changed, and a scale that fits is taken.
        assert (await gm.get(base)).json()["max_value"] is None
        assert (await gm.patch(base, json={"max_value": 100, "min_value": 0})).status_code == 200
    finally:
        await w.clean_up()
