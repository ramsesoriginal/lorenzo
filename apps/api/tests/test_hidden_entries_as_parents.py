"""ADR 0443: an entry a library hides (ADR 0437) is not found by its id in `PUT .../parents`, the
one answer a read by address gives."""

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _hidden_world import world
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.config import get_settings
from lorenzo_api.models import EntityPrototype


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def test_a_hidden_entry_is_a_404_as_a_parent_by_either_route_and_a_visible_one_is_not(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server)
    try:
        made = await h.reader.post(
            f"/tenants/{h.library}/entities", json={"name": "Library Blade", "kinds": ["item"]}
        )
        assert made.status_code == 201, made.text
        own = made.json()["id"]
        longsword = str(h.hidden["Longsword"])

        by_entry = await h.reader.put(
            f"/tenants/{h.library}/entities/{own}/parents",
            json={"parent_ids": [str(h.visible), longsword]},
        )
        by_item = await h.reader.put(
            f"/tenants/{h.library}/items/{own}/prototypes",
            json={"prototype_ids": [longsword]},
        )

        for refused in (by_entry, by_item):
            assert refused.status_code == 404, refused.text
            assert refused.json()["type"].endswith("entity-not-found")
            assert longsword in refused.json()["detail"]  # the id the caller named
            assert "Longsword" not in refused.text  # and not its name
        async with admin_session_factory() as session:
            held = (
                await session.scalars(
                    select(EntityPrototype.prototype_id).where(
                        EntityPrototype.tenant_id == h.library, EntityPrototype.entity_id == own
                    )
                )
            ).all()
        assert held == []  # nothing was written, the visible one included

        allowed = await h.reader.put(
            f"/tenants/{h.library}/entities/{own}/parents", json={"parent_ids": [str(h.visible)]}
        )
        assert allowed.status_code == 200, allowed.text
        assert [p["id"] for p in allowed.json()["prototypes"]] == [str(h.visible)]
    finally:
        await h.done()


async def test_a_library_that_hides_nothing_still_takes_any_entry_as_a_parent(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    h = await world(raw_client, fake_jwks_server, choice="show", protected=False)
    try:
        made = await h.reader.post(
            f"/tenants/{h.library}/entities", json={"name": "Library Blade", "kinds": ["item"]}
        )
        assert made.status_code == 201, made.text

        shown = await h.reader.put(
            f"/tenants/{h.library}/entities/{made.json()['id']}/parents",
            json={"parent_ids": [str(h.ids["Longsword"])]},
        )

        assert shown.status_code == 200, shown.text
    finally:
        await h.done()
