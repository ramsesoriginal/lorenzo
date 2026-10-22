"""Clock conversions preserve exact evidence, ranges and reader scope (ADR 0321)."""

import uuid
from fractions import Fraction

import pytest

from lorenzo_api.clock_conversion import (
    ConversionLimit,
    Relation,
    RelationDefinition,
    Work,
    affine,
    resolve,
)
from lorenzo_api.clock_values import ReadingRange
from lorenzo_api.routers.clock_relationships import conversion


def point(value):
    return ReadingRange(lo=value, hi=value)


def relation(a, b, ratio="2", anchor=True):
    return Relation(
        a,
        b,
        RelationDefinition(
            ratio=ratio,
            clock_anchor="0" if anchor else None,
            reference_anchor="0" if anchor else None,
        ),
    )


def test_exact_chains_inverse_negative_ranges_and_duration_only():
    a, b, c = [uuid.uuid4() for _ in range(3)]
    edges = [relation(a, b, "1/3"), relation(b, c, "3")]
    result = resolve(edges, a, c, point("1"), duration=False, work=Work())
    assert result.reading == point("1")
    result = resolve([relation(a, b, "2", False)], a, b, point("6"), duration=True, work=Work())
    assert result.reading == point("3")
    assert (
        resolve([relation(a, b, "2", False)], a, b, point("6"), duration=False, work=Work()).reading
        is None
    )
    value = affine(ReadingRange(lo="1", hi="2", hi_inclusive=False), Fraction(-2), Fraction(0))
    assert value.model_dump() == {
        "lo": "-4",
        "hi": "-2",
        "lo_inclusive": False,
        "hi_inclusive": True,
    }


def test_consistent_cycles_conflicts_and_entered_values_are_distinct():
    a, b, c = [uuid.uuid4() for _ in range(3)]
    names = {a: "A", b: "B", c: "C"}
    edges = [relation(a, b, "2"), relation(b, c, "3"), relation(a, c, "6")]
    result = conversion(edges, names, [(a, point("12"))], c, duration=False)
    assert result.status == "derived" and result.reading == point("2")
    edges[-1] = relation(a, c, "7")
    result = conversion(edges, names, [(a, point("12"))], c, duration=False)
    assert result.status == "conflicting" and result.reading is None and result.conflict_paths
    result = conversion(
        [relation(a, b)], names, [(a, point("40")), (b, point("21"))], b, duration=False
    )
    assert result.status == "conflicting" and result.reading == result.entered_reading == point(
        "21"
    )
    result = conversion(
        [relation(a, b)],
        names,
        [(a, ReadingRange(lo="38", hi="44")), (b, ReadingRange(lo="20", hi="23"))],
        c,
        duration=False,
    )
    assert result.status == "not_reckoned"


def test_bounded_work_and_rational_growth_are_not_unknown_readings():
    a, b, c = [uuid.uuid4() for _ in range(3)]
    with pytest.raises(ConversionLimit):
        resolve(
            [relation(a, b), relation(b, c)],
            a,
            c,
            point("1"),
            duration=False,
            work=Work(remaining=0),
        )
    with pytest.raises(ConversionLimit):
        affine(point("99999999999999999999999999999999999999"), Fraction(2), Fraction(0))
    for values in [{"ratio": "0"}, {"ratio": "2", "clock_anchor": "1"}]:
        with pytest.raises(ValueError):
            RelationDefinition.model_validate(values)


async def clock(actor, t, name, public=True):
    result = await actor.post(f"/tenants/{t}/clocks", json={"name": name, "is_public": public})
    assert result.status_code == 201, result.text
    return result.json()["entity_id"]


async def save(actor, t, a, b, **body):
    route = f"/tenants/{t}/clocks/{a}/relationships"
    version = (await actor.get(route)).headers["etag"]
    return await actor.client.put(
        route + f"/{b}", json={"ratio": "2", **body}, headers={**actor.headers, "If-Match": version}
    )


async def preview(actor, t, a, b, value="40", kind="reading"):
    return await actor.post(
        f"/tenants/{t}/clock-conversions",
        json={
            "source_clock_id": a,
            "target_clock_id": b,
            "reading": {"lo": value, "hi": value},
            "kind": kind,
        },
    )


