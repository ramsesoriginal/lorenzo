"""The Editions shared with a reviewer, across libraries (ADR 0495)."""

from _author_world import make_world
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup, make_actor
from httpx import AsyncClient


async def test_a_reviewer_lists_the_editions_shared_with_them_in_every_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    first = await make_world(raw_client, fake_jwks_server, kind="play")
    second = await make_world(raw_client, fake_jwks_server, kind="play")
    reviewer = await make_actor(raw_client, fake_jwks_server, "reviewer-of-two", roles=())
    stranger = await make_actor(raw_client, fake_jwks_server, "not-a-reviewer", roles=())
    try:
        editions = {}
        for label, world, name in (("a", first, "Zeta tale"), ("b", second, "Alpha tale")):
            base = f"/tenants/{world.tenant_id}"
            book = (await world.author.post(base + "/writing/books", json={"name": name})).json()
            edition = book["editions"][0]["id"]
            editions[label] = edition
            granted = await world.author.put(
                base + f"/writing/reviews/{edition}/reviewers/{reviewer.user_id}"
            )
            assert granted.status_code == 204, granted.text
        # A third Edition that was not shared with them.
        base = f"/tenants/{first.tenant_id}"
        await first.author.post(base + "/writing/books", json={"name": "Private draft"})

        listed = await reviewer.get("/me/writing-reviews")
        assert listed.status_code == 200, listed.text
        assert listed.headers["cache-control"] == "private, no-store"
        rows = listed.json()
        # By name, whichever library holds it; only what a review shows.
        assert [(row["name"], row["edition_id"], row["tenant_id"]) for row in rows] == [
            ("Alpha tale", editions["b"], str(second.tenant_id)),
            ("Zeta tale", editions["a"], str(first.tenant_id)),
        ]
        assert all(set(row) == {"tenant_id", "edition_id", "name"} for row in rows)
        assert "Private draft" not in listed.text
        # Somebody with no grant is told of nothing, and one reviewer's grants are not another's.
        assert (await stranger.get("/me/writing-reviews")).json() == []
        # Taking the grant away takes the row away.
        revoked = await first.author.delete(
            f"/tenants/{first.tenant_id}/writing/reviews/{editions['a']}/reviewers/{reviewer.user_id}"
        )
        assert revoked.status_code == 204, revoked.text
        again = (await reviewer.get("/me/writing-reviews")).json()
        assert [row["name"] for row in again] == ["Alpha tale"]
    finally:
        await cleanup([first.tenant_id, second.tenant_id], [reviewer, stranger])
        await first.clean_up()
        await second.clean_up()
