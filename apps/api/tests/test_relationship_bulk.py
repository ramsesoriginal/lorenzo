"""The bulk write of relationships and standings, and the library's type stats (ADR 0400)."""

import uuid
from typing import Any

from test_distance_read import definition, give
from test_locations import place
from test_placement import entry
from test_relationships import listing, made
from test_story_sessions import world


async def bulk(actor: Any, t: Any, operations: list[dict[str, Any]]):
    return await actor.post(f"/tenants/{t}/relationships/bulk", json={"operations": operations})


async def etag(actor: Any, t: Any, relationship: str) -> str:
    got = await actor.get(f"/tenants/{t}/relationships/{relationship}")
    assert got.status_code == 200, got.text
    return str(got.headers["etag"])


async def standings(actor: Any, t: Any, stat: str) -> dict[str, Any]:
    read = await actor.get(
        f"/tenants/{t}/entities/effective-stats",
        params={"kind": "relationship", "stat_definition_id": stat, "size": 100},
    )
    assert read.status_code == 200, read.text
    return {
        row["name"]: {s["stat_definition_id"]: s for s in row["stats"]}.get(stat)
        for row in read.json()["items"]
    }


async def test_a_bulk_write_makes_sets_clears_and_deletes_in_one_go(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        dren = await place(gm, t, "Dren", is_public=True)
        honor = await definition(gm, t, "honor", "int")
        trust = await definition(gm, t, "trust", "int")
        first = await bulk(
            gm,
            t,
            [
                {
                    "op": "create",
                    "name": "Mara honors Wren",
                    "end_a": mara["id"],
                    "end_b": wren["id"],
                    "one_way": True,
                    "stats": [{"stat_definition_id": honor, "value": 4}],
                },
                {
                    "op": "create",
                    "name": "Wren honors Mara",
                    "end_a": wren["id"],
                    "end_b": mara["id"],
                    "one_way": True,
                    "is_public": True,
                    "stats": [
                        {"stat_definition_id": honor, "value": -2},
                        {"stat_definition_id": trust, "value": 7},
                    ],
                },
                {"op": "create", "name": "Wren and Dren", "end_a": wren["id"], "end_b": dren["id"]},
            ],
        )
        assert first.status_code == 200, first.text
        results = first.json()["results"]
        assert [r["op"] for r in results] == ["create"] * 3
        assert [r["index"] for r in results] == [0, 1, 2]
        one, two, three = (r["relationship"] for r in results)
        # Restricted unless asked, with the value written.
        assert one["is_public"] is False and two["is_public"] is True and one["one_way"] is True
        assert three["one_way"] is False
        seen = await standings(gm, t, honor)
        assert seen["Mara honors Wren"]["value"] == 4 and seen["Wren honors Mara"]["value"] == -2
        # Set, clear and delete, each with the ETag it was read at.
        second = await bulk(
            gm,
            t,
            [
                {
                    "op": "set",
                    "relationship_id": one["id"],
                    "stat_definition_id": honor,
                    "value": 9,
                    "if_match": await etag(gm, t, one["id"]),
                },
                {
                    "op": "clear",
                    "relationship_id": two["id"],
                    "stat_definition_id": trust,
                    "if_match": await etag(gm, t, two["id"]),
                },
                {
                    "op": "delete",
                    "relationship_id": three["id"],
                    "if_match": await etag(gm, t, three["id"]),
                },
            ],
        )
        assert second.status_code == 200, second.text
        assert [r["op"] for r in second.json()["results"]] == ["set", "clear", "delete"]
        assert second.json()["results"][2]["relationship"] is None
        assert (await standings(gm, t, honor))["Mara honors Wren"]["value"] == 9
        assert (await standings(gm, t, trust))["Wren honors Mara"] is None
        assert sorted(x["name"] for x in await listing(gm, t)) == [
            "Mara honors Wren",
            "Wren honors Mara",
        ]
    finally:
        await w.clean_up()


async def test_one_refused_operation_writes_nothing(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        vault = await place(gm, t, "Vault")
        honor = await definition(gm, t, "honor", "int")
        # The writer sees the vault; a reader who may not would be refused the same way. Use a
        # missing entry for the refusal, and a value outside a scale for another.
        ghost = str(uuid.uuid4())
        refused = await bulk(
            gm,
            t,
            [
                {"op": "create", "name": "Fine", "end_a": mara["id"], "end_b": wren["id"]},
                {"op": "create", "name": "Broken", "end_a": mara["id"], "end_b": ghost},
            ],
        )
        assert refused.status_code == 404, refused.text
        assert refused.json()["operation"] == 1
        assert refused.json()["detail"].startswith("Operation 1: ")
        assert await listing(gm, t) == []
        # A value outside the scale refuses the batch, and the first operation is not kept.
        scale = await gm.patch(
            f"/tenants/{t}/stat-definitions/{honor}", json={"min_value": -10, "max_value": 10}
        )
        assert scale.status_code == 200, scale.text
        kept = await made(gm, t, mara["id"], vault["id"], "Kept")
        outside = await bulk(
            gm,
            t,
            [
                {
                    "op": "set",
                    "relationship_id": kept["id"],
                    "stat_definition_id": honor,
                    "value": 3,
                    "if_match": await etag(gm, t, kept["id"]),
                },
                {
                    "op": "create",
                    "name": "Too much",
                    "end_a": mara["id"],
                    "end_b": wren["id"],
                    "stats": [{"stat_definition_id": honor, "value": 99}],
                },
            ],
        )
        assert outside.status_code == 422, outside.text
        assert outside.json()["operation"] == 1
        assert [x["name"] for x in await listing(gm, t)] == ["Kept"]
        assert (await standings(gm, t, honor))["Kept"] is None
    finally:
        await w.clean_up()


async def test_a_stale_version_is_a_412_and_nothing_changes(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        honor = await definition(gm, t, "honor", "int")
        tie = await made(gm, t, mara["id"], wren["id"], "Bond")
        stale = await etag(gm, t, tie["id"])
        await give(gm, t, tie["id"], honor, 1)
        late = await bulk(
            gm,
            t,
            [
                {
                    "op": "set",
                    "relationship_id": tie["id"],
                    "stat_definition_id": honor,
                    "value": 5,
                    "if_match": stale,
                }
            ],
        )
        assert late.status_code == 412, late.text
        assert late.json()["operation"] == 0
        assert (await standings(gm, t, honor))["Bond"]["value"] == 1
        # Two standings of one relationship go in together on one version.
        trust = await definition(gm, t, "trust", "int")
        current = await etag(gm, t, tie["id"])
        both = await bulk(
            gm,
            t,
            [
                {
                    "op": "set",
                    "relationship_id": tie["id"],
                    "stat_definition_id": honor,
                    "value": 6,
                    "if_match": current,
                },
                {
                    "op": "set",
                    "relationship_id": tie["id"],
                    "stat_definition_id": trust,
                    "value": 2,
                    "if_match": current,
                },
            ],
        )
        assert both.status_code == 200, both.text
        assert (await standings(gm, t, honor))["Bond"]["value"] == 6
        assert (await standings(gm, t, trust))["Bond"]["value"] == 2
    finally:
        await w.clean_up()


async def test_who_may_write_and_how_many(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        one = {"op": "create", "name": "Bond", "end_a": mara["id"], "end_b": wren["id"]}
        assert (await bulk(player, t, [one])).status_code == 403
        assert (await bulk(gm, t, [])).status_code == 422
        assert (await bulk(gm, t, [one] * 101)).status_code == 422
        # A delete or set of something the writer cannot see is the generic 404.
        gone = await bulk(
            gm,
            t,
            [{"op": "delete", "relationship_id": str(uuid.uuid4()), "if_match": '"x"'}],
        )
        assert gone.status_code == 404
        # A type that is no relationship is not one.
        thing = await entry(gm, t, "Not a bond")
        notone = await bulk(gm, t, [{"op": "delete", "relationship_id": thing, "if_match": '"x"'}])
        assert notone.status_code == 404
    finally:
        await w.clean_up()


async def test_a_standing_is_inherited_through_a_type_and_overridden(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        dren = await place(gm, t, "Dren", is_public=True)
        trust = await definition(gm, t, "trust", "int")
        friend = await entry(gm, t, "Friend of")
        await give(gm, t, friend, trust, 3)
        inherits = await made(gm, t, mara["id"], wren["id"], "Inherits", prototypes=[friend])
        await made(gm, t, mara["id"], dren["id"], "Overrides", prototypes=[friend])
        overrides = next(x for x in await listing(gm, t) if x["name"] == "Overrides")
        done = await bulk(
            gm,
            t,
            [
                {
                    "op": "set",
                    "relationship_id": overrides["id"],
                    "stat_definition_id": trust,
                    "value": 8,
                    "if_match": await etag(gm, t, overrides["id"]),
                }
            ],
        )
        assert done.status_code == 200, done.text
        seen = await standings(gm, t, trust)
        assert (seen["Inherits"]["value"], seen["Inherits"]["own"]) == (3, False)
        assert (seen["Overrides"]["value"], seen["Overrides"]["own"]) == (8, True)
        assert inherits["id"]
    finally:
        await w.clean_up()


async def test_the_type_stats_of_a_library_are_checked_set_and_cleared(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        owner = w.owner
        directed = await definition(gm, t, "directed", "bool")
        verb = await definition(gm, t, "reads as", "text")
        back = await definition(gm, t, "reads as back", "text")
        number = await definition(gm, t, "honor", "int")
        before = (await owner.get(f"/tenants/{t}")).json()
        assert before["relationship_directed_stat_id"] is None
        etag_now = (await owner.get(f"/tenants/{t}")).headers["etag"]

        async def patch(body: dict[str, Any]) -> Any:
            current = (await owner.get(f"/tenants/{t}")).headers["etag"]
            return await owner.client.patch(
                f"/tenants/{t}", headers={**owner.headers, "If-Match": current}, json=body
            )

        assert etag_now
        assert (await patch({"relationship_directed_stat_id": number})).status_code == 422
        assert (await patch({"relationship_reads_as_stat_id": directed})).status_code == 422
        assert (
            await patch({"relationship_reads_as_back_stat_id": str(uuid.uuid4())})
        ).status_code == 422
        done = await patch(
            {
                "relationship_directed_stat_id": directed,
                "relationship_reads_as_stat_id": verb,
                "relationship_reads_as_back_stat_id": back,
            }
        )
        assert done.status_code == 200, done.text
        assert done.json()["relationship_directed_stat_id"] == directed
        assert done.json()["relationship_reads_as_stat_id"] == verb
        assert done.json()["relationship_reads_as_back_stat_id"] == back
        # Deleting a definition clears only its reference.
        removed = await owner.delete(f"/tenants/{t}/stat-definitions/{verb}")
        assert removed.status_code == 204, removed.text
        after = (await owner.get(f"/tenants/{t}")).json()
        assert after["relationship_reads_as_stat_id"] is None
        assert after["relationship_directed_stat_id"] == directed
        cleared = await patch({"relationship_directed_stat_id": None})
        assert cleared.status_code == 200
        assert cleared.json()["relationship_directed_stat_id"] is None
    finally:
        await w.clean_up()
