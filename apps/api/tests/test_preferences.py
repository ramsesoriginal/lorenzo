"""A person's preferences in their account, and their saved views of lists (ADR 0532)."""

import uuid

from test_story_sessions import world


async def test_preferences_are_the_persons_own_and_replace_whole(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        a, b = w.author, w.outsider
        assert (await a.get("/me/preferences")).json() == {
            "theme": None,
            "density": None,
            "motion": None,
        }
        put = await a.put("/me/preferences", json={"theme": "dark", "density": "dense"})
        assert put.status_code == 200, put.text
        assert (await a.get("/me/preferences")).json() == {
            "theme": "dark",
            "density": "dense",
            "motion": None,
        }
        # Another person's are theirs; a part left out is cleared; an unknown word is refused.
        assert (await b.get("/me/preferences")).json()["theme"] is None
        await a.put("/me/preferences", json={"motion": "reduced"})
        assert (await a.get("/me/preferences")).json() == {
            "theme": None,
            "density": None,
            "motion": "reduced",
        }
        assert (await a.put("/me/preferences", json={"theme": "purple"})).status_code == 422
        assert (await a.put("/me/preferences", json={"color": "red"})).status_code == 422
    finally:
        await w.clean_up()


async def test_saved_views_are_kept_per_person_and_library(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, a, b = w.tenant_id, w.author, w.outsider
        base = f"/tenants/{t}/saved-views"
        made = await a.post(
            base,
            json={
                "app": "social",
                "list": "relationships",
                "name": "Allies of the court",
                "query": {"type": "ally", "min": 2},
            },
        )
        assert made.status_code == 201, made.text
        view = made.json()
        assert view["name"] == "Allies of the court" and view["query"] == {"type": "ally", "min": 2}
        # Listed by the one who made it, narrowed by app and list; never read by another person.
        assert [v["name"] for v in (await a.get(base)).json()] == ["Allies of the court"]
        assert (await a.get(base, params={"app": "maps"})).json() == []
        assert (await a.get(base, params={"app": "social", "list": "relationships"})).json()
        assert (await b.get(base)).json() == []
        assert (await b.patch(f"{base}/{view['id']}", json={"name": "Mine now"})).status_code == 404
        assert (await b.delete(f"{base}/{view['id']}")).status_code == 404
        # The same name for the same list replaces the query; another person may use the name.
        again = await a.post(
            base,
            json={
                "app": "social",
                "list": "relationships",
                "name": "Allies of the court",
                "query": {"type": "ally", "min": 5},
            },
        )
        assert again.status_code == 201 and again.json()["id"] == view["id"]
        assert [v["query"]["min"] for v in (await a.get(base)).json()] == [5]
        assert (
            await b.post(
                base,
                json={
                    "app": "social",
                    "list": "relationships",
                    "name": "Allies of the court",
                    "query": {},
                },
            )
        ).status_code == 201
        # Rename, then delete.
        renamed = await a.patch(f"{base}/{view['id']}", json={"name": "Court allies"})
        assert renamed.status_code == 200 and renamed.json()["name"] == "Court allies"
        assert (await a.delete(f"{base}/{view['id']}")).status_code == 204
        assert (await a.get(base)).json() == []
        assert (await a.delete(f"{base}/{uuid.uuid4()}")).status_code == 404
        # A view that is too large, and a name with no words in it, are refused.
        big = await a.post(
            base,
            json={
                "app": "social",
                "list": "relationships",
                "name": "Big",
                "query": {"x": "y" * 5000},
            },
        )
        assert big.status_code == 422, big.text
        empty = await a.post(
            base, json={"app": "social", "list": "relationships", "name": "", "query": {}}
        )
        assert empty.status_code == 422
    finally:
        await w.clean_up()


async def test_a_person_keeps_at_most_fifty_views_in_a_library(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        base = f"/tenants/{w.tenant_id}/saved-views"
        for n in range(50):
            made = await w.author.post(
                base, json={"app": "social", "list": "relationships", "name": f"v{n}", "query": {}}
            )
            assert made.status_code == 201, made.text
        over = await w.author.post(
            base, json={"app": "social", "list": "relationships", "name": "one more", "query": {}}
        )
        assert over.status_code == 422, over.text
        # Replacing one that is there is not adding one.
        same = await w.author.post(
            base, json={"app": "social", "list": "relationships", "name": "v3", "query": {"a": 1}}
        )
        assert same.status_code == 201
    finally:
        await w.clean_up()
