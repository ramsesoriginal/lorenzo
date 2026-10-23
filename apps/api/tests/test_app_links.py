import pytest
from httpx import AsyncClient

from lorenzo_api import app_links
from lorenzo_api.config import Settings


def test_defaults_are_the_official_pages_addresses() -> None:
    doc = app_links.document(Settings())
    assert doc["apps"] == {
        "account_hub": {"url": "https://lorenzo-account-hub.pages.dev"},
        "inventory_web": {"url": "https://lorenzo-inventory-web.pages.dev"},
        "beings": {"url": "https://lorenzo-beings.pages.dev"},
        "bench": {"url": "https://lorenzo-bench.pages.dev"},
        "calendars": {"url": "https://lorenzo-calendars.pages.dev"},
        "sessions": {"url": "https://lorenzo-sessions.pages.dev"},
        "maps": {"url": "https://lorenzo-maps.pages.dev"},
    }
    links = doc["links"]
    assert links["notifications"] == "https://lorenzo-account-hub.pages.dev/notifications/"
    assert links["notification"] == links["notifications"]
    assert links["device"] == "https://lorenzo-account-hub.pages.dev/device/"
    assert links["item"] == "https://lorenzo-inventory-web.pages.dev/item/?tenant={tenant}&id={id}"
    assert links["item_by_slug"].endswith("/item/?tenant={tenant}&slug={slug}")
    assert links["board"] == links["inventory"]
    assert links["board"].endswith("/board/?tenant={tenant}&character={id}")
    assert links["being"] == "https://lorenzo-beings.pages.dev/being/?tenant={tenant}&id={id}"
    assert links["being_by_slug"].endswith("/being/?tenant={tenant}&slug={slug}")
    assert links["repository"].endswith("/repositories/")
    assert links["studio"].endswith("/studio/")
    assert (
        links["calendar"] == "https://lorenzo-calendars.pages.dev/calendar/?tenant={tenant}&id={id}"
    )
    assert links["calendar_by_slug"].endswith("/calendar/?tenant={tenant}&slug={slug}")
    assert links["calendar_entry"].endswith("/entry/?tenant={tenant}&id={id}")


def test_overridden_addresses_lose_trailing_slashes() -> None:
    settings = Settings(
        account_hub_url="https://hub.example.com//", beings_url=" https://b.example/ "
    )
    assert app_links.account_hub_url(settings) == "https://hub.example.com"
    assert app_links.device_url(settings) == "https://hub.example.com/device/"
    assert app_links.links(settings)["being"].startswith("https://b.example/being/")


def test_template_overrides_win_and_can_add_links() -> None:
    settings = Settings(
        app_link_templates="item=https://i.example/{tenant}/{id} extra=https://x.example/?a=b"  # type: ignore[arg-type]
    )
    links = app_links.links(settings)
    assert links["item"] == "https://i.example/{tenant}/{id}"
    assert links["extra"] == "https://x.example/?a=b"
    assert (
        links["board"]
        == app_links.apps(Settings())["inventory_web"] + "/board/?tenant={tenant}&character={id}"
    )


def test_env_variables_feed_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INVENTORY_WEB_URL", "https://inv.example/")
    monkeypatch.setenv("APP_LINK_TEMPLATES", "studio=https://s.example/")
    settings = Settings()
    assert app_links.links(settings)["board"].startswith("https://inv.example/board/")
    assert app_links.links(settings)["studio"] == "https://s.example/"


def test_a_blank_variable_means_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BENCH_URL", "")
    monkeypatch.setenv("APP_LINK_TEMPLATES", "")
    assert app_links.apps(Settings())["bench"] == "https://lorenzo-bench.pages.dev"
    assert Settings().app_link_templates == {}


def test_a_malformed_override_is_refused() -> None:
    with pytest.raises(ValueError, match="name=template"):
        Settings(app_link_templates="oops")  # type: ignore[arg-type]


async def test_endpoint_is_public_and_cacheable(client: AsyncClient) -> None:
    response = await client.get("/app-links")  # no Authorization header
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    body = response.json()
    assert set(body["apps"]) == {
        "account_hub",
        "inventory_web",
        "beings",
        "bench",
        "calendars",
        "sessions",
        "maps",
    }
    assert "{tenant}" in body["links"]["item"]


async def test_endpoint_follows_the_settings(client: AsyncClient) -> None:
    from lorenzo_api.config import get_settings
    from lorenzo_api.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(bench_url="https://bench.example/")
    try:
        body = (await client.get("/app-links")).json()
    finally:
        del app.dependency_overrides[get_settings]
    assert body["apps"]["bench"] == {"url": "https://bench.example"}