async def test_fey_example_inverse_and_event_evidence_remains_entered(raw_client, fake_jwks_server):
    from test_session_play import event
    from test_story_sessions import world

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        fey = await clock(w.author, t, "Fey")
        mainland = await clock(w.author, t, "Mainland")
        saved = await save(
            w.author, t, fey, mainland, clock_anchor="34", reference_anchor="17", is_shared=True
        )
        assert saved.status_code == 200, saved.text
        forward = await preview(w.outsider, t, fey, mainland)
        assert forward.status_code == 200, forward.text
        assert forward.json()["status"] == "derived" and forward.json()["reading"]["lo"] == "20"
        inverse = await preview(w.outsider, t, mainland, fey, "20")
        assert inverse.json()["reading"]["lo"] == "40"
        duration = await preview(w.outsider, t, fey, mainland, "6", "duration")
        assert duration.json()["reading"]["lo"] == "3"
        e = await event(w, "Return")
        route = f"/tenants/{t}/events/{e}/clock-readings"
        current = await w.author.get(route)
        entered = await w.author.client.put(
            route + f"/{fey}",
            json={"reading": {"lo": "40", "hi": "40"}, "is_shared": True},
            headers={**w.author.headers, "If-Match": current.headers["etag"]},
        )
        assert entered.status_code == 200, entered.text
        derived = await w.outsider.get(route + f"/{mainland}/derived")
        assert derived.json()["status"] == "derived" and derived.json()["reading"]["lo"] == "20"
        assert len((await w.author.get(route)).json()["items"]) == 1
        mismatch = await w.author.client.put(
            route + f"/{mainland}",
            json={"reading": {"lo": "21", "hi": "21"}, "is_shared": True},
            headers={**w.author.headers, "If-Match": entered.headers["etag"]},
        )
        assert mismatch.status_code == 200, mismatch.text
        conflicted = await w.outsider.get(route + f"/{mainland}/derived")
        assert (
            conflicted.json()["status"] == "conflicting"
            and conflicted.json()["entered_reading"]["lo"] == "21"
        )
        assert len((await w.author.get(route)).json()["items"]) == 2
    finally:
        await w.clean_up()


async def test_private_paths_hidden_clocks_and_limits_do_not_influence_readers(
    raw_client, fake_jwks_server, monkeypatch
):
    from test_story_sessions import world

    from lorenzo_api.routers import clock_relationships as routes

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        a = await clock(w.author, t, "A")
        b = await clock(w.author, t, "B")
        first = await preview(w.outsider, t, a, b)
        private = await save(w.author, t, a, b, clock_anchor="0", reference_anchor="0")
        assert private.status_code == 200, private.text
        assert (await preview(w.outsider, t, a, b)).json() == first.json()
        assert (await w.outsider.get(f"/tenants/{t}/clocks/{a}/relationships")).json()[
            "items"
        ] == []
        shared = await save(
            w.author, t, a, b, clock_anchor="0", reference_anchor="0", is_shared=True
        )
        assert shared.status_code == 200, shared.text
        before = (await preview(w.outsider, t, a, b)).json()
        hidden = await clock(w.author, t, "Hidden", False)
        assert (
            await save(
                w.author, t, a, hidden, clock_anchor="0", reference_anchor="0", is_shared=True
            )
        ).status_code == 200
        assert (
            await save(
                w.author,
                t,
                b,
                hidden,
                ratio="3",
                clock_anchor="0",
                reference_anchor="0",
                is_shared=True,
            )
        ).status_code == 200
        monkeypatch.setattr(routes, "MAX_CLOCKS", 2)
        monkeypatch.setattr(routes, "MAX_RELATIONS", 1)
        after = await preview(w.outsider, t, a, b)
        assert after.json() == before
        assert (await preview(w.author, t, a, b)).json()["status"] == "limit_reached"
    finally:
        await w.clean_up()


async def test_relationship_concurrency_mode_guards_and_canonical_pair(
    raw_client, fake_jwks_server
):
    import asyncio

    from test_story_sessions import world

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        a, b, c = [await clock(w.author, t, name) for name in ["A", "B", "C"]]
        route = f"/tenants/{t}/clocks/{a}/relationships"
        before = await w.author.get(route)
        headers = {**w.author.headers, "If-Match": before.headers["etag"]}
        results = await asyncio.gather(
            *[
                w.author.client.put(route + f"/{target}", json={"ratio": "2"}, headers=headers)
                for target in [b, c]
            ]
        )
        assert sorted(r.status_code for r in results) == [200, 412]
        rows = await w.author.get(route)
        target = rows.json()["items"][0]["reference_clock_entity_id"]
        reversed_row = await w.author.get(f"/tenants/{t}/clocks/{target}/relationships")
        assert reversed_row.json()["items"][0]["ratio"] == "1/2"
        clock_row = await w.author.get(f"/tenants/{t}/clocks/{a}")
        refused = await w.author.client.put(
            f"/tenants/{t}/clocks/{a}",
            json={"ticking": False},
            headers={**w.author.headers, "If-Match": clock_row.headers["etag"]},
        )
        assert refused.status_code == 409, refused.text
        assert (await w.author.delete(f"/tenants/{t}/entities/{a}")).status_code == 409
    finally:
        await w.clean_up()
