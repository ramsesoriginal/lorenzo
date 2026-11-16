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
        "writing": {"url": "https://lorenzo-writing.pages.dev"},
        "maps": {"url": "https://lorenzo-maps.pages.dev"},
        "social": {"url": "https://lorenzo-social.pages.dev"},
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
    assert links["social_web"] == "https://lorenzo-social.pages.dev/web/?tenant={tenant}&id={id}"
    assert links["relationship"].endswith("/relationship/?tenant={tenant}&id={id}")


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
        "writing",
        "maps",
        "social",
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


def test_the_legal_app_has_no_default_and_appears_only_when_set() -> None:
    unset = app_links.document(Settings())
    assert "legal" not in unset["apps"]
    assert not any(name.startswith("legal_") for name in unset["links"])
    assert unset["support_url"] is None  # the document; the endpoint leaves a null out

    blank = app_links.document(Settings(legal_url="  ", support_url=""))
    assert "legal" not in blank["apps"]
    assert blank["support_url"] is None


def test_the_legal_pages_are_linked_per_language_when_set() -> None:
    doc = app_links.document(
        Settings(
            legal_url="https://legal.example.org/", support_url="https://support.example.org/x"
        )
    )
    assert doc["apps"]["legal"] == {"url": "https://legal.example.org"}
    assert doc["links"]["legal_notice_de"] == "https://legal.example.org/de/impressum/"
    assert doc["links"]["legal_notice_en"] == "https://legal.example.org/en/legal-notice/"
    assert doc["links"]["legal_privacy_de"] == "https://legal.example.org/de/datenschutz/"
    assert doc["links"]["legal_privacy_en"] == "https://legal.example.org/en/privacy-policy/"
    assert doc["support_url"] == "https://support.example.org/x"


async def test_the_endpoint_serves_the_legal_app_and_support_link(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lorenzo_api.config import get_settings

    monkeypatch.setattr(get_settings(), "legal_url", "https://legal.example.org")
    monkeypatch.setattr(get_settings(), "support_url", "https://support.example.org/x")

    body = (await client.get("/app-links")).json()

    assert body["apps"]["legal"]["url"] == "https://legal.example.org"
    assert body["links"]["legal_notice_en"] == "https://legal.example.org/en/legal-notice/"
    assert body["support_url"] == "https://support.example.org/x"
